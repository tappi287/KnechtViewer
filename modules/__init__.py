from multiprocessing import Queue

try:
    from modules.utils.log import init_logging, setup_log_queue_listener, setup_logging
except ImportError as e:
    print(e)

print(f'Initial {__name__} log setup.')

#
# ---- StartUp ----
try:
    logging_queue = Queue(-1)
    setup_logging(logging_queue)
except Exception as e:
    print(e)

print(f'Initial {__name__} log setup, done.')
