import sys

import logging
import multiprocessing
from multiprocessing import Queue

from modules.utils.globals import FROZEN, MAIN_LOGGER_NAME, Resource
from modules.utils.gui_utils import KnechtExceptionHook
from modules.main_app import ViewerApp
from modules.utils.log import init_logging, setup_log_queue_listener, setup_logging
from modules.utils.settings import KnechtSettings, delayed_log_setup
from ui import viewer_resource

VERSION = '1.0'


def initialize_log_listener(logging_queue):
    global LOGGER
    LOGGER = init_logging(MAIN_LOGGER_NAME)

    # This will move all handlers from LOGGER to the queue listener
    log_listener = setup_log_queue_listener(LOGGER, logging_queue)

    return log_listener


def shutdown(log_listener):
    #
    # ---- CleanUp ----
    # We do this just to prevent the IDE from deleting the imports
    viewer_resource.qCleanupResources()

    # Shutdown logging and remove handlers
    LOGGER.info('Shutting down log queue listener and logging module.')

    log_listener.stop()
    logging.shutdown()


def main():
    multiprocessing.freeze_support()
    if FROZEN:
        # Set Exception hook
        sys.excepthook = KnechtExceptionHook.exception_hook

    #
    # ---- StartUp ----
    # Start log queue listener in it's own thread
    logging_queue = Queue(-1)
    setup_logging(logging_queue)
    log_listener = initialize_log_listener(logging_queue)
    log_listener.start()

    # Setup KnechtSettings logger
    delayed_log_setup()

    LOGGER.debug('---------------------------------------')
    LOGGER.debug('Application start.')

    # Update version in settings
    KnechtSettings.app['version'] = VERSION

    # Load GUI resource paths
    if not KnechtSettings.load_ui_resources():
        LOGGER.fatal('Can not locate UI resource files! Shutting down application.')
        shutdown(log_listener)
        return

    print(Resource.ui_paths)

    #
    #
    # ---- Start application ----
    app = ViewerApp(VERSION)
    result = app.exec_()
    #
    #

    #
    #
    # ---- Application Result ----
    LOGGER.debug('---------------------------------------')
    LOGGER.debug('Qt application finished with exitcode %s', result)

    #
    #
    shutdown(log_listener)

    sys.exit(result)


if __name__ == '__main__':
    main()
