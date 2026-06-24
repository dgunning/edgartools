"""
Regression tests for issue edgartools-rv86 / GH #873:
10-K MD&A (Item 7) unreachable when the filer incorporates it by reference into
an untitled "Financial Section" / page-range block.

Bug:
    Some large 10-K filers (ExxonMobil, JPMorgan) do not place MD&A / financial
    statements under the Item 7 / Item 8 headings. Item 7 holds a one-line
    pointer ("Reference is made to ... the Financial Section", "appears on pages
    46-160") and the real narrative lives later in an untitled block that carries
    no Item heading. The TOC detector has no anchor for that block, so the
    trailing item bucket (Item 15/16) absorbs the whole thing and Item 7/8 return
    only the pointer. There was no API that returned the MD&A.

Fix:
    edgar/documents/extractors/toc_section_extractor.py
    SECSectionExtractor._rescue_collapsed_incorporated_financials() (dispatched
    from _rescue_boundaries()): gated on a short
    incorporation-by-reference Item 7, discover the deferred block's own
    (sub-)TOC anchors, re-point Item 7/7A/8 at them (gap-fill Item 7's end to the
    financial-statements anchor when MD&A has no title link of its own), and
    clamp the trailing bucket that had absorbed the block. Gate skips normal
    filers, whose Item 7 already carries the MD&A.
"""
import re

import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig

MDA = re.compile(r"management.{0,3}s\s+discussion\s+and\s+analysis", re.IGNORECASE)


def _synthetic_10k(item7_pointer: bool, n: int = 1500) -> str:
    """Build a minimal 10-K whose Item 7/8 either point at a deferred Financial
    Section (item7_pointer=True) or carry their own content (False).

    ``n`` controls element count so the deferred body clears the element-span
    threshold the way a real filing's thousands of nodes do.
    """
    mda = ''.join(
        f'<p>MD&A narrative paragraph number {i} discussing results of operations.</p>'
        for i in range(n)
    )
    fs = ''.join(
        f'<p>Consolidated balance sheet line item {i} with financial figures.</p>'
        for i in range(n)
    )
    if item7_pointer:
        item7_body = '<p>Reference is made to the information in the Financial Section.</p>'
        item8_body = '<p>Reference is made to the Financial Section.</p>'
    else:
        item7_body = mda
        item8_body = fs

    return (
        '<html><body>'
        '<div><b>TABLE OF CONTENTS</b><table>'
        '<tr><td><a href="#i7">Item 7.</a></td><td><a href="#i7">Managements Discussion and Analysis</a></td><td><a href="#i7">28</a></td></tr>'
        '<tr><td><a href="#i8">Item 8.</a></td><td><a href="#i8">Financial Statements and Supplementary Data</a></td><td><a href="#i8">40</a></td></tr>'
        '<tr><td><a href="#i16">Item 16.</a></td><td><a href="#i16">Form 10-K Summary</a></td><td><a href="#i16">90</a></td></tr>'
        '</table></div>'
        f'<div id="i7"><b>Item 7.</b>{item7_body}</div>'
        f'<div id="i8"><b>Item 8.</b>{item8_body}</div>'
        '<div id="i16"><b>Item 16.</b><p>None.</p></div>'
        + (
            (
                '<div><b>Financial Section</b><table>'
                '<tr><td><a href="#fmda">Managements Discussion and Analysis</a><a href="#fmda">F-2</a></td></tr>'
                '<tr><td><a href="#ffs">Consolidated Financial Statements</a><a href="#ffs">F-30</a></td></tr>'
                '</table></div>'
                f'<div id="fmda"><b>Managements Discussion and Analysis</b>{mda}</div>'
                f'<div id="ffs"><b>Consolidated Financial Statements</b>{fs}</div>'
            )
            if item7_pointer else ''
        )
        + '</body></html>'
    )


