"""Regression tests for GitHub Issue #918: item sections rebuilt from
cross-references by the short-section rescue.

The defect produced mislabeled sections at full confidence with no warning
(bulk-scan cluster: ICE/CSCO/CTSH 10-Qs). On ICE's Q3 2024 10-Q (accession
0001571949-24-000017), ``obj['PART II, Item 1']`` returned 101,823 chars
opening mid-sentence inside MD&A prose ('Item 1 "Business — Regulation" …
included in our 2023 Form 10-K …'). The TOC anchor was CORRECT; the
correctly-anchored text is legitimately short ("See Note 13 …"), which trips
the <200-char rescue in ``get_section_text``. ``_text_on_item_heading``
judged the text mis-anchored because ``_ITEM_TITLE_PATTERNS`` holds the 10-K
titles ('1' → BUSINESS) while a 10-Q's Part II Item 1 is Legal Proceedings;
then ``_find_actual_item_content`` regex-hunted the RAW HTML document-wide
and matched the cross-reference (the curly-quote entity ``&#8220;`` is made
entirely of chars in the separator class), rebuilding the section from
another item's prose. Fixed by (a) accepting a text that OPENS with the
item's own "ITEM <n>" heading regardless of title, and (b) constraining the
rescue's search to the window between the section's start and end anchors —
its premise is an anchor that landed just before the body, so the real
heading is never behind the anchor.

(#918's second defect — FMCC 10-K items anchored on numbered "List of
Tables" index rows — is tracked separately and not covered here.)

Unit tests are synthetic (no network); the end-to-end assertion is
VCR-backed and pinned to the reported filing.

GitHub Issue: https://github.com/dgunning/edgartools/issues/918
"""

import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor

# ICE-shaped 10-Q: the Part II Item 1 anchor (t5) is correct and its section
# is a short incorporation-by-reference stub bounded by Item 1A's anchor (t6).
# A cross-reference to "Item 1 “Business — Regulation”" of the 10-K sits
# EARLIER in the document, inside MD&A — before the fix, the short-section
# rescue rebuilt Part II Item 1 from that prose.
ICE_SHAPED_10Q = """
<html><body>
<div>TABLE OF CONTENTS</div>
<table>
<tr><td><a href="#t1">Item 1.</a></td><td><a href="#t1">Financial Statements</a></td></tr>
<tr><td><a href="#t2">Item 2.</a></td><td><a href="#t2">Management&#8217;s Discussion and Analysis</a></td></tr>
<tr><td><a href="#t3">Item 3.</a></td><td><a href="#t3">Quantitative and Qualitative Disclosures About Market Risk</a></td></tr>
<tr><td><a href="#t4">Item 4.</a></td><td><a href="#t4">Controls and Procedures</a></td></tr>
<tr><td colspan="2">PART II</td></tr>
<tr><td><a href="#t5">Item 1.</a></td><td><a href="#t5">Legal Proceedings</a></td></tr>
<tr><td><a href="#t6">Item 1A.</a></td><td><a href="#t6">Risk Factors</a></td></tr>
</table>
<div id="t1"></div>
<div>ITEM 1. FINANCIAL STATEMENTS</div>
<p>Balance sheets and notes MARKER_FIN.</p>
<div id="t2"></div>
<div>ITEM 2. MANAGEMENT&#8217;S DISCUSSION AND ANALYSIS</div>
<p>See Item 1 &#8220;Business &#8212; Regulation&#8221; and Part 1, Item 1(A) "Risk Factors"
included in our 2023 Form 10-K for a discussion of the primary regulations
applicable to our business MARKER_XREF.</p>
<div id="t3"></div>
<div>ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK</div>
<p>Interest rate risk MARKER_MR.</p>
<div id="t4"></div>
<div>ITEM 4. CONTROLS AND PROCEDURES</div>
<p>Evaluation of disclosure controls MARKER_CTRL.</p>
<div>PART II</div>
<div id="t5"></div>
<div>ITEM 1. LEGAL PROCEEDINGS</div>
<p>See Note 13 to the consolidated financial statements MARKER_LEGAL.</p>
<div id="t6"></div>
<div>ITEM 1A. RISK FACTORS</div>
<p>There have been no material changes MARKER_RF.</p>
</body></html>
"""

@pytest.fixture
def tenq_extractor():
    return SECSectionExtractor(
        parse_html(ICE_SHAPED_10Q, ParserConfig(form="10-Q")), form="10-Q")


