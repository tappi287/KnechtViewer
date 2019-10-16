from pathlib import Path
from typing import Union

from PySide2.QtCore import QTimer, Qt, QPoint
from PySide2.QtWidgets import QComboBox, QLineEdit, QSlider, QToolButton

from modules.img_view import ImageView
from modules.utils.globals import APP_NAME, Resource
from modules.utils.gui_utils import SetupWidget, replace_widget
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.path_util import SetDirectoryPath
from modules.utils.ui_resource import IconRsc
from modules.widgets import FileDropWidget, ViewerSizeBox

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class ViewerWindow(FileDropWidget):
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
        # --- Setup Path LineEdit and ToolButton ---
        self.path_edit: QLineEdit
        self.path_btn: QToolButton
        self.path_edit.setPlaceholderText(_('Dateien oder Ordner in das Fenster ziehen oder hier Pfad einfügen.'))
        self.path_edit.setFocusPolicy(Qt.ClickFocus)
        self.path_btn.setFocusPolicy(Qt.ClickFocus)
        self.path_util = SetDirectoryPath(self, 'file', self.path_edit, self.path_btn, reject_invalid_path_edits=False)
        self.path_util.path_changed.connect(self.file_changed)

        self.path_util.dialog_opened.connect(self._path_dialog_opened)
        self.path_util.dialog_closed.connect(self._path_dialog_closed)
        self.previous_top_btn_state = True

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

        # --- --- Setup Window Movement --- ---
        # Install viewer move and resize wrapper
        self.org_img_view_resize_event = self.img_view.resizeEvent
        self.img_view.resizeEvent = self._img_view_resize_wrapper
        self.org_img_view_move_event = self.img_view.moveEvent
        self.img_view.moveEvent = self._img_view_move_wrapper

        self.file_dropped.connect(self.file_changed)

        QTimer.singleShot(50, self.window_shown)

    def window_shown(self):
        self.setFixedHeight(self.size().height())
        self.img_view.show_all()
        self.img_view.display_shortcuts(keep_overlay=False)

        # Move to screen center
        new_position = QPoint(self.x(), self.y() - round(self.img_view.height() / 2))
        self.move(new_position)

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
