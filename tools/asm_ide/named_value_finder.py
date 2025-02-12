from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QRegularExpression

from foundry.data_source import strip_comment


class NamedValue(NamedTuple):
    name: str
    value: str
    origin_file: Path
    origin_line_no: int


_CONST_REGEX = QRegularExpression("([A-Za-z][A-za-z0-9_]*)\s*\=\s*(\$[0-9A-F]+|\%[0-1]+|[0-9]+)")
_LABEL_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:\s*(.*)")
_RAM_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:\s*(\.ds.*)")

_CONST_LABEL_CALL_RAM_VAR_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)")

# todo keep track of macros


class NamedValueFinder:
    def __init__(self, root_path: Path):
        self.root_path = root_path

        self.constants: dict[str, NamedValue] = dict()
        self.ram_variables: dict[str, NamedValue] = dict()
        self.labels: dict[str, NamedValue] = dict()

        self.location_to_names: dict[tuple[Path, int], set[str]] = defaultdict(set)
        """
        The key is a tuple of file path and line number, the value is a list of all names we found there.
        These need to be updated when a line changes and when the number of lines changes.
        """
        self.name_to_locations: dict[str, set[tuple[Path, int]]] = defaultdict(set)

    def parse_files(self):
        smb3_path = self.root_path / "smb3.asm"

        self._parse_file_for_definitions(smb3_path)
        self._parse_file_for_references(smb3_path)

        # Pass 1, get all the definitions
        for prg_file in self.prg_files:
            yield prg_file
            self._parse_file_for_definitions(prg_file)

        # Pass 2, find all the references
        for prg_file in self.prg_files:
            yield prg_file
            self._parse_file_for_references(prg_file)

        self._cleanup_references()

    @property
    def prg_files(self):
        prg_dir = self.root_path / "PRG"

        return sorted(prg_dir.glob("prg[0-9]*.asm"))

    @property
    def prg_count(self):
        return len(self.prg_files)

    def _parse_file_for_definitions(self, file_path: Path):
        with file_path.open("r") as f:
            rel_path = file_path.relative_to(self.root_path)

            for line_no, line in enumerate(f.readlines(), 1):
                line = strip_comment(line)

                for regex, bucket in zip(
                    [_CONST_REGEX, _RAM_REGEX, _LABEL_REGEX], [self.constants, self.ram_variables, self.labels]
                ):
                    match_iterator = regex.globalMatch(line)

                    we_matched = match_iterator.hasNext()

                    while match_iterator.hasNext():
                        match = match_iterator.next()

                        matched_name = match.capturedView(1)
                        matched_value = match.capturedView(2)

                        self.location_to_names[(rel_path, line_no)].add(matched_name)
                        self.name_to_locations[matched_name].add((rel_path, line_no))

                        bucket.__setitem__(
                            matched_name,
                            NamedValue(matched_name, matched_value, rel_path, line_no),
                        )

                    if we_matched:
                        break

    def _parse_file_for_references(self, file_path: Path):
        with file_path.open("r") as f:
            rel_path = file_path.relative_to(self.root_path)

            for line_no, line in enumerate(f.readlines(), 1):
                line = strip_comment(line)

                match_iterator = _CONST_LABEL_CALL_RAM_VAR_REGEX.globalMatch(line)

                while match_iterator.hasNext():
                    match = match_iterator.next()

                    matched_name = match.capturedView(1)

                    self.location_to_names[(rel_path, line_no)].add(matched_name)
                    self.name_to_locations[matched_name].add((rel_path, line_no))

    def _cleanup_references(self):
        for bucket in (self.constants, self.ram_variables, self.labels):
            for name, named_value in bucket.items():
                _, _, file_path, line_no = named_value

                self.name_to_locations[name].remove((file_path, line_no))
