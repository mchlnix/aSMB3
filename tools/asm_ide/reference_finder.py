import time
from collections import defaultdict
from contextlib import suppress
from enum import Enum
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QObject, QRegularExpression, QRunnable, Signal

from foundry.data_source import strip_comment


class ReferenceType(Enum):
    CONSTANT = 0
    LABEL = 1
    RAM_VAR = 2


class ReferenceDefinitions(NamedTuple):
    name: str
    value: str
    origin_file: Path
    origin_line_no: int
    type: ReferenceType


_CONST_REGEX = QRegularExpression("([A-Za-z][A-za-z0-9_]*)\s*\=\s*(\$[0-9A-F]+|\%[0-1]+|[0-9]+)")
_LABEL_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:\s*(.*)")
_RAM_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:\s*(\.ds.*)")

_CONST_LABEL_CALL_RAM_VAR_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)")

# todo keep track of macros


class ParserSignals(QObject):
    finished = Signal()
    result = Signal()
    maximum_found = Signal(int)
    progress_made = Signal(int, str)


class ReferenceFinder(QRunnable):
    def __init__(self, root_path: Path):
        super().__init__()

        self.root_path = root_path

        self._local_copies: dict[Path, str] = {}
        self._currently_open_file: Path = None
        """
        When documents are modified, but not saved yet, we have to use the local copies, instead of the files on disk.
        """

        self.definitions: dict[str, ReferenceDefinitions] = {}
        self._definitions: dict[str, ReferenceDefinitions] = {}

        self.name_to_locations: dict[str, set[tuple[Path, int]]] = defaultdict(set)
        self._name_to_locations: dict[str, set[tuple[Path, int]]] = defaultdict(set)

        self.signals = ParserSignals()

        self.setAutoDelete(False)

    @property
    def prg_files(self):
        prg_dir = self.root_path / "PRG"

        return sorted(prg_dir.glob("prg[0-9]*.asm"))

    @property
    def prg_count(self):
        return len(self.prg_files)

    def run_with_local_copies(self, local_copies: dict[Path, str], open_file: Path = None):
        self._local_copies = local_copies
        self._currently_open_file = open_file

        return self.run

    def run(self):
        start_time = time.time()

        do_a_complete_parse = self._currently_open_file is None

        # smb3.asm twice, all the prg files twice and then cleaning up the references once
        # this is only for a progress dialog, where we always do a complete parse
        self.signals.maximum_found.emit(2 + self.prg_count * 2 + 1)
        progress = 0

        # Pass 1, get all the definitions
        smb3_path = self.root_path / "smb3.asm"

        if do_a_complete_parse:
            self._definitions.clear()
            self._name_to_locations.clear()

            for asm_file in [smb3_path] + self.prg_files:
                self.signals.progress_made.emit(progress, f"Parsing: {asm_file}")
                self._parse_file_for_definitions(asm_file)
                progress += 1

            added_definitions = []
        else:
            self._definitions = self.definitions.copy()
            self._name_to_locations = self.name_to_locations.copy()

            self._remove_all_definitions_of_file(self._currently_open_file)
            self._parse_file_for_definitions(self._currently_open_file)

            old_definitions = set(self.definitions.keys())
            new_definitions = set(self._definitions.keys())

            removed_definitions = list(old_definitions.difference(new_definitions))
            added_definitions = list(new_definitions.difference(old_definitions))

            for definition in removed_definitions:
                print(f"Popping References for removed {definition}: {self.name_to_locations.pop(definition, None)}")

        # Pass 2, find all the references
        for asm_file in [smb3_path] + self.prg_files:
            self.signals.progress_made.emit(progress, f"Parsing: {asm_file}")

            self._parse_file_for_references(asm_file, added_definitions, do_a_complete_parse)
            progress += 1

        self.signals.progress_made.emit(progress, "Cleaning up References")
        self._cleanup_references()

        self.definitions = self._definitions.copy()
        self.name_to_locations = self._name_to_locations.copy()

        self._local_copies.clear()

        print(f"Parsing took {round(time.time() - start_time, 2)} seconds")

    def _remove_all_definitions_of_file(self, abs_file_path: Path):
        rel_path = abs_file_path.relative_to(self.root_path)

        for name, value in list(self._definitions.items()):
            if value.origin_file == rel_path:
                self._definitions.pop(name)

    def _parse_file_for_definitions(self, file_path: Path):
        if file_path not in self._local_copies:
            with file_path.open("r") as f:
                lines = f.readlines()
        else:
            lines = self._local_copies[file_path].splitlines(True)

        rel_path = file_path.relative_to(self.root_path)

        for line_no, line in enumerate(lines, 1):
            line = strip_comment(line)

            for regex, nv_type in zip(
                (_CONST_REGEX, _RAM_REGEX, _LABEL_REGEX),
                (ReferenceType.CONSTANT, ReferenceType.RAM_VAR, ReferenceType.LABEL),
            ):
                match_iterator = regex.globalMatch(line)

                we_matched = match_iterator.hasNext()

                while match_iterator.hasNext():
                    match = match_iterator.next()

                    matched_name = match.capturedView(1)
                    matched_value = match.capturedView(2)

                    self._definitions[matched_name] = ReferenceDefinitions(
                        matched_name, matched_value, rel_path, line_no, nv_type
                    )

                    self._name_to_locations[matched_name].add((rel_path, line_no))

                if we_matched:
                    break

    def _parse_file_for_references(self, file_to_parse: Path, added_definitions: list[str], force_parse):
        if file_to_parse not in self._local_copies:
            data = file_to_parse.read_text()
        else:
            data = self._local_copies[file_to_parse]

        is_open_file = file_to_parse == self._currently_open_file

        if not (force_parse or is_open_file) and not any(value in data for value in added_definitions):
            return

        lines = data.splitlines(True)

        rel_path = file_to_parse.relative_to(self.root_path)

        print(f"Parsing {rel_path}")
        if not force_parse and is_open_file:
            for name, positions in self._name_to_locations.items():
                for file_path, line_no in list(positions):
                    if file_path == rel_path:
                        self._name_to_locations[name].remove((rel_path, line_no))

        for line_no, line in enumerate(lines, 1):
            line = strip_comment(line)

            match_iterator = _CONST_LABEL_CALL_RAM_VAR_REGEX.globalMatch(line)

            while match_iterator.hasNext():
                match = match_iterator.next()

                matched_name = match.capturedView(1)

                self._name_to_locations[matched_name].add((rel_path, line_no))

    def _cleanup_references(self):
        """Remove the location of the name definition from the list of references."""
        for name, named_value in self.definitions.items():
            _, _, file_path, line_no, _ = named_value

            with suppress(KeyError):
                self.name_to_locations[name].remove((file_path, line_no))
