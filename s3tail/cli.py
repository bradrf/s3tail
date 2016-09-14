'''
Utility to help "tail" AWS logs stored in S3 generated by S3 bucket
logging or ELB logging.
'''
from builtins import object

import click
import sys
import signal
import errno
import logging
import re

from boto import s3

from .s3tail import S3Tail

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option()
@click.option('-r', '--region', type=click.Choice(r.name for r in s3.regions()),
              help='AWS region to use when connecting')
@click.option('-b', '--bookmark', help='Bookmark to start at (key:line or a named bookmark)')
@click.option('-l', '--log-level', type=click.Choice(['debug','info','warning','error','critical']),
              help='set logging level', default='info')
@click.option('--log-file', metavar='FILENAME',
              help='write logs to FILENAME', default='STDERR')
@click.option('--cache-hours', type=int, default=24,
              help='Number of hours to keep in cache before removing on next run (0 disables caching)')
@click.argument('s3_uri')
def main(region, bookmark, log_level, log_file, cache_hours, s3_uri):
    '''Begins tailing files found at [s3://]BUCKET[/PREFIX]'''

    s3_uri = re.sub(r'^(s3:)?/+', '', s3_uri)
    bucket, prefix = s3_uri.split('/', 1)

    log_kwargs = {
        'level': getattr(logging, log_level.upper()),
        'format': '[%(asctime)s #%(process)d] %(levelname)-8s %(name)-12s %(message)s',
        'datefmt': '%Y-%m-%dT%H:%M:%S%z',
    }
    if log_file != 'STDERR':
        log_kwargs['filename'] = log_file
    logging.basicConfig(**log_kwargs)
    logger = logging.getLogger('s3tail')

    class Track(object):
        tail = None
        last_key = None
        last_num = None
        show_pick_up = bookmark != None

    def progress(key):
        Track.last_key = key
        logger.info('Starting %s', key)
        return True

    def dump(num, line):
        Track.last_num = num
        if Track.show_pick_up:
            logger.info('Picked up at line %s', num)
            Track.show_pick_up = False
        click.echo(line)

    tail = S3Tail(bucket, prefix, dump,
                  key_handler=progress, bookmark=bookmark,
                  region=region, hours=cache_hours)

    signal.signal(signal.SIGINT, tail.stop)
    signal.signal(signal.SIGTERM, tail.stop)
    signal.signal(signal.SIGPIPE, tail.stop)

    try:
        tail.watch()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, _)
    except IOError as exc:
        if exc.errno != errno.EPIPE: raise
        # just exit if piped to something that has terminated (i.e. head or tail)
    finally:
        tail.cleanup()

    logger.info('Stopped processing at %s:%d', Track.last_key, Track.last_num)
    logger.info('Bookmark: %s', tail.get_bookmark())

    sys.exit(0)

if __name__ == '__main__':
    main()
