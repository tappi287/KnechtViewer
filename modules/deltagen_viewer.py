import re
import sys
from threading import Event, Thread

# https://github.com/pywinauto/pywinauto/issues/472
from modules.utils.camera_info import ImageCameraInfo

sys.coinit_flags = 2  # Fix all kinds of Qt Conflicts after importing pywinauto

import win32gui

from pywinauto import Application
from PySide2.QtCore import QObject, QTimer, Signal, Slot, QRect, QPoint
from modules.utils.language import get_translation
from modules.knecht_socket import Ncat
from modules.utils.globals import DG_TCP_IP, DG_TCP_PORT
from modules.utils.gui_utils import MeasureExecTime, ButtonProgress
from modules.utils.log import init_logging

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class Win32WindowMgr:
    """Encapsulates some calls to the winapi for window management"""

    def __init__(self):
        """Constructor"""
        self._handle = None
        self._app = None

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
    def _read_dg_version(deltagen_window):
        name = deltagen_window.window_text()
        version = name[-5:]

        if version == '2018x':
            return 2018
        elif version == '2017x':
            return 2017
        else:
            return 12

    def find_deltagen_viewer_widget(self):
        """ Find the DeltaGen viewer window inside window controls """
        if not self.has_handle():
            return None

        if not self._app:
            try:
                self._app = Application().connect(handle=self._handle)
            except Exception as e:
                LOGGER.error(e, exc_info=1)
                return None

        try:
            dg_win = self._app.window(title_re='DELTAGEN *', depth=1, found_index=0)
        except Exception as e:
            LOGGER.error(e, exc_info=1)
            return None

        dg_version = self._read_dg_version(dg_win)
        viewer = None

        try:
            if dg_version == 2018:
                workspace = dg_win.child_window(title_re='workspace*', depth=1)
                viewer = workspace.child_window(title='pGLWidgetWindow', depth=2, found_index=0)
            else:
                workspace = dg_win.child_window(title='workspace', depth=1)
                viewer_window = workspace.child_window(title='untitled', depth=1, class_name='QWidget', found_index=0)
                search_terms = ('pGLWidget',  # DeltaGen > 2017x
                                ''  # DeltaGen 12.2
                                )
                for term in search_terms:
                    if viewer_window.child_window(title=term, depth=1, class_name='QWidget', found_index=0).exists():
                        viewer = viewer_window.child_window(title=term, depth=1, class_name='QWidget', found_index=0)
                        break

            if not viewer:
                return
        except Exception as e:
            LOGGER.error(e, exc_info=1)
            return None

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

    message_signal = Signal(str)
    progress_signal = Signal(int)


