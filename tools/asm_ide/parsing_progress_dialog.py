from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog


class ParsingProgressDialog(QProgressDialog):
    def __init__(self, parent, maximum: int, parsing_generator):
        super(ParsingProgressDialog, self).__init__(parent)

        self.setWindowTitle("Parsing Progress")
        self.setLabelText("Preparing to parse")

        self.parsing_generator = parsing_generator

        self.setRange(0, maximum)

        self.setWindowModality(Qt.ApplicationModal)

        self.show()

        # need (at least) two calls to have the dialog show up correctly on fast PCs
        QApplication.processEvents()
        QApplication.processEvents()

        for index, file_being_parsed in enumerate(self.parsing_generator, 1):
            self.setValue(index)
            self.setLabelText(f"Parsing {file_being_parsed}")

        self.close()
