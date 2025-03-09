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

from tools.asm_ide.application_settings import AppSettingKeys, AppSettings
from tools.asm_ide.asm_file_tree_view import AsmFileTreeView
from tools.asm_ide.global_search_popup import GlobalSearchPopup
from tools.asm_ide.menu_toolbar import MenuToolbar
from tools.asm_ide.parsing_progress_dialog import ParsingProgressDialog
from tools.asm_ide.project import Project
from tools.asm_ide.reference_finder import ReferenceFinder
from tools.asm_ide.settings_dialog import SettingsDialog
from tools.asm_ide.tab_widget import TabWidget


def _get_main_assembly_file() -> Path | None:
    main_assembly_file = QFileDialog.getOpenFileName(None, "Select Main Assembly File")

    if not main_assembly_file:
        return None

    return Path(main_assembly_file)


class MainWindow(QMainWindow):
    def __init__(self, root_path: Path | None = None):
        super().__init__()

        self.setMouseTracking(True)

        self._search_index_threads = QThreadPool()
        self._search_index_threads.setMaxThreadCount(1)

        self._global_search_widget: GlobalSearchPopup | None = None

        self._reference_finder = ReferenceFinder()

        self._tab_widget = TabWidget(self, self._reference_finder)
        self._tab_widget.contents_changed.connect(self._update_search_index)
        self._tab_widget.redirect_clicked.connect(self.follow_redirect)

        self._project = Project(self._tab_widget)

        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_PageUp), self, self._tab_widget.to_previous_tab)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_PageDown), self, self._tab_widget.to_next_tab)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S), self, self._tab_widget.save_current_file)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_F), self, self._tab_widget.focus_search_bar)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_F), self, self._start_global_search)

        self.setCentralWidget(self._tab_widget)

        self._set_up_toolbars()
        self._set_up_menubar()

        if AppSettings().value(AppSettingKeys.APP_START_MAXIMIZED):
            self.showMaximized()

        if not self._on_open(path=root_path):
            QApplication.quit()

    def _set_up_toolbars(self):
        self._set_up_menu_toolbar()
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self._file_tree_view = AsmFileTreeView()
        self._file_tree_view.file_clicked.connect(self._tab_widget.open_or_switch_file)

        toolbar.addWidget(self._file_tree_view)

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

        toolbar.position_change_requested.connect(self._tab_widget.move_to_position)

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
        settings_dialog = SettingsDialog(self, self._main_file_path)

        settings_dialog.exec()

        self._tab_widget.update_from_settings()

    @property
    def _root_path(self):
        return self._main_file_path.parent

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
                assemble_command = AppSettings().value(AppSettingKeys.ASSEMBLY_COMMAND)

                if not isinstance(assemble_command, str):
                    QMessageBox.critical(
                        self, "Error", "Assemble Command could not be found. Set it in the Settings Menu."
                    )
                    return

                assemble_command = assemble_command.replace("%f", self._main_file_path.name)

                subprocess.run(assemble_command, cwd=temp_path, shell=True, check=True, capture_output=True)

            except CalledProcessError as cpe:
                QMessageBox.critical(
                    self, "Assembling the code failed", f"{cpe.stderr.decode()}\n{cpe.stdout.decode()}"
                )
            except Exception as ex:
                QMessageBox.critical(self, "Assembling the code failed", str(ex))
            else:
                # copy back the compiled ROM
                temp_rom_path = temp_path / "smb3.nes"

                if not temp_rom_path.exists():
                    QMessageBox.critical(
                        self, "ROM not found", "Assembly seems to have succeeded, but no ROM file was found."
                    )

                else:
                    shutil.copy(temp_rom_path, self._root_path / "smb3.nes")

                    if AppSettings().value(AppSettingKeys.ASSEMBLY_NOTIFY_SUCCESS):
                        QMessageBox.information(
                            self, "Assembling finished", "Assembly was successful", QMessageBox.StandardButton.Ok
                        )

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

    def sizeHint(self):
        return QSize(1800, 1600)

    def _start_global_search(self):
        current_code_area = self._tab_widget.currentWidget()

        if current_code_area is None:
            return

        offset_side = offset_top = 20

        search_term = current_code_area.textCursor().selectedText()

        data_by_file = self._get_asm_with_local_copies(all_files=True)

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
        if self._search_index_threads.activeThreadCount() > 0:
            # don't allow parallel executions
            return

        parse_call = self._get_populated_parse_call(path_of_changed_file)

        self._search_index_threads.start(parse_call)

    def _get_populated_parse_call(self, path_of_changed_file: Path | None):
        local_copies = self._get_asm_with_local_copies()

        if path_of_changed_file is not None:
            path_of_changed_file = path_of_changed_file.relative_to(self._root_path)

        return self._tab_widget.reference_finder.run_with_local_copies(
            self._main_file_path, local_copies, path_of_changed_file
        )

    def _get_asm_with_local_copies(self, all_files=False):
        """
        Returns a dictionary whose keys are relative Paths to the referenced .asm files, and the values are the current
        contents of these files.

        If "all_files" is False, the dictionary contains paths to the currently open files and their (perhaps modified)
        content.
        If "all_files" is True, the dictionary also includes all the other files with their contents read from the disk.
        """
        asm: dict[Path, str] = dict()

        if all_files:
            for asm_path in self._reference_finder.found_files:
                asm[asm_path.relative_to(self._root_path)] = asm_path.read_text()

        for tab_index, asm_path in enumerate(self._tab_widget.tab_index_to_path):
            code_area = self._tab_widget.widget(tab_index)

            if code_area is None:
                continue

            if not code_area.text_document.isModified():
                continue

            asm[asm_path.relative_to(self._root_path)] = code_area.text_document.toPlainText()

        return asm

    def _on_open(self, *, path: Path | None = None):
        if self._tab_widget and not self._tab_widget.ask_to_quit_all_tabs_without_saving():
            return False

        if path is None:
            path = _get_main_assembly_file()

        if path is None:
            return

        self._project.close()

        self._main_file_path = path

        self._parse_with_progress_dialog()

        self._file_tree_view.set_root_path(self._root_path)
        self.setWindowTitle(f"ASMB3 IDE - {self._main_file_path}")

        self._project.open(self._main_file_path)

        return True

    def _parse_with_progress_dialog(self):
        parse_call = self._get_populated_parse_call(None)
        progress_dialog = ParsingProgressDialog(parse_call)

        self._reference_finder.signals.maximum_found.connect(progress_dialog.setMaximum)
        self._reference_finder.signals.progress_made.connect(progress_dialog.update_text)

        progress_dialog.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.ForwardButton:
            self._menu_toolbar.go_forward_action.trigger()

        elif event.buttons() & Qt.MouseButton.BackButton:
            self._menu_toolbar.go_back_action.trigger()

        return super().mousePressEvent(event)

    def closeEvent(self, event: QCloseEvent):
        if not self._tab_widget.ask_to_quit_all_tabs_without_saving():
            return event.ignore()

        self._project.close()

        return super().closeEvent(event)
