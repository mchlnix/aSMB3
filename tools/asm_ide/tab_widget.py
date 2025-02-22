from pathlib import Path
from typing import Generator

from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox, QTabWidget

from tools.asm_ide.code_area import CodeArea
from tools.asm_ide.reference_finder import ReferenceFinder
from tools.asm_ide.tab_bar import TabBar


class TabWidget(QTabWidget):
    redirect_clicked = Signal(Path, int)
    """
    :param Path The relative path of the document the redirect points to.
    :param int The line number the redirect points to.
    """
    text_position_clicked = Signal(Path, int)
    """
    :param Path The relative path of the document the position was changed in.
    :param int The block index the position was changed to.
    """
    document_modified = Signal(bool, bool)
    """
    :param bool True if the current document is modified.
    :param bool True if any open document is modified.
    """
    undo_redo_changed = Signal(bool, bool)
    """
    :param bool True if the current document has something to undo.
    :param bool True if the current document has something to redo.
    """
    contents_changed = Signal(Path)

    tabCloseRequested: SignalInstance
    currentChanged: SignalInstance

    def __init__(self, parent):
        super(TabWidget, self).__init__(parent)
        self.setMouseTracking(True)

        self.tab_index_to_path: list[Path] = []
        self.reference_finder: ReferenceFinder | None = None

        tab_bar = TabBar(self)
        tab_bar.middle_click_on.connect(self.tabCloseRequested.emit)
        self.setTabBar(tab_bar)

        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self.currentChanged.connect(self._on_current_tab_changed)

    @property
    def current_code_area(self) -> CodeArea | None:
        return self.currentWidget()

    def open_or_switch_file(self, abs_path: Path):
        if abs_path in self.tab_index_to_path:
            tab_index = self.tab_index_to_path.index(abs_path)

            self.setCurrentIndex(tab_index)

        else:
            self._load_asm_file(abs_path)

    def _load_asm_file(self, abs_path: Path) -> None:
        if self.reference_finder is None:
            raise ValueError("Error, ReferenceFinder not set")

        code_area = CodeArea(self, self.reference_finder)
        code_area.redirect_clicked.connect(self.redirect_clicked.emit)
        code_area.contents_changed.connect(lambda: self.contents_changed.emit(abs_path))

        self.tab_index_to_path.append(abs_path)

        tab_index = self.addTab(code_area, "")
        assert tab_index == len(self.tab_index_to_path) - 1

        code_area.text_document.setPlainText(abs_path.read_text())
        code_area.text_document.setModified(False)

        code_area.text_document.modificationChanged.connect(self._react_to_modification)
        code_area.text_document.contentsChanged.connect(self._emit_undo_redo_state)

        code_area.text_position_clicked.connect(lambda index: self.text_position_clicked.emit(abs_path, index))
        # Set the first navigation point of an opened file to the top.
        # Will be overwritten when the user clicks somewhere into the document.
        code_area.text_position_clicked.emit(0)

        code_area.moveCursor(QTextCursor.Start)

        self.setCurrentIndex(tab_index)
        self._update_title_of_tab_at_index(self.currentIndex())

    def save_current_file(self):
        self._save_file_at_index(self.currentIndex())

    def save_all_files(self):
        for index in range(self.count()):
            self._save_file_at_index(index)

    def _save_file_at_index(self, index: int):
        code_area = self.widget(index)

        if code_area is None:
            return

        path = self.tab_index_to_path[index]
        data = code_area.text_document.toPlainText()

        with path.open("w") as file:
            file.write(data)

        code_area.text_document.setModified(False)
        self._update_title_of_tab_at_index(index)

    def scroll_to_line(self, line_no: int):
        current_code_area = self.current_code_area

        if current_code_area is None:
            return

        current_cursor = current_code_area.textCursor()
        current_cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.MoveAnchor)
        current_cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_no - 1)

        current_code_area.setTextCursor(current_cursor)

        current_code_area.centerCursor()

    def scroll_to_position(self, block_index: int):
        current_code_area = self.current_code_area

        if current_code_area is None:
            return

        current_cursor = current_code_area.textCursor()
        current_cursor.setPosition(block_index, QTextCursor.MoveMode.MoveAnchor)

        current_code_area.setTextCursor(current_cursor)

        current_code_area.centerCursor()

    def _on_current_tab_changed(self):
        self._emit_undo_redo_state()
        self._react_to_modification()

    def _react_to_modification(self):
        # no open documents
        if self.currentIndex() == -1:
            self.document_modified.emit(False, False)
            return

        # update modified-star in tab title
        self._update_title_of_tab_at_index(self.currentIndex())

        # check for modification status
        current_document_is_modified = self.current_code_area and self.current_code_area.text_document.isModified()

        if current_document_is_modified or self.count() == 1:
            # if the current document is modified, then any document is modified, too
            # if there is only one open document, then whatever its modification status is, counts for all
            self.document_modified.emit(current_document_is_modified, current_document_is_modified)
            return

        any_document_is_modified = any(code_area.document().isModified() for code_area in self.widgets())

        self.document_modified.emit(False, any_document_is_modified)

    def _update_title_of_tab_at_index(self, index: int):
        if index == -1:
            return

        current_path = self.tab_index_to_path[index]

        tab_title = current_path.name

        code_area = self.widget(index)

        if code_area is None:
            return

        if code_area.text_document.isModified():
            tab_title += " *"

        self.setTabText(index, tab_title)

    def widgets(self) -> Generator[CodeArea, None, None]:
        for tab_index in range(self.count()):
            widget = self.widget(tab_index)

            if widget is not None:
                yield widget

    def _close_tab(self, index: int):
        path_of_tab = self.tab_index_to_path[index]

        code_area = self.widget(index)

        if (
            code_area is None
            or code_area.text_document.isModified()
            and not self._ask_for_close_without_saving([str(path_of_tab)])
        ):
            return

        self.tab_index_to_path.pop(index)
        self.removeTab(index)

    def to_next_tab(self):
        if self.currentIndex() == self.count() - 1:
            return

        self.setCurrentIndex(self.currentIndex() + 1)

    def to_previous_tab(self):
        if self.currentIndex() < 1:
            return

        self.setCurrentIndex(self.currentIndex() - 1)

    def on_undo(self):
        current_code_area: CodeArea | None = self.current_code_area

        if current_code_area is None:
            return

        if current_code_area.text_document.isUndoAvailable():
            current_code_area.undo()

        self._emit_undo_redo_state()

    def on_redo(self):
        current_code_area: CodeArea | None = self.current_code_area

        if current_code_area is None:
            return

        if current_code_area.text_document.isRedoAvailable():
            current_code_area.redo()

        self._emit_undo_redo_state()

    def _emit_undo_redo_state(self):
        if self.current_code_area is None:
            self.undo_redo_changed.emit(False, False)
            return

        undo_available = self.current_code_area.text_document.isUndoAvailable()
        redo_available = self.current_code_area.text_document.isRedoAvailable()

        self.undo_redo_changed.emit(undo_available, redo_available)

    def currentWidget(self) -> CodeArea | None:
        return super().currentWidget()

    def widget(self, index) -> CodeArea | None:
        return super().widget(index)

    def ask_to_quit_all_tabs_without_saving(self):
        modified_file_names: list[str] = [
            self.tabText(tab_index).removesuffix(" *")
            for tab_index, code_area in enumerate(self.widgets())
            if code_area.document().isModified()
        ]

        return self._ask_for_close_without_saving(modified_file_names)

    def clear(self):
        self.tab_index_to_path.clear()

        return super().clear()

    @staticmethod
    def _ask_for_close_without_saving(file_names: list[str]):
        file_name_list = "\n".join(file_names)

        if not file_name_list:
            return True

        ret_button = QMessageBox.warning(
            None,
            "Unsaved Changes",
            f"There are unsaved changes in:\n\n{file_name_list}\n\nDo you want to proceed without saving?",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
        )

        return ret_button == QMessageBox.StandardButton.Yes

    def focus_search_bar(self):
        if self.current_code_area is None:
            return

        self.current_code_area.focus_search_bar()
