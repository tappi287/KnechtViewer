import logging
import multiprocessing
import sys

from modules import logging_queue
from modules.main_app import ViewerApp
from modules.utils.globals import FROZEN, MAIN_LOGGER_NAME, Resource
from modules.utils.gui_utils import KnechtExceptionHook
from modules.utils.log import init_logging, setup_log_queue_listener
from modules.utils.settings import KnechtSettings, delayed_log_setup
from ui import viewer_resource

VERSION = '1.43'
LOGGER = init_logging(MAIN_LOGGER_NAME)


def shutdown(local_log_listener):
    #
    # ---- CleanUp ----
    # We do this just to prevent the IDE from deleting the imports
    viewer_resource.qCleanupResources()

    # Shutdown logging and remove handlers
    LOGGER.info('Shutting down log queue listener and logging module.')

    local_log_listener.stop()
    logging.shutdown()


def main():
    multiprocessing.freeze_support()
    if FROZEN:
        # Set Exception hook
        sys.excepthook = KnechtExceptionHook.exception_hook

    # Start log listening thread
    log_listener = setup_log_queue_listener(LOGGER, logging_queue)
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

    KnechtSettings.load()
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

    KnechtSettings.save()
    #
    #
    shutdown(log_listener)

    sys.exit(result)


if __name__ == '__main__':
    main()
