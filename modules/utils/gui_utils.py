import logging
from datetime import datetime, timedelta
from pathlib import Path
from time import time
from typing import Union

import numpy as np
from PySide2.QtCore import QEvent, QFile, QObject, QRect, QTimer, Qt, Signal, Slot
from PySide2.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent, Qt
from PySide2.QtWidgets import QTreeView, QWidget

from modules.utils.globals import UI_PATH, get_current_modules_dir, get_settings_dir
from modules.utils.log import init_logging
from modules.utils.ui_loader import loadUi

LOGGER = init_logging(__name__)


class MeasureExecTime:
    _start_time = time()

    @classmethod
    def start(cls):
        cls._start_time = time()

    @classmethod
    def finish(cls, msg='Generic Call took:'):
        LOGGER.debug('%s %s', msg, timedelta(seconds=time() - cls._start_time))


def handle_drag_event(e: Union[QDragMoveEvent, QDragEnterEvent], rect: QRect):
    """ Accept all URLs in dragEnter and dragMove Events inside the provided rect """
    LOGGER.debug('Drag event in %s', rect)

    if e.mimeData().hasUrls():
        e.setDropAction(Qt.LinkAction)
        e.accept(rect)
    else:
        e.ignore()


def handle_drop_event(e: QDropEvent, callback):
    LOGGER.debug('Drop event.')

    for url in e.mimeData().urls():
        if url.isLocalFile():
            callback(url.toLocalFile())
            e.accept()
            return

    e.ignore()


class DragNDropHandler(QObject):
    file_dropped = Signal(str)

    def __init__(self, widget: Union[QWidget, QTreeView]):
        super(DragNDropHandler, self).__init__(widget)

        if type(widget) is QTreeView:
            widget.setDragDropMode(QTreeView.DragDrop)

        widget.dropEvent = self.drop_event
        widget.dragEnterEvent = self.drag_enter_event
        widget.dragMoveEvent = self.drag_move_event
        widget.setAcceptDrops(True)

        self.widget = widget

    def drag_move_event(self, e: QDragMoveEvent):
        handle_drag_event(e, self.widget.rect())

    def drag_enter_event(self, e: QDragEnterEvent):
        handle_drag_event(e, self.widget.rect())

    def drop_event(self, e: QDropEvent):
        handle_drop_event(e, self.file_dropped.emit)


def replace_widget(old_widget, new_widget):
    parent = old_widget.parent()
    layout = parent.layout()
    layout.replaceWidget(old_widget, new_widget)
    old_widget.deleteLater()

    return new_widget


class SetupWidget(QObject):
    @staticmethod
    def from_ui_file(widget_cls, ui_file, custom_widgets=dict()):
        """ Load a Qt .ui file to setup the provided widget """
        # Store current log level and set it to ERROR for Ui load
        LOGGER.info('Loading UI File: %s - %s', type(widget_cls), ui_file)

        current_log_level = logging.root.getEffectiveLevel()
        logging.root.setLevel(logging.ERROR)

        # Load the Ui file
        ui_file = Path(get_current_modules_dir()) / UI_PATH / ui_file
        file = QFile(ui_file.as_posix())
        file.open(QFile.ReadOnly)
        loadUi(file, widget_cls, custom_widgets)
        file.close()

        # Restore previous log level
        logging.root.setLevel(current_log_level)


class ConnectCall(QObject):
    def __init__(self, *args, target=None, parent=None):
        super(ConnectCall, self).__init__(parent=parent)
        self.args = args
        self.target = target

    @Slot()
    def call(self):
        self.target(*self.args)


