"""
Regression test for GitHub Issue #251: Citigroup 10-K section extraction returns None.

Issue: Citigroup uses bare item numbers (e.g., "1.", "1A.") without the "Item" prefix
and the heading "FORM 10-K CROSS-REFERENCE INDEX" (all caps, hyphenated).
All three parsing strategies failed:
1. TOC parser: links contain only page numbers
2. CrossReferenceIndex: case-sensitive heading match + "Item" prefix required
3. Legacy chunked parser: no "Item X" text anywhere in the 16MB HTML

Solution: Made CrossReferenceIndex detection case-insensitive and hyphen-tolerant,
supported bare item numbers, en-dash page ranges, and continuation rows.

Pinned to Citigroup's FY2024 10-K (0000831001-25-000067, filed 2025-02-21),
committed at tests/fixtures/html/c/10k/c-10-k-2025-02-21.html. These tests used
to read the latest 10-K, while hard-coding page numbers from the FY2025 one
(Item 1A at 49-62); the next 10-K would have broken them. The values below
were read from the fixture's cross-reference table, not through the parser:

    1.   Business        4–32, 130–135, / 137, 169–173, / 314–315   (three rows)
    1A.  Risk Factors    50–64

Printed page 64 ends with "...see the macroeconomic challenges and
uncertainties risk factor above." and page 65 opens "NET ZERO AND
SUSTAINABILITY".

GitHub Issue: https://github.com/dgunning/edgartools/issues/251
"""
from pathlib import Path

import pytest

from edgar.company_reports import TenK
from edgar.documents import CrossReferenceIndex

pytestmark = pytest.mark.fast

CITI_FY2024 = Path(__file__).parents[2] / "fixtures" / "html" / "c" / "10k" / "c-10-k-2025-02-21.html"


class _FixtureFiling:
    """The surface TenK needs: html(), and identifiers used in logging."""
    base_dir = ""
    form = "10-K"
    company = "Citigroup Inc."
    cik = 831001
    accession_number = "0000831001-25-000067"
    filing_date = "2025-02-21"

    def __init__(self, html: str):
        self._html = html

    def html(self) -> str:
        return self._html


@pytest.fixture(scope="module")
def citi_html():
    return CITI_FY2024.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tenk(citi_html):
    return TenK(_FixtureFiling(citi_html))


def test_the_fixture_is_present():
    """Absent is not passing."""
    assert CITI_FY2024.is_file()


def test_citigroup_has_cross_reference_index(citi_html):
    """Citigroup's FORM 10-K CROSS-REFERENCE INDEX is detected."""
    assert CrossReferenceIndex(citi_html).has_index()


def test_citigroup_parses_all_items(citi_html):
    """Every item is parsed from bare item numbers."""
    entries = CrossReferenceIndex(citi_html).parse()

    assert sorted(entries) == sorted([
        '1', '1A', '1B', '1C', '2', '3', '4', '5', '6', '7', '7A', '8',
        '9', '9A', '9B', '9C', '10', '11', '12', '13', '14', '15',
    ])


def test_citigroup_item1_continuation_rows(citi_html):
    """Item 1's page ranges span three rows of the index."""
    entry = CrossReferenceIndex(citi_html).get_item('1')

    assert entry.item_title == 'Business'
    assert [(p.start, p.end) for p in entry.pages] == [
        (4, 32), (130, 135), (137, 137), (169, 173), (314, 315),
    ]


def test_citigroup_en_dash_page_ranges(citi_html):
    """En-dash (&#8211;) page ranges are parsed correctly."""
    entry = CrossReferenceIndex(citi_html).get_item('1A')

    assert entry.item_title == 'Risk Factors'
    assert [(p.start, p.end) for p in entry.pages] == [(50, 64)]


def test_citigroup_tenk_section_extraction(tenk):
    """TenK extracts actual content via the cross-reference index."""
    mda = tenk['Item 7']
    assert mda.startswith("MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION")
    assert len(mda) > 100000, f"MD&A too short: {len(mda)} chars"

    # Content, not just size: a page-offset error (GH #1346) returns a
    # neighbouring section of similar length.
    risk = tenk['Item 1A']
    assert risk.startswith("RISK FACTORS"), f"Item 1A opens with {risk[:80]!r}"
    assert risk.rstrip().endswith("see the macroeconomic challenges and uncertainties risk factor above.")
    assert "NET ZERO AND SUSTAINABILITY" not in risk
