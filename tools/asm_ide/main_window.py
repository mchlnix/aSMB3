from pathlib import Path

from PySide6.QtCore import QPoint, QSize, QThreadPool
from PySide6.QtGui import (
    QCloseEvent,
    QKeySequence,
    QMouseEvent,
    QShortcut,
    Qt,
)
from PySide6.QtWidgets import QFileDialog, QMainWindow, QToolBar

from tools.asm_ide.asm_file_tree_view import AsmFileTreeView
from tools.asm_ide.global_search_popup import GlobalSearchPopup
from tools.asm_ide.menu_toolbar import MenuToolbar
from tools.asm_ide.parsing_progress_dialog import ParsingProgressDialog
from tools.asm_ide.reference_finder import ReferenceFinder
from tools.asm_ide.tab_widget import TabWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ASMB3 IDE")
        self.setMouseTracking(True)

        self._search_index_threads = QThreadPool()
        self._search_index_threads.setMaxThreadCount(1)

        self._global_search_widget: GlobalSearchPopup | None = None

        self._tab_widget = TabWidget(self)
        self._tab_widget.contents_changed.connect(self._update_search_index)
        self._tab_widget.redirect_clicked.connect(self.follow_redirect)

        if not self._on_open():
            quit()

        self.setWindowTitle(f"ASMB3 IDE - {self._root_path}")

        self._reference_finder = ReferenceFinder(self._root_path)

        ParsingProgressDialog(self._reference_finder)

        self._tab_widget.reference_finder = self._reference_finder

        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_PageUp), self, self._tab_widget.to_previous_tab)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_PageDown), self, self._tab_widget.to_next_tab)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S), self, self._tab_widget.save_current_file)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F), self, self._tab_widget.focus_search_bar)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_F), self, self._start_global_search)

        self.setCentralWidget(self._tab_widget)

        self._set_up_toolbars()
        self._set_up_menubar()

        self._tab_widget.open_or_switch_file(self._root_path / "smb3.asm")

    def _set_up_toolbars(self):
        self._set_up_menu_toolbar()
        toolbar = QToolBar()
        toolbar.setMovable(False)

        file_tree_view = AsmFileTreeView(self._root_path)
        file_tree_view.file_clicked.connect(self._tab_widget.open_or_switch_file)

        toolbar.addWidget(file_tree_view)

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    def _set_up_menu_toolbar(self):
        toolbar = MenuToolbar(self)

        self._tab_widget.document_modified.connect(toolbar.update_save_status)
        self._tab_widget.text_position_clicked.connect(toolbar.push_position)

        toolbar.save_current_file_action.triggered.connect(self._tab_widget.save_current_file)
        toolbar.save_all_files_action.triggered.connect(self._tab_widget.save_all_files)

        toolbar.undo_action.triggered.connect(self._tab_widget.on_undo)
        toolbar.redo_action.triggered.connect(self._tab_widget.on_redo)

        self._tab_widget.undo_redo_changed.connect(toolbar.update_undo_redo_buttons)

        toolbar.position_change_requested.connect(self._move_to_position)

        QShortcut(QKeySequence(Qt.Modifier.ALT | Qt.Key.Key_Right), self, toolbar.go_forward_action.trigger)
        QShortcut(QKeySequence(Qt.Modifier.ALT | Qt.Key.Key_Left), self, toolbar.go_back_action.trigger)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self._menu_toolbar = toolbar

    def _set_up_menubar(self):
        self.menubar = self.menuBar()

        self.file_menu = self.menubar.addMenu("File")
        load_disassembly_action = self.file_menu.addAction("Load Disassembly")
        load_disassembly_action.triggered.connect(self._on_open)

        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def follow_redirect(self, relative_file_path: Path, line_no: int):
        current_code_area = self._tab_widget.currentWidget()

        if current_code_area is None:
            return

        self._move_to_line(relative_file_path, line_no)

        self._menu_toolbar.push_position(
            self._root_path / relative_file_path, current_code_area.textCursor().position()
        )

    def _move_to_line(self, relative_file_path: Path, line_no: int):
        self._tab_widget.open_or_switch_file(self._root_path / relative_file_path)
        self._tab_widget.scroll_to_line(line_no)

    def _move_to_position(self, abs_path: Path, block_index: int):
        self._tab_widget.open_or_switch_file(abs_path)
        self._tab_widget.scroll_to_position(block_index)

    def sizeHint(self):
        return QSize(1800, 1600)

    @property
    def prg_files(self) -> list[Path]:
        prg_dir = self._root_path / "PRG"

        return sorted(prg_dir.glob("prg[0-9]*.asm"))

    def _start_global_search(self):
        current_code_area = self._tab_widget.currentWidget()

        if current_code_area is None:
            return

        search_term = current_code_area.textCursor().selectedText()

        data_by_file = self._get_asm_with_local_copies()

        self._global_search_widget = GlobalSearchPopup(current_code_area, search_term, data_by_file)
        self._global_search_widget.search_result_clicked.connect(self.follow_redirect)

        self._global_search_widget.setMaximumSize(
            current_code_area.size() - QSize(40 + current_code_area.viewportMargins().left(), 40)
        )

        pos_in_self = QPoint(current_code_area.viewportMargins().left(), 0)
        pos_in_self += QPoint(20, 20)

        self._global_search_widget.move(pos_in_self)

        self._global_search_widget.show()

    def _update_search_index(self, path_of_changed_file: Path):
        if self._tab_widget.reference_finder is None:
            return

        local_copies = self._get_asm_with_local_copies()

        # todo: update this method, since local copies just has data for all files now
        self._search_index_threads.start(
            self._tab_widget.reference_finder.run_with_local_copies(local_copies, path_of_changed_file)
        )

    def _get_asm_with_local_copies(self):
        asm: dict[Path, str] = dict()

        for asm_path in [self._root_path / "smb3.asm"] + self.prg_files:
            if asm_path in self._tab_widget.tab_index_to_path:
                tab_index = self._tab_widget.tab_index_to_path.index(asm_path)

                code_area = self._tab_widget.widget(tab_index)

                if code_area is None:
                    continue

                asm[asm_path.relative_to(self._root_path)] = code_area.text_document.toPlainText()

            else:
                asm[asm_path.relative_to(self._root_path)] = asm_path.read_text()

        return asm

    def _on_open(self):
        if self._tab_widget and not self._tab_widget.ask_to_quit_all_tabs_without_saving():
            return False

        path = self._get_disassembly_root()

        if path is None:
            return False

        self._root_path = path

        # todo: make the loading make sense chronologically
        if self._tab_widget:
            self._tab_widget.clear()

            if self._tab_widget.reference_finder:
                self._tab_widget.reference_finder.root_path = self._root_path
                ParsingProgressDialog(self._tab_widget.reference_finder)

                self._tab_widget.open_or_switch_file(self._root_path / "smb3.asm")

        # todo only parse the PRG files mentioned in smb3.asm
        return True

    def _get_disassembly_root(self) -> Path | None:
        dis_asm_folder = QFileDialog.getExistingDirectory(self, "Select Disassembly Directory")

        dis_asm_root_path = Path(dis_asm_folder)

        if not dis_asm_root_path.is_dir() or not (dis_asm_root_path / "smb3.asm").exists():
            return None

        return dis_asm_root_path

    def mousePressEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.ForwardButton:
            self._menu_toolbar.go_forward_action.trigger()

        elif event.buttons() & Qt.MouseButton.BackButton:
            self._menu_toolbar.go_back_action.trigger()

        return super().mousePressEvent(event)

    def closeEvent(self, event: QCloseEvent):
        if not self._tab_widget.ask_to_quit_all_tabs_without_saving():
            return event.ignore()

        return super().closeEvent(event)
