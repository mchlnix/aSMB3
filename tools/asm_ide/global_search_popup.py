from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QBrush, QColor, QFocusEvent, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from typing_extensions import NamedTuple


class SearchResult(NamedTuple):
    file_path: Path
    line_no: int
    line: str

    def __str__(self):
        return f"{self.file_path} ({self.line_no}): {self.line}"


class _SearchInput(QLineEdit):
    textChanged: SignalInstance(str)

    def focusOutEvent(self, event: QFocusEvent):
        self.parent().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.parent().close()
            event.accept()

        return super().keyPressEvent(event)


class GlobalSearchPopup(QWidget):
    MINIMUM_CHAR_COUNT_FOR_SEARCH = 3

    search_result_clicked = Signal(Path, int)

    def __init__(self, parent, search_term, search_text_by_file: dict[Path, str]):
        super(GlobalSearchPopup, self).__init__(parent)
        self.setAutoFillBackground(True)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.setMinimumWidth(500)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._search_input = _SearchInput()
        self._search_input.textChanged.connect(self._update_results)

        self._input_more_label = QLabel("Input at least 3 characters for results.")
        self._no_results_found_label = QLabel("No results found.")
        self._no_results_found_label.hide()

        self.table_widget = SearchResultsTable([])
        self.table_widget.reference_clicked.connect(self.search_result_clicked.emit)
        self.table_widget.hide()

        self._layout.addWidget(self._search_input, stretch=0)
        self._layout.addWidget(self._input_more_label, stretch=0)
        self._layout.addWidget(self._no_results_found_label, stretch=0)
        self._layout.addWidget(self.table_widget, stretch=1)

        self._search_input.setFocus()

        self._search_text_by_file = search_text_by_file
        self._last_search_term = ""

        self._results_cache: dict[str, list[SearchResult]] = {"": []}

        self._search_input.setText(search_term)

    def _update_results(self, new_search_term: str):
        search_results = []

        new_search_term = new_search_term.strip().lower()

        # case 1, search term didn't actually change, just white space
        if new_search_term == self._last_search_term:
            return

        # case 2, we have already cached the search results
        elif new_search_term in self._results_cache:
            search_results = self._results_cache[new_search_term]

        # case 3, search term was extended, so only update from the already found results
        elif (
            len(self._last_search_term) >= self.MINIMUM_CHAR_COUNT_FOR_SEARCH
            and self._last_search_term in new_search_term
        ):
            last_results = self._results_cache[self._last_search_term]

            for result in last_results:
                if new_search_term in result.line.lower():
                    search_results.append(result)

        # case 4, search term was changed in a way, that requires searching everything again
        elif len(new_search_term) >= self.MINIMUM_CHAR_COUNT_FOR_SEARCH:
            for file_path, search_text in self._search_text_by_file.items():
                lines = search_text.splitlines()

                for line_no, line in enumerate(lines, 1):
                    if new_search_term in line.lower():
                        search_results.append(SearchResult(file_path, line_no, line))

        self._last_search_term = new_search_term
        self._results_cache[new_search_term] = search_results

        self.table_widget.set_search_results(search_results)

        self._input_more_label.setVisible(len(new_search_term) < self.MINIMUM_CHAR_COUNT_FOR_SEARCH)
        self._no_results_found_label.setVisible(self._input_more_label.isHidden() and not search_results)
        self.table_widget.setVisible(bool(search_results))

        width = max(self.sizeHint().width(), self.table_widget.sizeHint().width())
        height = max(self.sizeHint().height(), self.table_widget.sizeHint().height())

        self.resize(QSize(width, height))

    def resize_for_height(self, height: int):
        if height > self.table_widget.sizeHint().height():
            return

        current_width = self.table_widget.sizeHint().width()

        self.resize(current_width + self.table_widget.verticalScrollBar().width(), height)

    def focusOutEvent(self, event):
        if self._search_input.hasFocus() or self.table_widget.hasFocus():
            event.ignore()

        else:
            self.close()


class SearchResultsTable(QTableWidget):
    _DEFINITION_LABEL_ROW = 0
    _REFERENCE_LABEL_ROW = 2

    reference_clicked = Signal(Path, int)

    cellEntered: SignalInstance(int, int)
    cellClicked: SignalInstance(int, int)

    def __init__(self, results: list[str], parent=None):
        super(SearchResultsTable, self).__init__(parent)

        self._setup_widget()
        self._setup_table()

        self._bold_font = self.font()
        self._bold_font.setBold(True)

        self._next_row_index = 0

        self.resizeColumnsToContents()
        self.resizeRowsToContents()

        self._last_file_path = ""

    def _setup_widget(self):
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoFillBackground(True)

        self.setMouseTracking(True)  # for the cellEntered signal to trigger

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setFont(QFont("Monospace", 12))

    def _setup_table(self):
        self.setShowGrid(False)

        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setSelectionMode(self.SelectionMode.SingleSelection)

        self.cellEntered.connect(self._select_row)
        self.cellClicked.connect(self._on_click)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)

        # make readonly
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setColumnCount(3)

    def set_search_results(self, search_results: list[SearchResult]):
        self.clear()

        self.setRowCount(len(search_results))

        for file_path, line_no, line in search_results:
            file_path_item = self._make_file_path_item(file_path)
            line_number_item = self._make_line_number_item(line_no)
            line_item = self._make_line_item(line)

            if file_path != self._last_file_path:
                self._last_file_path = file_path

                for item in (file_path_item, line_number_item, line_item):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

            self._add_row(file_path_item, line_number_item, line_item)

        self.resizeColumnsToContents()
        self.resizeRowsToContents()

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

    def _on_click(self, row: int, column: int):
        file_path = Path(self.item(row, 0).text().strip())
        line_number = int(self.item(row, 1).text())

        self.reference_clicked.emit(file_path, line_number)

        self.close()

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

        return QSize(width, self.rowCount() * self.rowHeight(0))
