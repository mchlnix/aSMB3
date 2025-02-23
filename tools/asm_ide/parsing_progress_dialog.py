from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog


class ParsingProgressDialog(QProgressDialog):
    def __init__(self, parse_callback: Callable) -> None:
        super(ParsingProgressDialog, self).__init__(None)

        self._parse_callback = parse_callback

        self.setWindowTitle("Parsing Progress")
        self.setLabelText(f"Preparing to parse'")

        self.setWindowModality(Qt.ApplicationModal)

        self.show()

    def start(self):
        self._parse_callback()

        self.close()

    def update_text(self, progress: int, text: str):
        self.setValue(progress)
        self.setLabelText(text)

        QApplication.processEvents()

    def close(self):
        return super().close()
