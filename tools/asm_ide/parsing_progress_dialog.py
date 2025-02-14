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
        self.named_value_finder.maximum_found.connect(self.setMaximum)
        self.named_value_finder.progress_made.connect(self._update_text)

        self.setWindowModality(Qt.ApplicationModal)

        self.show()

        self.named_value_finder.parse_files()

        self.close()

    def _update_text(self, progress: int, text: str):
        self.setValue(progress)
        self.setLabelText(text)

        QApplication.processEvents()
