import logging

from queue import Queue
from threading import Thread

_logger = logging.getLogger(__name__)

class BackgroundWriter(Thread):
    class WriteAfterDone(Exception):
        '''Indicates when an action is taken after requested to stop.'''

    def __init__(self, writer, done_callback=None):
        '''Wraps a writer I/O object with background write calls.

        Optionally, will call the done_callback just before the thread stops (to allow caller to
        close/operate on the writer)
        '''
        super(BackgroundWriter, self).__init__()
        _logger = logging.getLogger('s3tail.writer')
        self._done = False
        self._done_callback = done_callback
        self._queue = Queue()
        self._writer = writer
        self.name = writer.name

    def write(self, data):
        if self._done:
            raise self.WriteAfterDone('Refusing to write when stopping ' + self.name)
        self._queue.put(data)

    def mark_done(self):
        if not self._done:
            self._done = True
            _logger.debug('Asked to stop writing to %s', self.name)
            self._queue.put(True)

    def join(self, timeout=None):
        _logger.debug('Joining %s', self.name)
        self.mark_done()
        self._queue.join()
        super(BackgroundWriter, self).join(timeout)

    def run(self):
        while True:
            data = self._queue.get()
            if data is True:
                _logger.debug('Stopping %s', self.name)
                self._queue.task_done()
                if self._done_callback:
                    self._done_callback(self._writer)
                return
            self._writer.write(data)
            self._queue.task_done()
