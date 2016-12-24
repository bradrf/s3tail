from builtins import chr
from builtins import range
from builtins import object

import os
import logging
import zlib

from hashlib import sha256
from tempfile import NamedTemporaryFile

from .background_writer import BackgroundWriter
from .old_file_cleaner import OldFileCleaner

_logger = logging.getLogger(__name__)

class Cache(object):
    readers = []

    def __init__(self, path, hours):
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

    def lookup(self, name):
        if self.enabled:
            cache_pn = self._cache_path_for(name)
            cached = os.path.exists(cache_pn)
            return (cache_pn, cached)
        return (None, False)

    def open(self, name, reader):
        if not self.enabled:
            return self._open_reader(name, reader)

        cache_pn, cached = self.lookup(name)
        if cached:
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug('Found %s in cache: %s', name, cache_pn)
            else:
                _logger.info('Found %s in cache', name)
                return open(cache_pn)

        return self._Reader(name, self._open_reader(name, reader), cache_pn)

    def cleanup(self):
        for reader in self.readers:
            reader.cleanup()

    ######################################################################
    # private

    def _cache_path_for(self, name):
        safe_name = sha256(name).hexdigest()
        return os.path.join(self.path, safe_name[0:2], safe_name)

    def _open_reader(self, name, reader):
        reader.open()
        if name.endswith('.gz'): # TODO: lame! use header magic numbers for decompression algorithm
            # return GzipFile(fileobj=reader)
            return self._Decompressor(reader)
        return reader

    class _Decompressor(object):
        def __init__(self, reader):
            self._reader = reader
            self._decompressor = zlib.decompressobj(32 + zlib.MAX_WBITS)

        def read(self, size=-1):
            data = self._reader.read(size)
            return self._decompressor.decompress(data)

        def close(self):
            self._reader.close()

    class _Reader(object):
        def __init__(self, name, reader, cache_pn):
            self.name = name
            self.closed = False
            self._logger = logging.getLogger(__name__ + 'reader')
            self._reader = reader
            self._at_eof = False
            self._cache_pn = cache_pn
            # write to a tempfile in case of failure; move into place when writing is complete
            head, tail = os.path.split(cache_pn)
            self._tempfile = NamedTemporaryFile(dir=head, prefix=tail+'_')
            self._writer = BackgroundWriter(self._tempfile, self._move_into_place)
            self._writer.start()
            Cache.readers.append(self)

        def read(self, size=-1):
            data = self._reader.read(size)
            if size < 1 or len(data) < size:
                self._at_eof = True
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
            if self._at_eof:
                os.rename(self._tempfile.name, self._cache_pn)
                Cache.readers.remove(self)
                self._logger.debug('Placed: %s', self._cache_pn)
            else:
                os.remove(self._tempfile.name)
                self._logger.debug('Not keeping in cache (did not read all data): %s',
                                   self._tempfile.name)
