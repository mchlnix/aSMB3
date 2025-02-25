from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QTableWidgetItem,
    QWidget,
)

from tools.asm_ide.application_settings import AppSettingKeys, AppSettings
from tools.asm_ide.reference_finder import ReferenceDefinition, ReferenceType
from tools.asm_ide.table_widget import TableWidget


def _smb3_first_sort_key(reference: ReferenceDefinition):
    if reference.origin_file.name == "smb3.asm":
        return ReferenceDefinition("", "", Path("a"), 0, ReferenceType.UNSET, "")
    else:
        return reference


class RedirectPopup(QWidget):
    def __init__(self, definition: ReferenceDefinition, references: list[ReferenceDefinition], parent):
        super(RedirectPopup, self).__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setAutoFillBackground(True)

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self.table_widget = ReferenceTableWidget()
        self.table_widget.set_references(definition, references)

        self._layout.addWidget(self.table_widget)

        self.table_widget.setFocus()

    def resize_for_height(self, height: int):
        if height > self.table_widget.sizeHint().height():
            return

        current_width = self.table_widget.sizeHint().width()

        self.resize(current_width + self.table_widget.verticalScrollBar().width(), height)

    def focusOutEvent(self, event):
        if self.table_widget.hasFocus():
            return

        self.close()


class ReferenceTableWidget(TableWidget):
    _DEFINITION_LABEL_ROW = 0
    _REFERENCE_LABEL_ROW = 2

    def __init__(self, parent=None):
        super(ReferenceTableWidget, self).__init__(parent)

        self.setFont(QFont("Monospace", AppSettings().value(AppSettingKeys.EDITOR_REFERENCE_FONT_SIZE)))
        self._bold_font = self.font()
        self._bold_font.setBold(True)

    def set_references(self, definition: ReferenceDefinition, references: list[ReferenceDefinition]):
        # set row count
        row_count = 1 + 1  # "Definitions" label row and the actual definition

        if references:
            row_count += 1 + len(references)  # "References" label row and references

        self.setRowCount(row_count)
        self.setColumnCount(3)

        self._add_definition_row(definition)
        self._add_reference_rows(references)

        self.resizeColumnsToContents()
        self.resizeRowsToContents()

    def _add_label_row(self, label_text: str):
        label_item = QTableWidgetItem(label_text)
        label_item.setForeground(QColor.fromRgb(0xA0A1A7))

        self._add_row(label_item)

    def _add_definition_row(self, definition):
        assert self._next_row_index == self._DEFINITION_LABEL_ROW
        self._add_label_row("Definition:")

        file_item = self._make_file_path_item(definition.origin_file)
        file_item.setFont(self._bold_font)

        line_number_item = self._make_line_number_item(definition.origin_line_no)
        line_number_item.setFont(self._bold_font)

        line_item = self._make_line_item(definition.line)
        line_item.setFont(self._bold_font)

        self._add_row(file_item, line_number_item, line_item)

        self._select_row(1)

    def _add_reference_rows(self, references):
        if not references:
            return

        assert self._next_row_index == self._REFERENCE_LABEL_ROW
        self._add_label_row("References:")

        for reference in sorted(references, key=_smb3_first_sort_key):
            file_item = self._make_file_path_item(reference.origin_file)
            line_number_item = self._make_line_number_item(reference.origin_line_no)
            line_item = self._make_line_item(reference.line)

            if self._last_file_path != reference.origin_file:
                self._last_file_path = reference.origin_file

                file_item.setFont(self._bold_font)
                line_number_item.setFont(self._bold_font)
                line_item.setFont(self._bold_font)

            self._add_row(file_item, line_number_item, line_item)

    def _select_row(self, row: int, _column: int = -1):
        if row in (self._DEFINITION_LABEL_ROW, self._REFERENCE_LABEL_ROW):
            return

        super()._select_row(row, _column)

    def _on_position_selected(self, row: int, _column: int = -1):
        if row in (self._DEFINITION_LABEL_ROW, self._REFERENCE_LABEL_ROW):
            return

        super()._on_position_selected(row, _column)

    def _next_valid_index(self, offset: int) -> int:
        next_index = super()._next_valid_index(offset)

        if next_index in (self._DEFINITION_LABEL_ROW, self._REFERENCE_LABEL_ROW):
            next_index += offset

            next_index %= self.rowCount()

        return next_index

    def keyPressEvent(self, event: QKeyEvent):
        # todo add pgup and stuff
        if event.key() == Qt.Key.Key_Escape:
            self.parent().close()

        elif event.key() == Qt.Key.Key_Up:
            self.highlight_previous()

        elif event.key() == Qt.Key.Key_Down:
            self.highlight_next()

        elif event.key() in [Qt.Key.Key_Enter, Qt.Key.Key_Return]:
            self.on_enter()

        else:
            return super().keyPressEvent(event)

        event.accept()
