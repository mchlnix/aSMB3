from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QFileDialog, QMainWindow, QToolBar

from foundry import icon
from foundry.data_source.assembly_parser import AssemblyParser
from foundry.gui.FoundryMainWindow import TOOLBAR_ICON_SIZE
from tools.asm_ide.asm_file_tree_view import AsmFileTreeView
from tools.asm_ide.parsing_progress_dialog import ParsingProgressDialog
from tools.asm_ide.tab_widget import TabWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ASM IDE")

        # remove this when shipping
        self._root_path = Path("/home/michael/Gits/smb3")
        # self._get_disasm_folder()

        assembly_parser = AssemblyParser(self._root_path)
        parse_call = assembly_parser.parse()

        self._progress_dialog = ParsingProgressDialog(None, parse_call)

        self._central_widget = TabWidget(self, assembly_parser)
        self.setCentralWidget(self._central_widget)

        self._set_up_toolbars()
        self._set_up_menubar()

        self._central_widget.open_or_switch_file(self._root_path / "smb3.asm")

    def _set_up_toolbars(self):
        self._set_up_menu_toolbar()
        toolbar = QToolBar()
        toolbar.setMovable(False)

        file_tree_view = AsmFileTreeView(str(self._root_path))
        file_tree_view.file_clicked.connect(self._central_widget.open_or_switch_file)

        toolbar.addWidget(file_tree_view)

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    def _set_up_menu_toolbar(self):
        toolbar = QToolBar()
        toolbar.setIconSize(TOOLBAR_ICON_SIZE)
        toolbar.setMovable(False)

        save_action = toolbar.addAction("Save ROM")
        save_action.setIcon(icon("save.svg"))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _set_up_menubar(self):
        self.menubar = self.menuBar()

        self.file_menu = self.menubar.addMenu("File")
        load_disasm_action = self.file_menu.addAction("Load Disassembly")
        load_disasm_action.triggered.connect(self._get_disasm_folder)

        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def sizeHint(self):
        return QSize(1800, 1600)

    def _get_disasm_folder(self):
        dis_asm_folder = QFileDialog.getExistingDirectory(self, "Select Disassembly Directory")

        dis_asm_root_path = Path(dis_asm_folder)
        if not dis_asm_root_path.is_dir():
            return
