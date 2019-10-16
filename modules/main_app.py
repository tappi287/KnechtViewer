import sys
from PySide2.QtWidgets import QApplication

from modules.utils.globals import APP_NAME
from modules.main_ui import ViewerWindow
from modules.utils.log import init_logging

LOGGER = init_logging(__name__)


class ViewerApp(QApplication):
    def __init__(self, version: str):
        super(ViewerApp, self).__init__(sys.argv)
        self.setApplicationName(APP_NAME)
        self.setApplicationVersion(version)
        self.setApplicationDisplayName(self.applicationName())

        self.window = ViewerWindow(self)
        self.window.show()
