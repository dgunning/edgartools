"""
Regression test for Issue #794.

Entity.get_filings declares filing_date: Union[str, Tuple[str, str], None]
in its type hint, but extract_dates only handled the colon-separated string
form. Passing a tuple crashed with:

    TypeError: strptime() argument 1 must be str, not tuple

This regression test asserts the tuple form is now accepted by extract_dates
(and equivalently by filter_by_date, which delegates to it), preserving the
public type-hint contract on get_filings.
"""

from datetime import datetime, date

import pyarrow as pa
import pytest

from edgar.dates import InvalidDateException, extract_dates
from edgar.filtering import filter_by_date


@pytest.mark.fast
def test_extract_dates_accepts_tuple_of_two_strings():
    """The form advertised by Entity.get_filings's type hint."""
    start, end, is_range = extract_dates(("2026-01-29", "2026-04-29"))
    assert start == datetime(2026, 1, 29)
    assert end == datetime(2026, 4, 29)
    assert is_range is True


@pytest.mark.fast
def test_extract_dates_accepts_list_form_too():
    """Lists should be accepted equivalently — no reason to gate on tuple-vs-list."""
    start, end, is_range = extract_dates(["2026-01-29", "2026-04-29"])
    assert start == datetime(2026, 1, 29)
    assert end == datetime(2026, 4, 29)
    assert is_range is True


@pytest.mark.fast
def test_extract_dates_tuple_open_end_defaults_to_today():
    """(start, None) means 'from start to today', matching 'start:' string form."""
    start, end, is_range = extract_dates(("2026-01-29", None))
    assert start == datetime(2026, 1, 29)
    assert end is not None
    # end is 'today' at midnight; just assert it's >= start and is_range is True
    assert end >= start
    assert is_range is True


@pytest.mark.fast
def test_extract_dates_tuple_open_start_defaults_to_edgar_epoch():
    """(None, end) means 'from EDGAR epoch (1994-07-01) to end', matching ':end' string form."""
    start, end, is_range = extract_dates((None, "2026-04-29"))
    assert start == datetime(1994, 7, 1)
    assert end == datetime(2026, 4, 29)
    assert is_range is True


@pytest.mark.fast
def test_extract_dates_tuple_wrong_arity_raises():
    with pytest.raises(InvalidDateException, match="exactly two elements"):
        extract_dates(("2026-01-29",))
    with pytest.raises(InvalidDateException, match="exactly two elements"):
        extract_dates(("a", "b", "c"))


@pytest.mark.fast
def test_extract_dates_tuple_both_none_raises():
    with pytest.raises(InvalidDateException, match="at least one non-None bound"):
        extract_dates((None, None))


@pytest.mark.fast
def test_extract_dates_string_forms_still_work():
    """Adding tuple support must not break the original string forms."""
    # Single date
    start, end, is_range = extract_dates("2026-04-29")
    assert start == datetime(2026, 4, 29)
    assert end is None
    assert is_range is False

    # Colon range
    start, end, is_range = extract_dates("2026-01-29:2026-04-29")
    assert start == datetime(2026, 1, 29)
    assert end == datetime(2026, 4, 29)
    assert is_range is True

    # Open-ended forms
    start, end, _ = extract_dates("2026-01-29:")
    assert start == datetime(2026, 1, 29)
    assert end is not None  # today

    start, end, _ = extract_dates(":2026-04-29")
    assert start == datetime(1994, 7, 1)
    assert end == datetime(2026, 4, 29)


@pytest.mark.fast
def test_filter_by_date_accepts_tuple_input():
    """End-to-end: the filtering layer that get_filings calls must accept tuples too."""
    # Build a small pyarrow table mimicking the filings index shape
    table = pa.table({
        "filing_date": [date(2026, 2, 1), date(2026, 3, 15), date(2026, 5, 1)],
        "form": ["10-K", "10-Q", "8-K"],
    })

    # Tuple form (was crashing before this fix)
    filtered = filter_by_date(table, ("2026-01-29", "2026-04-29"), "filing_date")
    forms = filtered.column("form").to_pylist()
    assert sorted(forms) == ["10-K", "10-Q"]  # 8-K (May 1) excluded

    # String range produces the same result
    filtered_str = filter_by_date(table, "2026-01-29:2026-04-29", "filing_date")
    assert filtered_str.column("form").to_pylist() == filtered.column("form").to_pylist()
