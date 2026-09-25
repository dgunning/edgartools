"""
Anchor-to-anchor HTML slicing for TOC-detected sections.

TOC-detected sections carry no node tree — their content lives in the
original filing HTML, bounded by a *start anchor* (the section's own TOC
target) and an *end anchor* (the next section's target). Turning that
anchor pair into a clean, well-formed HTML subtree is the single
primitive that three features depend on:

  - ``Section.tables()``     — needs each ``<table>`` exactly once (issue #826)
  - ``Section.markdown()``   — needs a parseable subtree to render structure
                               (edgartools-4j6f; currently falls back to text)
  - 40-F section extraction  — same slicing need (edgartools-8zqq)

Before this module each feature re-derived a partial slice and hit a
different subset of the known edge cases. This centralizes the algorithm.

Algorithm
---------
1. Resolve the start element (and end element, if any) via id/name anchor.
2. Walk the tree in document order. Turn collection ON at the start anchor,
   OFF at the end anchor. Collect every element seen while ON.
3. Reduce to *top-level* collected elements — those whose parent is not
   itself collected. ``lxml.tostring`` already emits an element's full
   subtree, so serializing a nested descendant in addition to its ancestor
   would emit the descendant (and any ``<table>`` under it) more than once.
   This is the issue #826 fix.
4. Repair orphaned table fragments. When the start/end anchors sit inside a
   table, the top-level collected elements can be bare ``<tr>``/``<td>``/
   ``<tbody>`` fragments. ``lxml.html.fromstring`` silently drops a bare
   ``<tr>`` (it isn't valid outside a table), losing the row's content and
   any tables inside it. We wrap each run of consecutive table-internal
   fragments in a minimal ``<table><tbody>…`` so the content survives a
   round-trip through the parser.
5. Wrap the (repaired) top-level elements in a single synthetic ``<div>``
   so callers get one well-formed root to parse or render.

Edge cases (from the design sprint, Tension 3)
----------------------------------------------
Fully handled here:
  (6) table-row-bounded anchors losing ``<table>``/``<tbody>`` wrappers
      → step 4 reconstructs the wrappers.
  (7) nested-table re-serialization → step 3 (top-level-only).
  (1) next-section heading leak via nested anchors, (2) shared-wrapper
      LCA, (5) last-section-in-wrapper leak → when the end anchor (or hard
      end element) sits inside an element already collected, that element
      is replaced by a copy truncated at the end (``_truncate_at``), so the
      HTML stops where ``text()`` stops. Before this, the container was
      serialized whole and the next section's heading and body leaked into
      ``markdown()`` (GH #1345).

Mitigated (no worse than ``text()``, the prior behaviour):
  (4) inline anchor wrappers.

Not applicable:
  (3) same-anchor boundaries (start == end) → callers must not pass an end
      anchor equal to the start anchor; ``SECSectionExtractor`` orders
      sections so the next section's anchor differs. Guarded defensively.
"""

from __future__ import annotations

import copy
from typing import List, Optional

import lxml.html as lxml_html
from lxml import etree

from edgar.documents.utils.anchor_targets import find_anchor_targets, is_anchor_match

# Tags that are only valid *inside* a <table>. A bare one of these is an
# orphaned fragment that lxml.html.fromstring would drop.
_TABLE_INTERNAL_TAGS = {
    'tr', 'td', 'th', 'tbody', 'thead', 'tfoot', 'caption', 'col', 'colgroup',
}


def collect_range_elements(tree, start_anchor: str, end_anchor: Optional[str],
                           start_element=None, end_element=None) -> List:
    """Collect elements in document order between the start and end anchors.

    Collection turns on *after* the start anchor element and off *at* the
    end anchor element (the end anchor's content is excluded). Returns the
    raw list of every element seen while in range — callers typically reduce
    this to top-level elements via :func:`top_level_elements`.

    ``start_element`` / ``end_element`` are optional hard bounds for items that
    share one anchor and are told apart by their heading elements (GH #1345):
    collection starts *at* ``start_element`` (included) instead of after the
    anchor, and stops at ``end_element`` or the end anchor, whichever comes
    first.
    """
    if not start_anchor:
        return []
    # Defensive: a same-anchor boundary would collect nothing meaningful.
    if end_anchor and end_anchor == start_anchor:
        end_anchor = None

    collected: List = []
    in_range = False
    for _event, el in etree.iterwalk(tree, events=('start',)):
        if not hasattr(el, 'get'):
            continue
        if start_element is not None:
            if el is start_element:
                in_range = True
        elif is_anchor_match(el, start_anchor):
            in_range = True
            continue
        if ((in_range and end_element is not None and el is end_element)
                or (end_anchor and is_anchor_match(el, end_anchor))):
            collected = _truncate_at(collected, el)
            break
        if in_range:
            collected.append(el)
    return collected


