from pathlib import Path

from PySide2.QtCore import Qt, Signal, QObject
from PySide2.QtGui import QDragMoveEvent, QFont
from PySide2.QtWidgets import QComboBox, QWidget, QMenu, QAction

from modules.utils.globals import EXTRA_SIZE_FACTORS, MAX_SIZE_FACTOR, MIN_SIZE_FACTOR, SIZE_INCREMENT
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.path_util import path_exists
from modules.utils.settings import KnechtSettings
from modules.utils.ui_resource import IconRsc, FontRsc

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
    small_font = QFont(FontRsc.default_font_key)
    small_font.setPixelSize(FontRsc.small_pixel_size)

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
        self.recent_section = self.addSection(_('Kürzlich verwendete Verzeichnisse'))

        self.recent_actions = list()

        self.aboutToShow.connect(self.update_recent_files)

    def open_recent_dir(self):
        recent_action = self.sender()
        self.ui.file_changed(recent_action.file)

    def _clear_recent_actions(self):
        while self.recent_actions:
            action = self.recent_actions.pop()
            self.removeAction(action)

    def update_recent_files(self):
        self._clear_recent_actions()

        if not len(KnechtSettings.app.get('recent_files', list())):
            no_entries_dummy = QAction(_("Keine Einträge vorhanden"), self)
            no_entries_dummy.setEnabled(False)
            self.recent_actions.append(no_entries_dummy)

        recent_directories = set()
        for idx, entry in enumerate(KnechtSettings.app.get('recent_files')):
            if idx >= 20:
                break

            file, file_type = entry
            file = Path(file)

            if file.is_file():
                directory = file.parent
            else:
                directory = file

            if not path_exists(directory):
                # Skip non existing files/dirs
                continue

            recent_directories.add(directory)

        if recent_directories:
            KnechtSettings.app['recent_files'] = [(d.as_posix(), 'directory') for d in recent_directories]

        for directory in recent_directories:
            if len(str(directory)) > 95:
                name = f'...{str(directory)[-95:]}'
            else:
                name = str(directory)

            recent_action = QAction(name, self.recent_section)

            recent_action.setFont(self.small_font)
            recent_action.file = directory

            recent_action.setIcon(IconRsc.get_icon('img'))
            recent_action.triggered.connect(self.open_recent_dir)

            self.recent_actions.append(recent_action)

        self.addActions(self.recent_actions)
