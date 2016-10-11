from builtins import chr
from builtins import range
from builtins import object
import os
import logging

from hashlib import sha256
from tempfile import NamedTemporaryFile

from .background_writer import BackgroundWriter
from .old_file_cleaner import OldFileCleaner

_logger = logging.getLogger(__name__)

class Cache(object):
    readers = []

    def __init__(self, path, hours):
        _logger = logging.getLogger('s3tail.cache')
        self.path = path
        self.enabled = True
        if not self.path or hours < 1:
            self.enabled = False
            return
        if not os.path.isdir(path):
            os.mkdir(path)
            # create shard buckets for sha hexstring names
            chars = list(range(ord('0'), ord('9')+1)) + list(range(ord('a'), ord('f')+1))
            for i in chars:
                for j in chars:
                    os.mkdir(os.path.join(path, chr(i)+chr(j)))
        else:
            cleaner = OldFileCleaner(path, hours)
            cleaner.start()

    def open(self, name, reader):
        if not self.enabled:
            return reader.open()

        safe_name = sha256(name).hexdigest()
        cache_pn = os.path.join(self.path, safe_name[0:2], safe_name)
        if os.path.exists(cache_pn):
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug('Found %s in cache: %s', name, cache_pn)
            else:
                _logger.info('Found %s in cache', name)
                return open(cache_pn)

        return Cache._Reader(name, reader, cache_pn)

    def cleanup(self):
        for reader in Cache.readers:
            reader.cleanup()

    ######################################################################
    # private

    class _Reader(object):
        def __init__(self, name, reader, cache_pn):
            self.name = name
            self.closed = False
            _logger = logging.getLogger('s3tail.cache.reader')
            self._reader = reader
            self._final_size = reader.size
            self._cache_pn = cache_pn
            # write to a tempfile in case of failure; move into place when writing is complete
            head, tail = os.path.split(cache_pn)
            self._tempfile = NamedTemporaryFile(dir=head, prefix=tail+'_')
            self._writer = BackgroundWriter(self._tempfile, self._move_into_place)
            self._writer.start()
            self._reader.open()
            Cache.readers.append(self)

        def read(self, size=-1):
            data = self._reader.read(size)
            self._writer.write(data)
            return data

        def close(self):
            self._reader.close()
            self._writer.mark_done() # allow writer to finish async, not requiring caller to wait
            self.closed = True

        def cleanup(self):
            self._writer.join()

        def _move_into_place(self, _):
            self._tempfile.delete = False # prevent removal on close
            self._tempfile.close()
            temp_size = os.path.getsize(self._tempfile.name)
            if temp_size == self._final_size:
                os.rename(self._tempfile.name, self._cache_pn)
                Cache.readers.remove(self)
                _logger.debug('Placed: %s', self._cache_pn)
            else:
                os.remove(self._tempfile.name)
                _logger.debug('Not keeping in cache (expected %d bytes, wrote %d): %s',
                                   self._final_size, temp_size, self._tempfile.name)
