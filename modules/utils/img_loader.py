from pathlib import Path

from PySide2.QtCore import QObject, QThread, Signal, QTimer
from PySide2.QtGui import QImage, QPixmap

from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.img_utils import read_to_qpixmap

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class KnechtLoadImage(QThread):
    loaded_img = Signal(object)
    load_failed = Signal(str)

    def __init__(self, parent, img_file):
        super(KnechtLoadImage, self).__init__()
        self.parent = parent
        self.img_file = img_file

    def run(self):
        try:
            image = read_to_qpixmap(self.img_file)

            if isinstance(image, QPixmap):
                self.loaded_img.emit(image)
                return
            elif isinstance(image, str):
                self.load_failed.emit(image)
                return

            self.load_failed.emit('Unknown result')
        except Exception as e:
            self.load_failed.emit(str(e))


class KnechtLoadImageController(QObject):
    FILE_TYPES = ('.png', '.jpg', '.jpeg', '.tif', '.tga', '.hdr', '.exr', '.psd')

    def __init__(self, parent):
        """ Controller object to iterate images inside a given path/directory
            and load them threaded.

        :param modules.img_view.ImageView parent:
        """
        super(KnechtLoadImageController, self).__init__(parent)
        self.img_view = parent

        self.img_dir = Path('.')
        self.current_img = None
        self.img_list = list()
        self.img_index = 0

        self.img_loader = None

        self.load_timeout = QTimer()
        self.load_timeout.setSingleShot(True)
        self.load_timeout.setInterval(5000)
        self.load_timeout.timeout.connect(self.kill_load_thread)

    # ------ IMAGES -------
    def set_img_path(self, img_file_path: Path):
        if img_file_path.is_file():
            self.img_dir = img_file_path.parent
        else:
            self.img_dir = img_file_path

        self.list_img_files(img_file_path)
        self.iterate_images()

    def list_img_files(self, current_file: Path):
        self.img_index = 0
        self.img_list = list()

        for img_file in self.img_dir.glob('*.*'):
            if img_file.suffix.casefold() in self.FILE_TYPES:
                self.img_list.append(img_file)

        if current_file in self.img_list:
            current_idx = self.img_list.index(current_file)
            self.img_index = current_idx
            LOGGER.debug('Current file set to: %s', current_idx)

    def iterate_fwd(self):
        if not self._image_loader_available():
            return

        self.img_index += 1
        self.iterate_images()

    def iterate_bck(self):
        if not self._image_loader_available():
            return

        self.img_index -= 1
        self.iterate_images()

    def iterate_images(self):
        if not self.img_list:
            self.img_view.no_image_found()
            return

        if self.img_index < 0:
            self.img_index = len(self.img_list) - 1

        if self.img_index >= len(self.img_list):
            self.img_index = 0

        img_path = self.img_list[self.img_index]
        LOGGER.info('Image load Controller iterated to image: %s', img_path.as_posix())
        self.create_image_load_thread(img_path)

    def current_image(self):
        return self.img_list[self.img_index]

    def _image_loader_available(self):
        if self.img_loader is not None and self.img_loader.isRunning():
            return False
        return True

    def create_image_load_thread(self, img_path: Path):
        if not self.img_loader:
            LOGGER.debug('Starting image load thread for: %s', img_path.as_posix())
            self.img_loader = KnechtLoadImage(self, img_path)

            self.img_loader.loaded_img.connect(self._image_loaded)
            self.img_loader.load_failed.connect(self._image_load_failed)

            self.img_loader.finished.connect(self._img_loader_finished)

            self.img_loader.start()
            self.load_timeout.start()

    def _img_loader_finished(self):
        LOGGER.debug('Image Load Thread finished.')
        self.img_loader.deleteLater()
        self.img_loader = None

    def _image_loaded(self, image: QPixmap):
        self.load_timeout.stop()
        self.img_view.image_loaded(image)

    def _image_load_failed(self, error_msg: str):
        self.img_view.image_load_failed(error_msg)
        self.load_timeout.stop()

    def kill_load_thread(self):
        LOGGER.error('Image load timeout exceeded. Trying to kill load thread.')

        if self.img_loader is not None and self.img_loader.isRunning():
            self.img_loader.exit()
            LOGGER.error('Waiting for Image loader to exit.')
            self.img_loader.wait(msecs=3000)

            if self.img_loader.isRunning():
                LOGGER.error('Image loader exit took too long. Trying to terminate the QThread.')
                self.img_loader.terminate()

                # Thread terminated, application should be restarted
                self.close()

                if self.img_loader.isRunning():
                    LOGGER.error('Could not terminate Image loader QThread.')

                self.image_load_failed()
            self.img_loader = None
