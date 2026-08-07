"""Regression test for #765 — SearchResults rendered panel titles must be
the source section index (DocSection.loc), not the score-sorted display rank.

Previously BM25 path sorted by score so `panel title "0"` meant
"highest-scoring section" while regex path (no score) showed "0" for the
first match in document order — same query, different meaning per method.
"""

import pytest

from edgar.search.textsearch import DocSection, SearchResults


def _titles(result: SearchResults) -> list[str]:
    """Extract panel titles in the order __rich__ renders them."""
    rendered = result.__rich__()
    group = rendered.renderable  # outer Panel wraps a Group of Panels
    return [str(child.title) for child in group.renderables]


@pytest.mark.fast
def test_panel_titles_use_source_loc_not_display_rank():
    sections = [
        DocSection(loc=3, doc="alpha", score=0.5),
        DocSection(loc=11, doc="beta", score=2.0),
        DocSection(loc=17, doc="gamma", score=1.0),
    ]
    result = SearchResults(query="x", sections=sections)
    titles = _titles(result)
    # Sorted by score descending: beta (2.0), gamma (1.0), alpha (0.5)
    # But the DISPLAYED title must be the source loc, not the rank.
    assert titles == ["11", "17", "3"]


@pytest.mark.fast
def test_panel_titles_consistent_when_scores_all_zero():
    """Regex search returns DocSection with score=0.0 — original order kept,
    titles must still be the source loc not the enumeration index."""
    sections = [
        DocSection(loc=2, doc="alpha"),
        DocSection(loc=8, doc="beta"),
        DocSection(loc=14, doc="gamma"),
    ]
    result = SearchResults(query="x", sections=sections)
    titles = _titles(result)
    assert titles == ["2", "8", "14"]


@pytest.mark.fast
def test_empty_results_renders_without_panels():
    result = SearchResults(query="x", sections=[])
    rendered = result.__rich__()
    group = rendered.renderable
    assert list(group.renderables) == []
