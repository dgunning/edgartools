"""Navigation-pattern resolution is per document, not per section (edgartools-llmp.9).

The pattern cache is keyed by an md5 of the entire filing, so resolving costs an
encode plus a hash of every byte — ~340ms on a 9.8MB 10-K. Section extraction
filtered once per section, which re-derived that key roughly 25 times per
document to prove it had not changed.

These tests assert the *behaviour* rather than the timing: the key is derived a
bounded number of times per document however many sections are extracted, and
the text that comes out is unchanged.
"""
import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.utils import anchor_cache
from edgar.documents.utils.anchor_cache import (
    FALLBACK_PATTERNS,
    filter_navigation_lines,
    filter_with_cached_patterns,
    resolve_navigation_patterns,
)

# Offline: every test parses an inline HTML string. Marked explicitly rather than
# by filename so the collection gate in conftest can place the file in a CI job.
pytestmark = pytest.mark.fast

# Six items, plus a "Table of Contents" backlink repeated often enough to clear
# _analyze_navigation_minimal's min_frequency of 5.
NAV_LINK = '<div><a href="#toc">Table of Contents</a></div>'
ITEMS = [
    ("i1", "Item 1. Business", "BUSINESS_BODY"),
    ("i1a", "Item 1A. Risk Factors", "RISK_BODY"),
    ("i2", "Item 2. Properties", "PROPERTIES_BODY"),
    ("i3", "Item 3. Legal Proceedings", "LEGAL_BODY"),
    ("i5", "Item 5. Market for Registrant's Common Equity", "MARKET_BODY"),
    ("i7", "Item 7. Management's Discussion and Analysis", "MDA_BODY"),
]
FILING_HTML = (
    "<html><body><div id='toc'>"
    + "".join(f'<a href="#{anchor}">{title}</a>' for anchor, title, _ in ITEMS)
    + "</div>"
    + "".join(f"{NAV_LINK}<div id='{anchor}'><p>{title}</p><p>{body}</p></div>"
             for anchor, title, body in ITEMS)
    + "</body></html>"
)


@pytest.fixture
def count_hashes(monkeypatch):
    """Count every md5-of-the-filing the pattern cache performs."""
    calls = []
    original = anchor_cache.AnchorCache._get_html_hash

    def counting(self, html_content):
        calls.append(len(html_content))
        return original(self, html_content)

    monkeypatch.setattr(anchor_cache.AnchorCache, "_get_html_hash", counting)
    return calls


def test_filing_is_hashed_a_bounded_number_of_times_regardless_of_section_count(count_hashes):
    doc = parse_html(FILING_HTML, ParserConfig(form="10-K"))
    extracted = [s for s in (doc.sections or {}).values() if s.text()]

    assert len(extracted) >= 4, "need several sections for this to mean anything"
    # A cold document hashes twice — once to look the key up, once to store it.
    # What must not happen is scaling with the number of sections.
    assert len(count_hashes) <= 2, (
        f"hashed the filing {len(count_hashes)} times for {len(extracted)} sections")


def test_document_text_does_not_rehash_after_sections(count_hashes):
    doc = parse_html(FILING_HTML, ParserConfig(form="10-K"))
    for section in (doc.sections or {}).values():
        section.text()
    before = len(count_hashes)
    doc.text()
    assert len(count_hashes) == before, "Document.text() re-derived the cache key"


def test_patterns_are_resolved_once_and_reused():
    doc = parse_html(FILING_HTML, ParserConfig(form="10-K"))
    first = doc._get_navigation_patterns()
    assert first is doc._get_navigation_patterns()
    assert "Table of Contents" in first


def test_empty_pattern_set_is_cached_not_reresolved(count_hashes):
    """An empty result is a real answer, so it must not be mistaken for 'unset'."""
    doc = parse_html("<html><body><p>Item 1. Business</p><p>BODY</p></body></html>",
                     ParserConfig(form="10-K"))
    patterns = doc._get_navigation_patterns()
    assert patterns == frozenset()
    hashes = len(count_hashes)
    doc._get_navigation_patterns()
    assert len(count_hashes) == hashes


class TestResolveAndFilterSplit:
    """The two halves must compose back into the original single-call behaviour."""

    def test_missing_html_falls_back_to_the_generic_sec_patterns(self):
        assert resolve_navigation_patterns(None) == FALLBACK_PATTERNS
        assert resolve_navigation_patterns("") == FALLBACK_PATTERNS

    def test_filter_keeps_first_two_occurrences_and_drops_the_rest(self):
        text = "\n".join(["Table of Contents", "a", "Table of Contents", "b",
                          "Table of Contents", "c", "Table of Contents"])
        filtered = filter_navigation_lines(text, {"Table of Contents"})
        assert filtered.split("\n").count("Table of Contents") == 2
        assert filtered.split("\n") == ["Table of Contents", "a", "Table of Contents",
                                        "b", "c"]

    def test_empty_patterns_leave_text_untouched(self):
        text = "Table of Contents\nbody"
        assert filter_navigation_lines(text, set()) == text
        assert filter_navigation_lines("", {"Table of Contents"}) == ""

    @pytest.mark.parametrize("html", [None, FILING_HTML])
    def test_wrapper_matches_resolve_plus_filter(self, html):
        text = "\n".join(["Table of Contents", "body", "Table of Contents",
                          "more", "Table of Contents"])
        assert filter_with_cached_patterns(text, html) == filter_navigation_lines(
            text, resolve_navigation_patterns(html))

    def test_wrapper_short_circuits_empty_text(self):
        assert filter_with_cached_patterns("", FILING_HTML) == ""


def test_section_text_is_unchanged_by_the_split():
    """Equivalence: filtering through the cached patterns matches the old path."""
    doc = parse_html(FILING_HTML, ParserConfig(form="10-K"))
    for name, section in (doc.sections or {}).items():
        text = section.text() or ""
        expected = filter_with_cached_patterns(text, FILING_HTML)
        assert text == expected, f"{name} differs from the single-call path"
