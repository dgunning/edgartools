"""``Filing.markdown()`` renders images, with resolvable URLs (GH #886, edgartools-n45i).

WHAT WAS BROKEN. ``Filing.markdown()`` was the last public rendering method still
on the legacy ``edgar.files`` pipeline while ``text()``, ``view()`` and the
section extractors had all moved to ``edgar.documents``. The legacy renderer has
no image node at all: ``MarkdownRenderer.render`` in ``edgar/files/markdown.py``
handles ``text_block``, ``table``, ``heading`` and ``page_break``, and anything
else renders as nothing. Every ``<img>`` in every filing was dropped silently.

The reporter's example is the one pinned here — NVIDIA's 10-K Item 5 "Stock
Performance Graph", which is a chart image. The five-year total-return comparison
against the S&P 500 and the Nasdaq 100 exists *only* as that image; there is no
table beside it. So the legacy markdown of Item 5 asserted that a performance
comparison was presented and then showed nothing, which is worse for a RAG
pipeline than an outright gap.

TWO THINGS ARE ASSERTED, AND THE SECOND IS THE EASY ONE TO LOSE. Rendering
``![alt](src)`` is not sufficient, because the ``src`` in filing HTML is a bare
sibling file name — ``nvda-20250126_g2.jpg``. Emitted verbatim it resolves
against wherever the markdown ends up, which is nowhere. The reroute sets
``document.metadata.url`` to the filing's archive directory so the renderer's
``urljoin`` produces an absolute SEC URL. A refactor that keeps the image node
but forgets the base URL passes a naive "are there images?" test and still ships
markdown with dead links, so the absolute form is asserted explicitly.

GROUND TRUTH. NVIDIA's FY2025 10-K (accession 0001045810-25-000023, filed
2025-02-26) carries exactly two images: the corporate logo on the cover
(``nvda-20250126_g1.jpg``) and the Item 5 stock performance graph
(``nvda-20250126_g2.jpg``). Both file names were read off the fixture HTML, and
the archive directory follows from the accession number. Verified against the
live filing 2026-08-08: both URLs return HTTP 200 image/jpeg.
"""
import re
import warnings
from pathlib import Path
from urllib.parse import urljoin

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

FIXTURE = (Path(__file__).parent.parent.parent
           / "fixtures" / "html" / "nvda" / "10k" / "nvda-10-k-2025-02-26.html")

# The archive directory for accession 0001045810-25-000023 under CIK 1045810.
# Trailing slash is load-bearing: urljoin() discards the last path segment
# without it, and the images would resolve one directory too high.
NVDA_ARCHIVE_DIR = "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/"

COVER_LOGO = "nvda-20250126_g1.jpg"
STOCK_PERFORMANCE_GRAPH = "nvda-20250126_g2.jpg"

MARKDOWN_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]*)\)")


@pytest.fixture(scope="module")
def nvda_markdown():
    """Render the fixture exactly as the rerouted ``Filing.markdown()`` does."""
    assert FIXTURE.exists(), f"committed NVDA 10-K fixture is missing: {FIXTURE}"
    document = HTMLParser(ParserConfig(form="10-K")).parse(
        FIXTURE.read_text(errors="ignore"))
    document.metadata.url = NVDA_ARCHIVE_DIR
    return document.to_markdown()


