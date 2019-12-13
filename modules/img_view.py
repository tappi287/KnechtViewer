from pathlib import Path

from PySide2.QtCore import QEvent, QPoint, QRect, QSize, QTimer, Qt
from PySide2.QtGui import QKeySequence, QPalette, QColor
from PySide2.QtWidgets import QHBoxLayout, QLabel, QPushButton, QShortcut, QSizePolicy, QWidget

from modules.deltagen_viewer import SyncController
from modules.utils.globals import MAX_SIZE_FACTOR
from modules.utils.gui_utils import DragNDropHandler
from modules.utils.img_loader import KnechtLoadImageController
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.settings import KnechtSettings
from modules.utils.ui_overlay import InfoOverlay
from modules.utils.ui_resource import IconRsc

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class ViewerShortcuts:
    def __init__(self, viewer, ui):
        self.viewer, self.ui = viewer, ui

    def set_shortcuts(self, parent):
        # Viewer Image Canvas Display On/Off
        toggle_view = QShortcut(QKeySequence(Qt.Key_Tab), parent)
        toggle_view.activated.connect(self.ui.vis_btn.animateClick)
        toggle_view_x = QShortcut(QKeySequence(Qt.Key_X), parent)
        toggle_view_x.activated.connect(self.ui.vis_btn.animateClick)

        # Increase Image Size
        size_hi = QShortcut(QKeySequence(Qt.Key_Plus), parent)
        size_hi.activated.connect(self.viewer.increase_size)
        size_hi_e = QShortcut(QKeySequence(Qt.Key_E), parent)
        size_hi_e.activated.connect(self.viewer.increase_size)
        # Decrease Image Size
        size_lo = QShortcut(QKeySequence(Qt.Key_Minus), parent)
        size_lo.activated.connect(self.viewer.decrease_size)
        size_lo_q = QShortcut(QKeySequence(Qt.Key_Q), parent)
        size_lo_q.activated.connect(self.viewer.decrease_size)

        # Increase Viewer Window Opacity
        opa_hi_w = QShortcut(QKeySequence(Qt.Key_W), parent)
        opa_hi_w.activated.connect(self.viewer.increase_window_opacity)
        opa_hi = QShortcut(QKeySequence('Ctrl++'), parent)
        opa_hi.activated.connect(self.viewer.increase_window_opacity)
        # Decrease Viewer Window Opacity
        opa_lo_s = QShortcut(QKeySequence(Qt.Key_S), parent)
        opa_lo_s.activated.connect(self.viewer.decrease_window_opacity)
        opa_lo = QShortcut(QKeySequence('Ctrl+-'), parent)
        opa_lo.activated.connect(self.viewer.decrease_window_opacity)

        # Exit
        esc = QShortcut(QKeySequence(Qt.Key_Escape), parent)
        esc.activated.connect(self.viewer.close)

        # Load Next Image
        fwd = QShortcut(QKeySequence(Qt.Key_Right), parent)
        fwd.activated.connect(self.ui.fwd_btn.animateClick)
        fwd_d = QShortcut(QKeySequence(Qt.Key_D), parent)
        fwd_d.activated.connect(self.ui.fwd_btn.animateClick)
        # Load Previous Image
        bck = QShortcut(QKeySequence(Qt.Key_Left), parent)
        bck.activated.connect(self.ui.back_btn.animateClick)
        bck_a = QShortcut(QKeySequence(Qt.Key_A), parent)
        bck_a.activated.connect(self.ui.back_btn.animateClick)

        # Toggle DeltaGen Viewer Sync
        dg = QShortcut(QKeySequence(Qt.Key_F), parent)
        dg.activated.connect(self.viewer.dg_toggle_sync)


