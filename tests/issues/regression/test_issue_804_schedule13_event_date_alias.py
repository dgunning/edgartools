"""Regression test for GitHub issue #804.

Schedule13D exposed the triggering-event date as ``date_of_event`` while
Schedule13G exposed it as ``event_date``, breaking duck-typing across a
mixed list of 13D/13G filings. Both classes now accept either name as a
read-only alias for the underlying attribute.
"""

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.beneficial_ownership import Schedule13D, Schedule13G


TEST_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "beneficial_ownership"
SCHEDULE_13D_XML_PATH = TEST_DATA_DIR / "schedule13d.xml"
SCHEDULE_13G_XML_PATH = TEST_DATA_DIR / "schedule13g.xml"


def _load_schedule_13d() -> Schedule13D:
    filing = Mock()
    filing.form = "SCHEDULE 13D"
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=SCHEDULE_13D_XML_PATH.read_text())
    return Schedule13D.from_filing(filing)


def _load_schedule_13g() -> Schedule13G:
    filing = Mock()
    filing.form = "SCHEDULE 13G"
    filing.filing_date = date(2025, 11, 26)
    filing.xml = Mock(return_value=SCHEDULE_13G_XML_PATH.read_text())
    return Schedule13G.from_filing(filing)


@pytest.mark.fast
def test_schedule13d_exposes_event_date_alias():
    """Schedule13D.event_date must mirror the parsed date_of_event."""
    schedule = _load_schedule_13d()
    assert schedule.date_of_event == "12/31/2024"
    assert schedule.event_date == schedule.date_of_event


@pytest.mark.fast
def test_schedule13g_exposes_date_of_event_alias():
    """Schedule13G.date_of_event must mirror the parsed event_date."""
    schedule = _load_schedule_13g()
    assert schedule.event_date == "11/19/2025"
    assert schedule.date_of_event == schedule.event_date


@pytest.mark.fast
def test_event_date_works_across_mixed_schedule13_list():
    """A mixed iterable of 13D/13G must answer to a single attribute name."""
    schedules = [_load_schedule_13d(), _load_schedule_13g()]
    expected = ["12/31/2024", "11/19/2025"]

    # Both names work uniformly across the heterogeneous list.
    assert [s.event_date for s in schedules] == expected
    assert [s.date_of_event for s in schedules] == expected
