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


class NamedValueFinder:
    def __init__(self, root_path: Path):
        self.root_path = root_path

        self.constants: dict[str, NamedValue] = dict()
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
                match_iterator = _CONST_REGEX.globalMatch(line)

                while match_iterator.hasNext():
                    match = match_iterator.next()

                    const_name = match.capturedView(1)
                    const_value = match.capturedView(2)

                    semi_colon_index = line.find(";")

                    if -1 < semi_colon_index < match.capturedStart(1):
                        # label found inside a comment
                        continue

                    self.constants[const_name] = NamedValue(
                        const_name, const_value, file_path.relative_to(self.root_path), line_no
                    )

                match_iterator = _LABEL_REGEX.globalMatch(line)

                while match_iterator.hasNext():
                    match = match_iterator.next()

                    label_name = match.capturedView(1)
                    label_value = match.capturedView(2)

                    semi_colon_index = line.find(";")

                    if -1 < semi_colon_index < match.capturedStart(1):
                        # label found inside a comment
                        continue

                    self.labels[label_name] = NamedValue(
                        label_name, label_value, file_path.relative_to(self.root_path), line_no
                    )
