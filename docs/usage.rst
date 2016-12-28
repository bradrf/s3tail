=====
Usage
=====

.. code-block:: console

    $ s3tail --help

    Usage: s3tail [OPTIONS] S3_URI

      Begins tailing files found at [s3://]BUCKET[/PREFIX]

    Options:
      --version                       Show the version and exit.
      -c, --config-file PATH          Configuration file  [default:
                                      /Users/brad/.s3tailrc]
      -r, --region [us-east-1|us-west-1|us-gov-west-1|ap-northeast-2|ap-northeast-1|sa-east-1|eu-central-1|ap-southeast-1|ca-central-1|ap-southeast-2|us-west-2|us-east-2|ap-south-1|cn-north-1|eu-west-1|eu-west-2]
                                      AWS region to use when connecting
      -b, --bookmark TEXT             Bookmark to start at (key:line or a named
                                      bookmark)
      -l, --log-level [debug|info|warning|error|critical]
                                      set logging level
      --log-file FILENAME             write logs to FILENAME
      --cache-hours INTEGER           Number of hours to keep in cache before
                                      removing on next run (0 disables caching)
      --cache-lookup                  Report if s3_uri keys are cached (showing
                                      pathnames if found)
      -h, --help                      Show this message and exit.


Configuration
-------------

Follow the instructions provided by the Boto Python interface to AWS:
http://boto.cloudhackers.com/en/latest/boto_config_tut.html

Optionally, following can be configured to override the defaults by editing a configuration
file. Normally, this file stores bookmark information, but can also include a section for setting
command line options.

An example might look like this (usually lives in the executing user's ``HOME`` directory as
``.s3tailrc``):

.. code-block:: ini

    [bookmarks]
    barf = production/s3/collab-production-s3-access-2016-09-11-02-26-19-718F6332DA1867B6:2935
    last-look = production/s3/collab-production-s3-access-2016-09-18-21-27-17-79EB845D49F9F7E9:1611

    [options]
    cache_hours = 1
    cache_path = /Users/brad/.s3tailcache
    log_level = warn

Option descriptions:

* ``cache_hours``: Any integer describing the number of hours to keep items in the cache before they
  are discarded (can be a value of zero to disable the cache entirely).

* ``cache_path``: The full pathname to a directory for storing cached files when downloading from S3.

* ``log_file``: The full pathname to a file for writing all log output (only logs from s3tail;
  content extracted from S3 files is always written to standard output (``STDOUT``).

* ``log_level``: Any one of ``debug``, ``info``, ``warning``, ``error``, or ``critical``.

* ``region``: The AWS region for accessing S3 (see
  http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region).

Any options specified on the command line itself always will have preference over those stated in
the configuration file.


Basic Console Example
---------------------

.. code-block:: console

    $ s3tail s3://my-logs/production-s3-access-2016-08-04


Coding Example
--------------

To use the :class:`.s3tail.S3Tail` class in a project:

.. code-block:: python

    from s3tail import S3Tail
    from configparser import ConfigParser

    def process_line(num, line):
        print '%d: %s' % (num, line)

    config = ConfigParser() # stores the bookmarks
    tail = S3Tail(config, 'my-logs', 'production-s3-access-2016-08-04', process_line)
    tail.watch()
    tail.cleanup()

    print 'stopped at bookmark ' + tail.get_bookmark()

.. _go-access-example:

GoAccess Example
----------------

A great use for s3tail is as a data provider to the amazing GoAccess_ utility that can provide
beautiful visualization of traffic logs.

First, build GoAccess_ with the ability track incremental progress in a local database. The
following works when building on Ubuntu Trusty:

.. code-block:: console

    $ wget http://tar.goaccess.io/goaccess-1.0.2.tar.gz

    $ apt-get install libgeoip-dev libncursesw5-dev libtokyocabinet-dev libz-dev libbz2-dev

    $ ./configure --enable-geoip --enable-utf8 --enable-tcb=btree --with-getline

    $ make

    $ make install

Next, build a configuration file for GoAccess_. The ``log-format`` should match nicely with the `S3
Log Format`_. Many `GoAccess configuration options`_ are available, but the following works quite
well (e.g. placed in ``~/.goaccessrc_s3``):

.. code-block:: none

   date-format %d/%b/%Y
   time-format %H:%M:%S %z
   log-format %^ %v [%d:%t] %h %^ %^ %^ %^ "%m %U %H" %s %^ %b %^ %L %^ "%R" "%u" %~
   agent-list true
   4xx-to-unique-count true
   with-output-resolver true
   load-from-disk true
   keep-db-files true

Periodically, run something like the following to download and analyze traffic reported into an S3
bucket. Through the use of s3tail's named bookmark (``goaccess-traffic`` in the example below), each
successive run will pick up where s3tail left off on the previous run, continuing to read and feed
logs into GoAccess_:

.. code-block:: console

   $ s3tail --log-file /var/log/s3tail.log -b goaccess-traffic my-logs/production-s3-access-2016-08-04 | \
       goaccess -p ~/.goaccessrc_s3 -o ~/report.json

At any time, GoAccess_ can view the current dataset via it's wonderful CLI, generate a self-contained
HTML report, or make use of the live preview provided via a websocket (e.g. http://rt.goaccess.io/
is a live demo)!

.. code-block:: console

   $ goaccess -p ~/.goaccessrc_s3

.. _GoAccess: https://goaccess.io/
.. _GoAccess configuration options: https://github.com/allinurl/goaccess/blob/master/config/goaccess.conf
.. _S3 Log Format: http://docs.aws.amazon.com/AmazonS3/latest/dev/LogFormat.html
