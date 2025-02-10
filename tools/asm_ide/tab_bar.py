from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTabBar


class TabBar(QTabBar):
    middle_click_on = Signal(int)

    def __init__(self, parent=None):
        super(TabBar, self).__init__(parent)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            tab_index = self.tabAt(event.pos())

            if 0 <= tab_index <= self.count():
                self.middle_click_on.emit(tab_index)

                return super().mouseReleaseEvent(event)

        return super().mouseReleaseEvent(event)
