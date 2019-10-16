import re
from threading import Event, Thread

import win32gui
from PySide2.QtCore import QObject, QTimer, Signal, Slot

from modules.knecht_socket import Ncat
from modules.utils.globals import DG_TCP_IP, DG_TCP_PORT
from modules.utils.log import init_logging

LOGGER = init_logging(__name__)


class Win32WindowMgr:
    """Encapsulates some calls to the winapi for window management"""

    def __init__(self):
        """Constructor"""
        self._handle = None

    def has_handle(self):
        if self._handle:
            return True
        return False

    def clear_handle(self):
        self._handle = None

    def find_window(self, class_name, window_name=None):
        """find a window by its class_name"""
        self._handle = win32gui.FindWindow(class_name, window_name)

    def _window_enum_callback(self, hwnd, wildcard):
        """Pass to win32gui.EnumWindows() to check all the opened windows"""
        if re.match(wildcard, str(win32gui.GetWindowText(hwnd))) is not None:
            self._handle = hwnd

    def find_window_wildcard(self, wildcard):
        """find a window whose title matches the wildcard regex"""
        self._handle = None
        win32gui.EnumWindows(self._window_enum_callback, wildcard)

    def set_foreground(self):
        """put the window in the foreground"""
        if self._handle:
            win32gui.SetForegroundWindow(self._handle)


class KnechtImageViewerDgSyncSignals(QObject):
    set_btn_enabled_signal = Signal(bool)
    set_btn_checked_signal = Signal(bool)


class KnechtImageViewerDgSync(Thread):
    viewer_name_wildcard = '.* \[Camer.*\]$'  # Looking for window with name Scene_Name * [Camera]

    def __init__(self, viewer):
        """ Worker object to sync DG Viewer to Image Viewer position and size

        :param KnechtImageViewer viewer: Image viewer parent
        """
        super(KnechtImageViewerDgSync, self).__init__()
        self.viewer = viewer
        self.dg_window = Win32WindowMgr()

        # --- External event to end thread ---
        self.exit_event = Event()

        self.dg_btn_timeout = QTimer()
        self.dg_btn_timeout.setInterval(800)
        self.dg_btn_timeout.setSingleShot(True)
        self.dg_btn_timeout.timeout.connect(self.dg_reset_btn)

        self.sync_dg = False
        self.pull_viewer_foreground = False
        self.pull_viewer_on_sync_start = True

        self.ncat = Ncat(DG_TCP_IP, DG_TCP_PORT)

        self.signals = KnechtImageViewerDgSyncSignals()
        self.set_btn_enabled_signal = self.signals.set_btn_enabled_signal
        self.set_btn_enabled_signal.connect(self.viewer.dg_toggle_btn)
        self.set_btn_checked_signal = self.signals.set_btn_checked_signal
        self.set_btn_checked_signal.connect(self.viewer.dg_check_btn)

    def run(self):
        """ Thread loop running until exit_event set. As soon as a new send operation
            is scheduled, loop will pick up send operation on next loop cycle.
        """
        while not self.exit_event.is_set():
            if self.sync_dg:
                self.dg_set_viewer()
                self.viewer_pull_window()
            self.exit_event.wait(timeout=1.5)

        self.dg_close_connection()

    def dg_reset_btn(self):
        self.set_btn_enabled_signal.emit(True)

    def dg_set_viewer(self):
        self.ncat.check_connection()

        position = f'{self.viewer.frameGeometry().x()} {self.viewer.frameGeometry().y()}'
        size = f'{self.viewer.size().width()} {self.viewer.size().height()}'
        command = f'UNFREEZE VIEWER;BORDERLESS VIEWER TRUE;SIZE VIEWER {size};POSITION VIEWER {position};'

        try:
            self.ncat.send(command)
            self.ncat.receive(timeout=0.1, log_empty=False)
        except Exception as e:
            LOGGER.error('Sending viewer size command failed. %s', e)

    def dg_reset_viewer(self):
        self.ncat.check_connection()
        try:
            self.ncat.send('BORDERLESS VIEWER FALSE;')
        except Exception as e:
            LOGGER.error('Sending viewer size command failed. %s', e)

        self.dg_reset_btn()

    def dg_close_connection(self):
        if self.sync_dg:
            self.dg_reset_viewer()
            self.ncat.close()

    @Slot()
    def dg_toggle_sync(self):
        self.sync_dg = not self.sync_dg
        self.set_btn_enabled_signal.emit(False)
        self.set_btn_checked_signal.emit(self.sync_dg)
        self.dg_btn_timeout.start()

        if self.sync_dg:
            if self.ncat.deltagen_is_alive():
                self.pull_viewer_on_sync_start = True
                self.dg_window.clear_handle()
            else:
                self.dg_toggle_sync()  # No connection, toggle sync off
        else:
            self.dg_reset_viewer()

    @Slot(bool)
    def viewer_toggle_pull(self, enabled: bool):
        LOGGER.debug('Setting pull_viewer_foreground: %s', not enabled)
        self.pull_viewer_foreground = not enabled

    def viewer_window_find(self):
        """ Tries to find the MS Windows window handle and pulls the viewer window to foreground """
        try:
            self.dg_window.find_window_wildcard(self.viewer_name_wildcard)

            self.pull_viewer_on_sync_start = True
        except Exception as e:
            LOGGER.error('Error finding DeltaGen Viewer window.\n%s', e)

    def viewer_pull_window(self):
        # Pull DeltaGen Viewer to foreground
        if not self.pull_viewer_foreground and not self.pull_viewer_on_sync_start:
            return

        if not self.dg_window.has_handle():
            self.viewer_window_find()

        try:
            self.dg_window.set_foreground()
            LOGGER.debug('Pulling DeltaGen Viewer window to foreground.')
        except Exception as e:
            LOGGER.error('Error setting DeltaGen Viewer window to foreground:\n%s', e)

        # Initial pull done, do not pull to front on further sync
        self.pull_viewer_on_sync_start = False


class KnechtImageViewerSendController(QObject):
    toggle_sync_signal = Signal()
    toggle_pull_signal = Signal(bool)

    def __init__(self, viewer):
        super(KnechtImageViewerSendController, self).__init__(viewer)
        global LOGGER
        LOGGER = init_logging(__name__)

        self.viewer = viewer
        self.thread = KnechtImageViewerDgSync(viewer)
        self.toggle_sync_signal.connect(self.thread.dg_toggle_sync)
        self.toggle_pull_signal.connect(self.thread.viewer_toggle_pull)

    def toggle_sync(self):
        self.start()
        self.toggle_sync_signal.emit()

    def toggle_pull(self):
        enabled = self.viewer.ui.focus_btn.isChecked()
        self.toggle_pull_signal.emit(enabled)

    def start(self):
        if not self.thread.is_alive():
            self.thread.pull_viewer_foreground = self.viewer.ui.focus_btn.isChecked()
            self.thread.start()

    def exit(self):
        if self.thread.is_alive():
            self.thread.exit_event.set()
            self.thread.join()
