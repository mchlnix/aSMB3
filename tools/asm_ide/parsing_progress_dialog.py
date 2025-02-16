from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog

from tools.asm_ide.reference_finder import ReferenceFinder


class ParsingProgressDialog(QProgressDialog):
    def __init__(self, reference_finder: ReferenceFinder):
        super(ParsingProgressDialog, self).__init__(None)

        self._reference_finder = reference_finder

        self.setWindowTitle("Parsing Progress")
        self.setLabelText(f"Preparing to parse '{self._reference_finder.root_path}'")

        self._reference_finder.signals.maximum_found.connect(self.setMaximum)
        self._reference_finder.signals.progress_made.connect(self._update_text)

        self.setWindowModality(Qt.ApplicationModal)

        self.show()

        self._reference_finder.run()

        self.close()

    def _update_text(self, progress: int, text: str):
        self.setValue(progress)
        self.setLabelText(text)

        QApplication.processEvents()

    def close(self):
        self._reference_finder.signals.maximum_found.disconnect(self.setMaximum)
        self._reference_finder.signals.progress_made.disconnect(self._update_text)
        return super().close()
