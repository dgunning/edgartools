"""
Regression test: EntityFiling.parsed_items returned "" for an 8-K headed "Item - 5.02".

GitHub Issue: https://github.com/dgunning/edgartools/issues/1773

parsed_items had its own item regex (``(?:ITEM|Item)\\s+(\\d+...)``) that required whitespace
then the number, so the dash heading fixed in CurrentReport by #1590 was never matched.
It now uses CurrentReport's shared ``_ITEM_LABEL`` and ``_ITEM_NUMBER`` patterns.

Filing: Liaoning Shuiyun Qinghe Rice Industry Co., Ltd. (CIK 710782) 8-K 0000710782-24-000005,
SEC metadata items '5.02', heading "Item - 5.02 Departure of Directors of Principal Officers".
The fixture is the primary document saved for #1589.
"""

import pathlib

import pytest

from edgar import Company
from edgar.entity.filings import EntityFiling

FIXTURE = (pathlib.Path(__file__).parent.parent.parent
           / "fixtures" / "issues" / "regression" / "issue_1589" / "0000710782-24-000005.htm")


class _Document:
    def __init__(self, html):
        self._html = html

    def download(self):
        return self._html


def _filing_with(monkeypatch, html):
    filing = EntityFiling.__new__(EntityFiling)
    filing.form = "8-K"
    filing.accession_no = "0000710782-24-000005"
    monkeypatch.setattr(EntityFiling, "document", property(lambda self: _Document(html)))
    return filing


@pytest.mark.regression
def test_dash_heading_in_real_filing_is_parsed(monkeypatch):
    raw = FIXTURE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if "<TEXT>" in raw[:500]:
        raw = raw.split("<TEXT>", 1)[1].rsplit("</TEXT>", 1)[0]
    assert _filing_with(monkeypatch, raw).parsed_items == "5.02"


@pytest.mark.regression
def test_separators_and_invalid_numbers(monkeypatch):
    html = ("<html><body>"
            "<p>Item: 2.02 Results of Operations</p>"
            "<p>Item 9. 01 Financial Statements and Exhibits</p>"
            "<p>Section 401(k) plan; Item 2024 bonus awards</p>"
            "<p>Item 3 Not Applicable</p>"
            "</body></html>")
    assert _filing_with(monkeypatch, html).parsed_items == "2.02,9.01"


@pytest.mark.regression
@pytest.mark.network
@pytest.mark.vcr
def test_issue_1773_live_parsed_items_match_sec_metadata():
    filings = Company(710782).get_filings(form="8-K", filing_date="2024-01-01:2024-12-31")
    filing = next(f for f in filings if f.accession_no == "0000710782-24-000005")
    assert filing.items == "5.02"
    assert filing.parsed_items == "5.02"
