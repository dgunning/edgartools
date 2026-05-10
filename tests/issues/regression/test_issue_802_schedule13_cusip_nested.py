"""Regression test for GitHub issue #802.

The SEC moved the issuer CUSIP from a flat ``<issuerCUSIP>`` /
``<issuerCusip>`` element to a nested ``<issuerCusips><issuerCusipNumber>``
structure. The old parser only looked for the flat tag and silently
returned an empty string for newer Schedule 13D / 13G filings. PR #803
falls back to the nested element when the flat tag is missing.

The fixtures here are the actual ``primary_doc.xml`` payloads from the
two filings cited in the issue, so the test exercises the real wire
format and will fire if the fallback is ever removed or if BeautifulSoup's
recursive ``find()`` semantics are ever tightened.
"""

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.beneficial_ownership import Schedule13D, Schedule13G


TEST_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "beneficial_ownership"
SCHEDULE_13D_PATH = TEST_DATA_DIR / "schedule13d_nested_cusip.xml"
SCHEDULE_13G_PATH = TEST_DATA_DIR / "schedule13g_nested_cusip.xml"


def _load_schedule_13d() -> Schedule13D:
    filing = Mock()
    filing.form = "SCHEDULE 13D"
    filing.filing_date = date(2026, 5, 6)
    filing.xml = Mock(return_value=SCHEDULE_13D_PATH.read_text())
    return Schedule13D.from_filing(filing)


def _load_schedule_13g() -> Schedule13G:
    filing = Mock()
    filing.form = "SCHEDULE 13G"
    filing.filing_date = date(2026, 4, 7)
    filing.xml = Mock(return_value=SCHEDULE_13G_PATH.read_text())
    return Schedule13G.from_filing(filing)


@pytest.mark.fast
def test_schedule13d_extracts_nested_issuer_cusip():
    """13D filings using <issuerCusips><issuerCusipNumber> must yield the CUSIP."""
    schedule = _load_schedule_13d()
    assert schedule.issuer_info.cusip == "81221K108"
    assert schedule.security_info.cusip == "81221K108"


@pytest.mark.fast
def test_schedule13g_extracts_nested_issuer_cusip():
    """13G filings using <issuerCusips><issuerCusipNumber> must yield the CUSIP."""
    schedule = _load_schedule_13g()
    assert schedule.issuer_info.cusip == "053774105"
    assert schedule.security_info.cusip == "053774105"


@pytest.mark.fast
def test_fixtures_use_new_nested_schema():
    """Guard the fixtures themselves: regenerating them must keep the nested form."""
    for path in (SCHEDULE_13D_PATH, SCHEDULE_13G_PATH):
        body = path.read_text()
        assert "<issuerCusips>" in body, f"{path.name} no longer exercises nested schema"
        assert "<issuerCusipNumber>" in body, f"{path.name} no longer exercises nested schema"