def _truncated_clone(el, stop, stop_path: List):
    """Copy of ``el`` holding only what precedes ``stop`` in document order.

    ``stop_path`` is ``stop``'s ancestor chain. Children before the one that
    leads to ``stop`` are deep-copied whole (tails included); that one is
    truncated recursively, and nothing after it is kept.
    """
    clone = etree.Element(el.tag, attrib=dict(el.attrib))
    clone.text = el.text
    for child in el:
        if child is stop:
            break
        if any(child is a for a in stop_path):
            clone.append(_truncated_clone(child, stop, stop_path))
            break
        clone.append(_clone(child))
    return clone


def _truncate_at(collected: List, stop) -> List:
    """Cut the collected range at ``stop`` when a collected element contains it.

    Collection stops at ``stop``, but an element that *contains* it was
    collected when its start was seen, and :func:`top_level_elements` would
    then serialize it whole: ``stop`` and everything after it leak into the
    section's HTML (the next item's heading in ``markdown()``). Replace the
    outermost such container with a copy truncated at ``stop`` and drop its
    collected descendants, which the copy already holds (GH #1345).
    """
    stop_path = list(stop.iterancestors())
    # Outermost ancestor first: the first one found in the range is the
    # container to cut. ``in`` on lxml elements compares identity.
    outer_idx = next((collected.index(a) for a in reversed(stop_path) if a in collected), None)
    if outer_idx is None:
        return collected
    # Everything collected after the container started lies inside it (the
    # walk stopped at ``stop``, which is still inside it), so the truncated
    # copy replaces that whole tail of the list.
    return collected[:outer_idx] + [_truncated_clone(collected[outer_idx], stop, stop_path)]


def top_level_elements(collected: List) -> List:
    """Reduce collected elements to those whose parent is not also collected.

    ``id()``-based membership is safe: ``collected`` holds a live reference
    to every proxy, so lxml returns the same proxy (same id) for
    ``getparent()`` of a collected element. Document order is preserved.
    """
    collected_ids = {id(e) for e in collected}
    return [e for e in collected if id(e.getparent()) not in collected_ids]


def _repair_table_fragments(elements: List) -> List:
    """Wrap runs of orphaned table-internal fragments in minimal tables.

    Returns a list of lxml elements (some original, some newly-built table
    wrappers) ready to be appended under a single container.
    """
    repaired: List = []
    run: List = []

    def flush_run():
        if not run:
            return
        table = etree.Element('table')
        tbody = etree.SubElement(table, 'tbody')
        for frag in run:
            tag = frag.tag if isinstance(frag.tag, str) else ''
            if tag in ('thead', 'tbody', 'tfoot'):
                # Section grouping element — append directly to the table,
                # not inside our synthetic tbody.
                table.append(_clone(frag))
            elif tag in ('td', 'th'):
                # A bare cell needs a row wrapper.
                tr = etree.SubElement(tbody, 'tr')
                tr.append(_clone(frag))
            else:
                tbody.append(_clone(frag))
        repaired.append(table)
        run.clear()

    for el in elements:
        tag = el.tag if isinstance(el.tag, str) else ''
        if tag in _TABLE_INTERNAL_TAGS:
            run.append(el)
        else:
            flush_run()
            repaired.append(el)
    flush_run()
    return repaired


def _clone(el):
    """Deep-copy an lxml element so re-parenting it can't mutate the source tree.

    Uses ``copy.deepcopy`` rather than a serialize/re-parse round-trip so HTML
    void elements (``<br>``, ``<img>``, ...) survive — the XML parser would
    reject them as unbalanced tags.
    """
    return copy.deepcopy(el)


def build_section_subtree(tree, start_anchor: str, end_anchor: Optional[str],
                          start_element=None, end_element=None):
    """Build a single ``<div>`` element holding the section's content.

    The returned element is detached from the source tree (its children are
    clones), so callers may render or further parse it freely. Returns
    ``None`` if the start anchor can't be resolved or the range is empty.
    """
    start_elements = find_anchor_targets(tree, start_anchor)
    if not start_elements:
        return None

    collected = collect_range_elements(tree, start_anchor, end_anchor,
                                       start_element=start_element, end_element=end_element)
    if not collected:
        return None

    top_level = top_level_elements(collected)
    if not top_level:
        return None

    repaired = _repair_table_fragments(top_level)

    container = etree.Element('div')
    for el in repaired:
        # Table fragments were already cloned in _repair_table_fragments;
        # everything else needs cloning before re-parenting.
        tag = el.tag if isinstance(el.tag, str) else ''
        if tag == 'table' and el.getparent() is None:
            container.append(el)  # freshly built, already detached
        else:
            container.append(_clone(el))
    return container


def extract_section_html(tree, start_anchor: str, end_anchor: Optional[str],
                         start_element=None, end_element=None) -> str:
    """Return the section's HTML as a single well-formed ``<div>`` string.

    This is the hardened replacement for the inline slicing that lived in
    ``Section._extract_section_html``. Returns ``""`` when the section can't
    be resolved.
    """
    container = build_section_subtree(tree, start_anchor, end_anchor,
                                      start_element=start_element, end_element=end_element)
    if container is None:
        return ""
    return lxml_html.tostring(container, encoding='unicode')
