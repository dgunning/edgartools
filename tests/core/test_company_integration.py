"""Integration tests for FormType against real Company filing lookups.

This file used to be a top-to-bottom demo script: it built ``Company("AAPL")``
and ran six filing lookups at module scope, printed check marks, and wrapped
every check in ``try/except`` that printed a cross and carried on. It contained
no test functions, so it asserted nothing and could never fail a build — but
pytest still executed the module body during COLLECTION, and a collection error
aborts the entire session before a single test runs. That is exactly what
happened in CI when SEC answered 429: a 6,000-test regression run was
interrupted by this file and one other, whose own tests had been deselected
anyway.

Rewritten as real tests: the network happens inside a fixture, the checks are
assertions rather than prints, and a failure here fails these tests instead of
the suite.
"""
import pytest

from edgar import Company
from edgar.enums import FormType

pytestmark = pytest.mark.network

YEAR = 2023


@pytest.fixture(scope="module")
def apple():
    return Company("AAPL")


def test_form_type_enum_selects_filings(apple):
    """FormType members resolve to the same filings a form string selects."""
    annual = apple.get_filings(form=FormType.ANNUAL_REPORT, year=YEAR)
    quarterly = apple.get_filings(form=FormType.QUARTERLY_REPORT, year=YEAR)

    assert len(annual) > 0
    assert len(quarterly) > 0
    assert {f.form for f in annual} == {"10-K"}
    assert {f.form for f in quarterly} == {"10-Q"}


def test_form_strings_still_work(apple):
    """The pre-FormType string API is unchanged."""
    single = apple.get_filings(form="10-K", year=YEAR)
    combined = apple.get_filings(form=["10-K", "10-Q"], year=YEAR)

    assert len(single) > 0
    assert len(combined) >= len(single)
    assert {f.form for f in combined} <= {"10-K", "10-Q"}


def test_form_type_and_string_are_mixable(apple):
    """A list may mix FormType members and plain strings."""
    mixed = apple.get_filings(form=[FormType.ANNUAL_REPORT, "8-K"], year=YEAR)

    assert len(mixed) > 0
    assert {f.form for f in mixed} <= {"10-K", "8-K"}


def test_form_type_matches_string_exactly(apple):
    """FormType.ANNUAL_REPORT and "10-K" select the identical filing set.

    Accession numbers, not just counts — equal counts over different filings
    would still be a compatibility break.
    """
    by_enum = apple.get_filings(form=FormType.ANNUAL_REPORT, year=YEAR)
    by_string = apple.get_filings(form="10-K", year=YEAR)

    assert {f.accession_number for f in by_enum} == {f.accession_number for f in by_string}


def test_form_type_values_are_edgar_form_strings():
    """Offline: every member's value is the literal form string EDGAR uses."""
    assert FormType.ANNUAL_REPORT.value == "10-K"
    assert FormType.QUARTERLY_REPORT.value == "10-Q"
    assert all(isinstance(member.value, str) and member.value for member in FormType)
