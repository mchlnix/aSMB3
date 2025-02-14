import time
from collections import defaultdict
from contextlib import suppress
from enum import Enum
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QObject, QRegularExpression, QRunnable, Signal

from foundry.data_source import strip_comment


class NamedValueType(Enum):
    CONSTANT = 0
    LABEL = 1
    RAM_VAR = 2


class NamedValue(NamedTuple):
    name: str
    value: str
    origin_file: Path
    origin_line_no: int
    type: NamedValueType


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


class NamedValueFinder(QRunnable):
    def __init__(self, root_path: Path):
        super().__init__()

        self.root_path = root_path

        self._local_copies: dict[Path, str] = {}
        self._currently_open_file: Path = None
        """
        When documents are modified, but not saved yet, we have to use the local copies, instead of the files on disk.
        """

        self.values: dict[str, NamedValue] = {}
        self._values: dict[str, NamedValue] = {}

        self.location_to_names: dict[tuple[Path, int], set[str]] = defaultdict(set)
        self._location_to_names: dict[tuple[Path, int], set[str]] = defaultdict(set)
        """
        The key is a tuple of file path and line number, the value is a list of all names we found there.
        These need to be updated when a line changes and when the number of lines changes.
        """
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
        self._values.clear()
        self._location_to_names.clear()
        self._name_to_locations.clear()

        self.signals.maximum_found.emit(self.prg_count * 2 + 1)
        progress = 0

        # Pass 1, get all the definitions
        smb3_path = self.root_path / "smb3.asm"

        if self._currently_open_file is None:
            self._parse_file_for_definitions(smb3_path)

            for prg_file in self.prg_files:
                self.signals.progress_made.emit(progress, f"Parsing: {prg_file}")
                self._parse_file_for_definitions(prg_file)
                progress += 1
        else:
            self._parse_file_for_definitions(self._currently_open_file)

        # Pass 2, find all the references
        self._parse_file_for_references(smb3_path)

        for prg_file in self.prg_files:
            self.signals.progress_made.emit(progress, f"Parsing: {prg_file}")
            self._parse_file_for_references(prg_file)
            progress += 1

        self.signals.progress_made.emit(progress, "Cleaning up References")
        self._cleanup_references()

        self.values = self._values.copy()
        self.location_to_names = self._location_to_names.copy()
        self.name_to_locations = self._name_to_locations.copy()

        self._local_copies.clear()

        print(f"Parsing took {round(time.time() - start_time, 2)} seconds")

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
                (NamedValueType.CONSTANT, NamedValueType.RAM_VAR, NamedValueType.LABEL),
            ):
                match_iterator = regex.globalMatch(line)

                we_matched = match_iterator.hasNext()

                while match_iterator.hasNext():
                    match = match_iterator.next()

                    matched_name = match.capturedView(1)
                    matched_value = match.capturedView(2)

                    self._values[matched_name] = NamedValue(matched_name, matched_value, rel_path, line_no, nv_type)

                    self._location_to_names[(rel_path, line_no)].add(matched_name)
                    self._name_to_locations[matched_name].add((rel_path, line_no))

                if we_matched:
                    break

    def _parse_file_for_references(self, file_path: Path):
        if file_path not in self._local_copies:
            with file_path.open("r") as f:
                lines = f.readlines()
        else:
            lines = self._local_copies[file_path].splitlines(True)

        rel_path = file_path.relative_to(self.root_path)

        for line_no, line in enumerate(lines, 1):
            line = strip_comment(line)

            match_iterator = _CONST_LABEL_CALL_RAM_VAR_REGEX.globalMatch(line)

            while match_iterator.hasNext():
                match = match_iterator.next()

                matched_name = match.capturedView(1)

                self._location_to_names[(rel_path, line_no)].add(matched_name)
                self._name_to_locations[matched_name].add((rel_path, line_no))

    def _cleanup_references(self):
        """Remove the location of the name definition from the list of references."""
        for name, named_value in self.values.items():
            _, _, file_path, line_no, _ = named_value

            with suppress(KeyError):
                self.name_to_locations[name].remove((file_path, line_no))
