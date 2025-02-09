from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QKeySequence, QMouseEvent, QShortcut, Qt, QTextCursor
from PySide6.QtWidgets import QFileDialog, QMainWindow, QToolBar

from tools.asm_ide.asm_file_tree_view import AsmFileTreeView
from tools.asm_ide.menu_toolbar import MenuToolbar
from tools.asm_ide.parsing_progress_dialog import ParsingProgressDialog
from tools.asm_ide.tab_widget import TabWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ASM IDE")
        self.setMouseTracking(True)

        # remove this when shipping
        self._root_path = Path("/home/michael/Gits/smb3")
        # self._get_disasm_folder()

        progress_dialog = ParsingProgressDialog(self._root_path)

        self._central_widget = TabWidget(self, progress_dialog.named_value_finder)
        self._central_widget.redirect_clicked.connect(self.follow_redirect)
        self.setCentralWidget(self._central_widget)

        self._set_up_toolbars()
        self._set_up_menubar()

        self._central_widget.open_or_switch_file(self._root_path / "smb3.asm")

    def _set_up_toolbars(self):
        self._set_up_menu_toolbar()
        toolbar = QToolBar()
        toolbar.setMovable(False)

        file_tree_view = AsmFileTreeView(self._root_path)
        file_tree_view.file_clicked.connect(self._central_widget.open_or_switch_file)

        toolbar.addWidget(file_tree_view)

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    def _set_up_menu_toolbar(self):
        toolbar = MenuToolbar(self)

        self._central_widget.document_modified.connect(toolbar.update_save_status)
        self._central_widget.text_position_clicked.connect(toolbar.push_position)

        toolbar.save_current_file_action.triggered.connect(self._central_widget.save_current_file)
        toolbar.save_all_files_action.triggered.connect(self._central_widget.save_all_files)

        toolbar.position_change_requested.connect(self._move_to_position)

        QShortcut(QKeySequence(Qt.Modifier.ALT | Qt.Key.Key_Right), self, toolbar.go_forward_action.trigger)
        QShortcut(QKeySequence(Qt.Modifier.ALT | Qt.Key.Key_Left), self, toolbar.go_back_action.trigger)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self._menu_toolbar = toolbar

    def _set_up_menubar(self):
        self.menubar = self.menuBar()

        self.file_menu = self.menubar.addMenu("File")
        load_disasm_action = self.file_menu.addAction("Load Disassembly")
        load_disasm_action.triggered.connect(self._get_disasm_folder)

        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def follow_redirect(self, relative_file_path: Path, line_no: int):
        print("before redirect")
        self._move_to_line(relative_file_path, line_no)

        text_cursor = self._central_widget.currentWidget().textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.MoveAnchor)
        text_cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, n=line_no - 1)

        print("after redirect")
        self._menu_toolbar.push_position(self._root_path / relative_file_path, text_cursor.position())

    def _move_to_line(self, relative_file_path: Path, line_no: int):
        self._central_widget.open_or_switch_file(self._root_path / relative_file_path)
        self._central_widget.scroll_to_line(line_no)

    def _move_to_position(self, abs_path: Path, block_index: int):
        self._central_widget.open_or_switch_file(abs_path)
        self._central_widget.scroll_to_position(block_index)

    def sizeHint(self):
        return QSize(1800, 1600)

    def _get_disasm_folder(self):
        dis_asm_folder = QFileDialog.getExistingDirectory(self, "Select Disassembly Directory")

        dis_asm_root_path = Path(dis_asm_folder)
        if not dis_asm_root_path.is_dir():
            return

        self._root_path = dis_asm_root_path

        # todo check that there is an smb3 file
        # only parse the PRG files mentioned there

    def mousePressEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.ForwardButton:
            self._menu_toolbar.go_forward_action.trigger()

        elif event.buttons() & Qt.MouseButton.BackButton:
            self._menu_toolbar.go_back_action.trigger()

        return super().mousePressEvent(event)

    def close(self):
        return super().close()
