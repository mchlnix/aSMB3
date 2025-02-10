from math import floor, log10
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
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
    QWidget,
)

from foundry import ctrl_is_pressed
from tools.asm_ide.asm_syntax_highlighter import AsmSyntaxHighlighter
from tools.asm_ide.named_value_finder import NamedValueFinder


class LineNumberArea(QWidget):
    MARGIN_RIGHT = 10

    def __init__(self, editor: "CodeArea"):
        super().__init__(editor)

        self.editor = editor

        self._line_no_width = self._line_no_height = 1

    def update_text_measurements(self):
        font_metrics = QFontMetrics(self.editor.document().defaultFont())
        self._line_no_width = font_metrics.horizontalAdvance(self.no_of_digits * "9")
        self._line_no_height = font_metrics.lineSpacing()

        self.editor.setViewportMargins(self.sizeHint().width(), 0, 0, 0)

    @property
    def no_of_digits(self):
        line_count = self.editor.document().lineCount()
        digits_in_last_line_no = floor(log10(line_count) + 1)

        return digits_in_last_line_no

    def sizeHint(self):
        return QSize(self._line_no_width + self.MARGIN_RIGHT, self.editor.maximumSize().height())

    def paintEvent(self, event: QPaintEvent):
        self.paint_area(event)

    def paint_area(self, paint_event: QPaintEvent):
        painter = QPainter(self)
        painter.setFont(self.editor.font)
        painter.setPen(QColor(150, 150, 150))

        block = self.editor.firstVisibleBlock()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top() + 1
        bottom = top + self.editor.blockBoundingRect(block).height()

        rect = QRect(0, top, self._line_no_width, bottom)

        while block.isValid() and block.isVisible():
            line_no_str = str(block.blockNumber() + 1)

            painter.drawText(rect, Qt.AlignmentFlag.AlignBaseline | Qt.AlignmentFlag.AlignRight, line_no_str)

            rect.adjust(0, self._line_no_height + 1, 0, self._line_no_height + 1)

            block = block.next()

        painter.drawLine(QPoint(self.width() - 1, 0), QPoint(self.width() - 1, self.height()))

        painter.end()

    def wheelEvent(self, event):
        # sends the wheel event on the line number area to the editor, making it appear as if both scroll together
        self.editor.wheelEvent(event)


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

        self.font = QFont("Monospace", 14)
        self.text_document.setDefaultFont(self.font)

        self.last_block: QTextBlock | None = None
        self.last_word = ""

        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._line_number_area.update_text_measurements)

        self.cursorPositionChanged.connect(self._highlight_current_number)

    def _highlight_current_number(self):
        current_line_selection = QTextEdit.ExtraSelection()

        line_highligh_format = QTextCharFormat()
        line_highligh_format.setBackground(QBrush(QColor(255, 255, 153)))

        current_line_selection.cursor = self.textCursor()
        current_line_selection.format = line_highligh_format
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
        self.syntax_highlighter.label_under_cursor = ""

        if self.last_block is not None:
            self.syntax_highlighter.rehighlightBlock(self.last_block)
            self.last_block = None

        # todo: dedup
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

        return super().mouseMoveEvent(e)

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
