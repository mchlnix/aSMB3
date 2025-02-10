import typing
from math import floor, log10

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPaintEvent, Qt
from PySide6.QtWidgets import (
    QWidget,
)

if typing.TYPE_CHECKING:
    from tools.asm_ide.code_area import CodeArea


_LINE_NO_COLOR = QColor.fromRgb(0x2C91AF)


class LineNumberArea(QWidget):
    MARGIN_LEFT = 10
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

        # weird bug, when there are no tabs, you open one, the QPaintEvent rects don't grow with the widget. so force it
        self.resize(self.sizeHint())

    @property
    def no_of_digits(self):
        line_count = self.editor.document().lineCount()
        digits_in_last_line_no = floor(log10(line_count) + 1)

        return digits_in_last_line_no

    def sizeHint(self):
        size = QSize(self.MARGIN_LEFT + self._line_no_width + self.MARGIN_RIGHT, self.editor.maximumSize().height())
        return size

    def paintEvent(self, event: QPaintEvent):
        self.paint_area(event)

    def paint_area(self, _event: QPaintEvent):
        painter = QPainter(self)
        painter.setFont(self.editor.document().defaultFont())
        painter.setPen(_LINE_NO_COLOR)

        block = self.editor.firstVisibleBlock()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top() + 1
        bottom = top + self.editor.blockBoundingRect(block).height()

        rect = QRect(self.MARGIN_LEFT, top, self._line_no_width, bottom)

        while block.isValid() and block.isVisible():
            line_no_str = str(block.blockNumber() + 1)

            painter.drawText(rect, Qt.AlignmentFlag.AlignBaseline | Qt.AlignmentFlag.AlignRight, line_no_str)

            rect.adjust(0, self._line_no_height + 1, 0, self._line_no_height + 1)

            block = block.next()

        painter.setPen(QColor(150, 150, 150))
        painter.drawLine(QPoint(self.sizeHint().width() - 1, 0), QPoint(self.sizeHint().width() - 1, self.height()))

        painter.end()

    def wheelEvent(self, event):
        # sends the wheel event on the line number area to the editor, making it appear as if both scroll together
        self.editor.wheelEvent(event)
