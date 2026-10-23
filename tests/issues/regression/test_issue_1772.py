"""
Regression test: 8-K item detection accepted any number after "Item".

GitHub Issue: https://github.com/dgunning/edgartools/issues/1772

A body line starting "ITEM 2024 performance awards ..." was reported as item '2024', and
"ITEM - 2024 annual bonus ..." ended Item 5.02 early. Detection, item start and item end
in edgar/company_reports/current_report.py each matched ``\\d+\\.?\\s*\\d*``. They now share
``_ITEM_NUMBER``, which matches only a whole 8-K item number ("2.02", "9. 01", legacy "1"-"9").
"""

import pathlib

import pytest

from edgar.company_reports.current_report import (
    _ITEM_NUMBER,
    _extract_item_content_from_text,
    _extract_items_from_text,
)
from edgar.documents import HTMLParser, ParserConfig

TEXT = (
    "Item 5.02 Departure of Directors or Certain Officers.\n"
    "On March 1, the Board appointed a new Chief Financial Officer.\n"
    "ITEM - 2024 annual bonus targets were also approved.\n"
    "ITEM 2024 performance awards vest over three years.\n"
    "Item 9.01 Financial Statements and Exhibits.\n"
    "(d) Exhibits.\n"
)

FIXTURE = (pathlib.Path(__file__).parent.parent.parent
           / "fixtures" / "issues" / "regression" / "issue_1589" / "0000710782-24-000005.htm")


@pytest.mark.regression
def test_year_after_item_is_not_an_item():
    assert _extract_items_from_text(TEXT) == ["5.02", "9.01"]


@pytest.mark.regression
def test_year_after_item_does_not_end_the_item():
    content = _extract_item_content_from_text(TEXT, "Item 5.02")
    assert "bonus targets were also approved" in content
    assert "performance awards vest" in content
    assert "Item 9.01" not in content


@pytest.mark.regression
def test_legacy_item_does_not_start_at_a_longer_item_number():
    text = "Item 5.02 Departure\nfirst\nItem 5. Other Events\nsecond\nItem 7. Exhibits\n"
    assert _extract_items_from_text(text) == ["5", "5.02", "7"]
    assert _extract_item_content_from_text(text, "5") == "Item 5. Other Events\nsecond"


@pytest.mark.regression
@pytest.mark.parametrize("number,ok", [
    ("2.02", True), ("9. 01", True), ("7", True),
    ("2024", False), ("401", False), ("10", False),
])
def test_item_number_pattern(number, ok):
    import re
    assert bool(re.fullmatch(_ITEM_NUMBER, number)) is ok


@pytest.mark.regression
def test_real_filing_items_unchanged():
    # Liaoning Shuiyun Qinghe Rice Industry 8-K 0000710782-24-000005, headed "Item - 5.02"
    raw = FIXTURE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if "<TEXT>" in raw[:500]:
        raw = raw.split("<TEXT>", 1)[1].rsplit("</TEXT>", 1)[0]
    text = HTMLParser(ParserConfig(form="8-K")).parse(raw).text(table_max_col_width=500)
    assert _extract_items_from_text(text) == ["5.02"]
    content = _extract_item_content_from_text(text, "5.02")
    assert content.startswith("Item - 5.02 Departure of Directors of Principal Officers")
