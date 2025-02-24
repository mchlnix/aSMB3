from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QFocusEvent, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tools.asm_ide.settings import SettingKeys, Settings
from tools.asm_ide.table_widget import TableWidget


class SearchResult(NamedTuple):
    file_path: Path
    line_no: int
    line: str

    def __str__(self):
        return f"{self.file_path} ({self.line_no}): {self.line}"


class _SearchInput(QLineEdit):
    textChanged: SignalInstance

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

        self.table_widget = SearchResultsTable()
        self.table_widget.row_clicked.connect(self.search_result_clicked.emit)
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

    def close(self):
        # needed, because the code area doesn't get the focus otherwise for some reason
        self.parent().setFocus()

        super().close()


class SearchResultsTable(TableWidget):

    def __init__(self, parent=None):
        super(SearchResultsTable, self).__init__(parent)

        self.setFont(QFont("Monospace", Settings().value(SettingKeys.EDITOR_SEARCH_FONT_SIZE)))
        self._bold_font = self.font()
        self._bold_font.setBold(True)

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
