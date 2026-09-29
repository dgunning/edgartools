"""
Regression test for GitHub Issue #1346: Cross Reference Index extraction is off
by the number of unnumbered front-matter pages.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1346

The index cites *printed* page numbers, but ``extract_content_by_page_range``
located printed page N by counting N page breaks from the top of the HTML.
Citigroup's FY2022 10-K (0000831001-23-000037) has three extra breaks in its
front matter, so every item landed three pages early: Item 7A ("60-121")
opened on printed page 57 with "HUMAN CAPITAL RESOURCES AND MANAGEMENT", which
is Item 1 content.

Fix: the offset between page-break index and printed page number is calibrated
once per document from the page numbers printed in the footers, and applied to
every range. It is 0 when the footers do not agree on one, so aligned filings
(Citigroup FY2024, GE) extract byte-for-byte what they did before.

Offline: tracked fixtures under tests/fixtures/html/, and TenK is driven through
a minimal filing stub (the pattern of test_issue_821_citi_html_leak.py).
"""
import hashlib
import html as html_lib
import re
from pathlib import Path

import pytest

from edgar.company_reports import TenK
from edgar.documents import CrossReferenceIndex

FIXTURES = Path(__file__).parents[2] / "fixtures" / "html"
CITI_FY2022 = FIXTURES / "c" / "10k" / "c-10-k-2023-02-27.html"
CITI_FY2024 = FIXTURES / "c" / "10k" / "c-10-k-2025-02-21.html"
GE_FY2025 = FIXTURES / "ge" / "10k" / "ge-10-k-2026-01-29.html"


class _StubFiling:
    """Minimal surface TenK needs: html(), and identifiers used in logging."""
    base_dir = ""
    form = "10-K"
    company = "Citigroup Inc."
    cik = 831001

    def __init__(self, html: str, accession_number: str, filing_date: str):
        self._html = html
        self.accession_number = accession_number
        self.filing_date = filing_date

    def html(self) -> str:
        return self._html


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _sha1(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def citi_2022_html():
    return CITI_FY2022.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def citi_2022(citi_2022_html):
    return CrossReferenceIndex(citi_2022_html)


@pytest.fixture(scope="module")
def citi_2024():
    return CrossReferenceIndex(CITI_FY2024.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ge_2025():
    return CrossReferenceIndex(GE_FY2025.read_text(encoding="utf-8"))


class TestPageOffsetCalibration:

    def test_citi_fy2022_offset_is_three(self, citi_2022):
        """Three unnumbered front-matter pages: printed page N follows break N+3."""
        assert citi_2022._detect_page_offset() == 3

    def test_citi_fy2024_offset_is_zero(self, citi_2024):
        assert citi_2024._detect_page_offset() == 0

    def test_ge_offset_is_zero(self, ge_2025):
        """GE prints the number on only every other footer ("4 2025 FORM 10-K"
        vs "2025 FORM 10-K 5"); the readable half still agrees on 0."""
        assert ge_2025._detect_page_offset() == 0

    def test_no_footers_means_no_offset(self):
        """Nothing readable to calibrate from: stay with the old mapping."""
        pages = "".join(f"<p>Body text {i}.</p><hr style=\"page-break-after:always\"/>"
                        for i in range(30))
        assert CrossReferenceIndex(pages)._detect_page_offset() == 0


class TestCitiFY2022Extraction:

    def test_item_7a_page_range_is_the_printed_one(self, citi_2022):
        assert str(citi_2022.get_page_ranges("7A")[0]) == "60-121"

    def test_item_7a_opens_on_printed_page_60(self, citi_2022):
        """Printed page 60 opens mid-sentence inside Managing Global Risk (its
        heading is on page 59; the index cites 60). Before the fix this opened
        on printed page 57 with the Item 1 human capital section."""
        text = _text(citi_2022.extract_content_by_page_range(citi_2022.get_page_ranges("7A")[0]))
        assert text.startswith("with prescribed practices, internal policies and procedures or ethical standards.")
        assert "HUMAN CAPITAL RESOURCES AND MANAGEMENT" not in text[:20000]
        # The slice ends on the footer of printed page 121, the last page cited.
        assert text.endswith(" 121")

    def test_other_items_open_on_their_headings(self, citi_2022):
        assert _text(citi_2022.extract_item_content("1A")).startswith("RISK FACTORS The following discussion")
        assert _text(citi_2022.extract_item_content("1")).startswith(
            "OVERVIEW Citigroup’s history dates back to the founding of the City Bank of New York in 1812.")

    def test_tenk_item_7a(self, citi_2022_html):
        """The user-facing path: filing.obj()["Item 7A"] via the cross-reference branch."""
        tenk = TenK(_StubFiling(citi_2022_html, "0000831001-23-000037", "2023-02-27"))
        assert tenk["Item 7A"].startswith("with prescribed practices, internal policies")
        assert tenk["Item 1A"].startswith("RISK FACTORS\n")


class TestAlignedFilingsUnchanged:
    """Offset 0 must leave extraction exactly as it was before the fix.

    Hashes were taken from main before the fix (a229a01b) on these fixtures.
    """

    def test_citi_fy2024_item_7a(self, citi_2024):
        """Printed page 70, the first page Citi's FY2024 index cites for 7A."""
        content = citi_2024.extract_item_content("7A")
        assert _text(content).startswith(
            "Third Line of Defense: Internal Audit Internal Audit is independent of")
        assert _sha1(content) == "9c9b57e8d449406ba81acaf5c4ed892307209950"

    @pytest.mark.parametrize("item,sha1", [
        ("1A", "21bd4549a2d05e2cab08301bac12751dcbbed937"),
        ("7A", "4f4afc269618754adb29e88c289d96fbd7333e92"),
        ("8", "d21d721e679a03ac5240350e8c2630adba48e306"),
    ])
    def test_ge_items_byte_identical(self, ge_2025, item, sha1):
        assert _sha1(ge_2025.extract_item_content(item)) == sha1

    def test_ge_risk_factors_opening(self, ge_2025):
        assert _text(ge_2025.extract_item_content("1A")).startswith(
            "RISK FACTORS. The following discussion of the material factors")
