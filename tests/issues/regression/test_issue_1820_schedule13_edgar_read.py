"""edgar_read read no sections from a Schedule 13D or 13G filed since December 2024.

Since December 2024 these filings carry the form names ``SCHEDULE 13D`` and
``SCHEDULE 13G``, but the reader only routed ``SC 13D`` and ``SC 13G``. Every
current filing therefore offered just ``full_text``, and a requested ``purpose``
or ``ownership`` section came back as None. For an ``SC 13D`` the ``purpose``
section read an attribute Schedule13D does not have and fell back to ``str(obj)``,
so it returned the object's summary instead of Item 4.

Ground truth: BML Investment Partners' SCHEDULE 13D on Aadi Bioscience,
0001373604-24-000118, filed 2024-12-31 (tests/data/beneficial_ownership/schedule13d.xml).
Item 4 opens "The Reporting Persons purchased the Common Stock reported hereunder for
investment purposes", and Leonard Braden Michael reports 2,435,000 shares, 9.9% of the class.
In tests/data/beneficial_ownership/schedule13g.xml, Marex reports 10,000,000 shares of
Jushi Holdings, 5.1% of the class.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1820
"""
from datetime import date
from unittest.mock import Mock

import pytest

from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.reader import edgar_read
from edgar.beneficial_ownership import Schedule13D, Schedule13G
from tests.paths import TESTS_DIR

DATA_DIR = TESTS_DIR / "data" / "beneficial_ownership"


def _schedule13(form: str):
    schedule, xml = (Schedule13G, "schedule13g.xml") if "13G" in form else (Schedule13D, "schedule13d.xml")
    filing = Mock()
    filing.form = form
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=(DATA_DIR / xml).read_text())
    return schedule.from_filing(filing)


def _filing(form: str):
    class Filing:
        accession_number = "0001373604-24-000118"
        filing_date = "2024-12-31"
        company = "BML Investment Partners, L.P."
        cik = 1373604

        def obj(self):
            return _schedule13(form)

    Filing.form = form
    return Filing()


@pytest.mark.fast
@pytest.mark.parametrize("form", ["SCHEDULE 13D", "SCHEDULE 13D/A", "SC 13D"])
async def test_schedule13d_purpose_is_item_4(monkeypatch, form):
    monkeypatch.setattr(reader, "find", lambda search_id: _filing(form))
    response = await edgar_read(accession_number="0001373604-24-000118", sections=["purpose", "ownership"])
    sections = response.data["sections"]
    assert sections["purpose"].startswith(
        "The Reporting Persons purchased the Common Stock reported hereunder for investment purposes"
    )
    assert "Total Shares: 2,435,000" in sections["ownership"]
    assert "Ownership Percentage: 9.9%" in sections["ownership"]


@pytest.mark.fast
@pytest.mark.parametrize("form", ["SCHEDULE 13G", "SCHEDULE 13G/A", "SC 13G"])
async def test_schedule13g_ownership(monkeypatch, form):
    monkeypatch.setattr(reader, "find", lambda search_id: _filing(form))
    response = await edgar_read(accession_number="0001373604-24-000118", sections=["ownership"])
    ownership = response.data["sections"]["ownership"]
    assert "Total Shares: 10,000,000" in ownership
    assert "Ownership Percentage: 5.1%" in ownership


@pytest.mark.fast
@pytest.mark.parametrize("items", [None, Mock(spec=[])])
def test_schedule13_purpose_without_item_4_is_none(items):
    assert reader._extract_schedule13_section(Mock(spec=["items"], items=items), "purpose") is None


@pytest.mark.fast
@pytest.mark.parametrize(
    "form, sections",
    [
        ("SCHEDULE 13D", ["ownership", "purpose"]),
        ("SCHEDULE 13D/A", ["ownership", "purpose"]),
        ("SCHEDULE 13G", ["ownership"]),
        ("SCHEDULE 13G/A", ["ownership"]),
        ("SC 13G", ["ownership"]),
    ],
)
def test_schedule13_section_list(form, sections):
    assert reader._get_section_list(form) == sections
