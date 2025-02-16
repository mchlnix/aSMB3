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


def _smb3_first_sort_key(reference: ReferenceDefinition):
    if reference.origin_file.name == "smb3.asm":
        return ReferenceDefinition("", "", "a", 0, ReferenceType.UNSET, "")
    else:
        return reference


class RedirectPopup(QWidget):
    def __init__(self, definition: ReferenceDefinition, references: list[ReferenceDefinition], parent):
        super(RedirectPopup, self).__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setAutoFillBackground(True)

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        widget = ReferenceTableWidget(definition, references)

        self._layout.addWidget(widget)


class ReferenceTableWidget(QTableWidget):
    _DEFINITION_LABEL_ROW = 0
    _REFERENCE_LABEL_ROW = 2

    def __init__(self, definition: ReferenceDefinition, references: list[ReferenceDefinition], parent=None):
        super(ReferenceTableWidget, self).__init__(parent)

        self._setup_widget()

        self._setup_table(references)

        self._bold_font = self.font()
        self._bold_font.setBold(True)

        self._next_row_index = 0

        self._add_definition_row(definition)
        self._add_reference_rows(references)

        self.setFocus()

        self.resizeRowsToContents()

    def _setup_widget(self):
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoFillBackground(True)

        self.setMouseTracking(True)  # for the cellEntered signal to trigger

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.setFont(QFont("Monospace", 14))

    def _setup_table(self, references: list[ReferenceDefinition]):
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.cellEntered.connect(self._select_row)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)

        # make readonly
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # set row count
        row_count = 1 + 1  # "Definitions" row and the actual definition

        if references:
            row_count += 1 + len(references)  # "References" row and references

        self.setRowCount(row_count)
        self.setColumnCount(3)

    def _add_label_row(self, label_text: str):
        label_item = QTableWidgetItem(label_text)
        label_item.setForeground(QColor.fromRgb(0xA0A1A7))

        self._add_row(label_item)

    def _add_definition_row(self, definition):
        assert self._next_row_index == self._DEFINITION_LABEL_ROW
        self._add_label_row("Definition:")

        file_item = QTableWidgetItem(str(definition.origin_file))

        file_item.setForeground(QBrush(QColor.fromRgb(0xA626A4)))
        file_item.setFont(self._bold_font)

        line_number_item = QTableWidgetItem(str(definition.origin_line_no))

        line_number_item.setForeground(QBrush(QColor.fromRgb(0x2C91AF)))
        line_number_item.setFont(self._bold_font)
        line_number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._add_row(file_item, line_number_item, QTableWidgetItem(definition.line))

        self._select_row(1)

    def _add_reference_rows(self, references):
        if not references:
            return

        assert self._next_row_index == self._REFERENCE_LABEL_ROW
        self._add_label_row("References:")

        last_file = ""

        for reference in sorted(references, key=_smb3_first_sort_key):
            file_item = QTableWidgetItem(str(reference.origin_file))
            file_item.setForeground(QBrush(QColor.fromRgb(0xA626A4)))

            line_number_item = QTableWidgetItem(str(reference.origin_line_no))
            line_number_item.setForeground(QBrush(QColor.fromRgb(0x2C91AF)))
            line_number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if last_file != reference.origin_file:
                last_file = reference.origin_file

                file_item.setFont(self._bold_font)
                line_number_item.setFont(self._bold_font)

            self._add_row(file_item, line_number_item, QTableWidgetItem(reference.line))

    def _add_row(self, *cells: QTableWidgetItem | str):
        for column, cell in enumerate(cells):
            if isinstance(cell, str):
                cell = QTableWidgetItem(cell)

            self.setItem(self._next_row_index, column, cell)

        self._next_row_index += 1

    def _select_row(self, row: int, _column: int = -1):
        if row in (self._DEFINITION_LABEL_ROW, self._REFERENCE_LABEL_ROW):
            return

        self.selectRow(row)

    def sizeHint(self):
        width = sum(self.columnWidth(column_index) for column_index in range(self.columnCount() + 1)) + 2

        return QSize(width, self.rowCount() * self.rowHeight(0) + 2)
