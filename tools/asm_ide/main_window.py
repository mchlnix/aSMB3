from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMainWindow

from tools.asm_ide.code_area import CodeArea


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ASM IDE")

        self._set_up_menubar()

        self.text_area = CodeArea(self)

        self.setCentralWidget(self.text_area)

        self._load_disasm_file(Path("/home/michael/Gits/smb3"))

    def _set_up_menubar(self):
        self.menubar = self.menuBar()

        self.file_menu = self.menubar.addMenu("File")
        load_disasm_action = self.file_menu.addAction("Load Disassembly")
        load_disasm_action.triggered.connect(self._get_disasm_folder)

        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _get_disasm_folder(self):
        dis_asm_folder = QFileDialog.getExistingDirectory(self, "Select Disassembly Directory")

        dis_asm_root_path = Path(dis_asm_folder)
        if not dis_asm_root_path.is_dir():
            return

    def _load_disasm_file(self, path: Path) -> None:
        self.text_area.text_document.setPlainText((path / "smb3.asm").read_text())