class TestSyntheticReattribution:
    """Deterministic, no-network guard for the re-attribution logic."""

    def test_pointer_item7_recovers_deferred_mda(self):
        secs = parse_html(_synthetic_10k(item7_pointer=True), ParserConfig(form='10-K')).sections

        item7 = secs['part_ii_item_7'].text()
        item8 = secs['part_ii_item_8'].text()

        # Item 7 now carries the deferred MD&A body, not the 1-line pointer.
        assert len(item7) > 20000, f"Item 7 still a stub ({len(item7)} chars)"
        assert 'narrative paragraph number 700' in item7, "MD&A body not recovered into Item 7"
        assert 'Reference is made to' not in item7[:200] or 'narrative paragraph' in item7
        # Item 8 carries the deferred financial statements.
        assert 'balance sheet line item 700' in item8

    def test_trailing_bucket_no_longer_absorbs_block(self):
        secs = parse_html(_synthetic_10k(item7_pointer=True), ParserConfig(form='10-K')).sections
        item16 = secs['part_iv_item_16'].text()
        # Item 16 ("Form 10-K Summary": "None.") must snap back to its true tiny
        # size instead of absorbing the whole deferred block.
        assert len(item16) < 2000, f"Item 16 still absorbing the deferred block ({len(item16)} chars)"
        assert 'narrative paragraph' not in item16

    def test_gate_does_not_fire_on_normal_filer(self):
        # When Item 7 already carries the MD&A, re-attribution must not run.
        secs = parse_html(_synthetic_10k(item7_pointer=False), ParserConfig(form='10-K')).sections
        item7 = secs['part_ii_item_7']
        assert item7.detection_method != 'toc-reattributed'
        assert 'narrative paragraph number 700' in item7.text()


@pytest.mark.network
class TestRealWorldIncorporatedMDA:
    """Ground-truth assertions against the filings from GH #873 (pinned accessions)."""

    def test_exxonmobil_financial_section(self):
        import edgar

        # XOM 10-K, period 2025-12-31. Item 7 was a 265-char pointer; the real
        # ~314KB MD&A was absorbed into part_iv_item_16.
        ek = edgar.get_by_accession_number("0000034088-26-000045").obj()

        item7 = ek["Item 7"] or ""
        assert len(item7) > 50000, f"XOM Item 7 not recovered ({len(item7)} chars)"
        assert MDA.search(item7), "XOM Item 7 missing MD&A heading/body"
        # Leading navigation breadcrumb must be stripped (the anchor lands just
        # before the body MD&A heading).
        assert not item7.lstrip().lower().startswith("table of contents"), \
            "XOM Item 7 still has the leading TOC breadcrumb"

        item8 = ek["Item 8"] or ""
        assert len(item8) > 50000, f"XOM Item 8 not recovered ({len(item8)} chars)"

        # The trailing bucket that absorbed the block must have snapped back.
        item16 = ek.sections.get("part_iv_item_16")
        assert item16 is not None, \
            "XOM Item 16 missing — cannot verify the trailing-bucket clamp (GH #873)"
        assert len(item16.text()) < 100000, "XOM Item 16 still absorbing the Financial Section"

    def test_jpmorgan_mda_gap_fill(self):
        import edgar

        # JPM 10-K, period 2025-12-31. Item 7 pointer "appears on pages 46-160";
        # the real ~999KB MD&A+financials absorbed into part_iv_item_15. JPM has
        # no "Management's Discussion and Analysis" deferred title link, so Item 7
        # is recovered via the end-extension gap-fill.
        ek = edgar.get_by_accession_number("0001628280-26-008131").obj()

        item7 = ek["Item 7"] or ""
        assert len(item7) > 50000, f"JPM Item 7 not recovered ({len(item7)} chars)"
        assert MDA.search(item7), "JPM Item 7 missing MD&A"
        # MD&A must start at the supplement (not the Item 7 pointer), so the
        # exhibit index that physically precedes the supplement is excluded.
        assert "Certificate of Designations" not in item7, \
            "JPM Item 7 contaminated with the exhibit index"

        item8 = ek["Item 8"] or ""
        assert len(item8) > 100000, f"JPM Item 8 not recovered ({len(item8)} chars)"

        # Item 15 (Exhibits) must snap back to just the exhibit index, not absorb
        # the whole MD&A + financial supplement.
        item15 = ek.sections.get("part_iv_item_15")
        assert item15 is not None, \
            "JPM Item 15 missing — cannot verify the trailing-bucket clamp (GH #873)"
        assert len(item15.text()) < 100000, "JPM Item 15 still absorbing the supplement"

    def test_apple_control_unchanged(self):
        import edgar

        # AAPL 10-K, period 2025-09-27 — a normal filer whose Item 7 already holds
        # the ~18KB MD&A. The gate must NOT fire (no re-attribution, no inflation).
        ek = edgar.get_by_accession_number("0000320193-25-000079").obj()

        item7 = ek["Item 7"] or ""
        assert MDA.search(item7), "AAPL Item 7 missing MD&A"
        assert 10000 < len(item7) < 40000, f"AAPL Item 7 unexpectedly changed ({len(item7)} chars)"

        section = ek.sections.get("part_ii_item_7")
        assert section is not None
        assert section.detection_method != 'toc-reattributed', "Gate wrongly fired on AAPL"
