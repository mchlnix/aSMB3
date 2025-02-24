from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QToolBar, QToolButton

from tools.asm_ide.text_position_stack import TextPositionStack
from tools.asm_ide.util import TOOLBAR_ICON_SIZE, icon


class MenuToolbar(QToolBar):
    position_change_requested = Signal(Path, int)
    """
    :param Path The path of the file to jump to.
    :param int The position in the text to jump to.
    """

    def __init__(self, parent=None):
        super(MenuToolbar, self).__init__("Menu Toolbar", parent)

        self.setIconSize(TOOLBAR_ICON_SIZE)
        self.setMovable(False)

        self._position_stack = TextPositionStack()

        # Save Button
        self.save_current_file_action = self.addAction("Save Current File")
        self.save_current_file_action.setIcon(icon("save.svg"))

        self._save_button: QToolButton = self.widgetForAction(self.save_current_file_action)
        self._save_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.save_all_files_action = self._save_button.addAction("Save all open files")
        self.save_all_files_action.setIcon(icon("save.svg"))

        self.update_save_status(False, False)
        # Save Button End

        self.addSeparator()

        # Undo/Redo Buttons
        self.undo_action = self.addAction("Undo")
        self.undo_action.setIcon(icon("rotate-ccw.svg"))

        self.redo_action = self.addAction("Redo")
        self.redo_action.setIcon(icon("rotate-cw.svg"))

        self.undo_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_Z)
        self.redo_action.setShortcuts(
            [Qt.Modifier.CTRL | Qt.Key.Key_Y, Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_Z]
        )

        self.update_undo_redo_buttons(False, False)
        # Undo/Redo Buttons End

        self.addSeparator()

        # Navigation Buttons
        self.go_back_action = self.addAction("Back")
        self.go_back_action.setIcon(icon("arrow-left.svg"))
        self.go_back_action.triggered.connect(self._go_back)

        self.go_forward_action = self.addAction("Forward")
        self.go_forward_action.setIcon(icon("arrow-right.svg"))
        self.go_forward_action.triggered.connect(self._go_forward)

        self._update_navigation_buttons()
        # Navigation Buttons End

        self.addSeparator()

        self.assemble_rom_action = self.addAction("Assemble ROM")
        self.assemble_rom_action.setIcon(icon("terminal.svg"))

    def update_save_status(self, current_document_is_modified: bool, any_document_is_modified: bool):
        self.save_current_file_action.setEnabled(current_document_is_modified)
        self.save_all_files_action.setEnabled(any_document_is_modified)

        self._save_button.setEnabled(any_document_is_modified)

    def update_undo_redo_buttons(self, undo_available: bool, redo_available: bool):
        self.undo_action.setEnabled(undo_available)
        self.redo_action.setEnabled(redo_available)

    def push_position(self, abs_path: Path, block_index: int):
        self._position_stack.push(abs_path, block_index)

        self._update_navigation_buttons()

    def _go_back(self):
        if self._position_stack.is_at_the_beginning():
            return

        file_path, block_index = self._position_stack.go_back()

        self.position_change_requested.emit(file_path, block_index)

        self._update_navigation_buttons()

    def _go_forward(self):
        if self._position_stack.is_at_the_end():
            return

        file_path, block_index = self._position_stack.go_forward()

        self.position_change_requested.emit(file_path, block_index)

        self._update_navigation_buttons()

    def _update_navigation_buttons(self):
        self.go_back_action.setEnabled(not self._position_stack.is_at_the_beginning())
        self.go_forward_action.setEnabled(not self._position_stack.is_at_the_end())
