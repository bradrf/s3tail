=====
Usage
=====

.. code-block:: console

    $ s3tail --help

    Usage: s3tail [OPTIONS] S3_URI

      Begins tailing files found at [s3://]BUCKET[/PREFIX]

    Options:
      --version                       Show the version and exit.
      -r, --region [us-east-1|us-west-1|cn-north-1|ap-northeast-1|ap-southeast-2|sa-east-1|ap-southeast-1|ap-northeast-2|us-west-2|us-gov-west-1|ap-south-1|eu-central-1|eu-west-1]
                                      AWS region to use when connecting
      -b, --bookmark TEXT             Bookmark to start at (key:line or a named
                                      bookmark)
      -l, --log-level [debug|info|warning|error|critical]
                                      set logging level
      --log-file FILENAME             write logs to FILENAME
      --cache-hours INTEGER           Number of hours to keep in cache before
                                      removing on next run (0 disables caching)
      -h, --help                      Show this message and exit.


S3 Access
---------

Follow the instructions provided by the Boto Python interface to AWS:
http://boto.cloudhackers.com/en/latest/boto_config_tut.html


Basic Console Example
---------------------

.. code-block:: console

    $ s3tail s3://my-logs/production-s3-access-2016-08-04


Coding Example
--------------

To use the :class:`.s3tail.S3Tail` class in a project::

    from s3tail import S3Tail

    def process_line(num, line):
        print '%d: %s' % (num, line)

    tail = S3Tail('my-logs', 'production-s3-access-2016-08-04', process_line)
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
