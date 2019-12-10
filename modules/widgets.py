from PySide2.QtCore import Qt, Signal, QObject
from PySide2.QtGui import QDragMoveEvent
from PySide2.QtWidgets import QComboBox, QWidget

from modules.utils.globals import EXTRA_SIZE_FACTORS, MAX_SIZE_FACTOR, MIN_SIZE_FACTOR, SIZE_INCREMENT
from modules.utils.language import get_translation
from modules.utils.log import init_logging

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
