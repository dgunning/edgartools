"""
Regression test for GitHub issue #1421: SEC refuses the short filing index URL.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1421

`Filing.homepage_url` built `/Archives/edgar/data/<cik>/<accession>-index.html`.
As of 2026-10-06 SEC answers that URL with a 456-byte Akamai "Access Denied" 403
for every filing tried, while the same page inside the accession folder,
`/data/<cik>/<accession-no-dashes>/<accession>-index.html`, answers 200.

Everything that reads the index page went quiet. `Filing.html()` falls back to the
index page when the primary document starts with `<?xml` (common for inline XBRL),
so it returned None, and ChunkedDocument then raised TypeError. Eight fast tests
failed on every pull request until this changed.

The 32 cassettes that recorded the short URL had their request URIs rewritten to
the folder form; the folder page serves the same index, so the bodies are unchanged.
"""
import pytest

from edgar import Filing


def excelerate_10k():
    return Filing(company='Excelerate Energy, Inc.', cik=1888447, form='10-K',
                  filing_date='2024-02-29', accession_no='0000950170-24-023104')


@pytest.mark.fast
def test_homepage_url_is_inside_the_accession_folder():
    filing = excelerate_10k()
    assert filing.homepage_url == (
        "https://www.sec.gov/Archives/edgar/data/1888447/000095017024023104/0000950170-24-023104-index.html")
    assert filing.homepage_url.startswith(filing.base_dir + "/")


@pytest.mark.network
def test_inline_xbrl_html_reads_through_the_index_page():
    filing = excelerate_10k()
    assert filing.homepage.primary_html_document.document == 'ee-20231231.htm'
    html = filing.html()
    assert html is not None
    # The primary document itself, not the index page or the raw submission text.
    assert html.startswith("<?xml version='1.0' encoding='ASCII'?>")
    assert "Excelerate Energy, Inc." in html
