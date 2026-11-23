"""
Regression test for Issue #107: TenK function could not extract content of some filings

GitHub Issue: https://github.com/dgunning/edgartools/issues/107
Reporter: GitHub user

Bug (FIXED): TenK extraction was returning only item headings without actual content for
certain filings. Henry Schein's (CIK 1000228) 10-Ks filed in 2021, 2023 and 2024 returned
items of ~18 characters (just a heading like "ITEM 1.\\nBusiness\\n3") instead of the
full content. The issue also named CIK 350852 (2018, 2019 filings); that is not covered here.

Root Cause: ChunkedDocument (old parser) failed on certain filing formats.
Fix: TenK migrated to the new HTMLParser, which extracts full content.

These tests used to resolve "the latest 10-K filed since 2021-01-01" (and since 2023,
and since 2024). All three are open-ended ranges, so every case tested the same newest
filing and the 2021 and 2023 filings the issue names were never checked. They also
passed when an item came back None. They now run offline on the three filings the issue
names, saved verbatim (gzipped) under tests/fixtures/html_gz/hsic/10k/:

    0001000228-21-000019  filed 2021-02-17  hsicform10k20201226.htm  (FY2020)
    0001000228-23-000011  filed 2023-02-21  hsic-20221231.htm        (FY2022)
    0001000228-24-000011  filed 2024-02-28  form10k20231230.htm      (FY2023)

In each filing's HTML, Item 1 ends with the executive-officer biography "...as a
management consultant from 2000 to 2003." followed by "ITEM 1A. Risk Factors", and Item
1A ends "...the availability and cost of credit to us." followed by "Item 1B.
Unresolved Staff Comments".
"""
import gzip
from pathlib import Path

import pytest

from edgar.company_reports import TenK

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).parents[2] / "fixtures" / "html_gz" / "hsic" / "10k"

FILINGS = {
    "2021": ("0001000228-21-000019", "2021-02-17", "hsicform10k20201226.htm.gz"),
    "2023": ("0001000228-23-000011", "2023-02-21", "hsic-20221231.htm.gz"),
    "2024": ("0001000228-24-000011", "2024-02-28", "form10k20231230.htm.gz"),
}


class _FixtureFiling:
    """The surface TenK needs: html(), and identifiers used in logging."""
    base_dir = ""
    form = "10-K"
    company = "HENRY SCHEIN INC"
    cik = 1000228

    def __init__(self, accession_number: str, filing_date: str, html: str):
        self.accession_number = accession_number
        self.filing_date = filing_date
        self._html = html

    def html(self) -> str:
        return self._html


@pytest.fixture(scope="module", params=list(FILINGS))
def tenk(request):
    accession, filed, name = FILINGS[request.param]
    html = gzip.decompress((FIXTURES / name).read_bytes()).decode("utf-8")
    return TenK(_FixtureFiling(accession, filed, html))


def test_the_fixtures_are_present():
    """Absent is not passing."""
    for _, _, name in FILINGS.values():
        assert (FIXTURES / name).is_file(), name


def test_item_1_is_the_whole_business_section(tenk):
    item1 = tenk['Item 1']

    assert item1.startswith("Business")
    assert "Henry Schein, Inc. is a solutions company" in item1[:200]
    assert " ".join(item1.split()).endswith("as a management consultant from 2000 to 2003.")
    assert "ITEM 1A" not in item1
    assert len(item1) > 90000, f"Item 1 is {len(item1)} chars; the bug returned ~18"


def test_item_1a_is_the_whole_risk_factors_section(tenk):
    risk = tenk['Item 1A']

    assert risk.startswith("Our business operations could be affected by factors")
    assert " ".join(risk.split()).endswith("the availability and cost of credit to us.")
    assert "Unresolved Staff Comments" not in risk
    assert len(risk) > 60000, f"Item 1A is {len(risk)} chars"


def test_item_7_has_its_content(tenk):
    mda = tenk['Item 7']

    assert mda.startswith("Management’s Discussion and Analysis of Financial Condition")
    assert len(mda) > 50000, f"Item 7 is {len(mda)} chars; the bug returned ~18"
