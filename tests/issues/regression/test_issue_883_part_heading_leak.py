"""Regression test for GitHub Issue #883 (beads edgartools-m58p):

``TenQ.get_item_with_part('Part I', 'Item 4')`` leaked the trailing
"PART II — OTHER INFORMATION" heading into the returned text.

Root cause: the live path returns ``self.sections['part_i_item_4'].text()``
(``edgar/company_reports/ten_q.py``), which cleans boundary artifacts via
``Section._clean_boundary_artifacts``. Every ``PART`` rule there (2a/2b) only
fires when an ``Item N`` token follows the PART line, so Part II's *titled*
heading — "OTHER INFORMATION", with no item number — slipped through and was
appended to Part I's last item (Controls and Procedures).

Fix: one trailing-boundary rule in ``_clean_boundary_artifacts`` matching the
literal ``PART II ... OTHER INFORMATION`` heading. It admits only non-word
separators between the numeral and the title (a real space, em-dash,
glued/no-space, or a line break for a two-line render) and absorbs trailing
punctuation/qualifiers, so it strips the heading in all its rendered forms
without truncating body prose that merely names a part. The literal ``PART II``
anchor (not a general roman numeral) leaves the legitimate ``PART C — OTHER
INFORMATION`` heading of S-1 / N-1A / N-2 filings untouched, since the cleaner
runs for every form. A letter-only mojibake separator is deliberately not
matched — the heading survives rather than risk deleting real content.

The unit tests exercise ``_clean_boundary_artifacts`` directly (no network):
``TestNextPartHeadingStripped`` covers every rendered variant, and
``TestDoesNotOverStrip`` guards the regressions surfaced in code review. The
AAPL end-to-end assertion is marked ``network`` and pinned to the reported
filing.

Ground truth: accession 0000320193-20-000052 — Apple Inc. Form 10-Q filed
2020-05-01, period 2020-03-28. Item 4's body ends at "...internal control over
financial reporting."; "PART II — OTHER INFORMATION" is Part II's title, not
part of Item 4.

Out of scope (separate defect, flagged in the issue): the page-footer line
"Apple Inc. | Q2 2020 Form 10-Q | 33" still bleeds into Item 4; that is a
distinct footer-stripping issue and is intentionally not asserted away here.
"""
import pytest

from edgar.documents.document import Section

# The method uses no instance state, so bypass the (node-requiring) constructor.
_clean = Section.__new__(Section)._clean_boundary_artifacts

# Realistic tail of Part I / Item 4 (Controls and Procedures).
_BODY = (
    "Item 4. Controls and Procedures\n\n"
    "There were no changes in the Company's internal control over financial "
    "reporting during the most recently completed fiscal quarter that have "
    "materially affected, or are reasonably likely to materially affect, the "
    "Company's internal control over financial reporting."
)


class TestNextPartHeadingStripped:
    """A trailing next-Part heading must not leak into the prior item's text.

    The separator between "PART II" and "OTHER INFORMATION" varies across real
    filings, so each variant is exercised independently.
    """

    @pytest.mark.parametrize(
        "heading",
        [
            "PART II  —  OTHER INFORMATION",    # em-dash with spaces (AAPL 2020)
            "PART II OTHER INFORMATION",         # single ASCII space
            "PART IIOTHER INFORMATION",          # glued, no whitespace at all
            "**PART II — OTHER INFORMATION**",   # markdown bold decoration
            "## PART II — OTHER INFORMATION",    # markdown heading decoration
            "part ii — other information",       # lowercase (case-insensitive)
            "PART II. OTHER INFORMATION.",       # trailing period / period sep
            "PART II — OTHER INFORMATION (UNAUDITED)",  # trailing qualifier
        ],
    )
    def test_trailing_heading_removed(self, heading):
        cleaned = _clean(f"{_BODY}\n\n{heading}")
        assert "OTHER INFORMATION" not in cleaned.upper()
        assert "PART II" not in cleaned.upper()
        assert cleaned.rstrip().endswith("financial reporting.")

    def test_two_line_heading_removed(self):
        # Some filers render the numeral and the title as separate block
        # elements, so the heading arrives on two lines.
        cleaned = _clean(f"{_BODY}\n\nPART II\n\nOTHER INFORMATION")
        assert "OTHER INFORMATION" not in cleaned.upper()
        assert cleaned.rstrip().endswith("financial reporting.")

    def test_heading_after_page_footer_still_removed(self):
        # The real filing has a page footer between the item body and the Part
        # heading. The heading must still be stripped even when it is not
        # directly adjacent to the body text.
        text = f"{_BODY}\n\nApple Inc. | Q2 2020 Form 10-Q | 33\n\nPART II  —  OTHER INFORMATION"
        cleaned = _clean(text)
        assert "OTHER INFORMATION" not in cleaned.upper()


class TestDoesNotOverStrip:
    """The strip must be precise — it must not delete legitimate content.

    ``_clean_boundary_artifacts`` runs for every section of every form, so the
    rule is constrained to the literal ``PART II ... OTHER INFORMATION`` heading
    and never crosses body words. Regressions surfaced in code review (GH #883).
    """

    def test_prose_beginning_part_ii_ending_other_information(self):
        # A real sentence that starts "Part II" and ends "other information"
        # must survive — the separator admits only non-word characters, so the
        # word "contains" blocks the match.
        text = "Discussion of controls.\n\nPart II contains other information about the plan."
        assert _clean(text) == text.rstrip()

    def test_legitimate_part_c_other_information_heading(self):
        # S-1 / N-1A / N-2 registration statements use "PART C — OTHER
        # INFORMATION" as a real, content-bearing heading. The literal "PART II"
        # anchor must leave it untouched.
        text = "Exhibits index follows.\n\nPART C — OTHER INFORMATION"
        assert _clean(text) == text.rstrip()

    def test_body_prose_naming_a_part_is_not_truncated(self):
        prose = "See the disclosures in Part II of this report for further details."
        assert _clean(prose) == prose

    def test_other_information_in_body_not_over_stripped(self):
        text = "We disclose other information about controls here.\n\nSee above."
        assert _clean(text) == text.rstrip()


@pytest.mark.network
@pytest.mark.regression
def test_aapl_10q_item4_no_part_ii_heading():
    """End-to-end: AAPL 10-Q Item 4 must not carry Part II's title (GH #883)."""
    from edgar import get_by_accession_number

    filing = get_by_accession_number("0000320193-20-000052")
    tenq = filing.obj()

    item4 = tenq.get_item_with_part("Part I", "Item 4")

    assert item4 is not None
    # The bug: Part II's title leaked into Item 4.
    assert "OTHER INFORMATION" not in item4.upper()
    assert "PART II" not in item4.upper()
    # The item body itself is preserved and correct.
    assert "internal control over financial reporting" in item4
