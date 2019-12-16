import sys
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
    def __init__(self, version: str):
        super(ViewerApp, self).__init__(sys.argv)
        self.setApplicationName(f'{APP_NAME}')
        self.setApplicationVersion(version)
        self.setApplicationDisplayName(f'{APP_NAME} v{version}')
        load_style(self)

        self.window = ViewerWindow(self)
        self.window.show()
