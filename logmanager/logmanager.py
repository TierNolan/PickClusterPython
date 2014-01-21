import logging
import logging.handlers
import threading
import traceback
import sys
import os
import Queue
import multiprocessing as MP
import atexit


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
    log_queue = MP.Queue()
    global log_server
    log_server = LogServer(dir_name, filename, log_queue, level)
    log_server.start()
    set_log_queue(log_queue, "Main")
    info("<<<<<<<<<<<<<<<<<< Log File Opened >>>>>>>>>>>>>>>>>>")
    atexit.register(stop_log_server)
    return log_queue


def stop_log_server():
    log_server.shutdown()
    log_server.join()


class LogServer(MP.Process):
    def __init__(self, dir_name, filename, log_queue, level):
        super(LogServer, self).__init__(name="Log Server Thread", target=self._execute)
        self.__filename = filename
        self.__dir_name = dir_name
        self.__log_queue = log_queue
        self.__level = level

    def shutdown(self):
        self.__log_queue.put(None)

    def _execute(self):
        if os.path.isfile(self.__dir_name):
            print "Unable to create log directory"
        elif not os.path.exists(self.__dir_name):
            os.makedirs(self.__dir_name)

        root_logger = logging.getLogger()

        logging.basicConfig(level=self.__level)
        file_handler = logging.handlers.RotatingFileHandler(self.__dir_name + "/" + self.__filename, 'a', 1024*100, 5)

        logging.getLogger().addHandler(file_handler)

        formatter = logging.Formatter(
            fmt="%(asctime)s %(name)s %(levelname)s: %(message)s",
            datefmt="%d-%m %H:%M:%S"
        )

        file_handler.setFormatter(formatter)
        record = True
        while record:
            try:
                record = self.__log_queue.get(True, 10.0)
            except Queue.Empty:
                file_handler.flush()
                record = True
                continue
            if record:
                root_logger.handle(record)


def log_exception():
    if local_logger:
        exception_info = traceback.format_exception(*sys.exc_info())
        for line in exception_info:
            sub_lines = line.splitlines()
            for sub_line in sub_lines:
                local_logger.critical(sub_line)


class LoggingThread(threading.Thread):
        def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, verbose=None):
            self.__target = target
            self.__args = args
            self.__kwargs = kwargs
            super(LoggingThread, self).__init__(group, self.__execute_wrapper, name, (), {}, verbose)

        def __execute_wrapper(self):
            try:
                if self.__target:
                    self.__target(*self.__args, **self.__kwargs)
            except Exception:
                log_exception()


class LoggingProcess(MP.Process):
    def __init__(self, log_queue, group=None, target=None, name=None, args=(), kwargs={}):
        if not name:
            raise Exception

        self.__name = name.ljust(10, ' ')
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
        except Exception:
            log_exception()
