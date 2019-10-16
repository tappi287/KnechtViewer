from PySide2.QtGui import QFont, QFontDatabase, QIcon, QPixmap
from PySide2.QtMultimedia import QSound

from modules.utils.globals import Resource
from modules.utils.language import get_translation
from modules.utils.log import init_logging
from modules.utils.settings import KnechtSettings

LOGGER = init_logging(__name__)

# translate strings
lang = get_translation()
lang.install()
_ = lang.gettext


class IconRsc:
    # Store loaded icons here
    icon_storage = {
        'example_key': QIcon()
        }
    # Style Setting
    darkstyle = False

    @classmethod
    def get_app_style(cls):
        if KnechtSettings.app['app_style'] == 'fusion-dark':
            cls.darkstyle = True
        else:
            cls.darkstyle = False

    @classmethod
    def _get_icon_from_resource(cls, icon_key) -> QIcon:
        """ Return Icon from resource in either dark or default style,
            return empty icon if no resource with the given key exists.
        """
        if icon_key not in Resource.icon_paths.keys():
            return QIcon()

        icon_path = Resource.icon_paths.get(icon_key)

        if cls.darkstyle:
            dark_icon_key = icon_key + '_dark'

            if dark_icon_key in Resource.icon_paths.keys():
                icon_path = Resource.icon_paths.get(dark_icon_key)

        if not icon_path:
            return QIcon()

        return QIcon(QPixmap(icon_path))

    @classmethod
    def get_pixmap(cls, icon_key: str):
        if cls.darkstyle:
            icon_key = icon_key + '_dark'

        if icon_key not in Resource.icon_paths.keys():
            return QPixmap()

        return QPixmap(Resource.icon_paths[icon_key])

    @classmethod
    def get_icon(cls, icon_key: str):
        cls.get_app_style()

        if icon_key not in cls.icon_storage.keys():
            icon = cls._get_icon_from_resource(icon_key)
            cls.icon_storage[icon_key] = icon

        return cls.icon_storage[icon_key]


class FontRsc:
    font_storage = {
        'example_key': None
        }

    regular = None
    italic = None

    small_pixel_size = 16
    regular_pixel_size = 18
    big_pixel_size = 20

    default_font_key = 'Segoe UI'  # 'SourceSansPro-Regular'  # 'Segoe UI'

    @classmethod
    def init(cls, size: int=0):
        """
            Needs to be initialized after QApplication is running
            QFontDatabase is not available prior to app start
        """
        if not size:
            size = cls.regular_pixel_size

        cls.regular = QFont(cls.default_font_key)
        cls.regular.setPixelSize(size)
        cls.italic = QFont(cls.default_font_key)
        cls.italic.setPixelSize(size)
        cls.italic.setItalic(True)

    @classmethod
    def add_to_font_db(cls, font_key):
        font_id = QFontDatabase.addApplicationFont(Resource.icon_paths[font_key])
        cls.font_storage[font_key] = font_id
        LOGGER.debug('Font loaded and added to db: %s', QFontDatabase.applicationFontFamilies(font_id))

        return QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 8)

    @classmethod
    def get_font(cls, font_key) -> QFont():
        if font_key in cls.font_storage.keys():
            return QFont(QFontDatabase.applicationFontFamilies(cls.font_storage[font_key])[0], 8)

        if font_key in Resource.icon_paths.keys():
            return cls.add_to_font_db(font_key)

        return QFont()


class SoundRsc:
    storage = dict()  # resource key: resource_object

    hint = 'soneproject_sfx3'
    question = 'soneproject_ecofuture1'
    warning = 'soneproject_ecofuture2'
    finished = 'success'
    positive = 'positive'

    @classmethod
    def _get_resource_from_key(cls, resource_key, parent=None) -> QSound:
        if resource_key in cls.storage:
            return cls.storage.get(resource_key)

        if resource_key not in Resource.icon_paths.keys():
            return QSound('')

        rsc_path: str = Resource.icon_paths.get(resource_key)

        LOGGER.debug('Creating QSound for resource %s', rsc_path)

        sound_obj = QSound(rsc_path, parent)
        cls.storage[resource_key] = sound_obj

        return sound_obj

    @classmethod
    def get_sound(cls, sound_key, parent=None):
        return cls._get_resource_from_key(sound_key, parent)