class ImageView(QWidget):
    button_timeout = QTimer()
    button_timeout.setInterval(100)
    button_timeout.setSingleShot(True)

    shortcut_timeout = QTimer()
    shortcut_timeout.setInterval(50)
    shortcut_timeout.setSingleShot(True)

    slider_timeout = QTimer()
    slider_timeout.setInterval(20)
    slider_timeout.setSingleShot(True)

    DEFAULT_SIZE = (800, 450)
    MARGIN = 400

    MAX_SIZE = QSize(4096, 4096)

    def __init__(self, app, ui):
        """ Image Overlay frameless window that stays on top by default

        :param modules.main_app.ViewerApp app: Viewer QApplication
        :param modules.main_ui.ViewerWindow ui: Viewer QWidget main app window showing controls
        """
        super(ImageView, self).__init__(ui)
        self.app, self.ui = app, ui

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.CustomizeWindowHint | Qt.Tool)
        self.setWindowIcon(IconRsc.get_icon('img'))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AcceptDrops, True)
        self.setStyleSheet("QWidget{background-color: darkgray;}")
        self.setFocusPolicy(Qt.StrongFocus)

        self.current_img = None
        self.img_list = list()
        self.img_index = 0
        self.img_size_factor = 1.0
        self.img_size = QSize(*self.DEFAULT_SIZE)
        self.img_loader = None  # will be the loader thread

        # Save window position for drag
        self.oldPos = self.pos()

        self.current_opacity = 1.0
        self.setWindowOpacity(1.0)

        # --- Image Loader ---
        self.img_load_controller = KnechtLoadImageController(self)
        self.img_load_controller.camera_available.connect(self.camera_data_available)

        # --- Image canvas ---
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.img_canvas = QLabel(self)
        self.layout().addWidget(self.img_canvas)
        self.img_canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.img_canvas.setScaledContents(True)
        self.img_canvas.setObjectName('img_canvas')
        self.set_default_image()
        self.ui.reset()

        LOGGER.debug('Image View: %s', self.geometry())

        self.slider_timeout.timeout.connect(self.set_opacity_from_slider)
        self.ui.opacity_slider.setToolTip(_('Transparenz der Bildfläche festlegen [W/S]'))
        self.ui.opacity_slider.sliderReleased.connect(self.slider_timeout.start)
        self.ui.opacity_slider.valueChanged.connect(self.slider_timeout.start)

        self.ui.zoom_box.currentIndexChanged.connect(self.combo_box_size)
        self.ui.zoom_box.setToolTip(_('Anzeigegröße der Bilddatei anpassen [Q/E]'))

        self.ui.cam_btn.setToolTip(_('Kamera Daten an DeltaGen senden.'))
        self.ui.cam_btn.released.connect(self.img_load_controller.send_camera_data)

        self.ui.back_btn.pressed.connect(self.iterate_bck)
        self.ui.back_btn.setToolTip(_('Datei zurück navigieren [A oder <= Pfeiltaste]'))
        self.ui.fwd_btn.pressed.connect(self.iterate_fwd)
        self.ui.fwd_btn.setToolTip(_('Datei vorwärts navigieren [D oder => Pfeiltaste]'))
        self.ui.top_btn.setToolTip(_('Bildfläche immer im Vordergrund'))
        self.ui.top_btn.released.connect(self.toggle_stay_on_top)
        self.ui.vis_btn.setToolTip(_('Sichtbarkeit der Bildfläche an/aus [Tab]'))
        self.ui.vis_btn.released.connect(self.toggle_img_canvas)
        self.ui.input_btn.setToolTip(_('Maus und Tastatureingabe für Bildfläche de-/aktivieren'))
        self.ui.input_btn.released.connect(self.toggle_input_transparency)

        # --- DeltaGen Sync ---
        self.ui.sync_btn.setText(_('Sync DeltaGen Viewer'))
        self.ui.sync_btn.setToolTip(_('Bildfläche periodisch zum DeltaGen Viewer verschieben [F]'))
        self.ui.sync_btn.toggled.connect(self.dg_toggle_sync)
        self.ui.help_btn.setToolTip(_('Hilfe anzeigen'))
        self.ui.help_btn.pressed.connect(self.display_shortcuts)
        self.ui.focus_btn.setText(_('Pull DeltaGen Focus'))
        self.ui.focus_btn.pressed.connect(self.dg_toggle_pull)
        # Pulling focus is no longer necessary
        self.ui.focus_btn.hide()

        # --- DG Send thread controller ---
        self.dg_thread = SyncController(self)

        # --- Shortcuts ---
        self.shortcuts = ViewerShortcuts(self, self.ui)
        self.shortcuts.set_shortcuts(self.ui)

        # --- Drag n Drop ---
        self.drag_drop = DragNDropHandler(self)
        self.drag_drop.file_dropped.connect(self.ui.file_changed)

        # --- Info Overlay ---
        self.info_overlay = InfoOverlay(self)

        self.place_in_screen_center()

    def changeEvent(self, event):
        """ Not necessary when UI is normal window and is our parent.
            Used to be necessary when control window was also frameless.

        :param QEvent event:
        :return:
        """
        if event.type() == QEvent.WindowStateChange:
            if event.oldState() == Qt.WindowMinimized:
                LOGGER.debug('Restoring Image Overlay Window')
            if event.oldState() and Qt.WindowMinimized:
                LOGGER.debug('Image Overlay Window was restored')
            elif event.oldState() == Qt.WindowNoState:
                LOGGER.debug('Image Overlay Window minimized.')

    def display_shortcuts(self, keep_overlay: bool=True):
        msg = _('<h3>KnechtViewer Tastaturkürzel</h3>'
                '<ul>'
                '<li>Q/E - Bildfläche vergrößern/verkleinern</li>'
                '<li>A/D - Nächste/Vorherige Bilddatei</li>'
                '<li>W/S - Transparenz der Bildfläche erhöhen/verringern</li>'
                '<li>Tab - Bildfläche ein-/ausblenden</li>'
                '<li style="margin: 6px 0px;">'
                '<img src=":/main/collections.svg" width="24" height="24" '
                'style="float: left;vertical-align: middle;" />'
                'Bildfläche immer im Vordergrund ein-/ausschalten'
                '</li>'
                '<li style="margin: 6px 0px;">'
                '<img src=":/main/cursor.svg" width="24" height="24" '
                'style="float: left;vertical-align: middle;" />'
                'Bildfläche für Maus- und Tastatureingaben transparent machen'
                '</li>'
                '<li style="margin: 6px 0px;">'
                '<img src=":/main/compare.svg" width="24" height="24" '
                'style="float: left;vertical-align: middle;" />'
                'F   - DeltaGen Viewer Position und Größe synchronisieren'
                '</li>'
                '<li style="margin: 6px 0px;">'
                '<img src=":/main/locate.svg" width="24" height="24" '
                'style="float: left;vertical-align: middle;" />'
                'Bildfläche auf das gewählte Desktop Fenster verschieben'
                '</li>'
                '<li style="margin: 6px 0px;">'
                '<img src=":/main/videocam.png" width="24" height="24" '
                'style="float: left;vertical-align: middle;" />'
                'Kamera Daten aus Bildmetadaten an DeltaGen senden'
                '</li>'
                '</ul>'
                'Dateien oder Ordner auf die Bildfäche oder in das Bedienfenster ziehen um Bilddaten zu laden.'
                '<br><br>'
                'Unterstütze Formate: {}'
                ).format(' '.join(self.img_load_controller.FILE_TYPES))

        # Ensure visibility of image canvas
        if self.current_opacity < 0.7 or self.ui.vis_btn.isChecked():
            self.set_window_opacity(1.0)
            if self.ui.vis_btn.isChecked():
                self.ui.vis_btn.toggle()

        if keep_overlay:
            self.info_overlay.display_confirm(msg, (('[X]', None), ))
        else:
            self.info_overlay.display(msg, 6000)

    def set_default_image(self):
        self.current_img = IconRsc.get_pixmap('img_viewer_bg')
        self.img_canvas.setStyleSheet('background: rgba(0, 0, 0, 0);')
        self.img_canvas.setPixmap(self.current_img)
        self.img_size = self.current_img.size()
        self.img_size_factor = 1.0

        self.change_viewer_size()

    # ------ DeltaGen Sync -------
    def dg_toggle_btn(self, enabled: bool):
        """ Called by thread signal """
        self.ui.sync_btn.setEnabled(enabled)

    def dg_check_btn(self, checked: bool):
        """ Called by thread signal """
        self.ui.sync_btn.setChecked(checked)

    def dg_toggle_pull(self):
        """ Toggles pulling of the viewer window in front on/off """
        self.dg_thread.toggle_pull()

    def dg_toggle_sync(self):
        if not self.ui.sync_btn.isEnabled():
            return

        self.dg_thread.toggle_sync()

    # ------ IMAGES -------
    def set_img_path(self, file_path: Path):
        self.img_load_controller.set_img_path(file_path)
        self.ui.path_util.set_path_text(self.img_load_controller.img_dir)

    def _can_iterate_images(self) -> bool:
        if self.button_timeout.isActive():
            return False

        self.button_timeout.start()
        return True

    def iterate_fwd(self):
        if not self._can_iterate_images():
            return

        self.img_load_controller.iterate_fwd()

    def iterate_bck(self):
        if not self._can_iterate_images():
            return

        self.img_load_controller.iterate_bck()

    def no_image_found(self):
        self.set_default_image()
        self.ui.reset()

        self.info_overlay.display(_('Keine Bilddaten im Verzeichnis gefunden.'))

    def image_load_failed(self, error_msg=''):
        img_path = self.img_load_controller.current_image()

        if not error_msg:
            error_msg = img_path.as_posix()

        LOGGER.error('Could not load image file:\n%s', error_msg)

        self.set_default_image()
        self.ui.reset()

        self.img_loader = None

        self.info_overlay.display(_('Konnte keine Bilddaten laden: {}<br>{}').format(error_msg, img_path.as_posix()),
                                  8000, immediate=True)

    def image_loaded(self, image):
        def valid_img_name(img_path: Path) -> str:
            name = img_path.name
            if len(name) >= 85:
                name = f'{name[:65]}~{name[-20:]}'
            return name

        if not image:
            self.image_load_failed()
            return

        self.current_img = image

        self.img_canvas.setPixmap(self.current_img)
        self.img_size = self.current_img.size()
        self.change_viewer_size()

        prev_img_name = valid_img_name(self.img_load_controller.prev_image())
        img_name = valid_img_name(self.img_load_controller.current_image())
        next_img_name = valid_img_name(self.img_load_controller.next_image())

        self.ui.setWindowTitle(img_name)

        i = f'<span style="color: rgb(180, 180, 180);">' \
            f'{self.img_load_controller.get_valid_img_list_index(self.img_load_controller.img_index-1)+1:02d}/' \
            f'{len(self.img_load_controller.img_list):02d} - {prev_img_name}</span><br />'\
            f'{1+self.img_load_controller.img_index:02d}/' \
            f'{len(self.img_load_controller.img_list):02d} - {img_name}<br />' \
            f'<span style="color: rgb(180, 180, 180);">' \
            f'{self.img_load_controller.get_valid_img_list_index(self.img_load_controller.img_index+1)+1:02d}' \
            f'/{len(self.img_load_controller.img_list):02d} - {next_img_name}</span>'

        self.info_overlay.display(i, 3000, immediate=True)

    # ------ RESIZE -------
    def combo_box_size(self, idx):
        self.set_img_size_factor_from_combo_box()
        self.change_viewer_size()

    def set_img_size_factor_from_combo_box(self):
        data = self.ui.zoom_box.currentData()

        if data:
            self.img_size_factor = data

    def set_size_box_index(self, add_idx: int=0):
        cb = self.ui.zoom_box
        new_idx = min(cb.count() - 1, max(cb.currentIndex() + add_idx, 0))
        cb.setCurrentIndex(new_idx)

    def increase_size(self):
        self.set_size_box_index(1)
        self.set_img_size_factor_from_combo_box()
        self.change_viewer_size()

    def decrease_size(self):
        self.set_size_box_index(-1)
        self.set_img_size_factor_from_combo_box()
        self.change_viewer_size()

    def change_viewer_size(self):
        self.img_size_factor = max(0.01, min(self.img_size_factor, MAX_SIZE_FACTOR))

        w = round(self.img_size.width() * self.img_size_factor)
        h = round(self.img_size.height() * self.img_size_factor)
        new_size = QSize(w, h)

        self.resize_image_viewer(new_size)

    def resize_image_viewer(self, new_size: QSize):
        width = max(50, min(new_size.width(), self.MAX_SIZE.width()))
        height = max(50, min(new_size.height(), self.MAX_SIZE.height()))
        new_size = QSize(width, height)

        self.resize(new_size)

    # ------ OPACITY -------
    def increase_window_opacity(self):
        opacity = self.windowOpacity() + 0.15
        self.update_opacity_slider()
        self.set_window_opacity(opacity)

    def decrease_window_opacity(self):
        opacity = self.windowOpacity() - 0.15
        self.update_opacity_slider()
        self.set_window_opacity(opacity)

    def update_opacity_slider(self):
        self.ui.opacity_slider.setValue(round(self.windowOpacity() * self.ui.opacity_slider.maximum()))

    def set_opacity_from_slider(self):
        opacity = self.ui.opacity_slider.value() * 0.1
        self.set_window_opacity(opacity)

    def set_window_opacity(self, opacity):
        if self.shortcut_timeout.isActive():
            return

        opacity = max(0.05, min(1.0, opacity))
        self.current_opacity = opacity
        self.setWindowOpacity(opacity)

        self.shortcut_timeout.start()

    # --- Camera ----
    def camera_data_available(self, available: int):
        pal = QPalette()
        pal.setColor(QPalette.Button, QColor(240, 240, 240))

        if available == 0:
            self.ui.cam_btn.setEnabled(False)
        elif available == 1:
            self.ui.cam_btn.setEnabled(True)
        elif available == 2:
            pal.setColor(QPalette.Button, QColor(240, 150, 150))
            self.ui.cam_btn.setEnabled(True)

        self.ui.cam_btn.setAutoFillBackground(True)
        self.ui.cam_btn.setPalette(pal)
        self.ui.cam_btn.update()

    # ------ VISIBILITY -------
    def toggle_img_canvas(self):
        if self.shortcut_timeout.isActive():
            return

        if not self.ui.vis_btn.isChecked():
            self.setWindowOpacity(self.current_opacity)
        else:
            self.setWindowOpacity(0.0)

        self.shortcut_timeout.start()

    def _toggle_window_flag(self, window_flag: Qt) -> bool:
        enabled = False if self.windowFlags() & window_flag else True

        self.hide()
        self.setWindowFlag(window_flag, enabled)
        self.show()

        return enabled

    def switch_stay_on_top(self) -> bool:
        enabled = self._toggle_window_flag(Qt.WindowStaysOnTopHint)
        KnechtSettings.app['img_stay_on_top'] = enabled
        return enabled

    def toggle_stay_on_top(self):
        if self.shortcut_timeout.isActive():
            return

        enabled = self.switch_stay_on_top()
        self.info_overlay.display(_('Bildfläche erscheint nun nicht mehr im Vordergrund')
                                  if not enabled else _('Bildfläche erscheint nun immer im Vordergrund'),
                                  immediate=True)

        self.shortcut_timeout.start()

    def switch_input_transparency(self):
        enabled = self._toggle_window_flag(Qt.WindowTransparentForInput)
        KnechtSettings.app['img_input_transparent'] = enabled
        return enabled

    def toggle_input_transparency(self):
        if self.shortcut_timeout.isActive():
            return

        enabled = self.switch_input_transparency()
        self.info_overlay.display(_('Maus und Tastatureingabe für Bildfläche aktiviert.')
                                  if not enabled else _('Maus und Tastatureingabe für Bildfläche deaktiviert.'),
                                  immediate=True)

        self.shortcut_timeout.start()

    def hide_all(self):
        # self.ui.hide()
        self.hide()

    def show_all(self):
        self.place_inside_screen()
        self.showNormal()

        self.current_opacity = 1.0
        self.ui.opacity_slider.setValue(self.ui.opacity_slider.maximum())

    # ------ OVERRIDES -------
    def moveEvent(self, event):
        if self.moved_out_of_limit():
            event.ignore()
            return

        event.accept()

    def resizeEvent(self, event):
        if self.moved_out_of_limit():
            event.ignore()
            return

        event.accept()

    def moved_out_of_limit(self):
        limit = self.calculate_screen_limits()
        pos = self.geometry().topLeft()

        if not self.is_inside_limit(limit, pos):
            x = min(limit.width(), max(limit.x(), pos.x()))
            y = min(limit.height(), max(limit.y(), pos.y()))
            self.move(x, y)
            return True

        return False

    def place_inside_screen(self):
        limit = self.calculate_screen_limits()
        pos = self.geometry().topLeft()

        if not self.is_inside_limit(limit, pos):
            self.place_in_screen_center()

    def place_in_screen_center(self):
        screen = self.app.desktop().availableGeometry(self)

        center_x = screen.center().x() - self.geometry().width() / 2
        center_y = screen.center().y() - self.geometry().height() / 2

        self.move(center_x, center_y)

    def calculate_screen_limits(self):
        screen = QRect(self.app.desktop().x(), self.app.desktop().y(),
                       self.app.desktop().width(), self.app.desktop().availableGeometry().height())

        width_margin = round(self.geometry().width() / 2)
        height_margin = round(self.geometry().height() / 2)

        # Case where secondary screen has negative values
        desktop_width = screen.x() + screen.width()

        min_x = screen.x() - width_margin
        min_y = screen.y() - height_margin
        max_x = desktop_width - width_margin
        max_y = screen.height() - height_margin

        return QRect(min_x, min_y, max_x, max_y)

    def closeEvent(self, QCloseEvent):
        self.dg_thread.exit()
        self.ui.close()
        QCloseEvent.accept()

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)

        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    @staticmethod
    def is_inside_limit(limit: QRect, pos: QPoint):
        if pos.x() < limit.x() or pos.x() > limit.width():
            return False
        elif pos.y() < limit.y() or pos.y() > limit.height():
            return False

        return True
