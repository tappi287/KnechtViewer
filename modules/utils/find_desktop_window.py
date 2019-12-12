import sys
from typing import Union

from PySide2.QtCore import QObject, QEvent, QPoint, QTimer, Qt
from PySide2.QtGui import QMouseEvent, QCursor, QPainter, QPen, QPaintEvent
from PySide2.QtWidgets import QApplication, QWidget

# https://github.com/pywinauto/pywinauto/issues/472
sys.coinit_flags = 2  # Fix all kinds of Qt Conflicts after importing pywinauto
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from modules.utils.language import get_translation
from modules.utils.log import init_logging

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class FindDesktopWindowInteractive(QObject):
    tracking_rate = 2000

    def __init__(self, app: QApplication, widget: QWidget):
        super(FindDesktopWindowInteractive, self).__init__(app)
        self.app = app
        self.widget = widget

        self.cursor = QCursor()
        self.tracking_timer = QTimer()
        self.tracking_timer.setInterval(self.tracking_rate)
        self.tracking_timer.timeout.connect(self._track_cursor)

        self.pywin_desktop = Desktop()
        self.qt_desktop = app.desktop()

        self.org_paint_event = self.widget.paintEvent
        self.widget.paintEvent = self.paint_event
        LOGGER.debug('Desktop: %s', self.qt_desktop.screenGeometry().center())

    def paint_event(self, event: QPaintEvent):
        LOGGER.debug('Updating: %s', event.rect())
        p = QPainter()
        p.begin(self.widget)
        p.setPen(QPen(Qt.red, 4))
        p.drawLine(self.qt_desktop.screenGeometry().center(), self.cursor.pos())
        p.end()

    def start(self):
        self.tracking_timer.start()

    def _track_cursor(self):
        wrapper = self._find_window_by_point(self.cursor.pos().x(), self.cursor.pos().y())
        self._highlight_outline(wrapper)

        if wrapper:
            LOGGER.debug('Cursor at: %s - %s', wrapper.top_level_parent().window_text(), wrapper.window_text())
        else:
            LOGGER.debug('Cursor location: %s %s', self.cursor.pos().x(), self.cursor.pos().y())

    @staticmethod
    def _highlight_outline(wrapper):
        wrapper.draw_outline(colour='red', thickness=2, rect=wrapper.rectangle())

    def _find_window_by_point(self, x: int, y: int) -> Union[BaseWrapper, None]:
        try:
            return self.pywin_desktop.from_point(x, y)
        except Exception as e:
            LOGGER.debug(e, exc_info=1)
            return None
