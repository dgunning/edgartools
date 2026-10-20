"""Regression test for GitHub issue #1582.

edgar_read on a 10-K with no XBRL returned success with `financials: None` and
nothing saying why, and on a malformed accession number it dropped find()'s
ValidationError, answering 'Could not find filing' with no error_code.

No XBRL is an answer, not a failure (docs/upgrade/6.0.md), so the response stays
a success and now says why the statements are missing and where to read them.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1582
"""
import pytest

from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.reader import NO_XBRL_NOTE, edgar_read


class _FakeReport:
    financials = None


class _FakeFiling:
    accession_number = "0001193125-08-093063"
    filing_date = "2008-04-28"
    company = "CIRCUIT CITY STORES INC"
    cik = 104599

    def __init__(self, form, has_xbrl):
        self.form = form
        self._has_xbrl = has_xbrl

    def obj(self):
        return _FakeReport()

    def xbrl(self):
        return object() if self._has_xbrl else None


@pytest.mark.fast
@pytest.mark.asyncio
@pytest.mark.parametrize("form, pointer", [
    ("10-K", "sections=['Item 8']"),
    ("10-Q", "sections=['Part I, Item 1']"),
    ("20-F", "sections=['full_text']"),
])
async def test_no_xbrl_financials_say_why(monkeypatch, form, pointer):
    monkeypatch.setattr(reader, "find", lambda search_id: _FakeFiling(form, has_xbrl=False))
    r = await edgar_read(accession_number="0001193125-08-093063", sections=["financials"])
    assert r.success is True
    assert r.data["sections"] == {"financials": None}
    assert r.data["notes"] == {"financials": NO_XBRL_NOTE}
    assert pointer in r.next_steps[0]


@pytest.mark.fast
@pytest.mark.asyncio
async def test_financials_that_fail_to_render_get_no_no_xbrl_note(monkeypatch):
    # The filing has XBRL, so None means something else; don't claim there is none
    monkeypatch.setattr(reader, "find", lambda search_id: _FakeFiling("10-K", has_xbrl=True))
    r = await edgar_read(accession_number="0001193125-08-093063", sections=["financials"])
    assert "notes" not in r.data


@pytest.mark.fast
@pytest.mark.asyncio
async def test_malformed_accession_returns_the_validation_message_and_a_code():
    r = await edgar_read(accession_number="123456-99", sections=["financials"])
    assert r.success is False
    assert r.error_code == "INVALID_ARGUMENTS"
    assert "'123456-99' is not a valid accession number" in r.error


@pytest.mark.fast
@pytest.mark.asyncio
async def test_no_filing_found_has_a_code(monkeypatch):
    monkeypatch.setattr(reader, "find", lambda search_id: None)
    r = await edgar_read(accession_number="0000000000-00-000000")
    assert (r.success, r.error_code) == (False, "FILING_NOT_FOUND")


@pytest.mark.network
@pytest.mark.asyncio
async def test_circuit_city_10k_points_to_item_8_and_item_8_has_the_statements():
    # Circuit City 10-K for FY ended 2008-02-29, no XBRL attachments
    r = await edgar_read(accession_number="0001193125-08-093063", sections=["financials"])
    assert r.success is True and r.data["notes"] == {"financials": NO_XBRL_NOTE}
    r = await edgar_read(accession_number="0001193125-08-093063", sections=["Item 8"])
    item8 = r.data["sections"]["Item 8"]
    assert "11,743,691" in item8   # net sales, $ thousands
    assert "3,745,930" in item8    # total assets, $ thousands
