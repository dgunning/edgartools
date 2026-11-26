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


# Each 10-K's MD&A closes on the same cross-reference, then "ITEM 7A." follows.
ITEM_7_ENDINGS = {
    "2021": "please see Note 1 – Significant Accounting Policies included under Item 8.",
    "2023": "please see Note 1 – Basis of Presentation and Significant Accounting Policies "
            "included under Item 8.",
    "2024": "please see Note 1 – Basis of Presentation and Significant Accounting Policies "
            "included under Item 8.",
}


def test_item_7_ends_on_its_closing_cross_reference(request, tenk):
    """Item 7 keeps its last line (FY2023 lost it).

    In the FY2023 10-K the last line is two positioned divs: a link "Note 1 – ..."
    and "included under Item 8.", whose div holds an empty inline-block spacer. The
    end-of-section furniture pass read that div as a container, skipped its text, and
    took the link (printed three times in the filing) for a running header, so Item 7
    ended at "...please see".
    """
    year = request.node.callspec.params["tenk"]
    mda = " ".join(tenk['Item 7'].split())

    assert mda.endswith(ITEM_7_ENDINGS[year])
    assert "Quantitative and Qualitative Disclosures" not in mda[-500:]


# The opening sentence of Item 2 and the closing date of the auditor's report in Item 9A.
ITEM_2_OPENINGS = {
    "2021": "We own or lease the following properties with more than 100,000 square feet",
    "2023": "Within our health care distribution segment (for properties with more than 100,000 square feet)",
    "2024": "Within our health care distribution segment (for properties with more than 100,000 square feet)",
}
ITEM_9A_DATES = {"2021": "February 17, 2021", "2023": "February 21, 2023", "2024": "February 28, 2024"}


def test_item_2_opens_on_its_first_sentence(request, tenk):
    """FY2022 and FY2023 Item 2 opened mid-sentence ("and/or own approximately ...")."""
    year = request.node.callspec.params["tenk"]
    properties = " ".join(tenk['Item 2'].split())

    assert ITEM_2_OPENINGS[year] in properties[:200]


def test_item_9a_ends_on_the_auditors_report(request, tenk):
    """Item 9A ends on the report's date, not on "ITEM 9B. Other Information".

    Item 9B's TOC anchor is on "Not applicable." below its heading, so the
    heading belongs to Item 9B, not to the end of Item 9A.
    """
    year = request.node.callspec.params["tenk"]
    controls = " ".join(tenk['Item 9A'].split())

    assert controls.endswith(ITEM_9A_DATES[year])


def test_item_15_does_not_end_on_the_item_16_heading(tenk):
    exhibits = " ".join(tenk['Item 15'].split())

    assert not exhibits.endswith("Form 10-K Summary")
    assert "ITEM 16" not in exhibits[-200:]
