import os
import logging

from threading import Thread
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class OldFileCleaner(Thread):
    def __init__(self, path, hours):
        super(OldFileCleaner, self).__init__()
        self._path = path
        self._hours = hours

    def run(self):
        count = 0
        for dirpath, _, filenames in os.walk(self._path):
            for ent in filenames:
                curpath = os.path.join(dirpath, ent)
                file_modified = datetime.fromtimestamp(os.path.getatime(curpath))
                if datetime.now() - file_modified > timedelta(hours=self._hours):
                    _logger.debug('Removing %s', curpath)
                    os.remove(curpath)
                    count += 1
        if count > 0:
            _logger.info('Cleaned up %d files', count)