class PredictProgressTime(QObject):
    def __init__(self, num_steps: int, step_size: int=1):
        super(PredictProgressTime, self).__init__()
        if not isinstance(step_size, int) or step_size < 1:
            raise Exception('Step size must be integer greater than 1.')

        # Number of steps that need to be processed
        self.max_steps = int(round(num_steps / step_size))

        # Number of items already processed
        self.progressed_steps = 0

        # List of measured step durations
        self.step_durations = []

        self.progress_start = time()
        self.step_start_time = time()

    def _set_step_start_time(self):
        self.step_start_time = time()

    def update(self):
        return time_string(
            self._predict_remaining_time()
            )

    def _predict_remaining_time(self) -> float:
        self.progressed_steps += 1
        self.step_durations.append(time() - self.step_start_time)

        average_step_duration = self._average_duration()

        remaining_steps = self.max_steps - self.progressed_steps
        self._set_step_start_time()

        return average_step_duration * remaining_steps

    def _average_duration(self):
        n = np.array(self.step_durations, dtype=np.float32)
        return n.mean()


class IdleDetection(QObject):
    def __init__(self, parent):
        super(IdleDetection, self).__init__(parent)
        self._parent: QWidget = parent

        # Report user inactivity
        self._idle_timer = QTimer()
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setTimerType(Qt.VeryCoarseTimer)
        self._idle_timer.setInterval(10000)

        # Detect inactivity for automatic session save
        self._idle_timer.timeout.connect(self.set_inactive)
        self.idle = False

        self.parent.installEventFilter(self)

    def is_active(self):
        return self.idle

    def set_active(self):
        self.idle = False
        self._idle_timer.stop()

    def set_inactive(self):
        self.idle = True

    def eventFilter(self, obj, eve):
        if eve is None or obj is None:
            return False

        if eve.type() == QEvent.KeyPress or \
           eve.type() == QEvent.MouseMove or \
           eve.type() == QEvent.MouseButtonPress:
            self.set_active()
            return False

        if not self._idle_timer.isActive():
            self._idle_timer.start()

        return False


class MouseDblClickFilter(QObject):

    def __init__(self, widget_parent: QWidget, method_call: callable, *args):
        """ Capture Mouse double click events

        :param PySide2.QtWidgets.QWidget widget_parent: Widget the event filter will be installed on
        :param callable method_call: Method to call when event was triggered
        :param *args: Arguments to send to the method_call
        """
        super(MouseDblClickFilter, self).__init__(widget_parent)
        self.widget_parent = widget_parent
        self.method_call = method_call
        self.args = args

        self.widget_parent.installEventFilter(self)

    def eventFilter(self, obj, event: QEvent):
        if obj is None or event is None:
            return False

        if event.type() == QMouseEvent.MouseButtonDblClick:
            LOGGER.debug('Mouse Dbl Click: %s %s', obj, event)
            self.method_call(*self.args)
            event.accept()
            return True

        return False


class ExceptionSignal(QObject):
    exception_signal = Signal(str)


class KnechtExceptionHook:
    app = None
    signals = None
    signal_destination = None

    @classmethod
    def exception_hook(cls, etype, value, tb):
        """ sys.excepthook will call this method """
        import traceback

        # Print exception
        traceback.print_exception(etype, value, tb)

        # Log exception
        stacktrace_msg = ''.join(traceback.format_tb(tb))
        if etype:
            exception_msg = '{0}: {1}'.format(etype, value)
        else:
            exception_msg = 'Exception: {}'.format(value)

        LOGGER.critical(stacktrace_msg)
        LOGGER.critical(exception_msg)

        # Write to exception log file
        exception_file_name = datetime.now().strftime('RenderKnecht_Exception_%Y-%m-%d_%H%M%S.log')
        exception_file = Path(get_settings_dir()) / exception_file_name

        with open(exception_file, 'w') as f:
            traceback.print_exception(etype, value, tb, file=f)

        # Inform GUI of exception if QApplication set
        if cls.app:
            gui_msg = f'{stacktrace_msg}\n{exception_msg}'
            cls.send_exception_signal(gui_msg)

    @classmethod
    def setup_signal_destination(cls, dest):
        """ Setup GUI exception receiver from QApplication"""
        cls.signal_destination = dest

    @classmethod
    def send_exception_signal(cls, msg):
        """ This will fail if not run inside a QApplication """
        cls.signals = ExceptionSignal()
        cls.signals.exception_signal.connect(cls.signal_destination)
        cls.signals.exception_signal.emit(msg)
