"""
Regression test for Issue #505: TypeError crash on date filter with empty result set

GitHub Issue: https://github.com/dgunning/edgartools/issues/505
Reporter: jakobovski-arb

Bug: Filings.filter(date=...) crashed with
    TypeError: unsupported operand type(s) for -: 'datetime.date' and 'NoneType'

Where it happens: when the requested date range includes today (a single
date of today, or a range starting in the last five days that runs through
today), filter() checks how stale the data being filtered is, using that
Filings' own latest filing date. An empty Filings has no latest date, and
_get_data_staleness_days() subtracted None from today.

Fix: _get_data_staleness_days(None) returns 999999, and the call in filter()
skips the check when there is no latest date.

These tests used to download a year of SEC's filing index and filter it to
December 2025. That range never reached the crash: it does not include today,
so the staleness check never ran. With both guards removed, those tests still
passed, and an empty Filings filtered to today raised the TypeError above.
They now run offline on four real rows from SEC's 2023 Q1 form index.
"""
from datetime import date, timedelta

import pyarrow as pa
import pytest

from edgar._filings import Filings, _empty_filing_index, _get_data_staleness_days

pytestmark = pytest.mark.fast

# Rows from SEC's 2023 Q1 form index (get_filings(2023, 1, form="10-K")).
INDEX_ROWS = [
    ("10-K", "General Motors Co", 1467858, date(2023, 1, 31), "0001467858-23-000029"),
    ("10-K", "GENERAL ELECTRIC CO", 40545, date(2023, 2, 10), "0000040545-23-000023"),
    ("10-K", "EXXON MOBIL CORP", 34088, date(2023, 2, 22), "0000034088-23-000020"),
    ("10-K", "PFIZER INC", 78003, date(2023, 2, 23), "0000078003-23-000024"),
]


@pytest.fixture
def filings_2023():
    form, company, cik, filing_date, accession = zip(*INDEX_ROWS, strict=True)
    return Filings(pa.table({
        "form": pa.array(form, pa.string()),
        "company": pa.array(company, pa.string()),
        "cik": pa.array(cik, pa.int32()),
        "filing_date": pa.array(filing_date, pa.date32()),
        "accession_number": pa.array(accession, pa.string()),
    }))


def _ranges_that_include_today():
    today = date.today()
    return [today.isoformat(), f"{today - timedelta(days=2)}:", f"{today - timedelta(days=2)}:{today}"]


# Fixed ids: the dates change daily, and pytest-xdist workers must agree on names.
TODAY_IDS = ["today", "open-range-from-two-days-ago", "range-through-today"]


# --- The crash ----------------------------------------------------------------

@pytest.mark.parametrize("filing_date", _ranges_that_include_today(), ids=TODAY_IDS)
def test_an_empty_filings_filtered_to_today_does_not_crash(filing_date):
    filtered = Filings(_empty_filing_index()).filter(date=filing_date)

    assert isinstance(filtered, Filings)
    assert len(filtered) == 0


@pytest.mark.parametrize("filing_date", _ranges_that_include_today(), ids=TODAY_IDS)
def test_filtering_to_nothing_then_to_today_does_not_crash(filings_2023, filing_date):
    """The shape users hit: a filter that empties the set, then a current one."""
    empty = filings_2023.filter(date="2025-12-01:2025-12-31")

    filtered = empty.filter(date=filing_date)

    assert isinstance(filtered, Filings)
    assert len(filtered) == 0


# --- Empty results stay well-formed -------------------------------------------

def test_a_date_filter_selects_by_filing_date(filings_2023):
    """The control: the same kind of filter that empties the set picks real rows."""
    picked = filings_2023.filter(date="2023-02-22:2023-02-23")

    assert sorted(picked.data.column("company").to_pylist()) == ["EXXON MOBIL CORP", "PFIZER INC"]


def test_issue_505_empty_date_filter_no_crash(filings_2023):
    filtered = filings_2023.filter(date="2025-12-01:2025-12-31")

    assert isinstance(filtered, Filings)
    assert len(filtered) == 0


def test_issue_505_date_filter_chained_operations(filings_2023):
    tenks = filings_2023.filter(form="10-K", amendments=False)
    assert len(tenks) == 4

    filtered = tenks.filter(date="2025-12-01:2025-12-31")

    assert isinstance(filtered, Filings)
    assert len(filtered) == 0


def test_issue_505_empty_filings_date_range(filings_2023):
    assert filings_2023.date_range == (date(2023, 1, 31), date(2023, 2, 23))

    empty = filings_2023.filter(date="2025-12-01:2025-12-31")

    assert empty.date_range == (None, None)


def test_get_data_staleness_days_handles_none():
    staleness = _get_data_staleness_days(None)

    assert staleness == 999999
    assert isinstance(staleness, int)
