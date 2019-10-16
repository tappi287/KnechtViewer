from typing import Tuple

from PySide2.QtWidgets import QWidget
from PySide2.QtCore import QObject, QSize, QPropertyAnimation, QEasingCurve, QAbstractAnimation, Property
from PySide2.QtGui import QColor, QPalette

from modules.utils.log import init_logging

LOGGER = init_logging(__name__)


class BgrAnimationGroup(QObject):
    def __init__(self, start_color: tuple=(0, 0, 0), end_color: tuple= (255, 255, 255), duration: int=250):
        super(BgrAnimationGroup, self).__init__()
        self._widget_list = list()
        self.start_color = start_color
        self.end_color = end_color
        self.duration = duration

    def add_widget(self, widget):
        widget.bgr_animation = BgrAnimation(widget)
        self._widget_list.append(widget)

    def fade_end(self):
        for widget in self._widget_list:
            widget.bgr_animation.fade(self.start_color, self.end_color, self.duration)

    def fade_start(self):
        for widget in self._widget_list:
            widget.bgr_animation.fade(self.end_color, self.start_color, self.duration)


class BgrAnimation(QObject):

    def __init__(self, widget: QWidget, bg_color: Tuple[int, int, int, int], additional_stylesheet: str=''):
        """ Animate provided Widget background stylesheet color

        :param widget:
        :param bg_color:
        """
        super(BgrAnimation, self).__init__(widget)
        self.widget = widget
        self.color = QColor()

        self.bg_color = self.widget.palette().color(QPalette.Background)
        self.additional_stylesheet = additional_stylesheet
        if bg_color:
            self.bg_color = QColor(*bg_color)

        self.color_anim = QPropertyAnimation(self, b'backColor')
        self.color_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._setup_blink()

        self.pulsate_anim = QPropertyAnimation(self, b'backColor')
        self.pulsate_anim.setEasingCurve(QEasingCurve.InOutQuint)
        self._setup_pulsate()

        self.fade_anim = QPropertyAnimation(self, b'backColor')
        self.fade_anim.setEasingCurve(QEasingCurve.InCubic)

    def fade(self, start_color: tuple, end_color: tuple, duration:int):
        self.fade_anim.setStartValue(QColor(*start_color))
        self.fade_anim.setEndValue(QColor(*end_color))
        self.fade_anim.setDuration(duration)

        self.fade_anim.start(QAbstractAnimation.KeepWhenStopped)

    def _setup_blink(self, anim_color: tuple=(26, 118, 255, 255)):
        start_color = self.bg_color
        anim_color = QColor(*anim_color)

        self.color_anim.setStartValue(start_color)
        self.color_anim.setKeyValueAt(0.5, anim_color)
        self.color_anim.setEndValue(start_color)

        self.color_anim.setDuration(600)

    def blink(self, num: int=1):
        self.pulsate_anim.stop()
        self.color_anim.setLoopCount(num)
        self.color_anim.start()

    def _setup_pulsate(self, anim_color: tuple=(255, 80, 50, 255)):
        start_color = self.bg_color
        anim_color = QColor(*anim_color)

        self.pulsate_anim.setStartValue(start_color)
        self.pulsate_anim.setKeyValueAt(0.5, anim_color)
        self.pulsate_anim.setEndValue(start_color)

        self.pulsate_anim.setDuration(4000)

    def active_pulsate(self, num: int=-1):
        self.pulsate_anim.setLoopCount(num)
        self.pulsate_anim.start()

    def _get_back_color(self):
        return self.color

    def _set_back_color(self, color):
        self.color = color
        qss_color = f'rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})'
        try:
            self.widget.setStyleSheet(f'background-color: {qss_color};{self.additional_stylesheet}')
        except AttributeError as e:
            LOGGER.debug('Error setting widget background color: %s', e)

    backColor = Property(QColor, _get_back_color, _set_back_color)


class AnimatedButton:
    def __init__(self, btn, duration):
        self.btn = btn
        self.duration = duration

        self.animation = QPropertyAnimation(self.btn, b"iconSize")

        self.setup_animation()

    def setup_animation(self):
        size = self.btn.iconSize()
        start_value = QSize(round(size.width() * 0.2), round(size.height() * 0.2))
        end_value = size

        self.animation.setDuration(self.duration)
        self.animation.setKeyValueAt(0.0, end_value)
        self.animation.setKeyValueAt(0.5, start_value)
        self.animation.setKeyValueAt(1.0, end_value)
        self.animation.setEasingCurve(QEasingCurve.OutElastic)

    def play_highlight(self):
        self.animation.setDuration(self.duration)
        self.animation.setEasingCurve(QEasingCurve.OutElastic)
        self.play()

    def play_on(self):
        self.animation.setDuration(round(self.duration * 0.3))
        self.animation.setEasingCurve(QEasingCurve.InCirc)
        self.play()

    def play_off(self):
        self.animation.setDuration(round(self.duration * 0.3))
        self.animation.setEasingCurve(QEasingCurve.OutCirc)
        self.play()

    def play(self, event=None):
        if self.animation.state() != QAbstractAnimation.Running:
            self.animation.start()


class AnimateWindowOpacity:
    def __init__(self, widget: QWidget, duration: int, start_value: float=0.8, end_value: float=1.0):
        self.widget = widget
        self.duration = duration
        self.animation = QPropertyAnimation(self.widget, b"windowOpacity")
        self.start_value, self.end_value = start_value, end_value
        self.setup_animation(self.start_value, self.end_value)

    def setup_animation(self, start_value: float=0.0, end_value: float=1.0, duration: int=0):
        if not duration:
            duration = self.duration

        self.animation.setDuration(duration)
        self.animation.setKeyValueAt(0.0, start_value)
        self.animation.setKeyValueAt(1.0, end_value)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def fade_in(self, duration: int=0):
        if self.widget.windowOpacity() >= self.end_value:
            return False

        self.setup_animation(self.start_value, self.end_value, duration)
        self.play()
        return True

    def fade_out(self, duration: int=0):
        if self.widget.windowOpacity() <= self.start_value:
            return False

        self.setup_animation(self.end_value, self.start_value, duration)
        self.play()
        return True

    def play(self):
        if self.animation.state() != QAbstractAnimation.Running:
            self.animation.start()
