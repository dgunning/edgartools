"""
Tests for Schedule 14D-9 (tender offer solicitation/recommendation statement).

Ground truth: Lisata Therapeutics, Inc. (CIK 320017), SC 14D9 filed 2026-06-10,
accession 0001140361-26-024737. The board unanimously recommended shareholders
accept the offer -- verified by hand against the primary document at
https://www.sec.gov/Archives/edgar/data/320017/000114036126024737/ny20069664x1_sc14d9.htm
"""

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.tender_offers.schedule14d9 import (
    Schedule14D9,
    classify_recommendation,
    extract_item_section,
)

TEST_DATA_DIR = Path(__file__).parent / "data" / "tender_offers"
LISATA_SC14D9_PATH = TEST_DATA_DIR / "sc14d9_lisata_therapeutics.htm"


def _mock_filing(
    form="SC 14D9", html=None, company="Lisata Therapeutics, Inc.", cik="320017", accession_no="0001140361-26-024737", filing_date=date(2026, 6, 10)
):
    filing = Mock()
    filing.form = form
    filing.company = company
    filing.cik = cik
    filing.accession_no = accession_no
    filing.filing_date = filing_date
    filing.html = Mock(return_value=html)
    return filing


@pytest.mark.fast
def test_schedule14d9_from_filing_ground_truth():
    """Ground-truth assertion against a real, hand-verified filing."""
    html = LISATA_SC14D9_PATH.read_text()
    filing = _mock_filing(html=html)

    schedule = Schedule14D9.from_filing(filing)

    assert isinstance(schedule, Schedule14D9)
    assert schedule.company_name == "Lisata Therapeutics, Inc."
    assert schedule.cik == "320017"
    assert schedule.is_amendment is False
    # The board's actual, hand-verified recommendation on this filing.
    assert schedule.recommendation == "accept"
    assert "unanimously recommends" in schedule.item4_text.lower()


@pytest.mark.fast
def test_schedule14d9_wrong_form_raises():
    filing = _mock_filing(form="SC TO-T", html="<html></html>")
    with pytest.raises(AssertionError):
        Schedule14D9.from_filing(filing)


@pytest.mark.fast
def test_schedule14d9_missing_item4_raises_not_silent():
    """Silence check: a document with no Item 4 must fail loudly, not return a
    Schedule14D9 with a quietly-wrong `recommendation`."""
    filing = _mock_filing(html="<html><body>Not a real filing document.</body></html>")
    with pytest.raises(ValueError, match="Could not locate Item 4"):
        Schedule14D9.from_filing(filing)


@pytest.mark.fast
def test_schedule14d9_no_html_raises():
    filing = _mock_filing(html=None)
    with pytest.raises(ValueError, match="No HTML document"):
        Schedule14D9.from_filing(filing)


@pytest.mark.fast
@pytest.mark.parametrize(
    "text,expected",
    [
        ("the Board unanimously recommends that the holders of Shares accept the Offer", "accept"),
        ("the Board recommends that stockholders reject the Offer", "reject"),
        ("the Board expresses no opinion and remains neutral with respect to the Offer", "neutral"),
        ("the Board has determined to defer any recommendation pending further review", None),
        ("", None),
    ],
)
def test_classify_recommendation(text, expected):
    assert classify_recommendation(text) == expected


@pytest.mark.fast
def test_extract_item_section_ignores_quoted_cross_references():
    """A quoted cross-reference to 'Item 4' elsewhere in the document must not
    be mistaken for the real section heading (the same failure mode as the
    fabricated item-anchor bug in GH #918)."""
    text = (
        "As described in “Item 4. The Solicitation or Recommendation” above, "
        "the officers are listed here. "
        "Item 4. The Solicitation or Recommendation. "
        "The Board unanimously recommends that holders accept the Offer. "
        "Item 5. Persons Retained."
    )
    section = extract_item_section(text, 4, 5)
    assert section is not None
    assert section.startswith("Item 4. The Solicitation or Recommendation.")
    assert "unanimously recommends" in section


@pytest.mark.fast
def test_extract_item_section_returns_none_when_absent():
    assert extract_item_section("nothing relevant here", 4, 5) is None
