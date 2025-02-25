from pathlib import Path

from PySide6.QtCore import QModelIndex, Signal, SignalInstance
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class AsmFileTreeView(QTreeView):
    file_clicked = Signal(Path)

    doubleClicked: SignalInstance

    def __init__(self, parent=None):
        super(AsmFileTreeView, self).__init__(parent)

        self._root_path = Path()

        self.setWindowTitle("File Tree Sidebar")
        self.doubleClicked.connect(self.on_file_clicked)

    def set_root_path(self, root_path: Path):
        self._root_path = root_path

        file_system_model = QFileSystemModel()

        # only have .asm files clickable, still shows the rest, though
        file_system_model.setNameFilters(["*.asm"])

        self.setModel(file_system_model)

        # hide everything, except the file name
        self.setColumnHidden(1, True)  # file size
        self.setColumnHidden(2, True)  # file type
        self.setColumnHidden(3, True)  # modified date

        self.setRootIndex(file_system_model.setRootPath(str(self._root_path)))

        prg_index = file_system_model.index(str(self._root_path / "PRG"), 0)
        self.expand(prg_index)

    def on_file_clicked(self, model_index: QModelIndex):
        file_path = self._root_path / self.model().data(model_index, QFileSystemModel.Roles.FilePathRole)

        if not file_path.is_file() or file_path.suffix != ".asm":
            return

        self.file_clicked.emit(file_path)
