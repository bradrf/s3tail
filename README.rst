===============================
s3tail
===============================

.. image:: https://img.shields.io/pypi/v/s3tail.svg
        :target: https://pypi.python.org/pypi/s3tail

.. image:: https://img.shields.io/travis/bradrf/s3tail.svg
        :target: https://travis-ci.org/bradrf/s3tail

.. image:: https://readthedocs.org/projects/s3tail/badge/?version=latest
        :target: https://s3tail.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/bradrf/s3tail/shield.svg
     :target: https://pyup.io/repos/github/bradrf/s3tail/
     :alt: Updates


S3tail is a simple tool to help access log files stored in an S3 bucket in the same way one might
use the \*nix ``tail`` command (with far fewer options, most notably the lack of ``follow``).

* Free software: MIT license
* Documentation: https://s3tail.readthedocs.io.


Installation
------------

::

   $ pip install s3tail


Features
--------

S3tail downloads and displays the content of files stored in S3, optionally starting at a specific
prefix. For example, the following will start dumping all the log file contents found for August the
fourth in the order S3 provides from that prefix onward::

   $ s3tail s3://my-logs/production/s3/production-s3-access-2016-08-04

When s3tail is stopped or interrupted, it'll print a bookmark to be used to pick up at the exact
spot following the last log printed in a previous run. Something like the following might be used to
leverage this ability to continue tailing from a previous stopping point::

   $ s3tail s3://my-logs/production/s3/production-s3-access-2016-08-04
   ...
   ...a-bunch-of-file-output...
   ...
   INFO:s3tail:Bookmark: production/s3/production-s3-access-2016-08-04-00-20-31-61059F36E0DBF36E:706

This can then be used to pick up at line ``707`` later on, like this::

   $ s3tail s3://my-logs/production/s3/production-s3-access-2016-08-04 \
     --bookmark production/s3/production-s3-access-2016-08-04-00-20-31-61059F36E0DBF36E:706

It's safe to rerun s3tail sessions when working with piped commands searching for data in the stream
(e.g. ``grep``). S3tail keeps files in a local file system cache (for 24 hours by default) and will
always read and display from the cache before downloading from S3. This is done in a best-effort
background thread to avoid impacting performance. The file cache is stored in the user's ``HOME``
directory, in an ``.s3tailcache`` subdirectory, where the file names are the S3 keys hashed with
SHA-256.

To configure access to an AWS S3 bucket, follow the instructions provided by the Boto Python
interface to AWS: http://boto.cloudhackers.com/en/latest/boto_config_tut.html

Check out ``s3tail --help`` for full usage.

* TODO

  * allow for digit ranges to be looked up

  * add ability to expresss bookmark "manually" by setting the actual key of the *CURRENT* file and
    do search looking for one previous? consider having all bookmarks like this! way better
    usability

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project
template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
