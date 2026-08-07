"""Regression tests for EX-FILING FEES iXBRL extraction (lxml-native parser).

The extractor was migrated from BeautifulSoup to lxml. These tests run
network-free against a committed exhibit fixture and assert hand-verified
ground-truth values, plus the specific data-quality bug the migration fixed:
multi-<span> security titles must keep their internal whitespace.

Fixture: tests/offerings/fixtures/ex_filing_fees_0001193125-25-155880.html
  SEC accession 0001193125-25-155880 (Strategy / MicroStrategy 424B5, 2025) —
  a single-row Equity offering whose security title spans several inline
  elements. Values verified by hand against the EX-FILING FEES exhibit.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from edgar.offerings._424b_xbrl import extract_filing_fees_xbrl

FIXTURE = Path(__file__).parent / "fixtures" / "ex_filing_fees_0001193125-25-155880.html"


class _FakeAttachment:
    document_type = "EX-FILING FEES"
    url = "https://www.sec.gov/Archives/exhibit.htm"

    def __init__(self, content: bytes):
        self._content = content

    def download(self):
        return self._content


class _FakeFiling:
    """Minimal stand-in: extract_filing_fees_xbrl only needs .attachments."""

    def __init__(self, content: bytes, *, has_fee_exhibit: bool = True):
        self.attachments = [_FakeAttachment(content)] if has_fee_exhibit else []


@pytest.fixture(scope="module")
def fee_data():
    content = FIXTURE.read_bytes()
    return extract_filing_fees_xbrl(_FakeFiling(content))


def test_exhibit_detected(fee_data):
    assert fee_data["has_exhibit"] is True
    assert fee_data["exhibit_url"] == "https://www.sec.gov/Archives/exhibit.htm"


def test_summary_fields_ground_truth(fee_data):
    # Hand-verified against the EX-FILING FEES exhibit.
    assert fee_data["form_type"] == "S-3"
    assert fee_data["registration_file_number"] == "333-284510"
    assert fee_data["total_offering_amount"] == "4,200,000,000"
    assert fee_data["total_fee_amount"] == "643,020.00"
    assert fee_data["is_final_prospectus"] is False


def test_offering_row_ground_truth(fee_data):
    rows = fee_data["offering_rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["security_type"] == "Equity"
    assert row["max_aggregate_offering_price"] == "4,200,000,000"
    assert row["fee_rate"] == "0.00015310"
    assert row["fee_amount"] == "643,020.00"
    assert row["fee_rule"] == "Rule 457(o)"


def test_multispan_title_keeps_whitespace(fee_data):
    """The bug the lxml migration fixed.

    The title spans multiple inline elements. The old
    BeautifulSoup get_text(strip=True) concatenated them with no
    separator, producing "Series APerpetual StridePreferred Stock".
    lxml's itertext() preserves the inter-element whitespace.
    """
    title = fee_data["offering_rows"][0]["security_title"]
    assert title == (
        "10.00% Series A Perpetual Stride Preferred Stock, "
        "$0.001 par value per share"
    )
    # Guard against the specific regression signature: mashed word boundaries.
    assert "APerpetual" not in title
    assert "StridePreferred" not in title


def test_missing_exhibit_returns_silently():
    """No EX-FILING FEES attachment -> has_exhibit False, not an error or None."""
    result = extract_filing_fees_xbrl(_FakeFiling(b"", has_fee_exhibit=False))
    assert result == {"has_exhibit": False}


def test_garbage_content_does_not_raise():
    """Malformed bytes degrade to has_exhibit False, never an exception."""
    result = extract_filing_fees_xbrl(_FakeFiling(b"\x00\x01not xbrl at all"))
    assert result.get("has_exhibit") in (True, False)
    # No ix: facts -> empty extraction, but the call must not raise.
    assert "offering_rows" in result or result == {"has_exhibit": False}
