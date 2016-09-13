'''Utility to help "tail" AWS logs stored in S3 generated by S3 bucket logging or ELB logging.
'''
from builtins import str
from builtins import range
from builtins import object

import os
import logging

from configparser import SafeConfigParser
from boto import connect_s3
from boto.s3 import connect_to_region

from .cache import Cache

class S3Tail(object):
    '''An object that wraps the process of downloading and extracting lines from S3 files.

    Upon creation of the tail, the caller can next invoke :func:`S3Tail.watch` to begin the process
    of downloading files from S3 (or, opening them from the local file system cache) and invoking
    the provided `line_handler` to allow the caller to process each line in the file.

    :param bucket_name: the name of the S3 bucket from which files will be downloaded
    :param prefix: what objects in the S3 bucket should be matched
    :param line_handler: a function that will expect to be called for each line found in the
           downloaded files
    :param key_handler: a function that will expect to be called for each file
    :param bookmark: a location or name for where to pick up from a previous run
    :param region: a region to use when connection to the S3 bucket
    :param hours: the number of hours to keep files in the cache (0 will disable caching)
    '''

    BUFFER_SIZE = 1 * (1024*1024) # MiB
    '''Describes the number of bytes to read into memory when parsing lines.'''

    class MismatchedPrefix(Exception):
        '''Indicates when a prefix is provided that does not overlap with the requested bookmark.'''
        pass

    def __init__(self, bucket_name, prefix, line_handler,
                 key_handler=None, bookmark=None, region=None, hours=24):
        self._logger = logging.getLogger('s3tail')
        self._config = SafeConfigParser()
        self._config_fn = os.path.join(os.path.expanduser('~'), '.s3tailrc')
        if os.path.exists(self._config_fn):
            self._config.read(self._config_fn)
        self._cache = Cache(os.path.join(os.path.expanduser('~'), '.s3tailcache'), hours)
        if region:
            self._conn = connect_to_region(region)
        else:
            self._conn = connect_s3()
        self._bucket = self._conn.get_bucket(bucket_name)
        self._prefix = prefix
        self._line_handler = line_handler
        self._key_handler = key_handler
        self._set_bookmark(bookmark)
        self._marker = None
        self._buffer = None
        self._line_num = None

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
        for key in self._bucket.list(prefix=self._prefix, marker=self._bookmark_key):
            self._bookmark_key = None
            if self._key_handler:
                result = self._key_handler(key.name)
                if not result:
                    continue
            result = self._read(key)
            if result is not None:
                return result
            self._marker = key.name # marker always has to be _previous_ entry, not current

    def get_bookmark(self):
        '''Get a bookmark to represent the current location.'''
        if self._marker:
            return self._marker + ':' + str(self._line_num)
        if self._line_num:
            return ':' + str(self._line_num)

    def cleanup(self):
        '''Wait on any threads remaining and cleanup any unflushed state or configuration.'''
        self._save_bookmark()
        self._cache.cleanup()

    ######################################################################
    # private

    _BOOKMARKS = 'bookmarks'

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
        if self._config.has_section(S3Tail._BOOKMARKS):
            if self._config.has_option(S3Tail._BOOKMARKS, name):
                bookmark = self._config.get(S3Tail._BOOKMARKS, name)
                self._set_bookmark(bookmark)
                if bookmark.startswith(self._prefix):
                    self._logger.debug('Found %s bookmark: %s', name, bookmark)
                else:
                    self._prefix = os.path.commonprefix([self._prefix, bookmark])
                    if len(self._prefix) < 1:
                        raise S3Tail.MismatchedPrefix("Bookmark %s: %s" % (name, bookmark))
                    self._logger.warn('Adjusting prefix for %s bookmark to %s: %s',
                                      name, self._prefix, bookmark)

    def _save_bookmark(self):
        if not self._bookmark_name or not self._marker:
            return
        if not self._config.has_section(S3Tail._BOOKMARKS):
            self._config.add_section(S3Tail._BOOKMARKS)
        bookmark = self.get_bookmark()
        self._config.set(S3Tail._BOOKMARKS, self._bookmark_name, bookmark)
        with open(self._config_fn, 'wb') as configfile:
            self._config.write(configfile)
        self._logger.debug('Saved %s bookmark: %s', self._bookmark_name, bookmark)

    def _read(self, key):
        self._buffer = ''
        self._line_num = 0
        reader = self._cache.open(key.name, key)
        while not reader.closed:
            line = self._next_line(reader)
            self._line_num += 1
            if self._line_num < self._bookmark_line_num:
                continue
            self._bookmark_line_num = 0
            result = self._line_handler(self._line_num, line)
            if result is not None:
                return result
        self._bookmark_line_num = 0 # safety in case bookmark count was larger than actual lines

    def _next_line(self, reader):
        i = None
        for _ in range(0, 3): # try reading up to three times the buffer size
            i = self._buffer.find("\n")
            if i > -1:
                break
            more_data = reader.read(S3Tail.BUFFER_SIZE)
            if len(more_data) > 0:
                self._buffer += more_data
            else:
                reader.close()
                i = len(self._buffer) + 1 # use remaining info in buffer
                break
        line = self._buffer[0:i]
        self._buffer = self._buffer[i+1:]
        return line
