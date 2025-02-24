from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
)


class TableWidget(QTableWidget):
    row_clicked = Signal(Path, int)

    cellEntered: SignalInstance
    cellClicked: SignalInstance

    def __init__(self, parent=None):
        super(TableWidget, self).__init__(parent)

        self._setup_widget()
        self._setup_table()

        self._bold_font = self.font()
        self._bold_font.setBold(True)

        self._next_row_index = 0

        self._last_file_path = Path()

    def _setup_widget(self):
        self.setMouseTracking(True)  # for the cellEntered signal to trigger

        self.setFont(QFont("Monospace", 12))

    def _setup_table(self):
        self.setShowGrid(False)

        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setSelectionMode(self.SelectionMode.SingleSelection)

        self.cellEntered.connect(self._select_row)
        self.cellClicked.connect(self._on_position_selected)

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)

        # make readonly
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setColumnCount(3)

    def _add_row(self, *cells: QTableWidgetItem | str):
        for column, cell in enumerate(cells):
            if isinstance(cell, str):
                cell = QTableWidgetItem(cell)

            self.setItem(self._next_row_index, column, cell)

        self._next_row_index += 1

    @staticmethod
    def _make_file_path_item(file_path: Path):
        file_item = QTableWidgetItem(f"{file_path}   ")
        file_item.setForeground(QBrush(QColor.fromRgb(0xA626A4)))

        return file_item

    @staticmethod
    def _make_line_number_item(line_no: int):
        line_number_item = QTableWidgetItem(str(line_no))

        line_number_item.setForeground(QBrush(QColor.fromRgb(0x2C91AF)))
        line_number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return line_number_item

    @staticmethod
    def _make_line_item(line: str):
        line_item = QTableWidgetItem(f"   {line}")
        return line_item

    def _select_row(self, row: int, _column: int = -1):
        # If the cursor is on the last row and the row is not fully visible, all rows will scroll one higher to show
        # the now selected row fully.
        # But that would put the cursor over the next, not fully visible row, causing the same to happen again.
        # This either scrolls the table until the end in one go, or cause a recursion limit error.
        self.blockSignals(True)
        self.selectRow(row)
        self.blockSignals(False)

    def _on_position_selected(self, row: int, _column: int = -1):
        file_path = Path(self.item(row, 0).text().strip())
        line_number = int(self.item(row, 1).text())

        self.row_clicked.emit(file_path, line_number)

        self.close()

    def on_enter(self):
        selected_row_index = self._selected_row_index()

        if selected_row_index == -1:
            return

        self._on_position_selected(selected_row_index)

    def highlight_next(self):
        if (next_selected_index := self._next_valid_index(+1)) != -1:
            self._select_row(next_selected_index)

    def highlight_previous(self):
        if (next_selected_index := self._next_valid_index(-1)) != -1:
            self._select_row(next_selected_index)

    def _next_valid_index(self, offset: int):
        if self.rowCount() == 0:
            return -1

        selected_index = self._selected_row_index()

        if selected_index == -1:
            next_selected_index = 0
        else:
            next_selected_index = (selected_index + offset) % self.rowCount()

        return next_selected_index

    def _selected_row_index(self):
        selected = self.selectedItems()

        if not selected:
            return -1

        return selected[0].row()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.parent().close()

        event.accept()

    def focusOutEvent(self, event):
        self.parent().focusOutEvent(event)

    def clear(self):
        self._next_row_index = 0
        return super().clear()

    def close(self):
        return self.parent().close()

    def sizeHint(self):
        width = sum(self.columnWidth(column_index) for column_index in range(self.columnCount() + 1)) + 20

        return QSize(width, self.rowCount() * self.rowHeight(0) + 2)
