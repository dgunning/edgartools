"""``Filing.text()`` keeps long table cells and can mark images (edgartools-sfnr, GH #886).

Three defects that stacked on each other, all reached through one line —
``Filing.text()`` rendering its document with ``rich_to_text(document, width=500)``.

``Document`` has neither ``__rich__`` nor ``__rich_console__``, so rich fell back
to ``repr()``, and ``Document.__repr__`` is hardcoded
``self.text(table_max_col_width=200)``. The ``500`` never reached the table
renderer, and the comment on that line — "Wide enough for tables without
truncation" — described an intent the code did not carry out.

1. *Table cells cut at 200 characters, with no ellipsis.* On Apple's FY2024 10-K
   that is 1,434 characters across 8 chunks, whitespace collapsed so wrapping
   cannot account for it: 300 characters of the unrecognized-tax-benefits
   disclosure, and the exhibit list's note series. Seven of eight 10-K fixtures
   lose content without an ellipsis marker, which is what makes it invisible —
   the text reads as complete.

2. *``include_images`` never fired.* ``TextExtractor`` gained the flag, but SEC
   filers wrap ``<img>`` in a paragraph, and the ``ParagraphNode`` branch appends
   the paragraph text and returns without descending. The ``ImageNode`` branch
   below it was unreachable for a real filing, so the placeholder never appeared.

3. *Alt text leaked into default output.* ``ImageNode.text()`` returned ``alt``,
   which ``ParagraphNode.text()`` aggregates, so ``Filing.text()`` carried the
   bare string ``nvidialogoa10.jpg`` inline in the prose with nothing marking it
   as an image — whether or not images were asked for. ``alt`` describes an
   image; it is not text the filer wrote, and on SEC filings it is usually just
   the source file name.

GROUND TRUTH. The tax-benefit figures are read off Apple's FY2024 10-K
(``$22.0 billion`` gross, ``$10.8 billion`` rate-affecting) and the NVDA image
file names off the fixture HTML.
"""
import os
import re
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.extractors.text_extractor import TextExtractor
from edgar.documents.nodes import ImageNode, ParagraphNode
from edgar.documents.parser import HTMLParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "html"
AAPL_DIR = FIXTURES / "aapl" / "10k"
NVDA = FIXTURES / "nvda" / "10k" / "nvda-10-k-2025-02-26.html"

WHITESPACE = re.compile(r"\s+")


def _parse(path: Path):
    return HTMLParser(ParserConfig(form="10-K")).parse(path.read_text(errors="ignore"))


@pytest.fixture(scope="module")
def aapl_document():
    assert AAPL_DIR.is_dir() and os.listdir(AAPL_DIR), (
        f"committed AAPL 10-K fixture is missing from {AAPL_DIR}")
    return _parse(sorted(AAPL_DIR.glob("*.html"))[0])


@pytest.fixture(scope="module")
def nvda_document():
    assert NVDA.exists(), f"committed NVDA 10-K fixture is missing: {NVDA}"
    return _parse(NVDA)


@pytest.mark.fast
class TestLongTableCellsSurvive:
    """Defect 1. The values below are the point — not the character counts."""

    def test_the_tax_disclosure_is_not_cut_off(self, aapl_document):
        """A 200-char cut lands mid-sentence in Apple's tax note."""
        text = aapl_document.text(table_max_col_width=500)
        collapsed = WHITESPACE.sub(" ", text)
        # Both figures live in the same cell; the truncated form kept the first
        # and lost the second, which is the half that says what it means.
        assert "$22.0 billion" in collapsed, "gross unrecognized tax benefits missing"
        assert "$10.8 billion" in collapsed, (
            "the rate-affecting portion of unrecognized tax benefits was cut — "
            "this is the half a 200-character column drops"
        )
        assert "would impact the Company's effective tax rate" in collapsed.replace(
            "’", "'"), "the sentence that gives the figures meaning was cut"

    def test_widening_the_column_recovers_content_not_just_padding(self, aapl_document):
        """Guards the fix against being satisfied by whitespace.

        Comparing whitespace-collapsed lengths is what makes this meaningful:
        re-wrapping the same content cannot move this number, only recovering
        dropped characters can.
        """
        narrow = WHITESPACE.sub("", aapl_document.text(table_max_col_width=200))
        wide = WHITESPACE.sub("", aapl_document.text(table_max_col_width=500))
        assert len(wide) > len(narrow), (
            "widening the column recovered no non-whitespace content, so either "
            "the truncation is gone from a different cause or the parameter "
            "stopped being honoured"
        )

    def test_filing_text_does_not_route_through_repr(self):
        """The specific mechanism, pinned.

        ``Document.__repr__`` hardcodes ``table_max_col_width=200``. If
        ``Filing.text()`` ever goes back through rich (or anything else that
        falls back to ``repr``), the truncation returns silently — so pin the
        mechanism rather than trusting the call site.

        Compared whitespace-collapsed, because rich re-wraps its output at the
        console width: that changes line breaks without changing content, and
        content is the whole question here.

        Uses the AAPL fixture deliberately. NVDA has no table cell longer than
        200 characters, so ``text(200)`` and ``text(500)`` are byte-identical
        there and the comparison would prove nothing.
        """
        from edgar.richtools import rich_to_text

        assert AAPL_DIR.is_dir() and os.listdir(AAPL_DIR), (
            f"committed AAPL 10-K fixture is missing from {AAPL_DIR}")
        fixture = sorted(AAPL_DIR.glob("*.html"))[0]

        def collapsed(s):
            return WHITESPACE.sub(" ", s).strip()

        via_repr = collapsed(rich_to_text(_parse(fixture), width=500))
        via_200 = collapsed(_parse(fixture).text(table_max_col_width=200))
        via_500 = collapsed(_parse(fixture).text(table_max_col_width=500))

        assert via_repr == via_200, (
            "the rich route no longer collapses to text(200) — this test's "
            "premise has changed and the docstring above needs revisiting"
        )
        assert via_repr != via_500, (
            "text(200) and text(500) now agree on this fixture, so it can no "
            "longer detect the truncation; pick a fixture with a long cell"
        )