@pytest.mark.fast
class TestImagesSurviveIntoMarkdown:

    def test_both_images_are_rendered(self, nvda_markdown):
        """GH #886: the legacy renderer emitted zero of these."""
        sources = [m.group("src") for m in MARKDOWN_IMAGE.finditer(nvda_markdown)]
        missing = [name for name in (COVER_LOGO, STOCK_PERFORMANCE_GRAPH)
                   if not any(name in src for src in sources)]
        assert not missing, (
            f"images absent from rendered markdown: {missing}. Rendered image "
            f"sources were: {sources}"
        )

    def test_the_stock_performance_graph_is_the_one_that_matters(self, nvda_markdown):
        """Item 5's five-year return comparison exists only as this image."""
        assert STOCK_PERFORMANCE_GRAPH in nvda_markdown, (
            "the Item 5 stock performance graph is missing — this is the exact "
            "content GH #886 was filed about"
        )

    def test_image_urls_are_absolute_and_point_at_the_sec_archive(self, nvda_markdown):
        """A relative src in exported markdown is a dead link."""
        sources = [m.group("src") for m in MARKDOWN_IMAGE.finditer(nvda_markdown)]
        assert sources, "no images rendered at all"
        relative = [src for src in sources if not src.startswith("https://")]
        assert not relative, (
            f"image sources left unresolved: {relative}. They must be joined "
            f"against document.metadata.url ({NVDA_ARCHIVE_DIR})."
        )
        assert urljoin(NVDA_ARCHIVE_DIR, STOCK_PERFORMANCE_GRAPH) in sources

    def test_alt_text_is_preserved(self, nvda_markdown):
        """The alt attribute is the only text a reader gets for a chart image."""
        alts = [m.group("alt") for m in MARKDOWN_IMAGE.finditer(nvda_markdown)]
        assert any("nvidialogo" in alt for alt in alts), (
            f"cover logo alt text lost; alts were: {alts}"
        )

    def test_a_document_without_a_base_url_keeps_the_raw_src(self):
        """Parsing raw HTML must not fabricate a URL — silence check.

        ``HTMLParser().parse(html)`` has no filing behind it, so there is no
        correct absolute form. Keeping the raw ``src`` is honest; inventing an
        sec.gov prefix would produce links that 404.
        """
        assert FIXTURE.exists(), f"committed NVDA 10-K fixture is missing: {FIXTURE}"
        document = HTMLParser(ParserConfig(form="10-K")).parse(
            FIXTURE.read_text(errors="ignore"))
        markdown = document.to_markdown()
        sources = [m.group("src") for m in MARKDOWN_IMAGE.finditer(markdown)]
        assert STOCK_PERFORMANCE_GRAPH in sources, (
            f"expected the bare src to be preserved, got: {sources}"
        )


@pytest.mark.fast
class TestThePageBreakEscapeHatch:
    """``include_page_breaks=True`` still works, and says it is going away.

    The new pipeline has no page-break rendering — ``DocumentBuilder`` drops
    page-break ``<hr>``s and page-number containers as print chrome — so the
    flag keeps routing to the legacy renderer until 6.0. That is a deliberate
    trade, and the warning is the part users actually see.
    """

    def test_the_flag_warns_about_removal(self):
        from edgar.files._deprecation import PAGE_BREAK_DEPRECATION

        message = PAGE_BREAK_DEPRECATION.format(cls="Filing")
        assert "6.0" in message, "the warning must name the removal release"
        assert "images" in message, (
            "the warning must say what the caller gives up, not just that the "
            "flag is deprecated"
        )

    def test_the_legacy_renderer_still_emits_page_break_markers(self):
        """Guards the fallback itself, not just the warning."""
        from edgar.files.markdown import to_markdown

        html = (
            "<html><body>"
            "<div>Page one body text that is long enough to be a text block.</div>"
            "<hr style='page-break-after:always'/>"
            "<div>Page two body text that is long enough to be a text block.</div>"
            "</body></html>"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            markdown = to_markdown(html, include_page_breaks=True, start_page_number=1)
        assert markdown is not None
        assert re.search(r"\{\d+\}-{10,}", markdown), (
            f"no page break delimiter in legacy output:\n{markdown}"
        )


@pytest.mark.network
class TestEndToEndThroughFilingMarkdown:
    """The offline tests above cannot see ``Filing.markdown()``'s URL wiring.

    ``base_dir`` is built from the CIK and accession number, and nothing offline
    exercises that. This is the test that fails if the reroute renders images
    but joins them against the wrong directory.
    """

    def test_filing_markdown_emits_absolute_sec_image_urls(self):
        from edgar import Company

        filing = Company("NVDA").get_filings(form="10-K").latest()
        markdown = filing.markdown()

        sources = [m.group("src") for m in MARKDOWN_IMAGE.finditer(markdown)]
        assert sources, (
            f"Filing.markdown() rendered no images for {filing.accession_no}; "
            "GH #886 is not fixed"
        )
        assert all(src.startswith("https://www.sec.gov/Archives/") for src in sources), (
            f"image sources are not absolute SEC archive URLs: {sources}"
        )
        assert all(filing.accession_no.replace("-", "") in src for src in sources), (
            f"image URLs do not point at this filing's archive directory: {sources}"
        )

    def test_the_deprecated_path_warns_and_still_renders(self):
        from edgar import Company

        filing = Company("NVDA").get_filings(form="10-K").latest()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            markdown = filing.markdown(include_page_breaks=True, start_page_number=1)

        assert re.search(r"\{\d+\}-{10,}", markdown), "page break markers missing"
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations, "include_page_breaks=True must emit a DeprecationWarning"
        assert "6.0" in str(deprecations[0].message)
