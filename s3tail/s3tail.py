'''Utility to help "tail" AWS logs stored in S3 generated by S3 bucket logging or ELB logging.
'''
from builtins import str
from builtins import range
from builtins import object

import os
import logging

from boto import connect_s3
from boto.s3 import connect_to_region

from .cache import Cache

# TODO: consider ability to search concurrently in cases where the timing isn't important (i.e. i'm
# just looking for matches, don't care about relative times). this would be faster to get w/
# multiple threads

# FIXME: control-c'd while tailing into gunzip -c:
#   File "/usr/local/bin/s3tail", line 11, in <module>
#     sys.exit(main())
#   File "/usr/local/lib/python2.7/dist-packages/click/core.py", line 716, in __call__
#     return self.main(*args, **kwargs)
#   File "/usr/local/lib/python2.7/dist-packages/click/core.py", line 696, in main
#     rv = self.invoke(ctx)
#   File "/usr/local/lib/python2.7/dist-packages/click/core.py", line 889, in invoke
#     return ctx.invoke(self.callback, **ctx.params)
#   File "/usr/local/lib/python2.7/dist-packages/click/core.py", line 534, in invoke
#     return callback(*args, **kwargs)
#   File "/usr/local/lib/python2.7/dist-packages/s3tail/cli.py", line 74, in main
#     tail.watch()
#   File "/usr/local/lib/python2.7/dist-packages/s3tail/s3tail.py", line 88, in watch
#     result = self._read(key)
#   File "/usr/local/lib/python2.7/dist-packages/s3tail/s3tail.py", line 177, in _read
#     result = self._line_handler(self._line_num, line)
#   File "/usr/local/lib/python2.7/dist-packages/s3tail/cli.py", line 63, in dump
#     click.echo(line)
#   File "/usr/local/lib/python2.7/dist-packages/click/utils.py", line 260, in echo
#     file.flush()
# IOError: [Errno 4] Interrupted system call

_logger = logging.getLogger(__name__)

