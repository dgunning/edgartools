"""MCP handoff tests that retain the SEC document identity."""

from types import SimpleNamespace

import pytest

import edgar
from edgar.ai.mcp.tools.filing import edgar_filing
from edgar.ai.mcp.tools.text_search import edgar_text_search
from edgar.search.efts import EFTSResult, EFTSSearch


ACCESSION = "0000320193-23-000077"
FILING_URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/index.html"


class FakeFiling:
    accession_no = ACCESSION
    form = "10-Q"
    company = "Apple Inc."
    filing_date = "2023-05-05"
    report_date = "2023-04-01"
    url = FILING_URL

    def __init__(self, attachments):
        self.attachments = attachments

    def obj(self):
        return None

    def to_context(self, detail="standard"):
        return "Fake filing context"

    @property
    def period_of_report(self):
        raise AssertionError("the preloaded report_date should avoid loading period_of_report")


class UnavailableAttachmentsFiling(FakeFiling):
    def __init__(self):
        pass

    @property
    def attachments(self):
        raise RuntimeError("private attachment backend details")


def _attachment(filename, sequence):
    return SimpleNamespace(document=filename, sequence_number=sequence)


@pytest.mark.fast
@pytest.mark.asyncio
async def test_filing_sec_exhibit_url_preserves_attachment_identity(monkeypatch):
    attachment = _attachment("credit-agreement.htm", "7")
    filing = FakeFiling([attachment])
    find_calls = []

    def fake_find(*, search_id):
        find_calls.append(search_id)
        return filing

    monkeypatch.setattr(edgar, "find", fake_find)
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/credit-agreement.htm"

    response = await edgar_filing(input=url)

    assert response.success
    data = response.to_dict()["data"]
    assert data["accession_number"] == ACCESSION
    assert data["period_of_report"] == "2023-04-01"
    assert data["url"] == FILING_URL
    assert data["document_hint"] == {
        "filename": "credit-agreement.htm",
        "matched": True,
        "sequence_number": "7",
    }
    assert find_calls == [ACCESSION]
    assert any(
        "edgar_document" in step and ACCESSION in step and "credit-agreement.htm" in step
        for step in response.next_steps
    )


@pytest.mark.fast
@pytest.mark.asyncio
async def test_filing_sec_url_with_unknown_filename_is_explicitly_unmatched(monkeypatch):
    filing = FakeFiling([_attachment("primary.htm", "1")])
    monkeypatch.setattr(edgar, "find", lambda *, search_id: filing)
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/missing-exhibit.htm"

    response = await edgar_filing(input=url)

    assert response.success
    assert response.to_dict()["data"]["document_hint"] == {
        "filename": "missing-exhibit.htm",
        "matched": False,
    }
    assert any(
        "missing-exhibit.htm" in step
        and "not found" in step.lower()
        and "edgar_document" in step
        and ACCESSION in step
        for step in response.next_steps
    )


@pytest.mark.fast
@pytest.mark.asyncio
async def test_filing_sec_url_reports_unavailable_attachment_verification(monkeypatch):
    filing = UnavailableAttachmentsFiling()
    monkeypatch.setattr(edgar, "find", lambda *, search_id: filing)
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/credit-agreement.htm"

    response = await edgar_filing(input=url)

    assert response.success
    hint = response.to_dict()["data"]["document_hint"]
    assert hint == {
        "filename": "credit-agreement.htm",
        "matched": None,
        "status": "unavailable",
        "reason": "Attachment metadata could not be checked.",
    }
    assert any("edgar_document" in step and '"action": "list"' in step for step in response.next_steps)
    assert not any("not found" in step.lower() for step in response.next_steps)


@pytest.mark.fast
@pytest.mark.asyncio
async def test_text_search_routes_each_hit_using_its_document_id(monkeypatch):
    with_document = EFTSResult(
        accession_number=ACCESSION,
        form="8-K",
        filed="2023-05-05",
        file_type="EX-10.1",
        file_description="Credit Agreement",
        document_id="credit-agreement.htm",
    )
    without_document = EFTSResult(
        accession_number="0000320193-23-000088",
        form="8-K",
        filed="2023-05-10",
    )
    search = EFTSSearch(query="credit agreement", total=2, results=[with_document, without_document])

    def fake_search_filings(*args, **kwargs):
        return search

    monkeypatch.setattr("edgar.search.efts.search_filings", fake_search_filings)

    response = await edgar_text_search(query="credit agreement")

    assert response.success
    first, second = response.to_dict()["data"]["results"]
    assert first["file_type"] == "EX-10.1"
    assert first["file_description"] == "Credit Agreement"
    assert first["document_id"] == "credit-agreement.htm"
    assert any(
        "edgar_document" in step
        and ACCESSION in step
        and "credit-agreement.htm" in step
        for step in response.next_steps
    )
    assert any("edgar_filing" in step and second["accession_number"] in step for step in response.next_steps)
    assert not {"file_type", "file_description", "document_id"}.intersection(second)
