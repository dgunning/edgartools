"""
Tests for ``Section.markdown()``.

`Section.text()` walks the HTML subtree and emits newline-joined cell
content — tables and bullet lists are flattened to space/newline
soup. The whole-document `Filing.markdown()` (and `Document.to_markdown`)
preserves table pipe syntax and list markers but is whole-document
only — there is no per-item slice.

`Section.markdown()` closes that gap: same scope as ``text()`` (one
section) but the same renderer as ``Document.to_markdown`` so tables
and lists keep their syntax.

Downstream effect: per-item chunkers can call ``section.markdown()``
to get a structured per-item view instead of paying either the cost
of `text()` (flat) or the cost of `filing.markdown()` (no item
boundaries).
"""
from __future__ import annotations

import pytest

from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig


def _parse_html(html: str, form: str = "10-K"):
    return HTMLParser(ParserConfig(form=form)).parse(html)


class TestSectionMarkdownTablePreservation:
    """A `<table>` in section HTML should render as pipe-delimited
    markdown, not flattened cell-by-cell text."""

    HTML_WITH_TABLE = """
    <html><body>
    <h1>Item 1. Business</h1>
    <p>We operate three segments.</p>

    <h1>Item 2. Properties</h1>
    <p>Issuer Purchases of Equity Securities:</p>
    <table>
      <thead>
        <tr><th>Period</th><th>Total Shares</th><th>Avg Price</th></tr>
      </thead>
      <tbody>
        <tr><td>April</td><td>1,000</td><td>$50.00</td></tr>
        <tr><td>May</td><td>2,000</td><td>$52.50</td></tr>
        <tr><td>June</td><td>1,500</td><td>$53.25</td></tr>
      </tbody>
    </table>

    <h1>Item 3. Legal Proceedings</h1>
    <p>From time to time...</p>
    </body></html>
    """

    @pytest.fixture
    def properties_section(self):
        doc = _parse_html(self.HTML_WITH_TABLE)
        sections = doc.sections
        # Find the section containing the table — section keys vary by
        # detection method; locate by title substring.
        for name, section in sections.items():
            if "properties" in name.lower() or "item_2" in name.lower():
                return section
        pytest.skip("Test HTML did not produce an Item 2 section")

    def test_markdown_returns_str(self, properties_section):
        result = properties_section.markdown()
        assert isinstance(result, str)
        assert result  # non-empty

    def test_markdown_preserves_pipe_syntax(self, properties_section):
        """The hallmark: pipes show up between columns."""
        result = properties_section.markdown()
        assert "|" in result, (
            f"Section.markdown() must preserve pipe-table syntax; got:\n{result[:500]}"
        )

    def test_markdown_includes_cell_values(self, properties_section):
        """Sanity: actual cell contents are present."""
        result = properties_section.markdown()
        for value in ("Period", "Total Shares", "April", "1,000", "$50.00"):
            assert value in result, f"missing cell value {value!r} in markdown:\n{result}"

    def test_text_does_not_preserve_pipe_syntax(self, properties_section):
        """Negative control: confirm `text()` does NOT have pipes —
        otherwise the contrast we care about isn't there to begin with."""
        text = properties_section.text()
        # Cells appear in text() but not column-delimited
        assert "Period" in text  # still has the words
        assert "|" not in text, (
            f"text() should not have pipes (otherwise markdown isn't adding anything); "
            f"got:\n{text[:500]}"
        )


