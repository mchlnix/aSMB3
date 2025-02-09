from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog

from tools.asm_ide.named_value_finder import NamedValueFinder


class ParsingProgressDialog(QProgressDialog):
    def __init__(self, root_path: Path):
        super(ParsingProgressDialog, self).__init__(None)

        self.setWindowTitle("Parsing Progress")
        self.setLabelText(f"Preparing to parse '{root_path}'")

        self.named_value_finder = NamedValueFinder(root_path)

        self.setRange(0, self.named_value_finder.prg_count)

        self.setWindowModality(Qt.ApplicationModal)

        self.show()

        # need (at least) two calls to have the dialog show up correctly on fast PCs
        QApplication.processEvents()
        QApplication.processEvents()

        for index, file_being_parsed in enumerate(self.named_value_finder.parse_files(), 1):
            self.setValue(index)
            self.setLabelText(f"Parsing {file_being_parsed}")

        self.close()
