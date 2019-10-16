import os
import locale
import ctypes
from gettext import translation

from modules.utils.globals import get_current_modules_dir, APP_NAME


def get_ms_windows_language():
    """ Currently we only support english and german """
    windll = ctypes.windll.kernel32

    # Get the language setting of the Windows GUI
    try:
        os_lang = windll.GetUserDefaultUILanguage()
    except Exception as e:
        print(e)
        return

    # Convert language code to string
    lang = locale.windows_locale.get(os_lang)

    # Only return supported languages
    if not lang.startswith('de'):
        lang = 'en'

    # Return de or en
    return lang[:2]


def setup_translation(language=None):
    if not language:
        if not os.environ.get('LANGUAGE'):
            # Set from OS language en or de
            language = get_ms_windows_language()
            os.environ.setdefault('LANGUAGE', language)
    else:
        # Set language from settings
        os.environ.setdefault('LANGUAGE', language)

    # Setup OS locale for MS Windows
    # needed for eg. datetime weekday strings
    # https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-lcid/a9eac961-e77d-41a6-90a5-ce1a8b0cdb9c
    if language == 'de':
        locale.setlocale(category=locale.LC_ALL, locale="German")
    elif language == 'en':
        locale.setlocale(category=locale.LC_ALL, locale="English")


def get_translation():
    # Set OS language if not already set
    lang = os.environ.get('LANGUAGE')

    if not lang:
        print('Setting language from OS.')
        os.environ.setdefault('LANGUAGE', get_ms_windows_language())
        print('Local Language detected: ' + os.environ.get('LANGUAGE'))

    locale_dir = os.path.join(get_current_modules_dir(), 'locale')

    return translation(APP_NAME, localedir=locale_dir, codeset='UTF-8')
