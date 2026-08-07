"""Regression test for #819 — search()/grep() failed on plain-text filings."""

import pytest

from edgar import Company


PCG_TEXT_10K_ACCESSION = "0000929624-00-000321"


def _pcg_oldest_10k():
    filings = Company("PCG").get_filings(form="10-K")
    target = next(
        (f for f in filings if f.accession_no == PCG_TEXT_10K_ACCESSION),
        None,
    )
    assert target is not None, f"PCG 10-K {PCG_TEXT_10K_ACCESSION} missing from EDGAR results"
    return target


@pytest.mark.network
def test_text_filing_html_is_none_but_text_is_populated():
    filing = _pcg_oldest_10k()
    assert filing.html() is None
    text = filing.text()
    assert text is not None
    assert len(text) > 100_000
    assert "employees" in text.lower()


@pytest.mark.network
def test_sections_falls_back_to_text_for_plain_text_filings():
    filing = _pcg_oldest_10k()
    sections = filing.sections()
    assert isinstance(sections, list)
    assert len(sections) > 1
    assert any("employees" in s.lower() for s in sections)


@pytest.mark.network
def test_search_works_on_plain_text_filing():
    filing = _pcg_oldest_10k()
    results = filing.search("employees")
    assert results is not None
    assert len(results) >= 1


@pytest.mark.network
def test_grep_works_on_plain_text_filing():
    filing = _pcg_oldest_10k()
    matches = filing.grep("employees")
    assert len(matches) >= 1


@pytest.mark.network
def test_search_grep_still_work_on_html_filings():
    newest = Company("PCG").get_filings(form="10-K")[0]
    assert newest.html() is not None
    assert len(newest.search("employees")) > 0
    assert len(newest.grep("employees")) > 0
