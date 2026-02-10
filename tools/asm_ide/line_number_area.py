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
_ERROR_BG_COLOR = QColor.fromRgb(0xFF0000)


class LineNumberArea(QWidget):
    MARGIN_LEFT = 10
    MARGIN_RIGHT = 10

    line_number_highlighted = Signal(list)

    def __init__(self, editor: "CodeArea"):
        super().__init__(editor)

        self.editor = editor

        self._line_no_width = self._line_no_height = 1

        self.lines_to_highlight: list[int] = []
        self.error_line_no: int = -1

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

        for line_number in self._lines_to_draw():

            if line_number == self.error_line_no:
                self._draw_error_line_number(painter, rect, line_number)

            elif line_number in self.lines_to_highlight:
                self._draw_highlighted_line_number(painter, rect, line_number)

            else:
                self._draw_line_number(painter, rect, line_number)

            rect.adjust(0, self._line_no_height + 1, 0, self._line_no_height + 1)

        self._draw_error_arrow(painter)

        self._draw_vertical_line(painter)

        painter.end()

    def _draw_error_arrow(self, painter: QPainter):
        visible_line_numbers = self._lines_to_draw()

        if self.error_line_no in visible_line_numbers + [-1]:
            return

        min_no = min(visible_line_numbers)

        painter.save()
        painter.setBrush(QColor(255, 0, 0))

        arrow_width = 15
        arrow_height = 15

        if self.error_line_no < min_no:
            left = QPoint((self.width() - arrow_width) // 2, arrow_height)
            right = QPoint((self.width() + arrow_width) // 2, arrow_height)
            top = QPoint(self.width() // 2, 0)
        else:
            base_y = self.editor.viewport().height()

            if self.editor.horizontalScrollBar().isVisible():
                base_y -= self.editor.horizontalScrollBar().height()

            left = QPoint((self.width() - arrow_width) // 2, base_y - arrow_height)
            right = QPoint((self.width() + arrow_width) // 2, base_y - arrow_height)
            top = QPoint(self.width() // 2, base_y)

        painter.drawPolygon([left, right, top])

        painter.restore()

    def _draw_vertical_line(self, painter):
        painter.setPen(QColor(150, 150, 150))
        painter.drawLine(QPoint(self.sizeHint().width() - 1, 0), QPoint(self.sizeHint().width() - 1, self.height()))

    @staticmethod
    def _draw_line_number(painter, rect, line_number):
        line_no_str = str(line_number)

        painter.drawText(rect, Qt.AlignmentFlag.AlignBaseline | Qt.AlignmentFlag.AlignRight, line_no_str)

    def _draw_error_line_number(self, painter, rect, line_number):
        self._draw_line_number_with_background(painter, rect, line_number, _ERROR_BG_COLOR)

    def _draw_highlighted_line_number(self, painter, rect, line_number):
        self._draw_line_number_with_background(painter, rect, line_number, _LINE_NO_COLOR)

    def _draw_line_number_with_background(self, painter, rect, line_number, bg_color: QColor):
        painter.save()

        painter.setPen(QColor(255, 255, 255))
        painter.setBrush(bg_color)
        painter.fillRect(rect, painter.brush())

        self._draw_line_number(painter, rect, line_number)

        painter.restore()

    def _lines_to_draw(self):
        line_nos: list[int] = []

        block = self.editor.firstVisibleBlock()

        while block.isValid():
            top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top() + 1

            if top > self.editor.viewport().height():
                break

            line_number = block.blockNumber() + 1
            line_nos.append(line_number)

            block = block.next()

        return line_nos

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
