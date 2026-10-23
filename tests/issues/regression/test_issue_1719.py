"""edgar_read advertised ``full_text`` and returned success with null for most forms.

``_get_section_list`` lists ``full_text`` for every form outside its explicit map, and
for 6-K. The handler indexed the typed filing object (``obj['full_text']``): the
6-K, 424B5, S-4 and S-1/A objects have no subscript support, so the lookup raised
``TypeError`` and the handler swallowed it; the 40-F lookup returned None. Every
case answered ``success: True, sections: {'full_text': None}``.

``full_text`` now reads the filing's own text, and a filing with no text says so.

Ground truth (the first characters of each filing's primary document, read from SEC):
  HSBC Holdings 6-K 0001654954-26-002864          "FORM 6-K" ... "HSBC Holdings plc"
  Curis 424B5 0001108205-25-000026                "Filed pursuant to Rule 424(b)(5)" ... "1,974,432 Shares"

GitHub Issue: https://github.com/dgunning/edgartools/issues/1719
"""
import pytest

from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.reader import edgar_read
from tests._offline_filings import offline_filing


class _Filing:
    accession_number = "0000000000-00-000000"
    filing_date = "2024-01-01"
    company = "Test Co"
    cik = 1
    form = "6-K"


@pytest.fixture
def offline_find(monkeypatch):
    monkeypatch.setattr(reader, "find", lambda search_id: offline_filing(search_id))


@pytest.mark.vcr
async def test_issue_1719_six_k_full_text(offline_find):
    response = await edgar_read(accession_number="0001654954-26-002864", sections=["full_text"])
    text = response.data["sections"]["full_text"]
    assert response.success is True
    assert text.startswith("FORM 6-K")
    assert "HSBC Holdings plc" in text


@pytest.mark.vcr
async def test_issue_1719_424b5_full_text(offline_find):
    response = await edgar_read(accession_number="0001108205-25-000026", sections=["full_text"])
    text = response.data["sections"]["full_text"]
    assert text.startswith("Filed pursuant to Rule 424(b)(5)")
    assert "1,974,432 Shares" in text
    # Capped like every other section
    assert text.endswith("... (truncated)")


@pytest.mark.fast
async def test_full_text_is_not_taken_from_a_typed_object_that_returns_none(monkeypatch):
    """The 40-F object answers ``obj['full_text']`` with None; the filing still has text."""
    class FortyF:
        def __getitem__(self, key):
            return None

    class Filing(_Filing):
        form = "40-F"

        def obj(self):
            return FortyF()

        def text(self):
            return "FORM 40-F\nannual report"

    monkeypatch.setattr(reader, "find", lambda search_id: Filing())
    response = await edgar_read(accession_number="0000000000-00-000000", sections=["full_text"])
    assert response.data["sections"]["full_text"] == "FORM 40-F\nannual report"


@pytest.mark.fast
async def test_filing_with_no_text_says_so(monkeypatch):
    class Filing(_Filing):
        def obj(self):
            return object()

        def text(self):
            return ""

    monkeypatch.setattr(reader, "find", lambda search_id: Filing())
    response = await edgar_read(accession_number="0000000000-00-000000", sections=["full_text"])
    assert response.data["sections"]["full_text"] == "Full text is not available for this filing."


@pytest.mark.fast
@pytest.mark.parametrize("form", ["CORRESP", "S-8"])
async def test_full_text_is_served_for_forms_with_no_typed_object(monkeypatch, form):
    """``filing.obj()`` is None for these forms, which offer only ``full_text``."""
    class Filing(_Filing):
        def obj(self):
            return None

        def text(self):
            return "Dear Staff, we respond to your comment letter."

    Filing.form = form
    monkeypatch.setattr(reader, "find", lambda search_id: Filing())
    response = await edgar_read(accession_number="0000000000-00-000000", sections=["full_text"])
    assert response.success is True
    assert response.data["available_sections"] == ["full_text"]
    assert response.data["sections"] == {"full_text": "Dear Staff, we respond to your comment letter."}


@pytest.mark.fast
async def test_a_text_failure_does_not_discard_other_sections(monkeypatch):
    class Report:
        def __getitem__(self, key):
            return "business text" if key == "business" else None

    class Filing(_Filing):
        form = "10-K"

        def obj(self):
            return Report()

        def text(self):
            raise OSError("download failed")

    monkeypatch.setattr(reader, "find", lambda search_id: Filing())
    response = await edgar_read(accession_number="0000000000-00-000000", sections=["business", "full_text"])
    sections = response.data["sections"]
    assert sections["business"] == "business text"
    assert sections["full_text"] == "Could not read the filing's full text: download failed"
    assert "error" not in sections