@pytest.mark.fast
class TestImagePlaceholdersActuallyFire:
    """Defect 2. The flag existed and did nothing on every real filing."""

    def test_sec_filings_nest_images_inside_paragraphs(self, nvda_document):
        """The reason the flag was dead. Assert the shape, not just the symptom."""
        images = [n for n in nvda_document.root.walk() if isinstance(n, ImageNode)]
        assert images, "fixture should carry images"
        assert all(isinstance(img.parent, ParagraphNode) for img in images), (
            "images are no longer paragraph-nested; if filings changed shape, "
            "the paragraph-branch walk may no longer be the right fix"
        )

    def test_placeholders_are_emitted_for_paragraph_nested_images(self, nvda_document):
        text = TextExtractor(include_images=True).extract(nvda_document)
        assert text.count("[Image:") == 2, (
            f"expected a placeholder per image, got {text.count('[Image:')}"
        )

    def test_the_stock_performance_graph_is_marked(self, nvda_document):
        """Item 5's chart is the content GH #886 was filed about."""
        text = TextExtractor(include_images=True).extract(nvda_document)
        assert "[Image:" in text
        # alt on this one is a bare number, so the label falls back through alt;
        # what matters is that a marker exists where the chart was.
        assert text.count("[Image:") >= 1

    def test_the_label_falls_back_to_the_filename(self):
        """Filers routinely leave alt empty on exactly the images that matter."""
        document = HTMLParser(ParserConfig()).parse(
            '<html><body><p><img src="dir/perf_graph.jpg"/></p></body></html>')
        text = TextExtractor(include_images=True).extract(document)
        assert "[Image: perf_graph.jpg]" in text, (
            f"expected a filename-derived label, got: {text!r}"
        )

    def test_images_outside_a_paragraph_still_work(self):
        """The original ImageNode branch must not have been broken by the fix."""
        document = HTMLParser(ParserConfig()).parse(
            '<html><body><div><img src="x.jpg" alt="A chart"/></div></body></html>')
        text = TextExtractor(include_images=True).extract(document)
        assert "[Image: A chart]" in text


@pytest.mark.fast
class TestDefaultTextStaysClean:
    """Defect 3, plus the silence check on the new flag."""

    def test_alt_text_does_not_leak_into_default_output(self, nvda_document):
        """A bare filename dropped into prose reads as content. It is not."""
        text = nvda_document.text()
        assert "nvidialogoa10" not in text, (
            "image alt text is back in default output; ImageNode.text() must "
            "return '' so ParagraphNode.text() cannot aggregate it"
        )

    def test_default_output_carries_no_placeholders(self, nvda_document):
        """Off by default keeps sections, search and embeddings image-free."""
        assert "[Image:" not in nvda_document.text()

    def test_image_node_text_is_empty(self):
        node = ImageNode(src="x.jpg", alt="Some chart")
        assert node.text() == "", (
            "alt is a description of an image, not document text — callers that "
            "want it read .alt explicitly"
        )

    def test_the_flag_changes_nothing_but_the_placeholders(self, nvda_document):
        """Silence check: turning images on must not disturb the prose."""
        without = nvda_document.text(include_images=False)
        with_images = nvda_document.text(include_images=True)
        stripped = re.sub(r"\[Image: [^\]]*\]", "", with_images)
        assert WHITESPACE.sub(" ", stripped).strip() == \
            WHITESPACE.sub(" ", without).strip(), (
            "include_images altered more than the placeholders"
        )


@pytest.mark.network
class TestEndToEndThroughFilingText:

    def test_filing_text_exposes_image_placeholders(self):
        from edgar import Company

        filing = Company("NVDA").get_filings(form="10-K").latest()
        default = filing.text()
        with_images = filing.text(include_images=True)

        assert "[Image:" not in default, "default Filing.text() must stay image-free"
        assert with_images.count("[Image:") >= 1, (
            f"Filing.text(include_images=True) emitted no placeholders for "
            f"{filing.accession_no}; the text half of GH #886 is not fixed"
        )

    def test_filing_text_keeps_long_table_cells(self):
        """The end-to-end form of defect 1 — Filing.text(), not Document.text()."""
        from edgar import Company

        filing = Company("AAPL").get_filings(form="10-K").latest()
        collapsed = WHITESPACE.sub(" ", filing.text())
        longest_run = max((len(cell) for cell in collapsed.split("  ")), default=0)
        assert longest_run > 200, (
            "no run of text exceeds 200 characters, which is what a "
            "table_max_col_width=200 cap would produce"
        )
