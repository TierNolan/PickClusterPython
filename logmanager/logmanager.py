import logging
import logging.handlers
import threading
import traceback
import os
import sys
import multiprocessing as MP


class QueueHandler(logging.Handler):
    def __init__(self, queue):
        super(QueueHandler, self).__init__()
        self.__queue = queue

    def get_queue(self):
        return self.__queue

    def emit(self, record):
        try:
            self.__queue.put(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

local_logger = None
log_server = None


def exception_handler(typ, value, traceback):
    if local_logger:
        local_logger.info("Caught exception")
        # local_logger.critical("Exception thrown")
        # local_logger.critical("Type: %s" % typ)
        # local_logger.critical("Value: %s" % value)
        # local_logger.critical("Traceback: %s" % traceback)
    else:
        print "No local logger"


def set_log_queue(queue, process_name):
    queue_handler = QueueHandler(queue)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)
    global local_logger
    local_logger = logging.getLogger(process_name)


def info(message):
    if local_logger:
        local_logger.info(message)


def start_log_server(level, dir_name, filename):
    if os.path.isfile(dir_name):
        print "Unable to create log directory"
    elif not os.path.exists(dir_name):
        os.makedirs(dir_name)
    logging.basicConfig(level=level)
    file_handler = logging.handlers.RotatingFileHandler(dir_name + "/" + filename, 'a', 102400, 5)
    formatter = logging.Formatter(
        fmt="%(asctime)s: %(name)s: %(levelname)s: %(message)s",
        datefmt="%d-%m %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)
    log_queue = MP.Queue()
    global log_server
    log_server = LogServer(log_queue)
    log_server.start()
    return log_queue


def stop_log_server():
    log_server.shutdown()


class LogServer(threading.Thread):
    def __init__(self, log_queue):
        super(LogServer, self).__init__(target=self._execute)
        self.__log_queue = log_queue
        self.__root_logger = logging.getLogger()

    def shutdown(self):
        self.__log_queue.put(None)

    def _execute(self):
        record = True
        while record:
            record = self.__log_queue.get()
            if record:
                self.__root_logger.handle(record)


class LoggingThread(threading.Thread):
        def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
            self.__target = target
            self.__args = args
            self.__kwargs = kwargs
            super(LoggingThread, self).__init__(group, self.__execute_wrapper, name, None, None, verbose)

        def __execute_wrapper(self):
            try:
                if self.__target:
                    self.__target(*self.__args, **self.__kwargs)
            except Exception as e:
                if local_logger:
                    local_logger.exception(e)


class LoggingProcess(MP.Process):
    def __init__(self, log_queue, group=None, target=None, name=None, args=(), kwargs={}):
        if not name:
            raise Exception

        self.__name = name
        self.__log_queue = log_queue
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
        super(LoggingProcess, self).__init__(group, self._execute_wrapper, name, (), {})

    def _execute_wrapper(self):
        set_log_queue(self.__log_queue, self.__name)
        try:
            if self.__target:
                self.__target(*self.__args, **self.__kwargs)
        except Exception as e:
            if local_logger:
                exception_info = traceback.format_exception(*sys.exc_info())
                for line in exception_info:
                    sub_lines = line.splitlines()
                    for sub_line in sub_lines:
                        local_logger.critical(sub_line)