import typing
from math import floor, log10

from PySide6.QtCore import QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFontMetrics, QMouseEvent, QPainter, QPaintEvent, Qt
from PySide6.QtWidgets import (
    QWidget,
)

if typing.TYPE_CHECKING:
    from tools.asm_ide.code_area import CodeArea


_LINE_NO_COLOR = QColor.fromRgb(0x2C91AF)


class LineNumberArea(QWidget):
    MARGIN_LEFT = 10
    MARGIN_RIGHT = 10

    line_number_highlighted = Signal(list)

    def __init__(self, editor: "CodeArea"):
        super().__init__(editor)

        self.editor = editor

        self._line_no_width = self._line_no_height = 1

        self.lines_to_highlight: list[int] = []

    def update_text_measurements(self):
        font_metrics = QFontMetrics(self.editor.document().defaultFont())
        self._line_no_width = font_metrics.horizontalAdvance(self.no_of_digits * "9")
        self._line_no_height = font_metrics.lineSpacing()

        viewport_margins = self.editor.viewportMargins()
        viewport_margins.setLeft(self.sizeHint().width())
        self.editor.setViewportMargins(viewport_margins)

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

    def react_to_editor(self, _, scrolled_by: int):
        if scrolled_by != 0:
            self.repaint()

    def paintEvent(self, event: QPaintEvent):
        self.paint_area()

    def paint_area(self):
        painter = QPainter(self)
        painter.setFont(self.editor.document().defaultFont())
        painter.setPen(_LINE_NO_COLOR)

        block = self.editor.firstVisibleBlock()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top() + 1
        bottom = top + self.editor.blockBoundingRect(block).height()

        rect = QRect(self.MARGIN_LEFT, top, self._line_no_width, bottom)

        while block.isValid() and block.isVisible():
            line_number = block.blockNumber() + 1
            line_no_str = str(line_number)

            if line_number in self.lines_to_highlight:
                painter.save()

                painter.setPen(QColor(255, 255, 255))
                painter.setBrush(_LINE_NO_COLOR)

                painter.fillRect(rect, painter.brush())
                painter.drawText(rect, Qt.AlignmentFlag.AlignBaseline | Qt.AlignmentFlag.AlignRight, line_no_str)

                painter.restore()

            else:
                painter.drawText(rect, Qt.AlignmentFlag.AlignBaseline | Qt.AlignmentFlag.AlignRight, line_no_str)

            rect.adjust(0, self._line_no_height + 1, 0, self._line_no_height + 1)

            block = block.next()

        painter.setPen(QColor(150, 150, 150))
        painter.drawLine(QPoint(self.sizeHint().width() - 1, 0), QPoint(self.sizeHint().width() - 1, self.height()))

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        clicked_line_number = self._line_number_at(event.pos())

        if clicked_line_number == -1:
            return super().mousePressEvent(event)

        if clicked_line_number in self.lines_to_highlight:
            self.lines_to_highlight.remove(clicked_line_number)
        else:
            self.lines_to_highlight.append(clicked_line_number)

        self.line_number_highlighted.emit(self.lines_to_highlight)

        self.repaint()

        return super().mousePressEvent(event)

    def _line_number_at(self, pos: QPoint):
        block = self.editor.firstVisibleBlock()

        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top() + 1
        bottom = top + self.editor.blockBoundingRect(block).height()
        rect = QRect(0, top, self.width(), bottom)

        clicked_line = block.blockNumber() + 1

        while not rect.contains(pos):
            rect.adjust(0, self._line_no_height + 1, 0, self._line_no_height + 1)

            clicked_line += 1

            if not self.visibleRegion().contains(rect.topLeft()):
                clicked_line = -1
                break

        return clicked_line

    def wheelEvent(self, event):
        # sends the wheel event on the line number area to the editor, making it appear as if both scroll together
        self.editor.wheelEvent(event)
