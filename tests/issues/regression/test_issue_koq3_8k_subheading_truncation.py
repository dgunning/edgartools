"""
Regression tests for issue edgartools-koq3 / GH #871:
8-K item section truncated at an internal bold sub-heading.

Bug:
    For an 8-K whose item body contains an internal bold sub-heading, the
    pattern section extractor ended the item's section at that sub-heading and
    dropped the rest of the item body. The sub-heading is captured as a
    HeadingNode (Strategy 1 adds every HeadingNode unconditionally), and
    ``_find_section_end`` closed the section at the next header whose level was
    <= the item header's level — without checking whether that header was an
    actual section boundary.

    Example: NVIDIA 8-K, accession 0001045810-26-000024 (filed 2026-03-06).
    Item 5.02 ("Adoption of Fiscal Year 2027 Variable Compensation Plan") was
    returned as a 214-char stub instead of its full ~3179-char body, because
    the bold sub-heading line was treated as the start of a new section.

Fix:
    edgar/documents/extractors/pattern_section_extractor.py, _find_section_end()
    A header may only close a section if it looks like a real section boundary
    (``_looks_like_section_header``: Item/PART/SIGNATURE/EXHIBIT/...). Internal
    sub-headings are skipped, so the body paragraphs that follow them stay
    attached to the current item.
"""
import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.nodes import HeadingNode


class TestSubheadingDoesNotTruncateItem:
    """Deterministic, no-network guard for the boundary fix."""

    # Mirrors the NVDA structure: a bold item header (parsed as a paragraph),
    # then an internal bold sub-heading (parsed as a HeadingNode), then the
    # item body, then the next item.
    HTML = """
    <html><body>
    <p style="font-weight:bold">Item 5.02. Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers; Compensatory Arrangements of Certain Officers.</p>
    <h3 style="font-weight:bold">Adoption of Fiscal Year 2027 Variable Compensation Plan</h3>
    <p>On March 2, 2026, the Compensation Committee of the Board of Directors adopted the Variable Compensation Plan for Fiscal Year 2027. This is the substantive body that must not be dropped.</p>
    <p>A second body paragraph with additional detail about the plan terms and eligibility.</p>
    <p style="font-weight:bold">Item 9.01. Financial Statements and Exhibits.</p>
    <p>(d) Exhibits</p>
    </body></html>
    """

    def _doc(self):
        return parse_html(self.HTML, ParserConfig(form='8-K'))

    def test_subheading_is_a_heading_node(self):
        """Precondition: the sub-heading is captured as a HeadingNode.

        This is what makes it a candidate section boundary; if the parser ever
        stops doing this the test below would pass trivially, so assert it.
        """
        doc = self._doc()
        sub = next(
            (n for n in doc.root.walk()
             if isinstance(n, HeadingNode) and 'Adoption' in (n.text() or '')),
            None,
        )
        assert sub is not None, "Sub-heading should be parsed as a HeadingNode"

    def test_item_body_not_truncated_at_subheading(self):
        """The Item 5.02 body must survive the internal bold sub-heading."""
        doc = self._doc()
        sections = doc.sections
        assert 'item_502' in sections, "Should detect Item 5.02"

        text = sections['item_502'].text()
        # The sub-heading line itself is retained...
        assert 'Adoption of Fiscal Year 2027 Variable Compensation Plan' in text
        # ...AND the body paragraphs that follow it (the regression).
        assert 'substantive body that must not be dropped' in text, \
            "Item body after the bold sub-heading was dropped (GH #871)"
        assert 'second body paragraph' in text, \
            "Trailing item paragraphs were dropped (GH #871)"

    def test_subheading_body_not_misfiled_under_next_item(self):
        """The dropped body must not leak into the following item either."""
        doc = self._doc()
        item_901 = doc.sections['item_901'].text()
        assert 'substantive body that must not be dropped' not in item_901, \
            "Item 5.02 body must belong to item_502, not item_901"


@pytest.mark.network
class TestNvidia8KGroundTruth:
    """Ground-truth assertion against the real filing from GH #871."""

    @pytest.mark.vcr
    def test_nvidia_item_502_full_body(self):
        import edgar

        # NVIDIA 8-K, 2026-03-06, items 5.02 + 9.01. Item 5.02 has an internal
        # bold sub-heading ("Adoption of Fiscal Year 2027 Variable Compensation
        # Plan"). Before the fix this returned a 214-char stub.
        filing = edgar.get_by_accession_number("0001045810-26-000024")
        ek = filing.obj()

        text = ek["Item 5.02"]
        assert text is not None

        # Full body is ~3179 chars (the legacy chunked parser's value); the
        # section parser now matches it closely. Well above the 214-char stub.
        assert len(text.strip()) > 3000, \
            f"Item 5.02 truncated to {len(text.strip())} chars (expected full ~3179-char body)"

        # Body content that lived *after* the bold sub-heading must be present.
        assert "Compensation Committee" in text
        assert "Variable Compensation Plan for Fiscal Year 2027" in text

        # sections[...] and __getitem__ resolve to the same (full) text.
        assert ek.sections["item_502"].text().strip() == text.strip()
