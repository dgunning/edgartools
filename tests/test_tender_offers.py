"""
Tests for Schedule 14D-9 (tender offer solicitation/recommendation statement).

Ground truth, all hand-verified against the primary document:
- Lisata Therapeutics, Inc. (CIK 320017), SC 14D9 filed 2026-06-10,
  accession 0001140361-26-024737 -- board recommended ACCEPT.
  https://www.sec.gov/Archives/edgar/data/320017/000114036126024737/ny20069664x1_sc14d9.htm
- Moody National REIT II, Inc. (CIK 1615222), SC 14D9 filed 2023-06-21,
  accession 0001387131-23-007870 -- board recommended REJECT.
  https://www.sec.gov/Archives/edgar/data/1615222/000138713123007870/mnrtii-sc14d9_062123.htm
- Moody National REIT II, Inc. (CIK 1615222), SC 14D9 filed 2024-05-08,
  accession 0001999371-24-005776 -- board recommended NEUTRAL (explicitly
  "express no opinion and remain neutral with respect to the Offer").
  https://www.sec.gov/Archives/edgar/data/1615222/000199937124005776/mnrtii-sc14d9_050824.htm
"""

from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.tender_offers.schedule14d9 import (
    Schedule14D9,
    _recommendation_window,
    classify_recommendation,
    extract_item_section,
)

TEST_DATA_DIR = Path(__file__).parent / "data" / "tender_offers"
LISATA_SC14D9_PATH = TEST_DATA_DIR / "sc14d9_lisata_therapeutics.htm"
MOODY_REJECT_PATH = TEST_DATA_DIR / "sc14d9_moody_national_reit_ii_reject.htm"
MOODY_NEUTRAL_PATH = TEST_DATA_DIR / "sc14d9_moody_national_reit_ii_neutral.htm"


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
def test_schedule14d9_from_filing_ground_truth_accept():
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
def test_schedule14d9_from_filing_ground_truth_reject():
    """Second ground truth: a real, unambiguous REJECT recommendation."""
    html = MOODY_REJECT_PATH.read_text()
    filing = _mock_filing(
        html=html,
        company="Moody National REIT II, Inc.",
        cik="1615222",
        accession_no="0001387131-23-007870",
        filing_date=date(2023, 6, 21),
    )

    schedule = Schedule14D9.from_filing(filing)

    assert schedule.company_name == "Moody National REIT II, Inc."
    assert schedule.recommendation == "reject"
    assert "reject the offer" in schedule.recommendation_text.lower()


@pytest.mark.fast
def test_schedule14d9_from_filing_ground_truth_neutral():
    """Third ground truth: a real, unambiguous NEUTRAL recommendation."""
    html = MOODY_NEUTRAL_PATH.read_text()
    filing = _mock_filing(
        html=html,
        company="Moody National REIT II, Inc.",
        cik="1615222",
        accession_no="0001999371-24-005776",
        filing_date=date(2024, 5, 8),
    )

    schedule = Schedule14D9.from_filing(filing)

    assert schedule.recommendation == "neutral"
    assert "remain neutral" in schedule.recommendation_text.lower()


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
def test_recommendation_text_truncated_flag():
    html = LISATA_SC14D9_PATH.read_text()
    schedule = Schedule14D9.from_filing(_mock_filing(html=html))
    # Lisata's Item 4 runs to background/reasons narrative well past the
    # recommendation statement itself, so recommendation_text is a cut, not
    # the whole section.
    assert schedule.recommendation_text_truncated is True
    assert len(schedule.recommendation_text) < len(schedule.item4_text)


@pytest.mark.fast
def test_recommendation_text_not_truncated_when_item4_is_short():
    schedule = Schedule14D9(
        filing=_mock_filing(),
        item4_text="The Board unanimously recommends that holders accept the Offer.",
    )
    assert schedule.recommendation_text_truncated is False
    assert schedule.recommendation_text == schedule.item4_text


@pytest.mark.fast
@pytest.mark.parametrize(
    "text,expected",
    [
        ("the Board unanimously recommends that the holders of Shares accept the Offer", "accept"),
        ("the Board recommends that stockholders reject the Offer", "reject"),
        ("the Board expresses no opinion and remains neutral with respect to the Offer", "neutral"),
        ("the Board has determined to defer any recommendation pending further review", None),
        # A real rejection that never uses the words "reject" or "tender" at all
        # (Woodbridge Liquidation Trust, accession 0001140361-20-000734).
        ("the Supervisory Board unanimously recommends that the Interestholders not accept the Offer", "reject"),
        # A recommendation split across a line wrap mid-sentence, as HTML text
        # extraction produces in practice (Genco Shipping, accession
        # 0000930413-26-001621) -- must not be defeated by the embedded newline.
        ("the Genco Board unanimously recommends that holders of Shares\nREJECT the Offer and NOT TENDER any Shares", "reject"),
        ("", None),
    ],
)
def test_classify_recommendation(text, expected):
    assert classify_recommendation(text) == expected


@pytest.mark.fast
def test_classify_recommendation_ignores_background_section_hedging():
    """Regression test for the real defect found in review of PR #940: classifying
    against the whole Item 4 section let a hedging phrase in the Background
    narrative outrank the board's actual, current recommendation."""
    text = (
        "The Board unanimously recommends that stockholders accept the Offer "
        "and tender their Shares. "
        "Background of the Offer. At the January meeting, the Board determined "
        "to express no opinion pending further review."
    )
    assert classify_recommendation(text) == "accept"


@pytest.mark.fast
def test_recommendation_window_cuts_at_background_heading():
    text = "The Board unanimously recommends that holders accept the Offer. Background of the Offer. Many years of history follow here."
    window = _recommendation_window(text)
    assert window == "The Board unanimously recommends that holders accept the Offer."
    assert "Background" not in window


@pytest.mark.fast
def test_recommendation_window_falls_back_to_fixed_cap_when_no_heading():
    text = "word " * 1000  # no "background of the" / "reasons for the recommendation" heading
    window = _recommendation_window(text)
    assert len(window) <= 2500


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
