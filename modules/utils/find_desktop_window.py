import sys
from typing import Union

from PySide2.QtCore import QObject, QEvent, QTimer, Qt, QRect, Signal, QMargins, QPoint
from PySide2.QtGui import QCursor, QPainter, QPen, QPaintEvent, QColor
from PySide2.QtWidgets import QWidget, QDesktopWidget, QApplication

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
    tracking_rate = 500
    painting_rate = 15

    result = Signal(QRect)

    def __init__(self, app: QApplication, origin_draw_position: QPoint):
        """
        Locate a desktop window rectangle with the mouse cursor

        :param QApplication app: App to install event filter on
        :param QPoint origin_draw_position: Position of the line, indicating the tracked cursor, is drawn from
        """
        super(FindDesktopWindowInteractive, self).__init__()
        self.app = app

        self.tracking_timer = QTimer()
        self.tracking_timer.setInterval(self.tracking_rate)
        self.tracking_timer.timeout.connect(self._track_cursor)

        self.paint_timer = QTimer()
        self.paint_timer.setInterval(self.painting_rate)
        self.paint_timer.timeout.connect(self.paint)

        self.cursor = QCursor()
        self.pywin_desktop = Desktop()

        self.highlight_rect = QRect()

        self.origin_draw_pos = origin_draw_position

        # -- Transparent widget across the desktop to draw on --
        self.desk_draw_widget = DesktopDrawWidget(app.desktop())
        self.desk_draw_widget.paintEvent = self.paint_event

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """ Install on QApplication to grab result as soon as we loose focus
            aka mousePress outside of any of our widgets.

            Cancel if any unbound keys are pressed. Shortcut keys will be ignored.
        """
        if event.type() == QEvent.FocusOut:
            self.stop()
            return True
        elif event.type() == QEvent.KeyPress:
            self.abort()
            return True
        return False

    def paint(self):
        """ Trigger a desktop overlay widget paint event """
        self.desk_draw_widget.update()

    def paint_event(self, event: QPaintEvent):
        pen = QPen(QColor(250, 120, 20))
        w = 4
        m = round(w/2)
        pen.setWidth(w)
        pen.setJoinStyle(Qt.RoundJoin)

        inner_rect = self.highlight_rect.marginsRemoved(QMargins(m, m, m, m))

        p = QPainter()
        p.begin(self.desk_draw_widget)
        p.setPen(pen)
        p.drawLine(self.origin_draw_pos, self.cursor.pos())
        p.drawRect(inner_rect)
        p.end()

    def start(self):
        self.desk_draw_widget.show()
        self.app.installEventFilter(self)

        self.tracking_timer.start()
        self.paint_timer.start()

    def stop(self):
        LOGGER.debug('Selected Area: %s', self.highlight_rect)
        self.result.emit(self.highlight_rect)
        self.finish()

    def abort(self):
        self.finish()

    def finish(self):
        self.app.removeEventFilter(self)

        self.tracking_timer.stop()
        self.paint_timer.stop()

        self.desk_draw_widget.close()
        self.desk_draw_widget.deleteLater()
        self.deleteLater()

    def _track_cursor(self):
        wrapper = self._find_window_by_point(self.cursor.pos().x(), self.cursor.pos().y())
        if not wrapper:
            return

        r = wrapper.rectangle()
        self.highlight_rect = QRect(r.left, r.top, r.width(), r.height())

    def _find_window_by_point(self, x: int, y: int) -> Union[BaseWrapper, None]:
        try:
            return self.pywin_desktop.from_point(x, y)
        except Exception as e:
            LOGGER.debug(e, exc_info=1)
            return None

    @staticmethod
    def _highlight_outline(wrapper):
        """ Alternative highlight method from pywinauto """
        wrapper.draw_outline(colour='red', thickness=2, rect=wrapper.rectangle())


class DesktopDrawWidget(QWidget):
    def __init__(self, desktop: QDesktopWidget):
        """ Transparent non interact-able Desktop Overlay to draw on """
        super(DesktopDrawWidget, self).__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint |
                            Qt.Tool | Qt.WindowTransparentForInput)

        self.setGeometry(desktop.screenGeometry())
