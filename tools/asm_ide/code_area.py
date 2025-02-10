from pathlib import Path

from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPaintEvent,
    Qt,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QPlainTextDocumentLayout,
    QPlainTextEdit,
    QTextEdit,
    QToolTip,
)

from foundry import ctrl_is_pressed
from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter
from tools.asm_ide.line_number_area import LineNumberArea
from tools.asm_ide.named_value_finder import NamedValueFinder


class CodeArea(QPlainTextEdit):
    text_position_clicked = Signal(int)
    """
    :param The block index the cursor was put to.
    """
    redirect_clicked = Signal(Path, int)
    """
    :param Path The relative file path to go to.
    :param int The line number to go to.
    """
    blockCountChanged: SignalInstance(int)
    cursorPositionChanged: SignalInstance()

    def __init__(self, parent, named_value_finder: NamedValueFinder):
        super(CodeArea, self).__init__(parent)

        self._named_value_finder = named_value_finder
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMouseTracking(True)

        self.text_document = QTextDocument()
        self.text_document.setDocumentLayout(QPlainTextDocumentLayout(self.text_document))
        self.setDocument(self.text_document)

        self.syntax_highlighter = AsmSyntaxHighlighter(self, named_value_finder)
        self.syntax_highlighter.setDocument(self.text_document)

        self._font = QFont("Monospace", 14)
        self._font.setBold(True)
        self.text_document.setDefaultFont(self._font)

        self.last_block: QTextBlock | None = None
        self.last_word = ""

        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._line_number_area.update_text_measurements)

        self.cursorPositionChanged.connect(self._highlight_current_number)

    def _highlight_current_number(self):
        current_line_selection = QTextEdit.ExtraSelection()

        line_highlight_format = QTextCharFormat()
        line_highlight_format.setBackground(QBrush(QColor(255, 255, 153)))

        current_line_selection.cursor = self.textCursor()
        current_line_selection.format = line_highlight_format
        current_line_selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        self.setExtraSelections([current_line_selection])

    def paintEvent(self, e: QPaintEvent):
        self._line_number_area.repaint()
        return super().paintEvent(e)

    def mouseMoveEvent(self, e):
        text_cursor = self.cursorForPosition(e.pos())

        text_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = text_cursor.selectedText().strip()

        if word == self.last_word:
            return super().mouseMoveEvent(e)

        # reset potentially old const highlighting
        self.last_word = ""
        self.syntax_highlighter.const_under_cursor = ""
        self.syntax_highlighter.ram_variable_under_cursor = ""
        self.syntax_highlighter.label_under_cursor = ""

        if self.last_block is not None:
            self.syntax_highlighter.rehighlightBlock(self.last_block)
            self.last_block = None

        self._update_tooltip(e, text_cursor, word)

        return super().mouseMoveEvent(e)

    def _update_tooltip(self, e, text_cursor, word):
        word_is_a_constant = word in self._named_value_finder.constants
        word_is_a_ram_variable = word in self._named_value_finder.ram_variables
        word_is_a_label = word in self._named_value_finder.labels

        if not (word_is_a_constant or word_is_a_ram_variable or word_is_a_label):
            self.setToolTip(None)
            return

        self.last_word = word
        tooltip = QToolTip()
        tooltip.setFont(QFont("Monospace", 14))

        if word_is_a_constant:
            name, value, file, line_no = self._named_value_finder.constants[word]
            self.syntax_highlighter.const_under_cursor = word
        elif word_is_a_ram_variable:
            name, value, file, line_no = self._named_value_finder.ram_variables[word]
            self.syntax_highlighter.ram_variable_under_cursor = word
        else:
            name, value, file, line_no = self._named_value_finder.labels[word]
            self.syntax_highlighter.label_under_cursor = word

        tooltip.showText(e.globalPos(), f"{file}+{line_no}: {name} = {value}", self)

        self.last_block = text_cursor.block()
        self.syntax_highlighter.rehighlightBlock(self.last_block)

    def mousePressEvent(self, event: QMouseEvent):
        text_cursor_at_click = self.cursorForPosition(event.pos())

        cursor_pos_changed = text_cursor_at_click.position() != self.textCursor().position()
        navigated_by_mouse = event.buttons() & (Qt.MouseButton.BackButton | Qt.MouseButton.ForwardButton)

        if cursor_pos_changed and not navigated_by_mouse:
            # todo: could be done with signal of QPlainTextEdit
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
            return super().mouseReleaseEvent(e)

        _, _, relative_file_path, line_no = info

        self.redirect_clicked.emit(relative_file_path, line_no)

        return super().mouseReleaseEvent(e)
