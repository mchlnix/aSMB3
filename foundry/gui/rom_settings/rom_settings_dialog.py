from PySide6.QtGui import QUndoStack

from foundry.gui.CustomDialog import CustomDialog
from foundry.gui.rom_settings.managed_levels_mixin import ManagedLevelsMixin


class RomSettingsDialog(ManagedLevelsMixin, CustomDialog):
    def __init__(self, parent):
        super(RomSettingsDialog, self).__init__(parent)

        self.setWindowTitle("ROM Settings")

        self.update()

    @property
    def undo_stack(self) -> QUndoStack:
        return self.parent().window().findChild(QUndoStack, "undo_stack")

    def update(self):
        super(RomSettingsDialog, self).update()

    def closeEvent(self, event):
        super(RomSettingsDialog, self).closeEvent(event)
