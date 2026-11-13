"""`report.section(item)`: the section behind `report[item]`, with its confidence.

Bead edgartools-ywzj (with llmp.6.6 and the remainder of xrs0): section
extraction computes a confidence and plain-sentence warnings for every section,
but `tenk['Item 8']` returns bare text, so a caller could not tell a
table-of-contents section from a guardrail-flagged one. `section()` returns the
`Section` found by the SAME lookup, and `strict=True` refuses a doubtful one.

Offline: tracked fixtures under tests/fixtures/html/, driven through a minimal
filing stand-in.

Ground truth, hand-verified against NVIDIA's FY2025 10-K
(accession 0001045810-25-000023, filed 2025-02-26): Item 8 is a 207-char
pointer, "The information required by this Item is set forth in our
Consolidated Financial Statements ... included in this Annual Report on Form
10-K", and the statements are filed under Item 15.
"""
from pathlib import Path

import pytest

from edgar.company_reports import TenK, TenQ
from edgar.company_reports._base import text_only_section
from edgar.exceptions import (
    LowConfidenceSectionError,
    ParsingError,
    SectionNotFoundError,
    ValidationError,
)

pytestmark = pytest.mark.fast

HTML_ROOT = Path(__file__).parents[1] / "fixtures" / "html"
NVDA_10K = HTML_ROOT / "nvda" / "10k" / "nvda-10-k-2025-02-26.html"
NVDA_10Q = HTML_ROOT / "nvda" / "10q" / "nvda-10-q-2025-08-27.html"
AAPL_10K = HTML_ROOT / "aapl" / "10k" / "aapl-10-k-2024-11-01.html"


class FixtureFiling:
    """The minimum surface a report touches, backed by a local file."""

    filing_date = None
    company = "fixture"

    def __init__(self, path: Path, form: str):
        self._path = path
        self.form = form
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def nvda():
    return TenK(FixtureFiling(NVDA_10K, "10-K"))


@pytest.fixture(scope="module")
def aapl():
    return TenK(FixtureFiling(AAPL_10K, "10-K"))


def test_the_fixtures_are_present():
    """Absent is not passing."""
    for path in (NVDA_10K, NVDA_10Q, AAPL_10K):
        assert path.exists(), path


def test_flagged_section_reports_its_confidence_and_warning(nvda):
    item8 = nvda.section("Item 8")
    assert item8.confidence == 0.5
    assert item8.detection_method == "toc"
    assert len(item8.text()) == 207
    assert item8.text().endswith("included in this Annual Report on Form 10-K.")
    assert len(item8.warnings) == 1
    assert "incorporation by reference" in item8.warnings[0]


def test_strict_refuses_a_flagged_section_and_says_why(nvda):
    with pytest.raises(LowConfidenceSectionError) as raised:
        nvda.section("Item 8", strict=True)
    error = raised.value
    assert isinstance(error, ParsingError)
    assert error.item == "Item 8"
    assert error.confidence == 0.5
    assert error.min_confidence == 0.8
    assert error.detection_method == "toc"
    assert "incorporation by reference" in error.warnings[0]
    # The message names the item, the confidence, the threshold and the way out.
    message = str(error)
    assert "'Item 8'" in message and "0.50" in message and "0.8" in message
    assert "strict=False" in message


def test_strict_accepts_a_toc_section(nvda):
    item7 = nvda.section("Item 7", strict=True)
    assert item7.confidence == 0.95
    assert item7.detection_method == "toc"
    assert item7.text().startswith("Item 7. Management")


def test_min_confidence_moves_the_threshold(nvda):
    assert nvda.section("Item 8", strict=True, min_confidence=0.5).confidence == 0.5
    with pytest.raises(LowConfidenceSectionError):
        nvda.section("Item 7", strict=True, min_confidence=1.0)


@pytest.mark.parametrize("bad", [1.5, -0.1, "high", None, True])
def test_bad_min_confidence_is_a_validation_error(nvda, bad):
    with pytest.raises(ValidationError, match="min_confidence"):
        nvda.section("Item 7", min_confidence=bad)


def test_missing_item_raises_like_getitem(nvda):
    with pytest.raises(SectionNotFoundError):
        nvda.section("Item 99")
    with pytest.raises(SectionNotFoundError):
        nvda["Item 99"]


def test_section_is_the_one_getitem_reads(aapl):
    """Every spelling resolves to the same text through either accessor."""
    for spelling in ("Item 1", "1", "1A", "ITEM 7", "item 7", "Item 7A", "Item 8",
                     "business", "risk_factors", "mda"):
        assert aapl.section(spelling).text() == aapl[spelling], spelling


def test_ten_q_part_qualified_lookup():
    tenq = TenQ(FixtureFiling(NVDA_10Q, "10-Q"))
    risk = tenq.section("Part II, Item 1A")
    assert risk.part == "II" and risk.item == "1A"
    assert risk.confidence == 0.95
    assert risk.text() == tenq["Part II, Item 1A"]


def test_text_only_section_returns_its_text_unchanged():
    """Fallback text (cross-reference index, 8-K raw-text scan, 40-F AIF) is
    final: section(x).text() must equal report[x] byte for byte."""
    raw = "Item 7. Results\n\nPage 12 of 90\n\nITEM 8. FINANCIAL STATEMENTS"
    section = text_only_section("part_ii_item_7", "Item 7", raw,
                                detection_method="index", confidence=0.85,
                                warnings=["read from the index"], part="II", item="7")
    assert section.text() == raw
    assert (section.confidence, section.detection_method) == (0.85, "index")
    assert (section.part, section.item, section.kind) == ("II", "7", "item")
    assert section.warnings == ["read from the index"]
