import re
from pathlib import Path
from threading import Event, Thread

import win32gui
from PySide2.QtCore import QObject, QTimer, Signal, Slot, QRect, QPoint
from pywinauto import Application

from modules.knecht_socket import Ncat
from modules.utils.globals import DG_TCP_IP, DG_TCP_PORT
from modules.utils.log import init_logging

LOGGER = init_logging(__name__)


class Win32WindowMgr:
    """Encapsulates some calls to the winapi for window management"""

    def __init__(self):
        """Constructor"""
        self._handle = None

    def handle(self):
        if self.has_handle():
            return self._handle

    def has_handle(self):
        if self._handle:
            return True
        return False

    def clear_handle(self):
        self._handle = None

    def find_window(self, class_name, window_name=None):
        """find a window by its class_name"""
        self._handle = win32gui.FindWindow(class_name, window_name)

    def find_child_windows(self):
        LOGGER.debug('Enumerating child windows')
        if self._handle:
            win32gui.EnumChildWindows(self._handle, self._child_enum_callback, None)

    @staticmethod
    def _child_enum_callback(hwnd, lparam):
        LOGGER.debug('%s, %s, %s', hwnd, win32gui.GetWindowText(hwnd), win32gui.GetWindowRect(hwnd))
        return 1

    @staticmethod
    def find_deltagen_viewer_widget(hwnd):
        """ Find the DeltaGen viewer window inside window controls """
        def find_last_untitled(parent_win, title='untitled'):
            win = parent_win.child_window(title=title)

            while win.child_window(title=title).exists():
                win = win.child_window(title=title)

            return win.child_window(depth=1)

        app = Application().connect(handle=hwnd)
        dg_win = app.window(title_re='DELTAGEN *')
        workspace = dg_win.child_window(title='workspace')
        viewer = find_last_untitled(workspace)

        return viewer

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


class DgSyncThreadSignals(QObject):
    set_btn_enabled_signal = Signal(bool)
    set_btn_checked_signal = Signal(bool)
    position_img_viewer_signal = Signal(QPoint)


class DgSyncThread(Thread):
    viewer_name_wildcard = '.* \[Camer.*\]$'  # Looking for window with name Scene_Name * [Camera]
    dg_window_name_wildcard = 'DELTAGEN .*'  # Look for DeltaGen Window name

    def __init__(self, viewer):
        """ Worker object to sync DG Viewer to Image Viewer position and size

        :param KnechtImageViewer viewer: Image viewer parent
        """
        super(DgSyncThread, self).__init__()
        self.viewer = viewer
        self.win_mgr = Win32WindowMgr()

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

        self.signals = DgSyncThreadSignals()
        self.set_btn_enabled_signal = self.signals.set_btn_enabled_signal
        self.set_btn_enabled_signal.connect(self.viewer.dg_toggle_btn)
        self.set_btn_checked_signal = self.signals.set_btn_checked_signal
        self.set_btn_checked_signal.connect(self.viewer.dg_check_btn)

        self.signals.position_img_viewer_signal.connect(self.viewer.move)

    def run(self):
        """ Thread loop running until exit_event set. As soon as a new send operation
            is scheduled, loop will pick up send operation on next loop cycle.
        """
        while not self.exit_event.is_set():
            if self.sync_dg:
                self.sync_img_viewer()
                self.pull_dg_focus()
            self.exit_event.wait(timeout=1.5)

        self.dg_close_connection()

    def dg_reset_btn(self):
        self.set_btn_enabled_signal.emit(True)

    def sync_img_viewer(self):
        """ Resize DG Viewer widget and move img viewer to DG Viewer widget position """
        self.ncat.check_connection()
        size = f'{self.viewer.size().width()} {self.viewer.size().height()}'
        command = f'UNFREEZE VIEWER;SIZE VIEWER {size};'
        try:
            self.ncat.send(command)
            self.ncat.receive(timeout=0.1, log_empty=False)
        except Exception as e:
            LOGGER.error('Sending viewer size command failed. %s', e)

        self.sync_window_position()

    def sync_window_position(self):
        """ Position the image viewer over the DeltaGen Viewport viewer """
        if not self.win_mgr.has_handle():
            return

        try:
            dg_viewer = self.win_mgr.find_deltagen_viewer_widget(self.win_mgr.handle())
        except Exception as e:
            LOGGER.error(e)
            return

        r = dg_viewer.rectangle()
        x, y = r.left, r.top
        w, h = r.right - r.left, r.bottom - r.top
        viewer_rect = QRect(x, y, w, h)

        LOGGER.debug('DeltaGen Viewer found at %s %s %s %s', x, y, w, h)
        self.signals.position_img_viewer_signal.emit(viewer_rect.topLeft())

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
            self.win_mgr.clear_handle()
            self.ncat.close()

    @Slot()
    def dg_toggle_sync(self):
        self.sync_dg = not self.sync_dg
        self.set_btn_enabled_signal.emit(False)
        self.set_btn_checked_signal.emit(self.sync_dg)
        self.dg_btn_timeout.start()

        if self.sync_dg:
            if self.ncat.deltagen_is_alive():
                self.find_dg_window()
                self.pull_viewer_on_sync_start = True
            else:
                self.dg_toggle_sync()  # No connection, toggle sync off
        else:
            self.dg_reset_viewer()

    def find_dg_window(self):
        """ Tries to find the MS Windows window handle and pulls the viewer window to foreground """
        LOGGER.debug('Finding viewer')
        try:
            self.win_mgr.find_window_wildcard(self.dg_window_name_wildcard)
            self.pull_viewer_on_sync_start = True
        except Exception as e:
            LOGGER.error('Error finding DeltaGen Viewer window.\n%s', e)

    @Slot(bool)
    def viewer_toggle_pull(self, enabled: bool):
        LOGGER.debug('Setting pull_viewer_foreground: %s', not enabled)
        self.pull_viewer_foreground = not enabled

    def pull_dg_focus(self):
        # Pull DeltaGen Viewer to foreground
        if not self.pull_viewer_foreground and not self.pull_viewer_on_sync_start:
            return

        if not self.win_mgr.has_handle():
            return

        try:
            self.win_mgr.set_foreground()
            LOGGER.debug('Pulling DeltaGen Viewer window to foreground.')
        except Exception as e:
            LOGGER.error('Error setting DeltaGen Viewer window to foreground:\n%s', e)

        # Initial pull done, do not pull to front on further sync
        self.pull_viewer_on_sync_start = False


class SyncController(QObject):
    toggle_sync_signal = Signal()
    toggle_pull_signal = Signal(bool)

    def __init__(self, viewer):
        super(SyncController, self).__init__(viewer)
        global LOGGER
        LOGGER = init_logging(__name__)

        self.viewer = viewer
        self.thread = DgSyncThread(viewer)
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
