from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QMouseEvent, Qt, QTextBlock, QTextCursor, QTextDocument
from PySide6.QtWidgets import QTextEdit, QToolTip

from foundry import ctrl_is_pressed
from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter
from tools.asm_ide.named_value_finder import NamedValueFinder


class CodeArea(QTextEdit):
    text_position_clicked = Signal(int)
    """
    :param The block index the cursor was put to.
    """
    redirect_clicked = Signal(Path, int)
    """
    :param Path The relative file path to go to.
    :param int The line number to go to.
    """

    def __init__(self, parent, named_value_finder: NamedValueFinder):
        super(CodeArea, self).__init__(parent)

        self._named_value_finder = named_value_finder
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        self.text_document = QTextDocument()
        self.setDocument(self.text_document)

        self.syntax_highlighter = AsmSyntaxHighlighter(self, named_value_finder)
        self.syntax_highlighter.setDocument(self.text_document)

        self.text_document.setDefaultFont(QFont("Monospace", 14))

        self.last_block: QTextBlock | None = None
        self.last_word = ""

    def mouseMoveEvent(self, e):
        text_cursor = self.cursorForPosition(e.pos())

        text_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = text_cursor.selectedText().strip()

        if word == self.last_word:
            return

        # reset potentially old const highlighting
        self.last_word = ""
        self.syntax_highlighter.const_under_cursor = ""
        self.syntax_highlighter.label_under_cursor = ""

        if self.last_block is not None:
            self.syntax_highlighter.rehighlightBlock(self.last_block)
            self.last_block = None

        if word in self._named_value_finder.constants:
            self.last_word = word

            name, value, file, line_no = self._named_value_finder.constants[word]

            tooltip = QToolTip()
            tooltip.setFont(QFont("Monospace", 14))

            tooltip.showText(e.globalPos(), f"{file}+{line_no}: {name} = {value}", self)
            self.syntax_highlighter.const_under_cursor = word

            self.last_block = text_cursor.block()
            self.syntax_highlighter.rehighlightBlock(self.last_block)

        elif word in self._named_value_finder.labels:
            self.last_word = word

            name, value, file, line_no = self._named_value_finder.labels[word]

            tooltip = QToolTip()
            tooltip.setFont(QFont("Monospace", 14))

            tooltip.showText(e.globalPos(), f"{file}+{line_no}: {name}: {value}", self)
            self.syntax_highlighter.label_under_cursor = word

            self.last_block = text_cursor.block()
            self.syntax_highlighter.rehighlightBlock(self.last_block)

        else:
            self.setToolTip(None)

    def mousePressEvent(self, event: QMouseEvent):
        text_cursor_at_click = self.cursorForPosition(event.pos())

        cursor_pos_changed = text_cursor_at_click.position() != self.textCursor().position()
        navigated_by_mouse = event.buttons() & (Qt.MouseButton.BackButton | Qt.MouseButton.ForwardButton)

        if cursor_pos_changed and not navigated_by_mouse:
            self.text_position_clicked.emit(text_cursor_at_click.position())

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, e):
        text_cursor = self.cursorForPosition(e.pos())
        text_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = text_cursor.selectedText().strip()

        if word in self._named_value_finder.constants:
            info = self._named_value_finder.constants[word]
        elif word in self._named_value_finder.labels:
            info = self._named_value_finder.labels[word]
        else:
            return super().mouseReleaseEvent(e)

        if not ctrl_is_pressed():
            return

        _, _, relative_file_path, line_no = info

        self.redirect_clicked.emit(relative_file_path, line_no)