class DgSyncThread(Thread):
    viewer_name_wildcard = '.* \[Camer.*\]$'  # Looking for window with name Scene_Name * [Camera]
    dg_window_name_wildcard = 'DELTAGEN .*'  # Look for DeltaGen Window name

    def __init__(self, viewer):
        """ Worker object to sync DG Viewer to Image Viewer position and size

        :param modules.img_view.ImageView viewer: Image viewer parent
        """
        super(DgSyncThread, self).__init__()
        self.viewer = viewer
        self.win_mgr = Win32WindowMgr()

        # --- External event to end thread ---
        self.exit_event = Event()

        self.dg_btn_timeout = QTimer()
        self.dg_btn_timeout.setInterval(4000)
        self.dg_btn_timeout.setSingleShot(True)
        self.dg_btn_timeout.timeout.connect(self.dg_reset_btn)

        self.sync_dg = False
        self.pull_viewer_foreground = False
        self.initial_sync_started = True
        self.initial_viewer_size = str()
        self.last_known_win32_wrapper = None

        self.ncat = Ncat(DG_TCP_IP, DG_TCP_PORT)

        self.signals = DgSyncThreadSignals()
        self.set_btn_enabled_signal = self.signals.set_btn_enabled_signal
        self.set_btn_enabled_signal.connect(self.viewer.dg_toggle_btn)
        self.set_btn_checked_signal = self.signals.set_btn_checked_signal
        self.set_btn_checked_signal.connect(self.viewer.dg_check_btn)
        self.message = self.signals.message_signal
        self.progress = self.signals.progress_signal

        self.signals.position_img_viewer_signal.connect(self.viewer.move)

    def run(self):
        """ Thread loop running until exit_event set. As soon as a new send operation
            is scheduled, loop will pick up send operation on next loop cycle.
        """
        while not self.exit_event.is_set():
            sync_refresh_rate = 1.5  # seconds
            if self.sync_dg:
                if not self.sync_img_viewer():
                    # Not synced, toggle off
                    LOGGER.debug('Sync unsuccessful, stopping sync.')
                    self.dg_toggle_sync()
                    self.message.emit(_('Synchronisation beendet. Keine Verbindung zum DeltaGen Host oder kein Viewer'
                                      'Fenster gefunden.'))
                else:
                    # Synced
                    sync_refresh_rate = 0.8  # sync quicker if enabled
                    self.pull_dg_focus()
            self.exit_event.wait(timeout=sync_refresh_rate)

        self.dg_close_connection()

    def dg_reset_btn(self):
        self.set_btn_enabled_signal.emit(True)

    def sync_img_viewer(self) -> bool:
        """ Resize DG Viewer widget and move img viewer to DG Viewer widget position """
        if self.initial_sync_started:
            self.progress.emit(10)
            if not self.ncat.deltagen_is_alive():
                LOGGER.info('No socket connected to DeltaGen or no Viewer window active/in focus.')
                return False

        # -- Sync window position
        sync_result = self.sync_window_position()

        if not sync_result:
            return False

        # -- Sync DeltaGen Viewer size
        size = f'{self.viewer.size().width()} {self.viewer.size().height()}'
        command = f'UNFREEZE VIEWER;SIZE VIEWER {size};'
        try:
            self.ncat.send(command)
            self.ncat.receive(timeout=0.1, log_empty=False)
        except Exception as e:
            LOGGER.error('Sending viewer size command failed. %s', e)
            return False

        return True

    def _find_dg_viewer(self):
        MeasureExecTime.start()
        dg_viewer = self.win_mgr.find_deltagen_viewer_widget()
        MeasureExecTime.finish('Find DG Viewer widget took')

        if not dg_viewer:
            LOGGER.info('Could not find DeltaGen Viewer widget.')
            return
        return dg_viewer

    def sync_window_position(self) -> bool:
        """ Position the image viewer over the DeltaGen Viewport viewer """
        if not self.win_mgr.has_handle():
            return False

        if self.last_known_win32_wrapper is None or self.initial_sync_started:
            # Find pywinauto window handle
            MeasureExecTime.start()
            dg_viewer = self._find_dg_viewer()
            if not dg_viewer:
                return False

            self.last_known_win32_wrapper = dg_viewer.wrapper_object()
            MeasureExecTime.finish('Finding DG Viewer widget took')

        # - Get viewer OpenGl Area rectangle
        try:
            r = self.last_known_win32_wrapper.rectangle()
        except Exception as e:
            LOGGER.debug('Last known window handle invalid. %s', e)
            self.last_known_win32_wrapper = None
            return False

        # - Convert to QRect and QPoint
        x, y, w, h = r.left, r.top, r.width(), r.height()

        if self.initial_sync_started:
            # Save initial viewer size before syncing
            self.initial_viewer_size = f'{w} {h}'

        if x + y + w + h < 1:
            # Empty values indicate a destroyed window
            return False

        viewer_rect = QRect(x, y, w, h)

        # - Check if is inside screen limits
        # (minimizing the window will move it's position to eg. -33330)
        if self.viewer.is_inside_limit(self.viewer.calculate_screen_limits(), viewer_rect.topLeft()):
            LOGGER.debug('DeltaGen Viewer found at %s %s %s %s', x, y, w, h)
            self.signals.position_img_viewer_signal.emit(viewer_rect.topLeft())

        return True

    def dg_reset_viewer(self):
        try:
            self.ncat.send(f'BORDERLESS VIEWER FALSE;SIZE VIEWER {self.initial_viewer_size}')
        except Exception as e:
            LOGGER.error('Sending viewer size command failed. %s', e)

        self.dg_reset_btn()

    def dg_close_connection(self):
        if self.sync_dg:
            self.dg_reset_viewer()
            self.win_mgr.clear_handle()
            self.ncat.close()

    def dg_set_camera(self, cam_info: ImageCameraInfo):
        try:
            self.ncat.send(cam_info.create_deltagen_camera_cmd())
        except Exception as e:
            LOGGER.warning('Could not trasmit camera data to DeltaGen: %s', e)

    @Slot()
    def dg_toggle_sync(self):
        self.sync_dg = not self.sync_dg
        self.set_btn_enabled_signal.emit(False)
        self.set_btn_checked_signal.emit(self.sync_dg)
        self.dg_btn_timeout.start()

        LOGGER.debug(f'Toggled sync {"on" if self.sync_dg else "off"}.', )

        if self.sync_dg:
            self.find_dg_window()
            self.initial_sync_started = True
            self.message.emit(_('Synchronisierung startet. Suche Anwendungsfenster...'))
        else:
            self.progress.emit(0)
            self.dg_reset_viewer()

    def find_dg_window(self):
        """ Tries to find the MS Windows window handle and pulls the viewer window to foreground """
        LOGGER.debug('Finding viewer')
        try:
            self.win_mgr.find_window_wildcard(self.dg_window_name_wildcard)
            self.initial_sync_started = True
        except Exception as e:
            LOGGER.error('Error finding DeltaGen Viewer window.\n%s', e)

    @Slot(bool)
    def viewer_toggle_pull(self, enabled: bool):
        LOGGER.debug('Setting pull_viewer_foreground: %s', not enabled)
        self.pull_viewer_foreground = not enabled

    def pull_dg_focus(self):
        # Pull DeltaGen Viewer to foreground
        if not self.pull_viewer_foreground and not self.initial_sync_started:
            return

        if not self.win_mgr.has_handle():
            return

        try:
            self.win_mgr.set_foreground()
            LOGGER.debug('Pulling DeltaGen Viewer window to foreground.')
        except Exception as e:
            LOGGER.error('Error setting DeltaGen Viewer window to foreground:\n%s', e)

        # Initial pull done, do not pull to front on further sync
        self.initial_sync_started = False


