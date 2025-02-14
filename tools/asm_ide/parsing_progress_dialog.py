from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog

from tools.asm_ide.named_value_finder import NamedValueFinder


class ParsingProgressDialog(QProgressDialog):
    def __init__(self, named_value_finder: NamedValueFinder):
        super(ParsingProgressDialog, self).__init__(None)

        self.named_value_finder = named_value_finder

        self.setWindowTitle("Parsing Progress")
        self.setLabelText(f"Preparing to parse '{self.named_value_finder.root_path}'")

        self.named_value_finder.signals.maximum_found.connect(self.setMaximum)
        self.named_value_finder.signals.progress_made.connect(self._update_text)

        self.setWindowModality(Qt.ApplicationModal)

        self.show()

        self.named_value_finder.run()

        self.close()

    def _update_text(self, progress: int, text: str):
        self.setValue(progress)
        self.setLabelText(text)

        QApplication.processEvents()

    def close(self):
        self.named_value_finder.signals.maximum_found.disconnect(self.setMaximum)
        self.named_value_finder.signals.progress_made.disconnect(self._update_text)
        return super().close()
