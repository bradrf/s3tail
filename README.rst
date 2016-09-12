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

See :doc:`installation`


Features
--------

S3tail downloads and displays the content of files stored in S3, optionally starting at a specific
prefix. For example, the following will start dumping all the log file contents found for August the
fourth in the order S3 provides from that prefix onward:

.. code-block:: console

    $ s3tail s3://my-logs/production-s3-access-2016-08-04

When s3tail is stopped or interrupted, it'll print a bookmark to be used to pick up at the exact
spot following the last log printed in a previous run. Something like the following might be used to
leverage this ability to continue tailing from a previous stopping point:

.. code-block:: console

    $ s3tail s3://my-logs/production-s3-access-2016-08-04
    ...
    ...a-bunch-of-file-output...
    ...
    Bookmark: production-s3-access-2016-08-04-00-20-31-61059F36E0DBF36E:706

This can then be used to pick up at line ``707`` later on, like this:

.. code-block:: console

    $ s3tail s3://my-logs/production-s3-access-2016-08-04 \
        --bookmark production-s3-access-2016-08-04-00-20-31-61059F36E0DBF36E:706

Additionally, it's often useful to let s3tail track where things were left off and pick up at that
spot without needing to copy and paste the previous bookmark. This is where "named bookmarks" come
in handy. The examples above could have been reduced to these operations:

.. code-block:: console

    $ s3tail --bookmark my-special-spot s3://my-logs/production-s3-access-2016-08-04
    ...
    ^C
    $ s3tail --bookmark my-special-spot s3://my-logs/production-s3-access
    Starting production-s3-access-2016-08-04-02-22-32-415AE699C8233AC3
    Found production-s3-access-2016-08-04-02-22-32-415AE699C8233AC3 in cache
    Picked up at line 707
    ...

It's safe to rerun s3tail sessions when working with piped commands searching for data in the stream
(e.g. ``grep``). S3tail keeps files in a local file system cache (for 24 hours by default) and will
always read and display from the cache before downloading from S3. This is done in a best-effort
background thread to avoid impacting performance. The file cache is stored in the user's ``HOME``
directory, in an ``.s3tailcache`` subdirectory, where the file names are the S3 keys hashed with
SHA-256.

Check out :doc:`usage` for more details and examples (like how to leverage GoAccess to generate
beautiful traffic reports!).


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project
template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