class SyncController(QObject):
    toggle_sync_signal = Signal()
    toggle_pull_signal = Signal(bool)
    transmit_camera_data_signal = Signal(ImageCameraInfo)

    find_window_result = Signal(object)

    def __init__(self, viewer):
        """ Worker object to sync DG Viewer to Image Viewer position and size

        :param modules.img_view.ImageView viewer: Image viewer parent
        """
        super(SyncController, self).__init__(viewer)

        self.viewer = viewer
        self.thread = None

        self.progress_btn = ButtonProgress(self.viewer.ui.sync_btn)
        self._setup_thread()

    def _setup_thread(self):
        self.thread = DgSyncThread(self.viewer)
        self.thread.message.connect(self.display_sync_message)
        self.thread.progress.connect(self.update_progress)
        self.toggle_sync_signal.connect(self.thread.dg_toggle_sync)
        self.toggle_pull_signal.connect(self.thread.viewer_toggle_pull)
        self.transmit_camera_data_signal.connect(self.thread.dg_set_camera)

    def update_progress(self, duration: int):
        self.progress_btn.start_timed_progress(duration)

    def toggle_sync(self):
        if not self.viewer.ui.top_btn.isChecked():
            self.viewer.ui.top_btn.setChecked(self.viewer.switch_stay_on_top())

        self.start()
        self.toggle_sync_signal.emit()

    def toggle_pull(self):
        enabled = self.viewer.ui.focus_btn.isChecked()
        self.toggle_pull_signal.emit(enabled)

    def display_sync_message(self, msg):
        self.viewer.info_overlay.display(msg, duration=5000, immediate=True)

    def send_camera_data(self, camera: ImageCameraInfo):
        self.transmit_camera_data_signal.emit(camera)

    def start(self):
        if not self.thread.is_alive():
            self.thread.pull_viewer_foreground = self.viewer.ui.focus_btn.isChecked()
            self.thread.start()

    def exit(self):
        if self.thread.is_alive():
            self.thread.exit_event.set()
            self.thread.join()