class TestSectionMarkdownListPreservation:
    """Bullet lists in section HTML should render with list markers."""

    HTML_WITH_BULLETS = """
    <html><body>
    <h1>Item 1A. Risk Factors</h1>
    <p>Our business is subject to the following risks:</p>
    <ul>
      <li>decreased demand in the restaurant business</li>
      <li>volatility in commodity costs</li>
      <li>foreign currency exchange rate fluctuations</li>
    </ul>

    <h1>Item 2. Properties</h1>
    <p>Our principal facilities are located worldwide.</p>
    </body></html>
    """

    @pytest.fixture
    def risk_factors_section(self):
        doc = _parse_html(self.HTML_WITH_BULLETS)
        sections = doc.sections
        for name, section in sections.items():
            if "risk_factors" in name.lower() or "item_1a" in name.lower():
                return section
        pytest.skip("Test HTML did not produce an Item 1A section")

    def test_bullets_preserved_in_markdown(self, risk_factors_section):
        result = risk_factors_section.markdown()
        # Markdown bullets can render as '-', '*', or '+' — accept any.
        bullet_lines = [
            line for line in result.splitlines()
            if line.lstrip().startswith(("-", "*", "+"))
        ]
        assert len(bullet_lines) >= 3, (
            f"expected at least 3 bullet lines; got {len(bullet_lines)}:\n{result[:500]}"
        )

    def test_bullet_text_preserved(self, risk_factors_section):
        result = risk_factors_section.markdown()
        for phrase in (
            "decreased demand in the restaurant business",
            "volatility in commodity costs",
            "foreign currency exchange rate fluctuations",
        ):
            assert phrase in result, f"missing bullet text {phrase!r}"


