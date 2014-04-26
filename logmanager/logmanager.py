from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import logging.handlers
import threading
import traceback
import sys
import os
import Queue
import multiprocessing
import atexit

MP = multiprocessing
mpQueue = MP.Queue


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
    local_logger = logging.getLogger(process_name.ljust(15, ' '))


def info(message):
    if local_logger:
        local_logger.info(message)


def start_log_server(level, dir_name, filename):
    log_queue = MP.Queue()
    global log_server
    log_server = LogServer(dir_name, filename, log_queue, level)
    log_server.start()
    set_log_queue(log_queue, "Main")
    info("<<<<<<<<<<<<<<<<<< Log File Opened >>>>>>>>>>>>>>>>>>\n")
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
        file_handler = None
        root_logger = logging.getLogger()
        try:
            if os.path.isfile(self.__dir_name):
                    print ("Unable to create log directory")
            elif not os.path.exists(self.__dir_name):
                os.makedirs(self.__dir_name)

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
        finally:
            root_logger.info("Log server shutting down\n")
            root_logger.info("<<<<<<<<<<<<<<<<<< Log File Closed >>>>>>>>>>>>>>>>>>\n\n\n")
        if file_handler:
                file_handler.flush()


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

        self._interrupted = False
        self.__mp_in_queue = mpQueue()
        self.__mp_out_queue = mpQueue()
        self.__name = name
        self.__log_queue = log_queue
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
        self.__started = False
        super(LoggingProcess, self).__init__(group, self._execute_wrapper, name, (), {})

    def mp_queue_get(self, block=True, timeout=None):
        return self.__mp_out_queue.get(block, timeout)

    def mp_queue_put(self, value):
        self.__mp_in_queue.put(value)

    def _mp_queue_get_internal(self, block=True, timeout=None):
        return self.__mp_in_queue.get(block, timeout)

    def _mp_queue_put_internal(self, data):
        self.__mp_out_queue.put(data)

    def get_log_queue(self):
        return self.__log_queue

    def start(self):
        super(LoggingProcess, self).start()
        if not self.__started:
            self.__started = True
            start_code = self.mp_queue_get(True, 2)
            if start_code != -1:
                raise Exception

    def _execute_wrapper(self):
        set_log_queue(self.__log_queue, self.__name)
        self._mp_queue_put_internal(-1)
        try:
            if self.__target:
                self.__target(*self.__args, **self.__kwargs)
        except Exception:
            log_exception()
