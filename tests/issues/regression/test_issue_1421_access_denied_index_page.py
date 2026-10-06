"""`Filing.text()` returned raw `<XBRL>` markup when SEC refused the filing index page.

On NVIDIA's FY2026 10-K (`0001045810-26-000021`) SEC answered the index page
(`...-index.html`) with a 456-byte "Access Denied" 403. `Filing.html()` and
`Filing.parse()` returned None, `TenK["Item 7"]` raised TypeError, and
`Filing.text()` returned 1,967,829 characters of the submission's raw `<TEXT>`
block, opening `<XBRL>\\n<?xml version='1.0' encoding='ASCII'?>`.

The submission already carried the document. The inline XBRL primary document
opens with an XML declaration, and `Filing.html()` treated every primary document
starting with `<?xml` as XML, which for a 10-K meant asking the index page for an
HTML rendering. That route exists for XML primary documents such as Form D's
`primary_doc.xml`, whose readable view is SEC's XSLT rendering listed on the index
page. An XHTML document is already HTML, so `html()` now returns it from the
submission.

Apple's FY2024 10-K, checked in at `data/sgml/0000320193-24-000123.txt`, has the
same shape (`aapl-20240928.htm` opens with the same XML declaration), so it
stands in for NVIDIA and the test runs offline. The refused index page is served
to the real `FilingHomepage.load()`.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1421
"""

from pathlib import Path

import httpx
import pytest

from edgar import Filing
from edgar.company_reports import TenK
from edgar.sgml import FilingSGML

pytestmark = pytest.mark.fast

# The page SEC served for NVIDIA's index page, minus Akamai's per-request reference lines.
ACCESS_DENIED = (
    b"<HTML><HEAD>\n<TITLE>Access Denied</TITLE>\n</HEAD><BODY>\n<H1>Access Denied</H1>\n \n"
    b"You don't have permission to access \"http&#58;&#47;&#47;www&#46;sec&#46;gov&#47;"
    b"Archives&#47;edgar&#47;data&#47;1045810&#47;0001045810&#45;26&#45;000021&#45;"
    b'index&#46;html" on this server.<P>\n'
    b"</BODY>\n</HTML>\n"
)

MDA_HEADING = "Discussion and Analysis of Financial Condition and Results of Operations"


@pytest.fixture(autouse=True)
def _clear_filing_caches():
    """`html` and `text` are `lru_cache`d on the class, and Filings that compare
    equal share entries, so another test's result could be served here."""
    Filing.html.cache_clear()
    Filing.text.cache_clear()
    yield
    Filing.html.cache_clear()
    Filing.text.cache_clear()


@pytest.fixture
def refused_index_page(monkeypatch):
    """Every index page request gets SEC's 403 Access Denied page."""

    def get_with_retry(url, *args, **kwargs):
        return httpx.Response(403, content=ACCESS_DENIED, request=httpx.Request("GET", url))

    monkeypatch.setattr("edgar.attachments.get_with_retry", get_with_retry)


@pytest.fixture
def no_raw_text_fallback(monkeypatch):
    """`text()`'s last resort downloads the submission's raw `<TEXT>` block, which is
    what it returned for NVIDIA. Reaching it here is the failure."""

    def download_text_between_tags(url, tag):
        raise AssertionError(f"text() fell back to the raw <{tag}> block of {url}")

    monkeypatch.setattr("edgar._filings.download_text_between_tags", download_text_between_tags)


@pytest.fixture(scope="module")
def apple_sgml():
    return FilingSGML.from_source(Path("data/sgml/0000320193-24-000123.txt"))


@pytest.fixture
def apple_10k(apple_sgml):
    filing = Filing(
        form="10-K",
        company="Apple Inc.",
        cik=320193,
        filing_date="2024-11-01",
        accession_no="0000320193-24-000123",
    )
    filing._sgml = apple_sgml
    return filing


def test_inline_xbrl_html_comes_from_the_submission(apple_10k, apple_sgml, refused_index_page):
    html = apple_10k.html()

    assert html is not None, "html() went to the refused index page instead of the submission"
    assert html.startswith("<?xml version='1.0' encoding='ASCII'?>")
    assert len(html) == 1_503_779  # aapl-20240928.htm as carried in the submission
    assert html == apple_sgml.html()


def test_text_is_the_document_not_raw_markup(apple_10k, refused_index_page, no_raw_text_fallback):
    text = apple_10k.text()

    assert not text.startswith("<XBRL>")
    assert "<?xml" not in text
    assert "For the fiscal year ended September 28, 2024" in text
    assert MDA_HEADING in text


def test_tenk_items_are_read_from_the_submission(apple_10k, refused_index_page):
    """NVIDIA's `TenK` had no document and no items, and `tenk["Item 7"]` raised TypeError."""
    tenk = TenK(apple_10k)

    assert "Item 7" in tenk.items
    item_7 = tenk["Item 7"]
    assert item_7 is not None
    assert MDA_HEADING in item_7[:200]


def test_an_xml_primary_document_still_gets_the_index_page_rendering():
    """The other side of the line: Form D's primary document is XML, not HTML, and
    its readable view is still the index page's rendering of it."""
    filing = Filing(
        form="D",
        company="VEPF VIII Co-Invest 4-A, L.P.",
        cik=2002260,
        filing_date="2024-01-11",
        accession_no="0002002260-24-000001",
    )
    filing._sgml = FilingSGML.from_source(Path("data/sgml/0002002260-24-000001.nc"))
    primary = filing.sgml().html()
    assert primary is not None and primary.startswith("<?xml"), "fixture no longer has an XML primary document"

    class _Rendering:
        empty = False

        def is_binary(self):
            return False

        def download(self):
            return "<html><body>Form D rendered by SEC</body></html>"

    class _Homepage:
        primary_html_document = _Rendering()

    filing._filing_homepage = _Homepage()

    assert filing.html() == "<html><body>Form D rendered by SEC</body></html>"