class TestSectionMarkdownAcrossDetectionPaths:
    """Markdown should work whether the section came from heading-based,
    pattern-based, or TOC-based detection."""

    def test_pattern_based_section(self):
        """Pattern-extractor sections have `detection_method='pattern'`
        and a populated `node`. Markdown renders the node tree."""
        html = """
        <html><body>
        <p><strong>Item 1. Business</strong></p>
        <p>We design products.</p>
        <table>
          <tr><th>Segment</th><th>Revenue</th></tr>
          <tr><td>Auto</td><td>$100M</td></tr>
        </table>
        <p><strong>Item 2. Properties</strong></p>
        <p>Facilities worldwide.</p>
        </body></html>
        """
        doc = _parse_html(html)
        # Find any section that has a table in it.
        found = False
        for name, section in doc.sections.items():
            md = section.markdown()
            if "|" in md and "Segment" in md:
                found = True
                # Must include the cell values too.
                assert "Auto" in md
                assert "$100M" in md
                break
        assert found, "no section produced pipe-table markdown — synthetic HTML may need adjustment"

    def test_toc_section_falls_back_to_text(self):
        """TOC-based sections fall back to ``text()`` output.

        Per the docstring on :meth:`Section.markdown`, the TOC path
        is conservative — extracting a TOC section's HTML subtree
        cleanly (without leaking adjacent sections or losing
        structural ``<table>``/``<tbody>`` wrappers when anchors
        cross those boundaries) is non-trivial. The fallback returns
        the same string ``Section.text()`` would produce so callers
        get correct content rather than risk corruption. Full TOC
        markdown support is tracked as a follow-up.
        """
        from edgar.documents.document import Section as _Section
        from edgar.documents.nodes import SectionNode

        # Synthetic TOC section with a stub text extractor.
        expected = "This is the TOC section text."
        sect = _Section(
            name="part_i_item_1",
            title="Item 1",
            node=SectionNode(section_name="part_i_item_1"),
            detection_method="toc",
            _text_extractor=lambda name, **kw: expected,
        )
        assert sect.markdown() == expected

    def test_boundary_artifacts_cleaned_from_markdown(self):
        """Regression for codex review round 7: SEC page-break
        artifacts (``\\n<page_num>\\nPART X\\nItem N\\n``) and trailing
        next-item headers must be stripped from markdown output just
        as ``Section.text()`` strips them. Without the cleanup, the
        markdown path would leak boundary noise that the text path
        already removes.
        """
        from edgar.documents.document import Section as _Section
        from edgar.documents.nodes import SectionNode

        # Build a Section with a stub renderer-friendly node, then
        # assert cleanup applies to the rendered output.
        sect = _Section(
            name="item_1",
            title="Item 1",
            node=SectionNode(section_name="item_1"),
            detection_method="heading",
        )
        # Exercise _clean_boundary_artifacts directly via markdown's
        # cleanup hook by feeding text that contains the boundary
        # artifact pattern.
        raw = "Body content here.\n\n  100\n\n  PART II\n\nItem 5"
        cleaned = sect._clean_boundary_artifacts(raw)
        # Trailing PART/Item artifact must be stripped.
        assert "PART II" not in cleaned, (
            f"boundary cleanup must strip trailing PART artifact; got:\n{cleaned}"
        )
        assert "Item 5" not in cleaned
        assert "Body content here" in cleaned

    def test_boundary_artifacts_cleaned_when_markdown_escaped(self):
        """Regression for codex review round 8: ``MarkdownRenderer``
        escapes periods as ``\\.``, so a trailing ``Item 5.`` in the
        raw text becomes ``Item 5\\.`` after rendering. The cleanup
        regex must accept the optional backslash so it strips both
        the plain (``text()``) and markdown-escaped variants.
        """
        from edgar.documents.document import Section as _Section
        from edgar.documents.nodes import SectionNode

        sect = _Section(
            name="item_1",
            title="Item 1",
            node=SectionNode(section_name="item_1"),
            detection_method="heading",
        )
        # The renderer would produce this trailing artifact shape:
        markdown_escaped = "Body content here.\n\nItem 5\\."
        cleaned = sect._clean_boundary_artifacts(markdown_escaped)
        assert "Item 5" not in cleaned, (
            f"backslash-escaped trailing Item header must be stripped; got:\n{cleaned!r}"
        )
        assert "Body content here" in cleaned

        # And the interior PART + Item\. variant in markdown form:
        with_interior = (
            "Body content here.\n\n  16\n\n  PART I\n\nItem 1A\\.\n\nMore body."
        )
        cleaned_interior = sect._clean_boundary_artifacts(with_interior)
        assert "PART I" not in cleaned_interior, (
            f"interior PART + Item\\. artifact must be stripped; got:\n{cleaned_interior!r}"
        )
        assert "Body content here" in cleaned_interior
        assert "More body" in cleaned_interior

    def test_boundary_artifacts_cleaned_when_markdown_decorated(self):
        """Regression for codex review round 9: ``MarkdownRenderer``
        can emit trailing next-item headers as ``# Item 5``,
        ``## Item 5\\.``, or ``**Item 5\\.**`` depending on the source
        HTML structure. All those decorated forms must be stripped by
        the cleanup, not just bare ``Item 5``.
        """
        from edgar.documents.document import Section as _Section
        from edgar.documents.nodes import SectionNode

        sect = _Section(
            name="item_1",
            title="Item 1",
            node=SectionNode(section_name="item_1"),
            detection_method="heading",
        )
        # Markdown heading form (``# Item 5``):
        for header_md in ("# Item 5", "## Item 5", "### Item 5\\.", "## ITEM 1A"):
            raw = f"Body content here.\n\n{header_md}"
            cleaned = sect._clean_boundary_artifacts(raw)
            assert "Item" not in cleaned.split("Body content here.", 1)[1], (
                f"markdown-heading boundary header {header_md!r} must be stripped; "
                f"got:\n{cleaned!r}"
            )
            assert "Body content here" in cleaned

        # Markdown bold form (``**Item 5**``):
        for bold_md in ("**Item 5**", "**Item 5.**", "**Item 5\\.**", "**ITEM 1A**"):
            raw = f"Body content here.\n\n{bold_md}"
            cleaned = sect._clean_boundary_artifacts(raw)
            assert "Item" not in cleaned.split("Body content here.", 1)[1], (
                f"markdown-bold boundary header {bold_md!r} must be stripped; "
                f"got:\n{cleaned!r}"
            )
            assert "Body content here" in cleaned

    def test_boundary_cleanup_handles_decorated_part_plus_item(self):
        """Regression for codex review round 10: a full page-footer
        artifact (page-number + PART + Item) can be rendered as
        ``100\\n\\n# PART II\\n\\n# Item 5`` after markdown processing.
        The combined cleanup regex must strip the whole footer block,
        not just the trailing Item line — otherwise the page number
        and PART line are left behind.
        """
        from edgar.documents.document import Section as _Section
        from edgar.documents.nodes import SectionNode

        sect = _Section(
            name="item_1",
            title="Item 1",
            node=SectionNode(section_name="item_1"),
            detection_method="heading",
        )

        # Trailing footer: page + heading-decorated PART + heading-decorated Item.
        raw_heading = "Body content here.\n\n  100\n\n# PART II\n\n# Item 5"
        cleaned = sect._clean_boundary_artifacts(raw_heading)
        for noise in ("PART II", "Item 5", "100"):
            assert noise not in cleaned, (
                f"footer noise {noise!r} leaked through after decorated PART/Item;\n"
                f"got: {cleaned!r}"
            )
        assert "Body content here" in cleaned

        # Bold-decorated variant.
        raw_bold = "Body content here.\n\n  29\n\n**PART I**\n\n**Item 1A\\.**"
        cleaned_bold = sect._clean_boundary_artifacts(raw_bold)
        for noise in ("PART I", "Item 1A", "29"):
            assert noise not in cleaned_bold, (
                f"footer noise {noise!r} leaked through after bold PART/Item;\n"
                f"got: {cleaned_bold!r}"
            )
        assert "Body content here" in cleaned_bold

    def test_markdown_is_idempotent(self):
        """Calling markdown() twice should return the same string."""
        html = """
        <html><body>
        <h1>Item 1. Business</h1>
        <p>We operate three segments.</p>
        <ul><li>auto</li><li>energy</li></ul>
        </body></html>
        """
        doc = _parse_html(html)
        for name, section in doc.sections.items():
            a = section.markdown()
            b = section.markdown()
            assert a == b, "markdown() must be deterministic across calls"
            break