class TestTextOnItemHeading:
    """A text opening with the item's own heading is on-heading, whatever the form."""

    def test_10q_legal_proceedings_stub_is_on_heading(self, tenq_extractor):
        """The ICE bug: correctly-anchored brief 10-Q Part II Item 1."""
        text = "ITEM\xa01.\xa0\xa0LEGAL PROCEEDINGS\n\nSee Note 13, incorporated by reference."
        assert tenq_extractor._text_on_item_heading(text, "1") is True

    def test_paren_letter_style_is_on_heading(self, tenq_extractor):
        """ICE writes 'ITEM 1(A).' for Item 1A."""
        text = "ITEM 1(A).    RISK FACTORS\n\nNo material changes."
        assert tenq_extractor._text_on_item_heading(text, "1A") is True

    def test_part_header_prefix_is_on_heading(self, tenq_extractor):
        """An anchor on the PART header directly before the item still bounds it."""
        text = "PART II\n\nITEM 1. LEGAL PROCEEDINGS\n\nNone."
        assert tenq_extractor._text_on_item_heading(text, "1") is True

    def test_part_iii_item_without_title_entry_is_on_heading(self, tenq_extractor):
        """Items 10+ have no _ITEM_TITLE_PATTERNS entry; the heading still counts."""
        text = "ITEM 11. EXECUTIVE COMPENSATION\n\nIncorporated by reference."
        assert tenq_extractor._text_on_item_heading(text, "11") is True

    def test_wrong_item_number_is_not_on_heading(self, tenq_extractor):
        assert tenq_extractor._text_on_item_heading("ITEM 10. DIRECTORS", "1") is False
        assert tenq_extractor._text_on_item_heading("ITEM 1A. RISK FACTORS", "1") is False

    def test_repeated_digit_heading_is_not_on_heading(self, tenq_extractor):
        """The separator class carries 0-9 for entity noise, so without the
        leading-digit lookbehind it swallowed the first '1' of 'ITEM 11' and
        item 1 matched the second."""
        assert tenq_extractor._text_on_item_heading(
            "ITEM 11. EXECUTIVE COMPENSATION", "1") is False
        # The entity noise the digits exist for still matches.
        assert tenq_extractor._text_on_item_heading(
            "ITEM&#160;1.&#160;BUSINESS", "1") is True

    def test_bare_part_header_is_not_on_heading(self, tenq_extractor):
        """The case the rescue exists for: an anchor stuck on a PART header."""
        assert tenq_extractor._text_on_item_heading("PART I", "1") is False

    def test_mid_prose_cross_reference_is_not_on_heading(self, tenq_extractor):
        text = 'We refer you to Item 1 "Business" of our 2023 Form 10-K.'
        assert tenq_extractor._text_on_item_heading(text, "1") is False


class TestCrossReferenceRescue:
    """The short-section rescue no longer rebuilds sections from cross-references."""

    def test_part_ii_item_1_keeps_its_short_stub(self, tenq_extractor):
        text = tenq_extractor.get_section_text("part_ii_item_1")
        assert text is not None
        assert text.lstrip().upper().startswith("ITEM 1. LEGAL PROCEEDINGS")
        assert "MARKER_LEGAL" in text
        assert "MARKER_XREF" not in text
        assert "Business" not in text

    def test_rescue_search_is_bounded_by_the_section_anchors(self, tenq_extractor):
        """Even when invoked directly, the hunt cannot land before the anchor."""
        boundary = tenq_extractor.section_boundaries["part_ii_item_1"]
        rescued = tenq_extractor._find_actual_item_content(
            ICE_SHAPED_10Q, "1", boundary, clean=False)
        assert rescued is None or "MARKER_XREF" not in rescued


@pytest.mark.fast
@pytest.mark.vcr
def test_ice_10q_part_ii_item_1_is_not_a_cross_reference():
    """End-to-end on the reported filing: ICE Q3 2024 10-Q.

    Before the fix ``obj['PART II, Item 1']`` returned 101,823 chars opening
    mid-sentence inside the MD&A cross-reference to the 10-K's Item 1.
    """
    from edgar import Filing

    filing = Filing(form='10-Q', filing_date='2024-10-31',
                    company='Intercontinental Exchange, Inc.',
                    cik=1571949, accession_no='0001571949-24-000017')
    obj = filing.obj()

    content = obj['PART II, Item 1']
    assert content is not None
    assert len(content) == 144
    assert content.lstrip().replace('\xa0', ' ').upper().startswith(
        "ITEM 1.    LEGAL PROCEEDINGS")
    assert "Business" not in content
    assert "Regulation" not in content

    # The size guardrail no longer flags this stub, and should not: a 10-Q's
    # Part II Item 1 is Legal Proceedings, which is legitimately a pointer to a
    # note, and it was only ever judged against Part I's Financial Statements
    # floor because the bands were keyed on the bare item number
    # (edgartools-xhmd). What this regression is about is unchanged and asserted
    # above — the content is no longer 101K chars of another section's prose.
    section = obj.document.sections["part_ii_item_1"]
    assert section.confidence == 0.95
    assert not section.warnings
