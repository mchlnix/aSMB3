import time
from collections import defaultdict
from contextlib import suppress
from enum import Enum
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QObject, QRegularExpression, QRunnable, Signal

from tools.asm_ide.util import strip_comment


class ReferenceType(Enum):
    CONSTANT = 0
    LABEL = 1
    RAM_VAR = 2
    UNSET = 99


class ReferenceDefinition(NamedTuple):
    name: str
    value: str
    origin_file: Path
    origin_line_no: int
    type: ReferenceType
    line: str


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
    def __init__(self):
        super().__init__()

        self._path_to_data: dict[Path, str] = {}
        """
        Holds a Path and the data that Path points to. Could be the file data on disk or the (perhaps) modified data of
        the opened file in the editor.
        This allows finding definitions and references, that are not yet saved to disk.
        """

        self._currently_open_file: Path | None = None
        """
        When documents are modified, but not saved yet, we have to use the local copies, instead of the files on disk.
        """

        self.definitions: dict[str, ReferenceDefinition] = {}
        self._definitions: dict[str, ReferenceDefinition] = {}

        self.name_to_references: dict[str, set[ReferenceDefinition]] = defaultdict(set)
        self._name_to_references: dict[str, set[ReferenceDefinition]] = defaultdict(set)

        self.signals = ParserSignals()

        self.setAutoDelete(False)

    def clear(self):
        self.definitions.clear()
        self.name_to_references.clear()

        self._path_to_data.clear()
        self._currently_open_file = None

    def run_with_local_copies(self, files: dict[Path, str], currently_open_file: Path | None = None):
        self._path_to_data = files
        self._currently_open_file = currently_open_file

        return self.run

    def run(self):
        start_time = time.time()

        do_a_complete_parse = self._currently_open_file is None

        # smb3.asm twice, all the prg files twice and then cleaning up the references once
        # this is only for a progress dialog, where we always do a complete parse
        self.signals.maximum_found.emit(len(self._path_to_data) * 2 + 1)

        # Pass 1, get all the definitions
        if do_a_complete_parse:
            added_definitions = []
            progress = self._parse_all_files_for_definitions()
        else:
            added_definitions = self._parse_current_file_for_definitions()
            progress = 0

        # Pass 2, find all the references
        progress = self._parse_all_files_for_references(added_definitions, do_a_complete_parse, progress)

        self.signals.progress_made.emit(progress, "Cleaning up References")
        self._cleanup_references()

        # Copy over new state
        self.definitions = self._definitions.copy()
        self.name_to_references = self._name_to_references.copy()

        self._path_to_data.clear()

        print(f"Parsing took {round(time.time() - start_time, 2)} seconds")

    def _parse_current_file_for_definitions(self):
        self._definitions = self.definitions.copy()
        self._name_to_references = self.name_to_references.copy()

        if self._currently_open_file is not None:
            self._remove_all_definitions_of_file(self._currently_open_file)
            self._parse_file_for_definitions(self._currently_open_file)

        old_definitions = set(self.definitions.keys())
        new_definitions = set(self._definitions.keys())

        removed_definitions = list(old_definitions.difference(new_definitions))
        added_definitions = list(new_definitions.difference(old_definitions))

        for definition in removed_definitions:
            print(f"Popping References for removed {definition}: {self.name_to_references.pop(definition, None)}")

        return added_definitions

    def _parse_all_files_for_definitions(self):
        progress = 0

        self._definitions.clear()
        self._name_to_references.clear()

        for file_path in self._path_to_data:
            self.signals.progress_made.emit(progress, f"Parsing for Definitions: {file_path}")
            self._parse_file_for_definitions(file_path)
            progress += 1

        return progress

    def _remove_all_definitions_of_file(self, rel_file_path: Path):
        for name, value in list(self._definitions.items()):
            if value.origin_file == rel_file_path:
                self._definitions.pop(name)

    def _parse_file_for_definitions(self, file_path: Path):
        lines = self._path_to_data[file_path].splitlines(True)

        for line_no, line in enumerate(lines, 1):
            self._find_definitions_in_line(line, line_no, file_path)

    def _find_definitions_in_line(self, line, line_no, rel_path):
        clean_line = strip_comment(line)

        for regex, nv_type in zip(
            (_CONST_REGEX, _RAM_REGEX, _LABEL_REGEX),
            (ReferenceType.CONSTANT, ReferenceType.RAM_VAR, ReferenceType.LABEL),
        ):
            match_iterator = regex.globalMatch(clean_line)

            we_matched = match_iterator.hasNext()

            while match_iterator.hasNext():
                match = match_iterator.next()

                matched_name = match.capturedView(1)
                matched_value = match.capturedView(2)

                self._definitions[matched_name] = ReferenceDefinition(
                    matched_name, matched_value, rel_path, line_no, nv_type, " ".join(line.split())
                )

            if we_matched:
                return

    def _parse_all_files_for_references(self, added_definitions, do_a_complete_parse, progress):
        for file_path in self._path_to_data:
            self.signals.progress_made.emit(progress, f"Parsing for References: {file_path}")

            self._parse_file_for_references(file_path, added_definitions, do_a_complete_parse)
            progress += 1
        return progress

    def _parse_file_for_references(self, file_to_parse: Path, added_definitions: list[str], force_parse):
        data = self._path_to_data[file_to_parse]

        is_open_file = file_to_parse == self._currently_open_file

        if not (force_parse or is_open_file) and not any(value in data for value in added_definitions):
            return

        lines = data.splitlines(True)

        print(f"Parsing {file_to_parse}")
        self._remove_reference_of_file(force_parse, is_open_file, file_to_parse)

        for line_no, line in enumerate(lines, 1):
            self._find_references_in_line(line, line_no, file_to_parse)

    def _find_references_in_line(self, line, line_no, rel_path):
        clean_line = strip_comment(line)
        match_iterator = _CONST_LABEL_CALL_RAM_VAR_REGEX.globalMatch(clean_line)

        while match_iterator.hasNext():
            match = match_iterator.next()

            matched_name = match.capturedView(1)

            reference = ReferenceDefinition(
                matched_name, "", rel_path, line_no, ReferenceType.UNSET, " ".join(line.split())
            )

            self._name_to_references[matched_name].add(reference)

    def _remove_reference_of_file(self, force_parse, is_open_file, rel_path):
        if force_parse or not is_open_file:
            return

        for name, references in self._name_to_references.items():
            for reference in list(references):
                if reference.origin_file == rel_path:
                    self._name_to_references[name].remove(reference)

    def _cleanup_references(self):
        """Remove the location of the name definition from the list of references."""
        for name, definition in self.definitions.items():
            _, _, file_path, line_no, _, _ = definition

            with suppress(KeyError):
                for reference in list(self._name_to_references[name]):
                    if reference.origin_file == file_path and reference.origin_line_no == line_no:
                        self._name_to_references[name].remove(reference)
