"""
Regression test for 8-K item headings written with a dash after "Item": "Item - 5.02".

GitHub Issue: https://github.com/dgunning/edgartools/issues/1589

Defect
------
Liaoning Shuiyun Qinghe Rice Industry Co., Ltd. (CIK 710782) heads its item in its 8-K
0000710782-24-000005 (filed 2024-12-20) as "Item - 5.02 Departure of Directors of
Principal Officers; Election of Directors; Appointment of Principal Officers." On the
unchanged code CurrentReport found no item at all: ``items == []``, ``content_type ==
'other'``, and ``report["5.02"]`` raised SectionNotFoundError.

Root cause
----------
The text-based item patterns in edgar/company_reports/current_report.py required
whitespace between "Item" and the number. A dash there was never matched, so the
item was missing from the item list, from the content-type classifier and from the
item lookup alike. The same whitespace-only rule sat in the pattern that ends an
item at the next item heading, so the next dash heading would not have ended the
item either.

Fix
---
One shared item label now accepts an optional dash, en dash, em dash or colon:
``Item\\s*[-–—:]?\\s*``. Detection, the start of an item and the end of an
item all use it, so they cannot disagree again.

Fixture
-------
tests/fixtures/issues/regression/issue_1589/0000710782-24-000005.htm is the primary
document of that filing (8kSYQH.htm), saved byte for byte as the SEC served it. That
includes a bot-defense <script> tag that www.sec.gov adds to every response; its src
changes from one request to the next, and it is not part of the filing. The HTML
parser removes script elements before it builds the text, and the assertions concern
the filed item headings and text, so the tag does not affect them. The SGML envelope
around the HTML is removed before parsing, as Filing.text() does. The test reads the
file with line endings normalised, so it passes on LF and CRLF checkouts.
"""

import pathlib

import pytest

from edgar.company_reports.current_report import (
    CurrentReport,
    _extract_item_content_from_text,
    _extract_items_from_text,
)
from edgar.documents import HTMLParser, ParserConfig
from edgar.exceptions import SectionNotFoundError

FIXTURE = (pathlib.Path(__file__).parent.parent.parent
           / "fixtures" / "issues" / "regression" / "issue_1589" / "0000710782-24-000005.htm")

HEADING = ("Item - 5.02 Departure of Directors of Principal Officers; Election of Directors; "
           "Appointment of Principal Officers.")


def _load_primary_document() -> str:
    raw = FIXTURE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    # The SEC envelope: <DOCUMENT><TYPE>...<TEXT> body </TEXT></DOCUMENT>. Filing.text()
    # never sees it, so the test removes it too.
    if "<TEXT>" in raw[:500]:
        raw = raw.split("<TEXT>", 1)[1].rsplit("</TEXT>", 1)[0]
    return raw


class FixtureFiling:
    """The minimal filing surface CurrentReport reads, backed by the saved primary document."""

    filing_date = None
    company = "Liaoning Shuiyun Qinghe Rice Industry Co., Ltd."
    accession_number = "0000710782-24-000005"
    base_dir = str(FIXTURE.parent)
    form = "8-K"
    attachments = []

    def __init__(self, html: str):
        self._html = html

    def html(self):
        return self._html

    def text(self, include_images: bool = False) -> str:
        document = HTMLParser(ParserConfig(form="8-K")).parse(self._html)
        return document.text(table_max_col_width=500, include_images=include_images)


@pytest.fixture(scope="module")
def eight_k():
    return CurrentReport(FixtureFiling(_load_primary_document()))


@pytest.fixture(scope="module")
def filing_text():
    return FixtureFiling(_load_primary_document()).text()


def test_dash_heading_is_detected_in_the_filing_text(filing_text):
    """The heading "Item - 5.02" on its own line is item 5.02."""
    assert HEADING in filing_text
    assert _extract_items_from_text(filing_text) == ["5.02"]


def test_report_lists_the_item_and_classifies_the_filing(eight_k):
    """items and content_type both read the item detected from the dash heading."""
    assert eight_k.items == ["Item 5.02"]
    assert eight_k.content_type == "director_change"


def test_item_text_runs_from_the_heading_to_the_signature(eight_k):
    """report["5.02"] is the item from its heading to the end of the item, before SIGNATURE."""
    text = eight_k["5.02"]

    assert text is not None
    assert text.startswith(HEADING)
    assert text.endswith("List of shareholder:\nRu Fan")
    assert "SIGNATURE" not in text
    assert "Baobin He" not in text
    assert eight_k["Item 5.02"] == text


def test_item_missing_from_the_filing_still_raises(eight_k):
    """A lookup that finds nothing raises a useful error; it does not return None."""
    with pytest.raises(SectionNotFoundError):
        eight_k["8.01"]


@pytest.mark.parametrize("heading", [
    "Item - 5.02 Departure of Directors",
    "Item – 5.02 Departure of Directors",   # en dash
    "Item — 5.02 Departure of Directors",   # em dash
    "Item: 5.02 Departure of Directors",
    "Item-5.02 Departure of Directors",
])
def test_each_separator_heading_is_an_item(heading):
    """The dash, en dash, em dash and colon forms are detected, and the item starts at the heading."""
    text = "Intro paragraph.\n\n" + heading + "\n\nThe director resigned.\n"

    assert _extract_items_from_text(text) == ["5.02"]
    content = _extract_item_content_from_text(text, "5.02")
    assert content == heading + "\n\nThe director resigned."


def test_mid_sentence_dash_reference_is_not_an_item():
    """A reference to an item inside a sentence is not a heading, with or without the dash."""
    text = "The change is described in Item - 5.02 above.\n"

    assert _extract_items_from_text(text) == []
    assert _extract_item_content_from_text(text, "5.02") is None


def test_standard_headings_are_still_detected():
    """The usual headings, "Item 8.01." with its trailing period included, are still items."""
    text = (
        "Item 2.02 Results of Operations and Financial Condition\n\n"
        "Revenue grew.\n\n"
        "Item 8.01. Other Events\n\n"
        "The company announced a dividend.\n\n"
        "Item 9.01 Financial Statements and Exhibits\n\n"
        "Exhibit 99.1\n"
    )

    assert _extract_items_from_text(text) == ["2.02", "8.01", "9.01"]
    content = _extract_item_content_from_text(text, "8.01")
    assert content is not None
    assert content.startswith("Item 8.01. Other Events")
    assert "Item 9.01" not in content


def test_dash_heading_ends_the_previous_item():
    """A dash heading is also the end of the item before it, so items do not run together."""
    text = (
        "Item - 5.02 Departure of Directors\n\n"
        "The first director resigned.\n\n"
        "Item - 8.01 Other Events\n\n"
        "The second paragraph is item 8.01.\n"
    )

    first = _extract_item_content_from_text(text, "5.02")
    assert first is not None
    assert first.endswith("The first director resigned.")
    assert "Item - 8.01" not in first
    assert "second paragraph" not in first
