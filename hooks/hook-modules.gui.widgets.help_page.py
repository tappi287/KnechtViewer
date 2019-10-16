"""
    Collect files for QWebEngineWidgets on win32 currently broken hooks in PyInstaller
    see https://justcode.nimbco.com/PyInstaller-with-Qt5-WebEngineView-using-PySide2/#could-not-find-qtwebengineprocessexe-on-windows
    Also see the qt bug report:
    https://bugreports.qt.io/browse/PYSIDE-626


    Collect:
    QtWebEngineProcess.exe    -> '.'
    PySide2/resources         -> './PySide2/resources'
    PySide2/translations      -> './PySide2/translations'
    qt.conf                   -> '.'
"""
import os
import logging
from PyInstaller.utils.hooks import collect_data_files

logger = logging.getLogger('user_hooks_logger')
web_engine_exe = 'QtWebEngineProcess.exe'

datas = list()


def reroute(collected, dest_dir):
    rerouted_collecton = list()
    for (src, dest) in collected:
        rerouted_collecton.append(
            (src, dest_dir)
            )
    return rerouted_collecton


# --- Create qt.conf pointing executable to resources ---
qt_conf = '[Paths]\nPrefix = PySide2\nLibraryExecutables = .'
qt_conf_file = os.path.abspath(os.path.join('hooks', 'qt.conf'))
with open(qt_conf_file, 'w') as f:
    f.write(qt_conf)
datas.append((qt_conf_file, '.'))

# --- Collect QtWebEngineProcess resources ---
datas += collect_data_files('PySide2', subdir='resources')

# --- Collect QtWebEngineProcess translation resources ---
datas += collect_data_files('PySide2', subdir='translations')

# --- Collect QtWebEngineProcess executable ---
collected_datas = [x for x in collect_data_files('PySide2') if x[0].endswith(web_engine_exe)]
if collected_datas:
    logger.info('Collected %s', web_engine_exe)
else:
    logger.warning('%s could not be found!', web_engine_exe)
datas += reroute(collected_datas, '.')

logger.info('Collected PySide2 %s resource data: %s files.', web_engine_exe, len(datas))
