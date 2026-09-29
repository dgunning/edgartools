"""`Filing.html()` raised AttributeError when the homepage had no primary document.

`FilingHomepage.primary_html_document` is declared `Optional[Attachment]` and
returns None when the homepage lists no primary documents at all
(`edgar/attachments.py`). `Filing.html()` used the result without a None check,
so instead of returning None it raised

    AttributeError: 'NoneType' object has no attribute 'empty'

Sibling call sites already guarded it — `Filing.document` tests the document for
truthiness and `Filing.agent` uses `if doc and doc.content` — so this was the one
path that did not.

It surfaced as a red scheduled run on main (job `test-fast (3.10)`, run
35606234183) failing `tests/test_htmltools.py::test_filing_with_pdf_primary_document`.
That test reaches this code over the network, where the homepage normally falls
back to `primary_documents[0]` and hands back the PDF attachment, so it only fails
on a cold or rate-limited run and passes locally in half a second. These tests
force the None directly instead, so they do not depend on cache warmth or on SEC
being reachable.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1033
Bead: edgartools-vwwl
"""

import pytest

from edgar._filings import Filing


@pytest.fixture(autouse=True)
def _clear_html_cache():
    """`Filing.html` is `lru_cache`d and Filings that compare equal share the
    entry, so one test's result would otherwise be served to the next."""
    Filing.html.cache_clear()
    yield
    Filing.html.cache_clear()


@pytest.fixture
def filing():
    return Filing(
        form="APP NTC",
        filing_date="2024-01-29",
        company="AMG Pantheon Credit Solutions Fund",
        cik=1995940,
        accession_no="9999999997-24-000210",
    )


class _NoPrimaryDocumentHomepage:
    """A homepage that lists no primary documents, as CI saw."""

    primary_html_document = None


class _Sgml:
    def __init__(self, html=None, xml=None):
        self._html = html
        self._xml = xml

    def html(self):
        return self._html

    def xml(self):
        return self._xml


def test_html_returns_none_when_the_homepage_has_no_primary_document(filing, monkeypatch):
    """The reported crash: the SGML carries no html, so html() falls back to the
    homepage, and the homepage has nothing to give."""
    monkeypatch.setattr(Filing, "sgml", lambda self: _Sgml(html=None))
    filing._filing_homepage = _NoPrimaryDocumentHomepage()

    assert filing.homepage.primary_html_document is None, "fixture no longer reproduces the shape"
    assert filing.html() is None


def test_html_returns_none_for_xml_with_no_homepage_fallback(filing, monkeypatch):
    """The same unguarded access one branch below, on the XML path: an `<?xml`
    primary document that is not an ownership or XML-native form falls through to
    the same homepage download."""
    monkeypatch.setattr(Filing, "sgml", lambda self: _Sgml(html="<?xml version='1.0'?><doc/>"))
    filing._filing_homepage = _NoPrimaryDocumentHomepage()

    assert filing.html() is None


def test_html_still_returns_none_for_a_binary_primary_document(filing, monkeypatch):
    """The guard must not swallow the case it was already handling: a PDF primary
    document is present but binary, which is what the original test asserts."""

    class _BinaryAttachment:
        empty = False

        def is_binary(self):
            return True

        def download(self):  # pragma: no cover - reaching this is the failure
            raise AssertionError("a binary primary document must not be downloaded")

    class _Homepage:
        primary_html_document = _BinaryAttachment()

    monkeypatch.setattr(Filing, "sgml", lambda self: _Sgml(html=None))
    filing._filing_homepage = _Homepage()

    assert filing.html() is None


def test_html_returns_the_document_when_the_homepage_has_a_real_one(filing, monkeypatch):
    """And the guard must not block the path that works: a present, non-empty,
    non-binary document is still downloaded and returned."""

    class _HtmlAttachment:
        empty = False

        def is_binary(self):
            return False

        def download(self):
            return "<html><body>filed</body></html>"

    class _Homepage:
        primary_html_document = _HtmlAttachment()

    monkeypatch.setattr(Filing, "sgml", lambda self: _Sgml(html=None))
    filing._filing_homepage = _Homepage()

    assert filing.html() == "<html><body>filed</body></html>"
