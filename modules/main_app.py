import sys

from PySide2.QtCore import QEvent, QTimer, Qt, Signal
from PySide2.QtWidgets import QApplication

from modules.utils.globals import APP_NAME
from modules.main_ui import ViewerWindow
from modules.utils.log import init_logging
from modules.utils.settings import KnechtSettings
from modules.utils.ui_resource import FontRsc

LOGGER = init_logging(__name__)


def load_style(app):
    # Load font size
    if not KnechtSettings.app.get('font_size'):
        KnechtSettings.app['font_size'] = FontRsc.regular_pixel_size

    FontRsc.init(KnechtSettings.app['font_size'])
    app.setFont(FontRsc.regular)


class ViewerApp(QApplication):
    idle_event = Signal()

    def __init__(self, version: str):
        super(ViewerApp, self).__init__(sys.argv)
        self.setApplicationName(f'{APP_NAME}')
        self.setApplicationVersion(version)
        self.setApplicationDisplayName(f'{APP_NAME} v{version}')
        load_style(self)

        self.idle_timer = QTimer()
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setTimerType(Qt.VeryCoarseTimer)
        self.idle_timer.setInterval(3 * 60 * 1000)  # 3 min until idle
        self.idle_timer.timeout.connect(self.set_idle)
        self.installEventFilter(self)

        self.window = ViewerWindow(self)
        self.window.show()

    def eventFilter(self, obj, eve):
        if eve is None or obj is None:
            return False

        if eve.type() == QEvent.KeyPress or \
           eve.type() == QEvent.MouseMove or \
           eve.type() == QEvent.MouseButtonPress:
            self.set_active()
            return False

        return False

    def set_active(self):
        self.idle_timer.start()

    def set_idle(self):
        LOGGER.debug('Application is idle.')
        self.idle_event.emit()
