"""Anchor indexing and document-order traversal (edgartools-llmp.7 / llmp.8).

Both changes are pure performance work whose whole value depends on producing
*identical* results to what they replace, so these tests assert equivalence
against the original implementations rather than against hand-written
expectations:

  * ``find_anchor_targets`` must return the same elements, in the same order, as
    the full-document XPath ``//*[@id=$a or (self::a and @name=$a)]``.
  * ``iterwalk_from`` must yield the same ``(event, element)`` sequence as
    ``etree.iterwalk`` from the document root, from the start element onward —
    ancestor ``end`` events included, since those carry paragraph breaks and
    tail text.
"""
import pytest
from lxml import etree
from lxml import html as lxml_html

from edgar.documents.utils.anchor_targets import (
    find_anchor_targets,
    invalidate_anchor_index,
    is_anchor_match,
)
from edgar.documents.utils.tree_traversal import (
    document_order_path,
    iterwalk_from,
    precedes,
)

# Fully offline: every test parses an inline HTML string with lxml and touches
# no filesystem or network. Marked explicitly rather than by filename so the
# collection gate in conftest can place the file in a CI job.
pytestmark = pytest.mark.fast

XPATH = '//*[@id=$anchor_id or (self::a and @name=$anchor_id)]'

# Exercises every branch the index has to mirror: plain id, <a name>, an <a>
# carrying id and name with the SAME value (must not be listed twice), an <a>
# whose id and name DIFFER (must be reachable under both), a duplicate id
# (document order matters), a non-anchor `name` (must be ignored), nesting, and
# a comment (which `//*` excludes but `iter()` yields).
SAMPLE = """
<html><body>
  <div id="top">top text
    <a name="alpha"></a>
    <p id="dup">first dup</p>
    <!-- a comment -->
    <a id="both" name="both">same value</a>
    <a id="idx" name="namex">different values</a>
    <input name="notananchor"/>
    <span id="nested"><b id="deep">deep</b></span>
  </div>
  <div id="second">
    <p id="dup">second dup</p>
  </div>
</body></html>
"""


def _tree():
    return lxml_html.fromstring(SAMPLE)


class TestAnchorIndexMatchesXPath:

    def test_every_id_and_name_resolves_identically(self):
        tree = _tree()
        ids = ["top", "alpha", "dup", "both", "idx", "namex", "nested",
               "deep", "second", "notananchor", "missing", ""]

        for anchor_id in ids:
            expected = tree.xpath(XPATH, anchor_id=anchor_id) if anchor_id else []
            got = find_anchor_targets(tree, anchor_id)
            assert len(got) == len(expected), f"{anchor_id!r}: {len(got)} vs {len(expected)}"
            assert all(g is e for g, e in zip(got, expected, strict=True)), \
                f"{anchor_id!r}: different elements or order"

    def test_element_with_matching_id_and_name_is_returned_once(self):
        """The XPath's `or` matches such an element once; a naive index lists it twice."""
        tree = _tree()

        assert len(find_anchor_targets(tree, "both")) == 1

    def test_anchor_reachable_under_both_id_and_name_when_they_differ(self):
        tree = _tree()

        by_id = find_anchor_targets(tree, "idx")
        by_name = find_anchor_targets(tree, "namex")

        assert len(by_id) == 1 and len(by_name) == 1
        assert by_id[0] is by_name[0]

    def test_name_on_non_anchor_element_is_not_a_target(self):
        """`self::a and @name` — only <a> elements match by name."""
        tree = _tree()

        assert find_anchor_targets(tree, "notananchor") == []

    def test_duplicate_ids_come_back_in_document_order(self):
        tree = _tree()

        got = find_anchor_targets(tree, "dup")

        assert [e.text for e in got] == ["first dup", "second dup"]

    def test_result_is_a_copy_so_callers_cannot_corrupt_the_cache(self):
        tree = _tree()

        first = find_anchor_targets(tree, "dup")
        first.clear()

        assert len(find_anchor_targets(tree, "dup")) == 2

    def test_repeated_lookups_are_stable(self):
        """The second lookup is served from the cache; it must not differ."""
        tree = _tree()

        a = find_anchor_targets(tree, "nested")
        b = find_anchor_targets(tree, "nested")

        assert a[0] is b[0]

    def test_invalidate_forces_a_rebuild(self):
        tree = _tree()
        find_anchor_targets(tree, "top")

        invalidate_anchor_index(tree)

        assert find_anchor_targets(tree, "top")[0] is tree.xpath(XPATH, anchor_id="top")[0]

    def test_index_is_built_from_the_document_root_not_the_subtree(self):
        """`//*` is absolute: called on a subtree element it still searches the
        whole document. An index built by walking that subtree would resolve
        fewer anchors."""
        tree = _tree()
        subtree = tree.xpath('//div[@id="second"]')[0]

        # "top" lives outside `subtree`, but the XPath finds it from there.
        assert len(subtree.xpath(XPATH, anchor_id="top")) == 1
        assert len(find_anchor_targets(subtree, "top")) == 1

    def test_separate_trees_do_not_share_an_index(self):
        one, two = _tree(), lxml_html.fromstring("<html><body><p id='top'>other</p></body></html>")

        assert find_anchor_targets(one, "top")[0].get("id") == "top"
        assert find_anchor_targets(two, "top")[0].text == "other"
        assert find_anchor_targets(two, "alpha") == []


