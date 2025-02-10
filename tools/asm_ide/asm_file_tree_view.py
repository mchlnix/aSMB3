from pathlib import Path

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class AsmFileTreeView(QTreeView):
    file_clicked = Signal(Path)

    def __init__(self, root_path: Path, parent=None):
        super(AsmFileTreeView, self).__init__(parent)

        self._root_path = root_path

        file_system_model = QFileSystemModel()

        # only have .asm files clickable, still shows the rest, though
        file_system_model.setNameFilters(["*.asm"])

        self.setModel(file_system_model)

        # hide everything, except the file name
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        self.setColumnHidden(3, True)

        self.setRootIndex(file_system_model.setRootPath(str(self._root_path)))

        prg_index = file_system_model.index(str(self._root_path / "PRG"), 0)
        self.expand(prg_index)

        self.doubleClicked.connect(self.on_file_clicked)

    def on_file_clicked(self, model_index: QModelIndex):
        file_path = self._root_path / self.model().data(model_index, QFileSystemModel.Roles.FilePathRole)

        if not file_path.is_file() or file_path.suffix != ".asm":
            return

        self.file_clicked.emit(file_path)
