"""
Tests for the anchor-to-anchor section slicing primitive
(`edgar.documents.utils.section_slicer`) and the TOC-based `Section.markdown()`
that builds on it.

The slicer centralizes the logic that was previously inlined in
`Section._extract_section_html`. It must:
  - serialize each <table> exactly once (issue #826 — top-level-only),
  - rescue orphaned table-row fragments so table-row-bounded anchors don't
    silently drop content (design sprint, Tension 3 edge case #6),
  - never make `markdown()` worse than `text()` (fallback safety).
"""
from collections import Counter
from pathlib import Path

import hashlib
import lxml.html as lxml_html
import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.utils.section_slicer import (
    build_section_subtree,
    extract_section_html,
    top_level_elements,
    collect_range_elements,
)

NKE_FIXTURE = Path('tests/fixtures/html/nke/10k/nke-10-k-2025-07-17.html')


# ---------------------------------------------------------------------------
# Unit: the slicing primitive on synthetic HTML (fast, no fixtures)
# ---------------------------------------------------------------------------

def test_orphaned_table_rows_are_rescued():
    """Anchors inside a <table> leave bare <tr> fragments; the slicer must
    rewrap them so content survives a parse round-trip (edge case #6).

    Without the wrap, `lxml.html.fromstring` drops a bare <tr> and the rows
    vanish — a silent data-loss bug.
    """
    html = """
    <html><body><table><tbody>
      <tr id="start"><td>heading row</td></tr>
      <tr><td>data 1</td></tr>
      <tr><td>data 2</td></tr>
      <tr id="end"><td>next section</td></tr>
    </tbody></table></body></html>
    """
    tree = lxml_html.fromstring(html)
    out = extract_section_html(tree, "start", "end")

    reparsed = lxml_html.fromstring(out)
    cells = [t.strip() for t in reparsed.xpath('.//td/text()')]
    assert cells == ['heading row', 'data 1', 'data 2']  # ground truth
    assert 'next section' not in cells  # end anchor excluded
    assert len(reparsed.xpath('.//table')) == 1


def test_nested_tables_not_duplicated():
    """Each <table> appears exactly once even when nested under collected
    ancestors (issue #826)."""
    html = """
    <html><body>
      <a id="s1"></a>
      <div>
        <div><table><tr><td>T1</td></tr></table></div>
        <div><table><tr><td>T2</td></tr></table></div>
      </div>
      <a id="s2"></a>
      <table><tr><td>T3-next</td></tr></table>
    </body></html>
    """
    tree = lxml_html.fromstring(html)
    out = extract_section_html(tree, "s1", "s2")
    reparsed = lxml_html.fromstring(out)

    cells = [t.strip() for t in reparsed.xpath('.//td/text()')]
    assert cells == ['T1', 'T2']  # exactly once each, T3 (next section) excluded
    assert len(reparsed.xpath('.//table')) == 2


def test_missing_start_anchor_returns_empty():
    """Silence check: an unresolvable start anchor returns '' rather than
    raising or fabricating content."""
    tree = lxml_html.fromstring("<html><body><p>x</p></body></html>")
    assert extract_section_html(tree, "does-not-exist", None) == ""
    assert build_section_subtree(tree, "does-not-exist", None) is None


def test_same_anchor_boundary_is_guarded():
    """A start==end boundary must not collect zero content silently; the end
    anchor is dropped so the section runs to the document end (edge case #3)."""
    html = '<html><body><a id="a"></a><p>after</p></body></html>'
    tree = lxml_html.fromstring(html)
    out = extract_section_html(tree, "a", "a")
    assert "after" in out


def test_top_level_elements_drops_nested():
    """`top_level_elements` keeps only elements whose parent isn't collected."""
    tree = lxml_html.fromstring(
        '<html><body><a id="s"></a><div><span>x</span></div><p>y</p>'
        '<a id="e"></a></body></html>'
    )
    collected = collect_range_elements(tree, "s", "e")
    top = top_level_elements(collected)
    tags = [e.tag for e in top]
    # div and p are top-level; the span nested in div is not
    assert 'div' in tags and 'p' in tags and 'span' not in tags


# ---------------------------------------------------------------------------
# Integration: real filing fixture (offline)
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def nke_sections():
    if not NKE_FIXTURE.exists():
        pytest.skip("NKE 10-K fixture not available")
    doc = HTMLParser(ParserConfig(form='10-K', detect_sections=True)).parse(NKE_FIXTURE.read_text())
    return doc.sections


def test_nke_item8_tables_no_duplication(nke_sections):
    """Ground truth: NKE 10-K Item 8 has 60 unique tables, each returned once.

    Verified by hand against the fixture; guards the #826 fix through the new
    primitive.
    """
    section = nke_sections["part_ii_item_8"]
    tables = section.tables()

    def _html(t):
        h = t.html
        return h() if callable(h) else h

    counts = Counter(hashlib.sha1(_html(t).encode("utf-8")).hexdigest() for t in tables)
    assert len(tables) == 60
    assert len(counts) == 60
    assert max(counts.values()) == 1


def test_nke_item1_markdown_preserves_tables(nke_sections):
    """`Section.markdown()` on a TOC section renders pipe-format tables rather
    than flattening them to text (edgartools-4j6f).

    Ground truth: NKE Item 1 contains the U.S. retail-store-count table; its
    markdown must contain that table in pipe format.
    """
    section = nke_sections["part_i_item_1"]
    assert section.detection_method == 'toc'

    md = section.markdown()
    text = section.text()

    # Pipe-format tables are present and markdown differs from flat text.
    assert md.count('|') > 10
    assert md.strip() != text.strip()
    # A known table cell from NKE Item 1 survives into the markdown table.
    assert 'NIKE Brand factory stores' in md


def test_markdown_never_worse_than_text(nke_sections):
    """Markdown fallback safety: every TOC section's markdown is non-empty
    whenever its text is non-empty."""
    for name, section in nke_sections.items():
        if section.detection_method != 'toc':
            continue
        text = section.text()
        if text and text.strip():
            assert section.markdown().strip(), f"{name}: markdown empty but text present"