class TestSectionMarkdownRealFiling:
    """
    Network-marked tests that exercise ``Section.markdown()`` against
    production SEC HTML — synthetic fixtures only prove the renderer
    wiring, not that the feature delivers value on real filings.

    Pattern-detected sections (8-K Item 9.01 'Financial Statements and
    Exhibits' is a reliable anchor — exhibit indices are almost always
    rendered as HTML tables) are the path where ``markdown()`` actually
    deviates from ``text()``. TOC-detected sections currently fall back
    to ``text()`` by design; that contract is covered by the synthetic
    ``test_toc_section_falls_back_to_text``.
    """

    @pytest.mark.network
    def test_section_markdown_preserves_exhibit_table_on_real_8k(self):
        """
        Regression: pattern-detected 8-K Item 9.01 returns pipe-format
        markdown for its exhibit table, where ``text()`` flattens it to
        space-padded columns. Pinned to AAPL 0000320193-26-000011 (8-K
        filed 2026-04-30) so the assertion targets a known table layout.
        """
        from edgar import Filing
        from edgar.documents import HTMLParser
        from edgar.documents.config import ParserConfig

        filing = Filing(
            company="Apple Inc.", cik=320193, form="8-K",
            filing_date="2026-04-30",
            accession_no="0000320193-26-000011",
        )
        doc = HTMLParser(ParserConfig(form=filing.form)).parse(filing.html())

        section = doc.sections["item_901"]
        # Anchor on the path that this PR actually changes.
        assert section.detection_method == "pattern", (
            f"expected pattern-detected section so markdown() goes through "
            f"MarkdownRenderer rather than the TOC fallback; got "
            f"detection_method={section.detection_method!r}. If this changes "
            f"the test loses its meaning — pick a different anchor filing "
            f"or section."
        )

        md = section.markdown()
        txt = section.text()

        # Structural assertion: pipe-table syntax must appear in markdown.
        # Use a markdown-specific signature (header separator) rather than
        # raw `|` count to avoid false positives from prose pipes.
        assert "| --- |" in md, (
            f"markdown() must emit pipe-format table for the exhibit list; "
            f"got: {md[:400]!r}"
        )

        # Negative control: text() must NOT contain the markdown table
        # separator. If this fires, the contrast the PR claims has
        # evaporated — either text() started emitting markdown or
        # markdown() stopped.
        assert "| --- |" not in txt, (
            f"text() unexpectedly contains markdown table syntax; got: {txt[:400]!r}"
        )

        # Content assertion: the exhibit content survives the renderer.
        # 'Press release' is the standard Item 9.01 phrasing for an
        # earnings-release 8-K; pinning on it locks in that we're
        # extracting the right subtree, not just emitting a stub.
        assert "Press release" in md
        assert "Apple Inc." in md
