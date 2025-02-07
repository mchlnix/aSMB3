from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTabWidget

from tools.asm_ide.code_area import CodeArea
from tools.asm_ide.named_value_finder import NamedValueFinder
from tools.asm_ide.tab_bar import TabBar


class TabWidget(QTabWidget):
    redirect_clicked = Signal(Path, int)

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

    def open_or_switch_file(self, file_path: Path):
        if file_path in self._path_to_tab:
            tab_index = self._path_to_tab.index(file_path)

            self.setCurrentIndex(tab_index)

        else:
            self._load_disasm_file(file_path)

    def scroll_to_line(self, line_no: int):
        current_code_area: CodeArea = self.currentWidget()
        total_lines = current_code_area.document().lineCount()

        current_code_area.moveCursor(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.MoveAnchor)
        current_cursor = current_code_area.textCursor()
        current_cursor.movePosition(
            QTextCursor.MoveOperation.Up, QTextCursor.MoveMode.MoveAnchor, total_lines - line_no
        )

        current_code_area.setTextCursor(current_cursor)

    def _load_disasm_file(self, path: Path) -> None:
        code_area = CodeArea(self, self._named_value_finder)
        code_area.redirect_clicked.connect(self.redirect_clicked.emit)

        tab_index = self.addTab(code_area, path.name)

        assert tab_index == len(self._path_to_tab)
        self._path_to_tab.append(path)

        code_area.text_document.setPlainText(path.read_text())
        code_area.moveCursor(QTextCursor.Start)

        self.setCurrentIndex(tab_index)

    def _close_tab(self, index):
        self.widget(index).redirect_clicked.disconnect(self.redirect_clicked.emit)
        self._path_to_tab.pop(index)
        self.removeTab(index)
