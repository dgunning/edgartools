"""
Regression tests for the GH #871 follow-up: the section-end fix must not bleed
title-based prospectus (424B / S-1) sections into one another.

Bug (introduced by the first #871 fix):
    ``_find_section_end`` was changed to close a section only at a header passing
    ``_looks_like_section_header`` — a fixed allowlist (Item/PART/SIGNATURE/
    EXHIBIT/RISK FACTORS/...). That fixed 8-K sub-heading truncation, but the same
    code path runs for 424B prospectuses whose sections are *title-based*
    ("Use of Proceeds", "Dilution", "Underwriting"). None of those titles are in
    the allowlist, so a section's end-finder skipped the next section's heading and
    the section swallowed everything that followed it — a content-bleed in the
    opposite direction of the original truncation bug.

Fix:
    edgar/documents/extractors/pattern_section_extractor.py
    A header may close a section if it starts one of *this form's* recognized
    sections (``boundary_indices``, precomputed in ``_match_sections``) OR matches
    the generic structural allowlist. Title-based sections thus close on their own
    headings, while internal sub-headings (which match neither) still do not.

This is the silent-regression guard the existing prospectus test could not catch:
``TestProspectusSections.test_section_text_extraction`` only asserts sections are
non-empty, and bleeding makes a section *longer*, never empty.
"""
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


class TestProspectusSectionsDoNotBleed:
    """Deterministic, no-network guard for the title-based-section boundary fix."""

    # A minimal 424B-shaped document: each section title is a semantic heading
    # (so it lands in the unfiltered HeadingNode list), with a distinctive body
    # marker. "Use of Proceeds" also carries an internal sub-heading that is NOT a
    # section boundary, to confirm the #871 protection still holds here.
    HTML = """
    <html><body>
    <h2>Use of Proceeds</h2>
    <p>MARKER_PROCEEDS_BODY: We intend to use the net proceeds from this offering
    for general corporate purposes, including working capital.</p>
    <h3>Anticipated Allocation</h3>
    <p>MARKER_PROCEEDS_TAIL: A portion may be allocated to repayment of debt.</p>
    <h2>Dilution</h2>
    <p>MARKER_DILUTION_BODY: If you invest in our securities, your interest will be
    diluted to the extent of the difference between the offering price and the net
    tangible book value per share.</p>
    <h2>Underwriting</h2>
    <p>MARKER_UNDERWRITING_BODY: Subject to the terms and conditions of the
    underwriting agreement, the underwriters have agreed to purchase the shares.</p>
    </body></html>
    """

    def _doc(self):
        return parse_html(self.HTML, ParserConfig(form='424B5'))

    def test_all_three_sections_detected(self):
        sections = self._doc().sections
        assert 'use_of_proceeds' in sections
        assert 'dilution' in sections
        assert 'underwriting' in sections

    def test_use_of_proceeds_does_not_swallow_following_sections(self):
        """The core regression: a title-based section must end at the next title."""
        text = self._doc().sections['use_of_proceeds'].text()
        # Its own body (including the part after the internal sub-heading) is kept.
        assert 'MARKER_PROCEEDS_BODY' in text
        assert 'MARKER_PROCEEDS_TAIL' in text, \
            "Body after the internal sub-heading was dropped (GH #871 protection)"
        # ...but the following sections' bodies must NOT bleed in.
        assert 'MARKER_DILUTION_BODY' not in text, \
            "Use of Proceeds bled into the Dilution section (title-based over-correction)"
        assert 'MARKER_UNDERWRITING_BODY' not in text, \
            "Use of Proceeds bled into the Underwriting section (title-based over-correction)"

    def test_dilution_does_not_swallow_underwriting(self):
        text = self._doc().sections['dilution'].text()
        assert 'MARKER_DILUTION_BODY' in text
        assert 'MARKER_UNDERWRITING_BODY' not in text, \
            "Dilution bled into the Underwriting section (title-based over-correction)"

    def test_internal_subheading_does_not_start_a_section(self):
        """The non-boundary sub-heading must stay inside Use of Proceeds."""
        sections = self._doc().sections
        # "Anticipated Allocation" is neither a 424B pattern nor in the allowlist,
        # so it must not appear as its own detected section.
        assert not any('allocation' in k.lower() for k in sections)
