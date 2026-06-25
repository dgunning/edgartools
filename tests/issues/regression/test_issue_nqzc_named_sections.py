"""Regression: named sections (Signatures) surface in document.sections.

edgartools-nqzc. ``part_iv_signatures`` flowed through the TOC mapping and the
extractor's section_boundaries but never reached ``document.sections``. Root
cause: ``_get_section_type_and_order('part_iv_signatures')`` matched no item
number, fell through to the Part rule, and returned order 400 from the
``part_iv`` prefix — sorting Signatures *first*. Boundaries are assigned as
"the next section's anchor", so Signatures was handed Item 1's anchor as its
end boundary: a backward end-anchor (end doc-pos before the start) that walked
to nothing, emptied the text, and tripped the detector's empty-text skip.

Ordering an allowlisted named section after the last item of its Part (or
globally last for a bare key) restores ``end_element_id=None`` (run to EOF), so
Signatures extracts its real content and surfaces. A side benefit: the last
Part IV item no longer runs to EOF and over-captures the signature block.

The ordering unit tests are offline; the end-to-end surfacing is asserted in
``test_issue_837_workiva_item1_missing`` which already loads the Allstate filing
under VCR (no second giant cassette).
"""
import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer

pytestmark = [pytest.mark.fast, pytest.mark.regression]


def _order(name: str) -> int:
    return TOCAnalyzer(form="10-K")._get_section_type_and_order(name)[1]


def test_part_prefixed_signatures_sorts_after_last_item():
    """part_iv_signatures must sort after Part IV Item 16, not as a Part header."""
    sig = _order("part_iv_signatures")
    assert sig > _order("part_iv_item_16")
    # And not the old order-400 misclassification that placed it before Item 1.
    assert sig > _order("part_i_item_1")


def test_bare_signatures_sorts_globally_last():
    """A bare 'signatures' key (no Part prefix) sorts after every item."""
    assert _order("signatures") > _order("part_iv_item_16")


def test_signatures_classified_as_named_section_not_part():
    """Type is 'section' (named), not 'part' — the prefix must not win."""
    kind, _ = TOCAnalyzer(form="10-K")._get_section_type_and_order("part_iv_signatures")
    assert kind == "section"


def test_unknown_named_suffix_still_treated_as_part_header():
    """A non-allowlisted 'part_iv_<word>' keeps the Part-header order (no leak)."""
    analyzer = TOCAnalyzer(form="10-K")
    kind, order = analyzer._get_section_type_and_order("part_iv_glossary")
    assert kind == "part"
    assert order == 400
