from logging import Formatter, INFO, StreamHandler, getLogger, handlers
from os import mkdir, sep
from os.path import exists
from time import sleep


class Logger:
    def __init__(self, filename=f'logs{sep}logs.log', grade=INFO):
        if not exists("logs"):
            mkdir("logs")
        self.logger = getLogger(__name__)
        format_str = Formatter('[%(asctime)s] [%(levelname)s]: %(message)s', '%Y-%m-%d %H:%M:%S')
        self.logger.setLevel(grade)
        sh = StreamHandler()
        sh.setFormatter(format_str)
        th = handlers.TimedRotatingFileHandler(filename=filename, when='D', encoding='utf-8')
        th.setFormatter(format_str)
        self.logger.addHandler(sh)
        self.logger.addHandler(th)

    def set_level(self, level):
        self.logger.setLevel(level)

    def debug(self, *args):
        self.logger.debug(' '.join([str(i) for i in args]))
        sleep(0.3)

    def info(self, *args):
        self.logger.info(' '.join([str(i) for i in args]))
        sleep(0.3)

    def warn(self, *args):
        self.logger.warning(' '.join([str(i) for i in args]))
        sleep(0.3)
