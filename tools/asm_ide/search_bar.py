from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QWidget

if TYPE_CHECKING:
    from tools.asm_ide.code_area import CodeArea


class SearchBar(QWidget):
    text_changed = Signal()
    next_match = Signal(int)
    settings_changed = Signal()

    def __init__(self, editor: "CodeArea"):
        super().__init__(editor)

        self.setAutoFillBackground(True)

        self._editor = editor
        self._layout = QHBoxLayout(self)

        self._search_input = QLineEdit()
        self._search_input.textChanged.connect(lambda _: self.text_changed.emit())

        self._highlight_all_checkbox = QCheckBox("Highlight All")
        self._highlight_all_checkbox.stateChanged.connect(lambda _: self.settings_changed.emit())

        self.layout().addWidget(self._search_input)
        self.layout().addWidget(self._highlight_all_checkbox)

        self.update_position()

    @property
    def should_highlight_all_matches(self):
        return self._highlight_all_checkbox.isChecked()

    @property
    def search_term(self):
        return self._search_input.text()

    def update_position(self):
        x_position = self._editor.width() - self.width()
        y_position = self._editor.height() - self.height()

        if self._editor.verticalScrollBar().isVisible():
            x_position -= self._editor.verticalScrollBar().width()

        if self._editor.horizontalScrollBar().isVisible():
            y_position -= self._editor.horizontalScrollBar().height()

        self.move(QPoint(x_position, y_position))

    def setFocus(self):
        self._search_input.selectAll()
        self._search_input.setFocus()

    def keyPressEvent(self, event):
        # pressing the Enter key for some reason also gets sent to the CodeArea, so accept the event to prevent this
        if event.key() in [Qt.Key.Key_Enter, Qt.Key.Key_Return]:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # todo use constants
                self.next_match.emit(-1)
            else:
                self.next_match.emit(1)

        elif event.key() == Qt.Key.Key_Escape:
            self._editor.setFocus()

        # Pressing Enter, Tab and other keys can leak into the main window.
        # Presumably because QLineEdit is not supposed to do anything with them and send them to its parent to handle.
        # So accept all keypress events regardless of what they are.
        event.accept()
