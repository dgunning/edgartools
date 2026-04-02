"""Regression test for GitHub issue #749.

13F Value column was in thousands for pre-Q4 2022 filings and dollars for
post-Q4 2022 filings. Values are now normalized to dollars for all periods.
"""
from datetime import datetime

from edgar.thirteenf.models import _13F_VALUE_IN_THOUSANDS_CUTOFF


def test_cutoff_date():
    """The schema change cutoff is 2022-09-30."""
    assert _13F_VALUE_IN_THOUSANDS_CUTOFF == datetime(2022, 9, 30)


def test_pre_cutoff_period_is_in_thousands():
    """Report periods on or before 2022-09-30 should be flagged as thousands."""
    assert datetime(2022, 9, 30) <= _13F_VALUE_IN_THOUSANDS_CUTOFF
    assert datetime(2021, 12, 31) <= _13F_VALUE_IN_THOUSANDS_CUTOFF


def test_post_cutoff_period_is_in_dollars():
    """Report periods after 2022-09-30 should NOT be flagged as thousands."""
    assert datetime(2022, 12, 31) > _13F_VALUE_IN_THOUSANDS_CUTOFF
    assert datetime(2023, 3, 31) > _13F_VALUE_IN_THOUSANDS_CUTOFF