class S3Tail(object):
    '''An object that wraps the process of downloading and extracting lines from S3 files.

    Upon creation of the tail, the caller can next invoke :func:`S3Tail.watch` to begin the process
    of downloading files from S3 (or, opening them from the local file system cache) and invoking
    the provided `line_handler` to allow the caller to process each line in the file.

    :param config: the configuration wrapper for saving bookmarks
    :param bucket_name: the name of the S3 bucket from which files will be downloaded
    :param prefix: what objects in the S3 bucket should be matched
    :param line_handler: a function that will expect to be called for each line found in the
           downloaded files
    :param key_handler: a function that will expect to be called for each file
    :param bookmark: a location or name for where to pick up from a previous run
    :param region: a region to use when connection to the S3 bucket
    :param cache_path: the path for where the cache should live (None will disable caching)
    :param hours: the number of hours to keep files in the cache (0 will disable caching)
    '''

    BUFFER_SIZE = 1 * (1024*1024) # MiB
    '''Describes the number of bytes to read into memory when parsing lines.'''

    MAX_BUFFER_SIZE = 5 * BUFFER_SIZE
    '''Describes the maximum amount of buffer to read into memory when parsing lines.'''

    class MismatchedPrefix(Exception):
        '''Indicates when a prefix is provided that does not overlap with the requested bookmark.'''
        pass

    def __init__(self, config, bucket_name, prefix, line_handler,
                 key_handler=None, bookmark=None, region=None, cache_path=None, hours=24):
        self._config = config
        if region:
            self._conn = connect_to_region(region)
        else:
            self._conn = connect_s3()
        self._bucket = self._conn.get_bucket(bucket_name)
        self._prefix = prefix
        self._line_handler = line_handler
        self._key_handler = key_handler or (lambda k,c,e: True)
        self._set_bookmark(bookmark)
        self._marker = None
        self._buffer = None
        self._line_num = None
        self._cache = Cache(cache_path, hours)

    def watch(self):
        '''Begin watching and reporting lines read from S3.

        This call will not return until all the files are read and processed or until a callback
        indicates the need to terminate processing early.

        Before reading each file, the optional `key_handler` provided when created will be invoked
        with the name of the S3 key. If the `key_handler` returns a "falsey" value the key will be
        skipped and the tail will move on to the next key.

        For every line parsed from the files found in S3, the `line_handler` provided when created
        will be invoked passing along the line number and line to the callback. If the
        `line_handler` returns a result (i.e. if it is not ``None``), processessing is terminated
        and the result will be returned from the call to `watch`.
        '''
        self._stopped = False
        for key in self._bucket.list(prefix=self._prefix, marker=self._bookmark_key):
            if self._stopped:
                break
            self._bookmark_key = None
            cache_pn, cached = self._cache.lookup(key.name)
            result = self._key_handler(key.name, cache_pn, cached)
            if not result:
                continue
            result = self._read(key)
            if result is not None:
                return result
            self._marker = key.name # marker always has to be _previous_ entry, not current
            self._line_num = 0

    def get_bookmark(self):
        '''Get a bookmark to represent the current location.'''
        if self._marker:
            return self._marker + ':' + str(self._line_num)
        if self._line_num:
            return ':' + str(self._line_num)

    def stop(self, *args):
        '''Request that a running watch should terminate processing at the next earliest convenience.

        This can be most useful if the tail is running in a separate thread and/or if the caller is
        trying to process an interrupt condition (i.e. from a signal or keyboard request). The
        arguments are ignored and allow this to be directly passed in as a signal handler::

            signal.signal(signal.SIGPIPE, tail.stop)
        '''
        self._stopped = True

    def cleanup(self):
        '''Wait on any threads remaining and cleanup any unflushed state or configuration.'''
        self._save_bookmark()
        self._cache.cleanup()

    ######################################################################
    # private

    def _set_bookmark(self, bookmark):
        self._bookmark_name = None
        self._bookmark_key = None
        self._bookmark_line_num = 0
        if not bookmark:
            return
        if ':' in bookmark:
            # an explicit key:line bookmark
            self._bookmark_key, self._bookmark_line_num = bookmark.split(':')
            if len(self._bookmark_key) == 0:
                self._bookmark_key = None
            else:
                self._bookmark_line_num = int(self._bookmark_line_num)
        else:
            # a named bookmark
            self._lookup_bookmark_name(bookmark)
            self._bookmark_name = bookmark

    def _lookup_bookmark_name(self, name):
        bookmark = self._config.bookmarks[name]
        if not bookmark:
            return
        self._set_bookmark(bookmark)
        if bookmark.startswith(self._prefix):
            _logger.debug('Found %s bookmark: %s', name, bookmark)
        else:
            self._prefix = os.path.commonprefix([self._prefix, bookmark])
            if len(self._prefix) < 1:
                raise self.MismatchedPrefix("Bookmark %s: %s" % (name, bookmark))
            _logger.warn('Adjusting prefix for %s bookmark to %s: %s',
                              name, self._prefix, bookmark)

    def _save_bookmark(self):
        if not self._bookmark_name or not self._marker:
            return
        bookmark = self.get_bookmark()
        self._config.bookmarks[self._bookmark_name] = bookmark
        self._config.save()
        _logger.debug('Saved %s bookmark: %s', self._bookmark_name, bookmark)

    def _read(self, key):
        reader = self._open_reader(key)
        while not reader.closed:
            if self._stopped:
                return self.stop
            line = self._next_line(reader)
            if not line: # normal closed reader with nothing else in the buffer
                break
            self._line_num += 1
            if self._line_num < self._bookmark_line_num:
                continue
            self._bookmark_line_num = 0
            result = self._line_handler(self._line_num, line)
            if result is not None:
                return result
        self._bookmark_line_num = 0 # safety in case bookmark count was larger than actual lines

    def _open_reader(self, key):
        self._buffer = ''
        self._line_num = 0
        return self._cache.open(key.name, key)

    # TODO: convert this into a wrapper that yields lines!
    def _next_line(self, reader):
        newline = self._find_newline_index(reader)
        if newline:
            line = self._buffer[0:newline]
            self._buffer = self._buffer[newline+1:]
        else:
            if len(self._buffer) == 0 and reader.closed:
                return None
            _logger.warn('Unable to locate newline in %s after line %d', reader.name, self._line_num)
            line = self._buffer
            self._buffer = ''
        return line

    def _find_newline_index(self, reader):
        i = self._buffer.find("\n")
        if i > -1:
            return i
        while True:
            buflen = len(self._buffer)
            if buflen + self.BUFFER_SIZE > self.MAX_BUFFER_SIZE:
                break
            more_data = reader.read(self.BUFFER_SIZE)
            if len(more_data) > 0:
                self._buffer += more_data
                i = more_data.find("\n")
                if i > -1:
                    return buflen + i
            else:
                reader.close()
                break
        return None
