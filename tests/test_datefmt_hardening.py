"""Regression tests for datefmt() non-string / None hardening.

datefmt() is display-only and is called in filing-header and former-name render
sites with values that are not guaranteed to be set — e.g. a former name's null
``to`` date (the SEC ``formerNames`` JSON can carry ``"to": null``) or a missing
``date_of_change``. Previously the non-string branch called ``value.strftime``
unconditionally, so a ``None`` (or any unexpected type) raised
``AttributeError`` and took down the whole table render rather than just that
field. These assert graceful degradation instead.

Complements the unrecognized-string pass-through tests in test_to_context.py.
"""
import datetime

import pytest

from edgar.display.formatting import datefmt


def test_none_returns_empty_string():
    # A null date (e.g. a former name's open-ended ``to``) must not crash.
    assert datefmt(None, "%B %d, %Y") == ""


def test_date_object_formats():
    assert datefmt(datetime.date(2022, 3, 4), "%B %d, %Y") == "March 04, 2022"


def test_datetime_object_formats():
    assert datefmt(datetime.datetime(2022, 3, 4), "%Y-%m-%d") == "2022-03-04"


@pytest.mark.parametrize("value,expected", [(12345, "12345"), (0, "0")])
def test_unexpected_type_degrades_to_str(value, expected):
    # Any non-(str|date|datetime) value degrades to its string form, never crashes.
    assert datefmt(value, "%B %d, %Y") == expected
