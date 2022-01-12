import json
import os
import time
import zlib
from pathlib import Path
from typing import Union, Any

import jsonpickle

from modules.utils.globals import Resource, UI_PATH, UI_PATHS_FILE, SETTINGS_FILE, DG_TCP_PORT
from modules.utils.globals import get_current_modules_dir, get_settings_dir
from modules.utils.language import setup_translation


def delayed_log_setup():
    from modules.utils.log import init_logging
    global LOGGER
    LOGGER = init_logging(__name__)


# jsonpickle.set_preferred_backend('ujson')


class Settings:
    """
        Load and save methods to save class attributes of setting classes
    """
    @staticmethod
    def load(obj: object, file):
        try:
            with open(file, 'r') as f:
                load_dict = json.load(f)
        except Exception as e:
            print('Could not load setting data:\n', e)
            return

        for key, attr in load_dict.items():
            setattr(obj, key, attr)

    @staticmethod
    def load_from_bytes(obj, data: bytes):
        load_dict = json.loads(data)

        for key, attr in load_dict.items():
            setattr(obj, key, attr)

    @staticmethod
    def save(obj: object, file: Union[Path, str]):
        save_dict = dict()

        for key, value in obj.__dict__.items():
            if key.startswith('__'):
                # Skip internal attributes
                continue

            if not Settings.is_serializable(value):
                # Skip non-serializable data
                continue

            LOGGER.debug('Saving %s: %s', key, value)
            save_dict.update({key: value})

        try:
            with open(file, 'w') as f:
                json.dump(save_dict, f)

            msg = 'Saved settings to file: {}'.format(file.absolute().as_posix())
            LOGGER.info(msg)
            print(msg)
        except Exception as e:
            LOGGER.error('Could not save file!\n%s', e)
            print('Could not save file!\n%s', e)

    @staticmethod
    def is_serializable(data: Any) -> bool:
        if isinstance(data, (int, str, float, bool, list, dict, tuple)):
            return True
        return False

    @staticmethod
    def pickle_save(obj: object, file: Path, compressed: bool=False) -> bool:
        try:
            w = 'wb' if compressed else 'w'
            with open(file.as_posix(), w) as f:
                if compressed:
                    f.write(zlib.compress(jsonpickle.encode(obj).encode('UTF-8'), level=1))
                else:
                    f.write(jsonpickle.encode(obj))

            msg = 'Jsonpickled settings object: {} to file: {}'.format(type(obj), file.absolute().as_posix())
            LOGGER.info(msg)
            print(msg)
            return True
        except Exception as e:
            LOGGER.error('Could not save file!\n%s', e)
            print('Could not save file!\n%s', e)
        return False

    @staticmethod
    def pickle_load(file: Path, compressed: bool=False) -> object:
        obj = None

        try:
            start = time.time()
            r = 'rb' if compressed else 'r'

            with open(file.as_posix(), r) as f:
                if compressed:
                    obj = jsonpickle.decode(zlib.decompress(f.read()))
                else:
                    obj = jsonpickle.decode(f.read())
            LOGGER.info('Pickle loaded object in %.2f: %s', time.time() - start, type(obj))

        except Exception as e:
            LOGGER.error('Error jsonpickeling object from file. %s', e)

        return obj


class KnechtSettings:
    """
        Store and Re-store application settings

        Settings are stored inside this class as class attributes(not instanced)
    """
    dark_style = {'bg_color': (26, 29, 30)}

    # --- Default values ----
    app = dict(
        version='0.0.0',
        current_path='',
        introduction_shown=False,
        app_style='fusion',
        font_size=20,
        port=DG_TCP_PORT,
        )

    language = 'de'

    @classmethod
    def load(cls) -> None:
        file = Path(cls.get_settings_path())

        try:
            if not file or not file.exists():
                print('Could not locate settings file! Using default settings!')
                return
        except OSError as e:
            print('Could not locate settings file! Using default settings!\n', e)
            return

        default_settings = dict()
        default_settings['app'] = dict()
        default_settings['app'].update(cls.app)

        Settings.load(KnechtSettings, file)

        # Update settings attributes with default settings if
        # eg. setting not available in previous versions
        for settings_key, settings_dict in default_settings.items():
            if settings_key not in ['app']:
                continue

            settings_attr = dict()

            if settings_key == 'app':
                settings_attr = cls.app

            for k, v in settings_dict.items():
                if k not in settings_attr:
                    settings_attr[k] = v

        # Clean up recent files
        updated_recent_files = list()
        for idx, entry in enumerate(cls.app.get('recent_files') or [('file.xml', 'xml')]):
            entry_file, entry_type = entry

            try:
                if Path(entry_file).exists():
                    updated_recent_files.append((entry_file, entry_type))
            except OSError as e:
                print('Can not access path: ', e)

        cls.app['recent_files'] = updated_recent_files

        cls.setup_lang()
        print('KnechtSettings successfully loaded from file.')

    @classmethod
    def save(cls) -> None:
        file = Path(cls.get_settings_path())

        if not file:
            LOGGER.warning('Could not save settings file! No setting will be saved.')
            return

        Settings.save(cls, file)

    @staticmethod
    def setup_lang():
        setup_translation(language=KnechtSettings.language)
        print('Application language loaded from settings: ', KnechtSettings.language)

    @classmethod
    def load_ui_resources(cls) -> bool:
        """ update app globals with GUI resource paths """
        ui_paths_file = Path(get_current_modules_dir()) / Path(UI_PATH) / Path(UI_PATHS_FILE)

        if not ui_paths_file.exists():
            print('Could not locate gui resource file: %s. Aborting application.',
                   ui_paths_file.absolute().as_posix())
            return False

        try:
            Settings.load(Resource, ui_paths_file)
        except Exception as e:
            print('Could not load GUI resources from file %s. Aborting application. Error:\n%s',
                   ui_paths_file.absolute().as_posix(), e)
            return False
        return True

    @classmethod
    def add_recent_file(cls, file: Union[Path, str], file_type: str='') -> None:
        if 'recent_files' not in cls.app.keys():
            cls.app['recent_files'] = list()

        file_str = Path(file).as_posix()
        recent_files = cls.app['recent_files']

        # Remove already existing/duplicate entry's
        for idx, entry in enumerate(recent_files):
            entry_file, entry_type = entry

            if file_str == entry_file and file_type == entry_type:
                recent_files.pop(idx)
                break

        recent_files.insert(0, (file_str, file_type))

        # Only keep the last [list_length] number of items
        if len(recent_files) > 10:
            cls.app['recent_files'] = recent_files[:10]

    @staticmethod
    def get_settings_path() -> str:
        _settings_dir = get_settings_dir()
        _settings_file = os.path.join(_settings_dir, SETTINGS_FILE)

        return _settings_file
