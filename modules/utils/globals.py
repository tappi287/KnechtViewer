import sys
import os
print('Python %s on %s' % (sys.version, sys.platform))

APP_NAME = 'KnechtViewer'
UI_PATH = 'ui'
UI_PATHS_FILE = 'viewer_gui_resource_paths.json'
UI_RSC_FILE = 'res/viewer_resource.qrc'

LOG_FILE_NAME = 'knechtviewer.log'
MAIN_LOGGER_NAME = 'knecht_main'

SETTINGS_FILE = 'settings.json'
SETTINGS_DIR_NAME = APP_NAME

# Viewer specific
MAX_SIZE = (4096, 4096)

MAX_SIZE_FACTOR = 2.5
MIN_SIZE_FACTOR = 0.25
SIZE_INCREMENT = 0.25
EXTRA_SIZE_FACTORS = [0.10, 0.15, 0.6666666, 1.3333333]
FILE_TYPES = ['.png', '.jpg', '.jpeg', '.tif', '.tga', '.hdr', '.exr']

# Updater Urls
# https://piwigo.ilikeviecher.com/ftp-upload/knecht2/version.txt
UPDATE_DIR_URL = 'https://piwigo.ilikeviecher.com/ftp-upload/knecht2/'
UPDATE_VERSION_FILE = 'version.txt'
UPDATE_INSTALL_FILE = 'KnechtViewer_Setup_{version}_win64.exe'

# DeltaGen address
DG_TCP_IP = 'localhost'
DG_TCP_PORT = 3333

# Frozen or Debugger
if getattr(sys, 'frozen', False):
    # -- Running in PyInstaller Bundle ---
    FROZEN = True
else:
    # -- Running in IDE ---
    FROZEN = False


def get_current_modules_dir():
    """ Return path to this app modules directory """
    # Path to this module OR path to PyInstaller executable directory _MEIPASS
    mod_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__ + '/../..')))

    return mod_dir


def get_settings_dir() -> str:
    _app_data = os.getenv('APPDATA')

    _knecht_settings_dir = os.path.join(_app_data, SETTINGS_DIR_NAME)

    if not os.path.exists(_knecht_settings_dir):
        try:
            os.mkdir(_knecht_settings_dir)
        except Exception as e:
            print('Error creating settings directory', e)
            return ''

    return _knecht_settings_dir


class Resource:
    """
        Qt resource paths for ui files and icons.
        Will be loaded from json dict on startup.

        create_gui_resource.py will create the json file for us.
        ui_path[filename] = relative path to ui file
        icon_path[filename] = Qt resource path
    """
    ui_paths = dict()
    icon_paths = dict()