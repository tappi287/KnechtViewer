from multiprocessing import Queue

from modules.utils.log import init_logging, setup_log_queue_listener, setup_logging

print(f'Initial {__name__} log setup.')

#
# ---- StartUp ----
logging_queue = Queue(-1)
setup_logging(logging_queue)

print(f'Initial {__name__} log setup, done.')
