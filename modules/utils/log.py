import sys
from pathlib import Path
import logging
import logging.config

from logging.handlers import QueueHandler, QueueListener
from PySide2.QtCore import QObject, Signal

from modules.utils.globals import get_settings_dir, LOG_FILE_NAME, FROZEN, MAIN_LOGGER_NAME


def setup_logging(logging_queue, overwrite_level: str=None):
    # Track calls to this method
    print('Logging setup called: ',
          Path(sys._getframe().f_back.f_code.co_filename).name,
          sys._getframe().f_back.f_code.co_name)

    if FROZEN:
        log_level = 'INFO'
    else:
        log_level = 'DEBUG'
    if overwrite_level:
        log_level = overwrite_level

    log_file_path = Path(get_settings_dir()) / Path(LOG_FILE_NAME)

    log_conf = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
                },
            'simple': {
                'format': '%(asctime)s %(name)s %(levelname)s: %(message)s',
                'datefmt': '%d.%m.%Y %H:%M'
                },
            'guiFormatter': {
                'format': '%(name)s %(levelname)s: %(message)s',
                'datefmt': '%d.%m.%Y %H:%M',
                },
            'file_formatter': {
                'format': '%(asctime)s.%(msecs)03d %(name)s %(levelname)s: %(message)s',
                'datefmt': '%d.%m.%Y %H:%M:%S'
                },
            },
        'handlers': {
            'console': {
                'level': log_level, 'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout', 'formatter': 'simple'
                },
            'guiHandler': {
                'level': log_level, 'class': 'logging.NullHandler',
                'formatter': 'simple',
                },
            'file': {
                'level': log_level, 'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_file_path.absolute().as_posix(), 'maxBytes': 5000000, 'backupCount': 4,
                'formatter': 'file_formatter',
                },
            'queueHandler': {
                'level': log_level, 'class': 'logging.handlers.QueueHandler',
                # From Python 3.7.1 defining a formatter will output the formatter of the queueHandler
                # as well as the re-routed handler formatter eg. console -> queue listener
                'queue': logging_queue
                },
            },
        'loggers': {
            # Main logger, these handlers will be moved to the QueueListener
            MAIN_LOGGER_NAME: {
                'handlers': ['file', 'guiHandler', 'console'], 'propagate': False, 'level': log_level,
                },
            # Log Window Logger
            'gui_logger': {
                'handlers': ['guiHandler', 'queueHandler'], 'propagate': False, 'level': 'INFO'
                },
            # Module loggers
            '': {
                'handlers': ['queueHandler'], 'propagate': False, 'level': log_level,
                }
            }
        }

    logging.config.dictConfig(log_conf)


def setup_log_queue_listener(logger, queue):
    """
        Moves handlers from logger to QueueListener and returns the listener
        The listener needs to be started afterwwards with it's start method.
    """
    handler_ls = list()
    for handler in logger.handlers:
        print('Removing handler that will be added to queue listener: ', str(handler))
        handler_ls.append(handler)

    for handler in handler_ls:
        logger.removeHandler(handler)

    handler_ls = tuple(handler_ls)
    queue_handler = QueueHandler(queue)
    logger.addHandler(queue_handler)

    listener = QueueListener(queue, *handler_ls)
    return listener


def init_logging(logger_name):
    logger_name = logger_name.replace('modules.', '')
    logger = logging.getLogger(logger_name)

    print('Logger requested by: ',
          Path(sys._getframe().f_back.f_code.co_filename).name,
          sys._getframe().f_back.f_code.co_name, logging.getLevelName(logger.getEffectiveLevel()))

    return logger


class _HandlerSignal(QObject):
    log_message = Signal(str)


class QPlainTextEditHandler(logging.Handler):
    """ Log handler that appends text to QPlainTextEdit """

    def __init__(self):
        super(QPlainTextEditHandler, self).__init__()
        self.Signal_cls = _HandlerSignal()
        self.log_message = self.Signal_cls.log_message

    def emit(self, record):
        msg = None

        try:
            msg = self.format(record)
            self.log_message.emit(msg)
        except Exception as e:
            # MS Visual Studio 15.4.x BUG ?, channel is not defined
            print(e)
            pass


class LoggerDummy:
    @staticmethod
    def debug(*args):
        return

    @staticmethod
    def info(*args):
        return

    @staticmethod
    def warning(*args):
        return

    @staticmethod
    def error(*args):
        return
