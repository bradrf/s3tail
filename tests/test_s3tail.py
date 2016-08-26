#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_s3tail
----------------------------------

Tests for `s3tail` module.
"""

import pytest

from contextlib import contextmanager
from click.testing import CliRunner

from s3tail import s3tail
from s3tail import cli


class TestS3tail(object):

    @classmethod
    def setup_class(cls):
        pass

    def test_something(self):
        pass
    def test_command_line_interface(self):
        runner = CliRunner()
        result = runner.invoke(cli.main)
        assert result.exit_code == 2
        assert 'Missing argument "s3_uri"' in result.output
        help_result = runner.invoke(cli.main, ['--help'])
        assert help_result.exit_code == 0
        assert 'Show this message and exit.' in help_result.output

    @classmethod
    def teardown_class(cls):
        pass
