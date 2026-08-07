"""Unit tests for authoritative-TOC selection (edgartools-4m4x).

A title-based filing can carry more than one set of vocabulary-matching internal
links: the real Table of Contents (a dense, contiguous block) plus body
back-references / "return to contents" links scattered through the document.
Those body links point *adjacent* to a section start, so when they leak into the
boundary set every section is sliced to a sliver (the Apple/JPM DEF 14A failure).

``TOCAnalyzer._authoritative_toc_span`` isolates the real TOC by picking the
densest run of links carrying the most distinct keys. These tests pin that
selection directly on the pure function so the behaviour is locked even though
no currently-flipped form (single-TOC prospectus/S-1) exercises the multi-run
path yet.
"""
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

span = TOCAnalyzer._authoritative_toc_span


def test_single_dense_toc_returns_full_span():
    # One contiguous TOC: every link within the run-gap of the previous.
    links = [(100, "a", "summary"), (110, "b", "risk_factors"), (122, "c", "underwriting")]
    assert span(links) == (100, 122)


def test_body_backlinks_excluded_in_favor_of_dense_toc():
    # Dense TOC up front (3 distinct keys, tight) ...
    toc = [(50, "t1", "summary"), (60, "t2", "risk_factors"), (72, "t3", "underwriting")]
    # ... then sparse body back-references far apart, each matching a key but
    # never forming a richer run than the real TOC.
    body = [(900, "b1", "summary"), (1800, "b2", "risk_factors"), (2700, "b3", "underwriting")]
    lo, hi = span(toc + body)
    assert (lo, hi) == (50, 72), "should select the dense TOC run, not body back-links"


def test_richest_run_wins_over_larger_sparse_run():
    # A later block has more links but fewer distinct keys (e.g. a proposals list
    # all collapsing to one key); the key-richer TOC must still win.
    toc = [(10, "t1", "summary"), (20, "t2", "risk_factors"),
           (30, "t3", "use_of_proceeds"), (40, "t4", "underwriting")]
    repetitive = [(500 + i * 5, f"p{i}", "voting_proposals") for i in range(8)]
    assert span(toc + repetitive) == (10, 40)


def test_no_matched_keys_returns_none():
    links = [(10, "a", None), (20, "b", None)]
    assert span(links) == (None, None)


def test_empty_returns_none():
    assert span([]) == (None, None)
