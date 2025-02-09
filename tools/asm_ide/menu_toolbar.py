from PySide6.QtWidgets import QToolBar, QToolButton

from foundry import icon
from foundry.gui.FoundryMainWindow import TOOLBAR_ICON_SIZE


class MenuToolbar(QToolBar):
    def __init__(self, parent=None):
        super(MenuToolbar, self).__init__(parent)

        self.setIconSize(TOOLBAR_ICON_SIZE)
        self.setMovable(False)

        self.save_current_file_action = self.addAction("Save Current File")
        self.save_current_file_action.setIcon(icon("save.svg"))

        self._save_button: QToolButton = self.widgetForAction(self.save_current_file_action)
        self._save_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.save_all_files_action = self._save_button.addAction("Save all open files")
        self.save_all_files_action.setIcon(icon("save.svg"))

        self.update_save_status(False, False)

    def update_save_status(self, current_document_is_modified: bool, any_document_is_modified: bool):
        self.save_current_file_action.setEnabled(current_document_is_modified)
        self.save_all_files_action.setEnabled(any_document_is_modified)

        self._save_button.setEnabled(any_document_is_modified)