class TestIsAnchorMatchUnchanged:

    def test_matches_by_id_and_by_anchor_name_only(self):
        tree = _tree()
        a_named = tree.xpath('//a[@name="alpha"]')[0]
        not_anchor = tree.xpath('//input')[0]

        assert is_anchor_match(a_named, "alpha") is True
        assert is_anchor_match(not_anchor, "notananchor") is False
        assert is_anchor_match(a_named, "") is False


class TestIterwalkFromMatchesRootWalk:

    def test_sequence_is_the_tail_of_the_root_walk(self):
        tree = _tree()
        full = list(etree.iterwalk(tree, events=('start', 'end')))

        for index, (event, element) in enumerate(full):
            if event != 'start':
                continue
            expected = full[index:]
            got = list(iterwalk_from(element))

            assert len(got) == len(expected), f"at {element.tag}: {len(got)} vs {len(expected)}"
            assert all(g[0] == e[0] and g[1] is e[1] for g, e in zip(got, expected, strict=True)), \
                f"diverged starting at {element.tag}"

    def test_ancestor_end_events_are_emitted(self):
        """The reason a subtree walk is not a substitute: content after a deep
        start element includes its ancestors' `end` events, which carry the
        block-level paragraph breaks and tail text."""
        tree = _tree()
        deep = tree.xpath('//b[@id="deep"]')[0]

        events = list(iterwalk_from(deep))
        ended = [el.get('id') for ev, el in events if ev == 'end']

        # Its own end, then the ancestors it sits inside, outermost last.
        assert 'deep' in ended
        assert 'nested' in ended
        assert 'top' in ended
        assert ended.index('nested') < ended.index('top')

    def test_following_siblings_are_included(self):
        tree = _tree()
        top = tree.xpath('//div[@id="top"]')[0]

        seen = {el.get('id') for ev, el in iterwalk_from(top) if ev == 'start'}

        assert 'second' in seen, "the sibling div after the start element was skipped"

    def test_starting_at_the_last_element_terminates(self):
        tree = _tree()
        last = tree.xpath('//div[@id="second"]/p')[0]

        events = list(iterwalk_from(last))

        assert events[0] == ('start', last)
        assert any(ev == 'end' and el is last for ev, el in events)


class TestDocumentOrder:

    def test_precedes_follows_document_order(self):
        tree = _tree()
        order = [el for el in tree.iter() if isinstance(el.tag, str)]

        for earlier, later in zip(order, order[1:], strict=False):
            assert precedes(earlier, later) is True
            assert precedes(later, earlier) is False

    def test_an_element_does_not_precede_itself(self):
        tree = _tree()
        el = tree.xpath('//*[@id="both"]')[0]

        assert precedes(el, el) is False

    def test_path_is_rooted_and_ordered(self):
        tree = _tree()
        top = tree.xpath('//div[@id="top"]')[0]
        second = tree.xpath('//div[@id="second"]')[0]

        assert document_order_path(top) < document_order_path(second)
        assert document_order_path(tree) == []
