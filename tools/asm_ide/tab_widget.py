from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTabWidget

from tools.asm_ide.code_area import CodeArea
from tools.asm_ide.named_value_finder import NamedValueFinder
from tools.asm_ide.tab_bar import TabBar


class TabWidget(QTabWidget):
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

    def _load_disasm_file(self, path: Path) -> None:
        code_area = CodeArea(self, self._named_value_finder)

        tab_index = self.addTab(code_area, path.name)

        assert tab_index == len(self._path_to_tab)
        self._path_to_tab.append(path)

        code_area.text_document.setPlainText(path.read_text())
        code_area.moveCursor(QTextCursor.Start)

        self.setCurrentIndex(tab_index)

    def _close_tab(self, index):
        self._path_to_tab.pop(index)
        self.removeTab(index)
