from pathlib import Path

from PySide2.QtCore import Qt, Signal, QObject
from PySide2.QtGui import QDragMoveEvent
from PySide2.QtWidgets import QComboBox, QWidget, QMenu, QAction

from modules.utils.globals import EXTRA_SIZE_FACTORS, MAX_SIZE_FACTOR, MIN_SIZE_FACTOR, SIZE_INCREMENT
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.path_util import path_exists
from modules.utils.settings import KnechtSettings
from modules.utils.ui_resource import IconRsc

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class ViewerSizeBox(QComboBox):
    def __init__(self, parent):
        super(ViewerSizeBox, self).__init__(parent)

        self.setFocusPolicy(Qt.ClickFocus)

        min = round(MIN_SIZE_FACTOR * 100)
        max = round((MAX_SIZE_FACTOR + SIZE_INCREMENT) * 100)
        step = round(SIZE_INCREMENT * 100)

        for s in range(min, max, step):
            while EXTRA_SIZE_FACTORS and s * 0.01 > EXTRA_SIZE_FACTORS[0]:
                xs = EXTRA_SIZE_FACTORS.pop(0)
                self.addItem(f'{xs * 100:.2f}%', float(xs))
                LOGGER.debug(f'Setting up ComboBox item: {xs * 100:.2f}% - {s:02d}')

            self.addItem(f'{s:02d}%', s * 0.01)

    def reset(self):
        """ Reset to 100% / 1.0 """
        idx = self.findData(1.0)
        self.setCurrentIndex(idx)


class FileMenu(QMenu):
    def __init__(self, ui):
        """
        :param modules.main_ui.ViewerWindow ui: main window
        """
        super(FileMenu, self).__init__()
        self.ui = ui

        self.change_path = QAction(IconRsc.get_icon('folder'), _('Verzeichnis auswählen'))
        self.change_path.triggered.connect(self.ui.path_btn.click)
        self.addAction(self.change_path)

        self.addSeparator()

        self.recent_actions = list()

        self.aboutToShow.connect(self.update_recent_files)

    def open_recent_file(self):
        recent_action = self.sender()
        self.ui.file_changed(recent_action.file)

    def _clear_recent_actions(self):
        while self.recent_actions:
            action = self.recent_actions.pop()
            self.removeAction(action)

    def update_recent_files(self):
        self._clear_recent_actions()

        if not len(KnechtSettings.app['recent_files']):
            no_entries_dummy = QAction(_("Keine Einträge vorhanden"), self)
            no_entries_dummy.setEnabled(False)
            self.recent_actions.append(no_entries_dummy)

        for idx, entry in enumerate(KnechtSettings.app['recent_files']):
            if idx >= 20:
                break

            file, file_type = entry
            file = Path(file)
            file_name = f'...{str(file.parent)[-25:]}\\{file.name}'

            if not path_exists(file):
                # Skip and remove non existing files
                KnechtSettings.app['recent_files'].pop(idx)
                continue

            recent_action = QAction(f'{file_name} - {file_type}', self)
            recent_action.file = file

            recent_action.setText(f'{file_name}')
            recent_action.setIcon(IconRsc.get_icon('img'))
            recent_action.triggered.connect(self.open_recent_file)

            self.recent_actions.append(recent_action)

        self.addActions(self.recent_actions)
