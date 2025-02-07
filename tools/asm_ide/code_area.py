from PySide6.QtGui import QFont, QTextBlock, QTextCursor, QTextDocument
from PySide6.QtWidgets import QTextEdit

from foundry.data_source.assembly_parser import AssemblyParser
from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter


class CodeArea(QTextEdit):
    def __init__(self, parent, assembly_parser: AssemblyParser):
        super(CodeArea, self).__init__(parent)

        self._assembly_parser = assembly_parser

        self.text_document = QTextDocument()
        self.setDocument(self.text_document)

        self.syntax_highlighter = AsmSyntaxHighlighter()
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

        if self.last_block is not None:
            self.syntax_highlighter.rehighlightBlock(self.last_block)
            self.last_block = None

        if word in self._assembly_parser._const_lut:
            self.last_word = word

            self.setToolTip(f"{word} = {self._assembly_parser._const_lut[word]}")
            self.syntax_highlighter.const_under_cursor = word

            self.last_block = text_cursor.block()
            self.syntax_highlighter.rehighlightBlock(self.last_block)

        else:
            self.setToolTip(None)
