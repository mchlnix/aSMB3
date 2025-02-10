from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QRegularExpression


class NamedValue(NamedTuple):
    name: str
    value: str
    origin_file: Path
    origin_line_no: int


_CONST_REGEX = QRegularExpression("([A-Za-z][A-za-z0-9_]*)\s*\=\s*(\$[0-9A-F]+|\%[0-1]+|[0-9]+)")
_LABEL_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:\s*(.*)")
_RAM_REGEX = QRegularExpression("([A-Za-z_][A-Za-z0-9_]*)\:\s*(\.ds.*)")

# todo keep track of macros


class NamedValueFinder:
    def __init__(self, root_path: Path):
        self.root_path = root_path

        self.constants: dict[str, NamedValue] = dict()
        self.ram_variables: dict[str, NamedValue] = dict()
        self.labels: dict[str, NamedValue] = dict()

    def parse_files(self):
        smb3_path = self.root_path / "smb3.asm"

        self._parse_file(smb3_path)

        for prg_file in self.prg_files:
            yield prg_file
            self._parse_file(prg_file)

    @property
    def prg_files(self):
        prg_dir = self.root_path / "PRG"

        contents = prg_dir.glob("prg[0-9]*.asm")

        return list(contents)

    @property
    def prg_count(self):
        return len(self.prg_files)

    def _parse_file(self, file_path: Path):
        with file_path.open("r") as f:
            for line_no, line in enumerate(f.readlines(), 1):
                semi_colon_index = line.find(";")

                for regex, bucket in zip(
                    [_CONST_REGEX, _RAM_REGEX, _LABEL_REGEX], [self.constants, self.ram_variables, self.labels]
                ):
                    match_iterator = regex.globalMatch(line)

                    we_matched = match_iterator.hasNext()

                    while match_iterator.hasNext():
                        match = match_iterator.next()

                        matched_name = match.capturedView(1)
                        matched_value = match.capturedView(2)

                        if -1 < semi_colon_index < match.capturedStart(1):
                            # match found inside a comment
                            continue

                        bucket.__setitem__(
                            matched_name,
                            NamedValue(matched_name, matched_value, file_path.relative_to(self.root_path), line_no),
                        )

                    if we_matched:
                        break
