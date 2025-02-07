from PySide6.QtGui import QFont, QTextBlock, QTextCursor, QTextDocument
from PySide6.QtWidgets import QTextEdit, QToolTip

from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter
from tools.asm_ide.named_value_finder import NamedValueFinder


class CodeArea(QTextEdit):
    def __init__(self, parent, named_value_finder: NamedValueFinder):
        super(CodeArea, self).__init__(parent)

        self._named_value_finder = named_value_finder

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
