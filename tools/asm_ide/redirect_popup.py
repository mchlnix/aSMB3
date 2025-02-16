from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from tools.asm_ide.reference_finder import ReferenceDefinition, ReferenceType


class RedirectPopup(QWidget):
    def __init__(self, definition: ReferenceDefinition, references: list[ReferenceDefinition], parent):
        super(RedirectPopup, self).__init__(parent)

        self.setAutoFillBackground(True)

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        widget = ReferenceTableWidget(definition, references)

        self._layout.addWidget(widget)


class ReferenceTableWidget(QTableWidget):
    def __init__(self, definition: ReferenceDefinition, references: list[ReferenceDefinition], parent=None):
        super(ReferenceTableWidget, self).__init__(parent)

        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoFillBackground(True)

        self.file_font = self.font()

        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)

        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setSelectionMode(self.SelectionMode.SingleSelection)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)

        self.setFont(QFont("Monospace", 12))

        self.setRowCount(len(references))
        self.setColumnCount(3)

        file_item = QTableWidgetItem(str(definition.origin_file))
        file_item.setForeground(QBrush(QColor.fromRgb(0xA626A4)))

        font = file_item.font()
        font.setBold(True)
        file_item.setFont(font)

        line_number_item = QTableWidgetItem(str(definition.origin_line_no))
        line_number_item.setForeground(QBrush(QColor(0, 0, 255)))
        line_number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._add_row(0, file_item, line_number_item, QTableWidgetItem(definition.line))

        self._add_reference_rows(references)

        self.setFocus()

        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)

        self.resizeRowsToContents()

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

    def _add_reference_rows(self, references):
        def _smb3_first(_reference: ReferenceDefinition):
            if _reference.origin_file.name == "smb3.asm":
                return ReferenceDefinition("", "", "a", 0, ReferenceType.UNSET, "")
            else:
                return _reference

        last_file = ""

        for row, reference in enumerate(sorted(references, key=_smb3_first), 1):
            file_item = QTableWidgetItem(str(reference.origin_file))

            if last_file != reference.origin_file:
                font = file_item.font()
                font.setBold(True)
                file_item.setFont(font)

                last_file = reference.origin_file

            line_number_item = QTableWidgetItem(str(reference.origin_line_no))
            line_number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self._add_row(row, file_item, line_number_item, QTableWidgetItem(reference.line))

    def _add_row(self, row: int, *cells: QTableWidgetItem):
        for column, cell in enumerate(cells):
            self.setItem(row, column, cell)

    def sizeHint(self):
        return QSize(self.horizontalHeader().width(), self.verticalHeader().height())
