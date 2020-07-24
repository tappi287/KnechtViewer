from pathlib import Path
from threading import Thread

from PySide2.QtCore import QObject, QThread, Signal, QTimer
from PySide2.QtGui import QImage, QPixmap

from modules.knecht_socket import Ncat
from modules.utils.camera_info import ImageCameraInfo
from modules.utils.globals import DG_TCP_IP, DG_TCP_PORT
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.img_utils import read_to_qpixmap
from modules.utils.settings import KnechtSettings

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class KnechtLoadImage(QThread):
    loaded_img = Signal(object)
    load_failed = Signal(str)
    found_camera_data = Signal(ImageCameraInfo)

    def __init__(self, parent, img_file):
        super(KnechtLoadImage, self).__init__()
        self.parent = parent
        self.img_file = img_file

    def run(self):
        try:
            image = read_to_qpixmap(self.img_file)

            if isinstance(image, QPixmap):
                self.loaded_img.emit(image)
                self.search_camera_data()
                return
            elif isinstance(image, str):
                self.load_failed.emit(image)
                return

            self.load_failed.emit('Unknown result')
        except Exception as e:
            self.load_failed.emit(str(e))

    def search_camera_data(self):
        # -- Load Camera Data if available
        try:
            cam_info_img = ImageCameraInfo(self.img_file)
            cam_info_img.read_image()

            if cam_info_img.is_valid():
                self.found_camera_data.emit(cam_info_img)
        except Exception as e:
            LOGGER.warning(e, exc_info=1)


class KnechtLoadImageController(QObject):
    camera_available = Signal(int)
    FILE_TYPES = ('.png', '.jpg', '.jpeg', '.tif', '.tga', '.hdr', '.exr', '.psd')

    def __init__(self, parent):
        """ Controller object to iterate images inside a given path/directory
            and load them threaded.

        :param modules.img_view.ImageView parent:
        """
        super(KnechtLoadImageController, self).__init__(parent)
        self.img_view = parent

        self.img_dir = Path('.')
        self.current_cam = None
        self.img_list = list()
        self.img_index = 0

        self.img_loader = None

        self.load_timeout = QTimer()
        self.load_timeout.setSingleShot(True)
        self.load_timeout.setInterval(5000)
        self.load_timeout.timeout.connect(self.kill_load_thread)

    # ------ IMAGES -------
    def set_img_path(self, img_file_path: Path, skip_load: bool=False):
        if img_file_path.is_file():
            self.img_dir = img_file_path.parent
        else:
            self.img_dir = img_file_path

        self.list_img_files(img_file_path)
        KnechtSettings.app['current_path'] = self.img_dir.as_posix()
        LOGGER.debug('Updated settings path with %s', self.img_dir.as_posix())
        if not skip_load:
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

    def get_valid_img_list_index(self, idx: int):
        if idx < 0:
            return len(self.img_list) - 1
        if idx >= len(self.img_list):
            return 0

        return idx

    def iterate_images(self):
        self.reset_camera_data()

        if not self.img_list:
            self.img_view.no_image_found()
            return

        self.img_index = self.get_valid_img_list_index(self.img_index)

        img_path = self.img_list[self.img_index]
        LOGGER.info('Image load Controller iterated to image: %s', img_path.as_posix())
        self.create_image_load_thread(img_path)

    def current_image(self):
        return self.img_list[self.img_index]

    def prev_image(self):
        return self.img_list[self.get_valid_img_list_index(self.img_index - 1)]

    def next_image(self):
        return self.img_list[self.get_valid_img_list_index(self.img_index + 1)]

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
            self.img_loader.found_camera_data.connect(self._camera_data_found)

            self.img_loader.finished.connect(self._img_loader_finished)

            self.img_loader.start()
            self.load_timeout.start()

    def reset_camera_data(self):
        self.current_cam = None
        self.camera_available.emit(0)

    def _camera_data_found(self, cam_info: ImageCameraInfo):
        self.current_cam = cam_info
        LOGGER.debug('Found camera data in image: %s', cam_info.create_deltagen_camera_cmd())

        if cam_info.validate_offsets():
            self.camera_available.emit(1)
        else:
            # Camera contains offsets
            self.camera_available.emit(2)

    def _img_loader_finished(self):
        LOGGER.debug('Image Load Thread finished.')
        self.img_loader.deleteLater()
        self.img_loader = None

    def _image_loaded(self, image: QPixmap):
        self._add_recent_entry(self.img_list[self.img_index])
        self.load_timeout.stop()
        self.img_view.image_loaded(image)

    def _image_load_failed(self, error_msg: str):
        self.img_view.image_load_failed(error_msg)
        self.load_timeout.stop()

    @staticmethod
    def _add_recent_entry(file: Path):
        directory = file.parent
        recent_dirs = set([Path(d) for d, _ in KnechtSettings.app.get('recent_files', list())])

        if directory not in recent_dirs:
            KnechtSettings.add_recent_file(directory, 'directory')

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
