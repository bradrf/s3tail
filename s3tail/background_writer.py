from queue import Queue
from threading import Thread

class BackgroundWriter(Thread):
    def __init__(self, writer, done_callback=None):
        '''Wraps a writer I/O object with background write calls.

        Optionally, will call the done_callback just before the thread stops (to allow caller to
        close/operate on the writer)
        '''
        super(BackgroundWriter, self).__init__()
        self._done = False
        self._done_callback = done_callback
        self._queue = Queue()
        self._writer = writer

    def write(self, data):
        self._queue.put(data)

    def mark_done(self):
        if not self._done:
            self._done = True
            self._queue.put(True)

    def join(self, timeout=None):
        self.mark_done()
        self._queue.join()
        super(BackgroundWriter, self).join(timeout)

    def run(self):
        while True:
            data = self._queue.get()
            if data is True:
                self._queue.task_done()
                if self._done_callback:
                    self._done_callback(self._writer)
                return
            self._writer.write(data)
            self._queue.task_done()
