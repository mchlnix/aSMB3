from pathlib import Path
from typing import Generator

from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTabWidget

from tools.asm_ide.code_area import CodeArea
from tools.asm_ide.named_value_finder import NamedValueFinder
from tools.asm_ide.tab_bar import TabBar


class TabWidget(QTabWidget):
    redirect_clicked = Signal(Path, int)
    """
    :param Path The relative path of the document the redirect points to.
    :param int The line number the redirect points to.
    """
    document_modified = Signal(bool, bool)
    """
    :param bool True if the current document is modified.
    :param bool True if any open document is modified.
    """

    tabCloseRequested: SignalInstance(int)

    def __init__(self, parent, named_value_finder: NamedValueFinder):
        super(TabWidget, self).__init__(parent)
        self.setMouseTracking(True)

        self._path_to_tab = []
        self._named_value_finder = named_value_finder

        tab_bar = TabBar(self)
        tab_bar.middle_click_on.connect(self.tabCloseRequested.emit)
        self.setTabBar(tab_bar)

        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self.currentChanged.connect(self._react_to_modification)

    def open_or_switch_file(self, file_path: Path):
        if file_path in self._path_to_tab:
            tab_index = self._path_to_tab.index(file_path)

            self.setCurrentIndex(tab_index)

        else:
            self._load_disasm_file(file_path)

    def _load_disasm_file(self, path: Path) -> None:
        code_area = CodeArea(self, self._named_value_finder)
        code_area.redirect_clicked.connect(self.redirect_clicked.emit)

        self._path_to_tab.append(path)

        tab_index = self.addTab(code_area, "")
        assert tab_index == len(self._path_to_tab) - 1

        code_area.text_document.setPlainText(path.read_text())
        code_area.text_document.setModified(False)
        code_area.text_document.modificationChanged.connect(self._react_to_modification)
        code_area.moveCursor(QTextCursor.Start)

        self.setCurrentIndex(tab_index)
        self._update_title_of_tab_at_index(self.currentIndex())

    def save_current_file(self):
        self._save_file_at_index(self.currentIndex())

    def save_all_files(self):
        for index in range(self.count()):
            self._save_file_at_index(index)

    def _save_file_at_index(self, index: int):
        code_area: CodeArea = self.widget(index)

        path = self._path_to_tab[index]
        data = code_area.text_document.toPlainText()

        with path.open("w") as file:
            file.write(data)

        code_area.text_document.setModified(False)
        self._update_title_of_tab_at_index(index)

    def scroll_to_line(self, line_no: int):
        current_code_area: CodeArea = self.currentWidget()
        total_lines = current_code_area.document().lineCount()

        current_code_area.moveCursor(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.MoveAnchor)
        current_cursor = current_code_area.textCursor()
        current_cursor.movePosition(
            QTextCursor.MoveOperation.Up, QTextCursor.MoveMode.MoveAnchor, total_lines - line_no
        )

        current_code_area.setTextCursor(current_cursor)

    def _react_to_modification(self):
        # no open documents
        if self.currentIndex() == -1:
            self.document_modified.emit(False, False)
            return

        # update modified-star in tab title
        self._update_title_of_tab_at_index(self.currentIndex())

        # check for modification status
        current_document_is_modified = self.currentWidget().text_document.isModified()

        if current_document_is_modified or self.count() == 1:
            # if the current document is modified, then any document is modified, too
            # if there is only one open document, then whatever its modification status is, counts for all
            self.document_modified.emit(current_document_is_modified, current_document_is_modified)
            return

        any_document_is_modified = any(code_area.document().isModified() for code_area in self._iter_widgets())

        self.document_modified.emit(False, any_document_is_modified)

    def _update_title_of_tab_at_index(self, index: int):
        if index == -1:
            return

        current_path = self._path_to_tab[index]

        tab_title = current_path.name

        if self.widget(index).text_document.isModified():
            tab_title += " *"

        self.setTabText(index, tab_title)

    def _iter_widgets(self) -> Generator[CodeArea, None, None]:
        for tab_index in range(self.count()):
            yield self.widget(tab_index)

    def _close_tab(self, index):
        self._path_to_tab.pop(index)
        self.removeTab(index)

    def currentWidget(self) -> CodeArea:
        return super().currentWidget()

    def widget(self, index) -> CodeArea:
        return super().widget(index)
