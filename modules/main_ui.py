from pathlib import Path
from typing import Union

from PySide2.QtCore import QPoint, QTimer, Qt, QRect, QEvent
from PySide2.QtWidgets import QComboBox, QLineEdit, QSlider, QToolButton, QWidget, QPushButton

from modules.img_view import ImageView
from modules.utils.find_desktop_window import FindDesktopWindowInteractive
from modules.utils.globals import APP_NAME, Resource
from modules.utils.gui_utils import DragNDropHandler, SetupWidget, replace_widget, ButtonClickKeyModifierHandler
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.path_util import SetDirectoryPath, path_exists
from modules.utils.settings import KnechtSettings
from modules.utils.ui_resource import IconRsc
from modules.widgets import ViewerSizeBox, FileMenu

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class ViewerWindow(QWidget):
    VIEWER_Y_MARGIN = 2

    def __init__(self, app):
        """ Main Window to easily minimize and restore the img_view window

        :param modules.main_app.ViewerApp app: Viewer QApplication
        """
        super(ViewerWindow, self).__init__()

        SetupWidget.from_ui_file(self, Resource.ui_paths.get('viewer'))

        self.app = app
        self.setWindowTitle(self.app.applicationName())
        self.setWindowIcon(IconRsc.get_icon('compare'))
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint |
                            Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint | Qt.NoDropShadowWindowHint)

        # Force minimum size dynamically
        self.resize(1280, 1)

        # --- --- Setup Widgets --- ---
        # --- Setup Size ComboBox ---
        self.zoom_box: QComboBox
        self.zoom_box = replace_widget(self.zoom_box, ViewerSizeBox(self))

        # --- Setup Opacity Slider ---
        self.opacity_slider: QSlider
        self.opacity_slider.setFocusPolicy(Qt.NoFocus)
        self.opacity_slider.setObjectName('slider')
        self.opacity_slider.setRange(1, 10)
        self.opacity_slider.setValue(10)
        self.opacity_slider.setSingleStep(1)

        # --- Image View ---
        self.img_view = ImageView(app, self)

        # --- File Menu ---
        self.file_menu = FileMenu(self)

        self.file_btn: QPushButton
        self.file_btn.setMenu(self.file_menu)

        # --- Setup Path LineEdit and ToolButton ---
        self.path_edit.setPlaceholderText(_('Dateien oder Ordner in das Fenster ziehen oder hier Pfad einfügen.'))
        self.path_edit.setFocusPolicy(Qt.ClickFocus)
        self.path_btn.setFocusPolicy(Qt.ClickFocus)
        self.path_btn.hide()
        self.path_util = SetDirectoryPath(self, 'file', self.path_edit, self.path_btn, reject_invalid_path_edits=False)

        # --- Setup ui specific buttons ---
        self.locate_btn: QPushButton
        btn_handler = ButtonClickKeyModifierHandler(self.locate_btn)
        btn_handler.shift_trigger.connect(self._start_locate_window)
        self.locate_btn.key_modifier = 0  # Will store the KeyboardModifier
        # Disable locate btn while syncing
        self.sync_btn.toggled.connect(self.locate_btn.setDisabled)
        self.locate_btn.setToolTip(_('Desktop Fenster auswählen und Bildfläche dorthin verschieben; Strg/Shift+Klick '
                                     'ignoriert Seitenverhältnis'))

        self.cam_btn.setToolTip(_('Kamera Daten an DeltaGen senden.'))
        self.cam_btn.pressed.connect(self._send_camera_data)

        self.load_settings()

        self.path_util.path_changed.connect(self.file_changed)
        self.path_util.dialog_opened.connect(self._path_dialog_opened)
        self.path_util.dialog_closed.connect(self._path_dialog_closed)

        # --- Drag n Drop ---
        drag_drop = DragNDropHandler(self)
        drag_drop.file_dropped.connect(self.file_changed)

        # --- --- Setup Window Movement --- ---
        # Install viewer move and resize wrapper
        self.org_img_view_resize_event = self.img_view.resizeEvent
        self.img_view.resizeEvent = self._img_view_resize_wrapper
        self.org_img_view_move_event = self.img_view.moveEvent
        self.img_view.moveEvent = self._img_view_move_wrapper

        QTimer.singleShot(50, self.window_shown)

    def enterEvent(self, event: QEvent):
        self.app.setActiveWindow(self)

    def window_shown(self):
        self.setFixedHeight(self.size().height())

        self.img_view.set_default_image()
        self.img_view.show_all()
        self.img_view.display_shortcuts(keep_overlay=False)

        # Move to screen center
        new_position = QPoint(self.x(), self.y() - round(self.img_view.height() / 2))
        self.move(new_position)

    def load_settings(self):
        current_path = Path(KnechtSettings.app.get('current_path'))
        if current_path != Path('.') and path_exists(current_path):
            self.path_util.set_path(current_path)
            self.img_view.img_load_controller.set_img_path(current_path, skip_load=True)

        if KnechtSettings.app.get('img_stay_on_top') is False:
            self.top_btn.setChecked(self.img_view.switch_stay_on_top())
        if KnechtSettings.app.get('img_input_transparent') is True:
            self.input_btn.setChecked(not self.img_view.switch_input_transparency())

    def _start_locate_window(self, btn_key_modifier: int):
        """ Move Image Viewer to the desktop window selected by the user """
        self.locate_btn.key_modifier = 0
        self.locate_btn.key_modifier = btn_key_modifier

        self.img_view.info_overlay.display(_('Desktop Fenster mit Mausklick auswählen. '
                                             'Beliebige Taste drücken zum abbrechen.'), 5000, immediate=True)
        find_win = FindDesktopWindowInteractive(self.app, self.locate_btn.mapToGlobal(self.locate_btn.rect().center()))
        find_win.start()
        find_win.result.connect(self._locate_win_result)

    def _locate_win_result(self, target_rect: QRect):
        if target_rect.width() < 2 or target_rect.height() < 2:
            return
        # Trigger a resize to regular size if previous size was fitted to a window
        self.img_view.change_viewer_size()

        if self.locate_btn.key_modifier == 0 and self.img_view.height() > 0:
            # No Key Modifier tries to keep aspect ratio
            height_factor: float = self.img_view.height() / self.img_view.width()
            height: int = round(target_rect.width() * height_factor)
            target_rect.setHeight(height)
            LOGGER.debug('Trying to keep aspect ratio at %s height factor. %s %s',
                         height_factor, target_rect.width(), height)
        elif self.locate_btn.key_modifier == Qt.ControlModifier:
            # Ctrl Key only moves window
            self.img_view.move(target_rect.topLeft())
            return
        elif self.locate_btn.key_modifier == Qt.ShiftModifier:
            # Shift/Any Key Modifier fits to window without respecting aspect ratio of image
            pass

        self.img_view.resize(target_rect.size())
        self.img_view.move(target_rect.topLeft())

    def _send_camera_data(self):
        cam = self.img_view.img_load_controller.current_cam

        if cam:
            self.img_view.dg_thread.send_camera_data(cam)

    def _path_dialog_opened(self):
        """ Toggle Image Canvas Stay On Top while Path Dialog opened """
        if self.top_btn.isChecked():
            self.img_view.toggle_stay_on_top()

    def _path_dialog_closed(self):
        if self.top_btn.isChecked():
            self.img_view.toggle_stay_on_top()

    def file_changed(self, file_path: Union[str, Path]):
        file_path = Path(file_path)
        LOGGER.debug('File changed: %s', file_path.as_posix())
        self.img_view.set_img_path(file_path)

    def reset(self):
        """ Reset to default """
        self.zoom_box.reset()
        self.setWindowTitle(f'{APP_NAME}')
        self.path_edit.setText('')

    def _img_view_move_wrapper(self, event):
        self.org_img_view_move_event(event)
        self._adapt_img_view_position()
        event.accept()

    def _img_view_resize_wrapper(self, event):
        self.org_img_view_resize_event(event)
        self._adapt_img_view_position()
        event.accept()

    def _adapt_img_view_position(self):
        x = self.img_view.x()
        y = self.img_view.y() - self.geometry().height() - self.VIEWER_Y_MARGIN

        self.setGeometry(x, y, self.img_view.size().width(), self.geometry().height())

    def moveEvent(self, event):
        y = self.geometry().y() + self.geometry().height() + self.VIEWER_Y_MARGIN
        self.img_view.move(self.geometry().x(), y)
        event.accept()

    def closeEvent(self, QCloseEvent):
        self.img_view.close()
        QCloseEvent.accept()
