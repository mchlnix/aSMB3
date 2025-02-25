import shutil
import subprocess
from pathlib import Path
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory

from PySide6.QtCore import QPoint, QSize, QThreadPool
from PySide6.QtGui import (
    QCloseEvent,
    QKeySequence,
    QMouseEvent,
    QShortcut,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QToolBar,
)

from tools.asm_ide.asm_file_tree_view import AsmFileTreeView
from tools.asm_ide.global_search_popup import GlobalSearchPopup
from tools.asm_ide.menu_toolbar import MenuToolbar
from tools.asm_ide.parsing_progress_dialog import ParsingProgressDialog
from tools.asm_ide.reference_finder import ReferenceFinder
from tools.asm_ide.settings import SettingKeys, Settings
from tools.asm_ide.settings_dialog import SettingsDialog
from tools.asm_ide.tab_widget import TabWidget


class MainWindow(QMainWindow):
    def __init__(self, root_path: Path | None = None):
        super().__init__()

        self.setWindowTitle("ASMB3 IDE")
        self.setMouseTracking(True)

        self._search_index_threads = QThreadPool()
        self._search_index_threads.setMaxThreadCount(1)

        self._global_search_widget: GlobalSearchPopup | None = None

        self._reference_finder = ReferenceFinder()

        self._tab_widget = TabWidget(self, self._reference_finder)
        self._tab_widget.contents_changed.connect(self._update_search_index)
        self._tab_widget.redirect_clicked.connect(self.follow_redirect)

        if not self._on_open(path=root_path):
            QApplication.quit()

        self.setWindowTitle(f"ASMB3 IDE - {self._root_path}")

        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_PageUp), self, self._tab_widget.to_previous_tab)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_PageDown), self, self._tab_widget.to_next_tab)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S), self, self._tab_widget.save_current_file)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F), self, self._tab_widget.focus_search_bar)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_F), self, self._start_global_search)

        self.setCentralWidget(self._tab_widget)

        self._set_up_toolbars()
        self._set_up_menubar()

        self._tab_widget.open_or_switch_file(self._root_path / "smb3.asm")

        if Settings().value(SettingKeys.APP_START_MAXIMIZED):
            self.showMaximized()

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

        toolbar.assemble_rom_action.triggered.connect(self._assemble_rom)

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

        settings_action = self.file_menu.addAction("Settings")
        settings_action.triggered.connect(self._on_settings)

        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _on_settings(self):
        settings_dialog = SettingsDialog(self)

        settings_dialog.exec()

        self._tab_widget.update_from_settings()

    def _assemble_rom(self):
        old_cursor = self.cursor()
        self.setCursor(Qt.CursorShape.BusyCursor)

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # copy all necessary files into the temp directory
            self._mirror_root_dir_to_temp_dir(temp_path)

            # copy currently open files
            self._write_modified_source_into_temp_dir(temp_path)

            # call the compiler and capture it's output
            try:
                subprocess.run(
                    Settings().value(SettingKeys.ASSEMBLY_COMMAND),
                    cwd=temp_path,
                    shell=True,
                    check=True,
                    capture_output=True,
                )
            except CalledProcessError as cpe:
                QMessageBox.critical(
                    self, "Assembling the code failed", f"{cpe.stderr.decode()}\n{cpe.stdout.decode()}"
                )
            except Exception as ex:
                QMessageBox.critical(self, "Assembling the code failed", str(ex))
            else:
                # copy back the compiled ROM
                shutil.copy((temp_path / "smb3.nes"), self._root_path / "smb3.nes")

                if Settings().value(SettingKeys.ASSEMBLY_NOTIFY_SUCCESS):
                    QMessageBox.information(self, "Assembling finished", "Assembly was successful")

        self.setCursor(old_cursor)

    def _mirror_root_dir_to_temp_dir(self, temp_path):
        for abs_path in self._root_path.iterdir():
            rel_path = abs_path.relative_to(self._root_path)
            if abs_path.is_file():
                shutil.copy(self._root_path / rel_path, temp_path / rel_path)

            elif abs_path.is_dir():
                shutil.copytree(self._root_path / rel_path, temp_path / rel_path)

    def _write_modified_source_into_temp_dir(self, temp_path):
        local_copies = self._get_asm_with_local_copies()

        for rel_file_path, text in local_copies.items():
            (temp_path / rel_file_path).write_text(text)

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

        offset_side = offset_top = 20

        search_term = current_code_area.textCursor().selectedText()

        data_by_file = self._get_asm_with_local_copies()

        self._global_search_widget = GlobalSearchPopup(current_code_area, search_term, data_by_file)
        self._global_search_widget.search_result_clicked.connect(self.follow_redirect)

        self._global_search_widget.setMaximumSize(
            current_code_area.size()
            - QSize(current_code_area.viewportMargins().left() + offset_side * 2, offset_top * 2)
        )

        pos_in_self = QPoint(current_code_area.viewportMargins().left() + offset_side, offset_top)

        self._global_search_widget.move(pos_in_self)

        self._global_search_widget.show()

    def _update_search_index(self, path_of_changed_file: Path):
        parse_call = self._get_populated_parse_call(path_of_changed_file)

        self._search_index_threads.start(parse_call)

    def _get_populated_parse_call(self, path_of_changed_file: Path | None):
        local_copies = self._get_asm_with_local_copies()

        if path_of_changed_file is not None:
            path_of_changed_file = path_of_changed_file.relative_to(self._root_path)

        return self._tab_widget.reference_finder.run_with_local_copies(local_copies, path_of_changed_file)

    def _get_asm_with_local_copies(self):
        """
        Returns a dictionary whose keys are relative Paths to the PRG and smb3.asm file and the values are the current
        contents of these files.
        Either from disk, or from the open code area.
        """
        # todo only parse the PRG files mentioned in smb3.asm?
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

    def _on_open(self, *, path: Path | None = None):
        if self._tab_widget and not self._tab_widget.ask_to_quit_all_tabs_without_saving():
            return False

        if path is None:
            path = self._get_disassembly_root()

        if path is None or not self._root_path_is_valid(path):
            return False

        self._root_path = path

        self._tab_widget.clear()

        self._parse_with_progress_dialog()

        self._tab_widget.open_or_switch_file(self._root_path / "smb3.asm")

        return True

    @staticmethod
    def _root_path_is_valid(root_path: Path):
        if not (root_path / "smb3.asm").exists():
            QMessageBox.critical(
                None, "Invalid Disassembly Directory", "The directory you selected did not contain an 'smb3.asm' file."
            )
            return False

        return True

    def _parse_with_progress_dialog(self):
        parse_call = self._get_populated_parse_call(None)
        progress_dialog = ParsingProgressDialog(parse_call)

        self._reference_finder.signals.maximum_found.connect(progress_dialog.setMaximum)
        self._reference_finder.signals.progress_made.connect(progress_dialog.update_text)

        progress_dialog.start()

    def _get_disassembly_root(self) -> Path | None:
        dis_asm_folder = QFileDialog.getExistingDirectory(self, "Select Disassembly Directory")

        if not dis_asm_folder:
            return None

        return Path(dis_asm_folder)

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
