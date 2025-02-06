from PySide6.QtGui import QFont, QTextDocument
from PySide6.QtWidgets import QTextEdit

from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter


class CodeArea(QTextEdit):
    def __init__(self, parent=None):
        super(CodeArea, self).__init__(parent)

        self.text_document = QTextDocument()
        self.setDocument(self.text_document)

        self.syntax_highlighter = AsmSyntaxHighlighter()
        self.syntax_highlighter.setDocument(self.text_document)

        self.text_document.setDefaultFont(QFont("Monospace", 14))

    def mouseMoveEvent(self, e):
        print(e.localPos(), self.cursorForPosition(e.pos()).block().text())
