"""Regression tests for edgartools-4q74 — section boundaries follow document order.

A section ends where the next section physically begins. The extractor used to
end each section at the next *item number* instead, which is a different thing:
item numbering is what a filer calls its sections, document order is where it
put them.

Morgan Stanley's FY2024 10-K is the case that separates the two. It groups
Items 1B/2/3/4/5 behind the financial statements, so its physical layout is

    1, 1A, 1C, 7, 7A, 8, 9, 9A, 9B, 9C, 1B, 2, 3, 4, 5, 10 … 15, Signatures

Ending at the next item number failed in both directions at once:

  * Item 1A ran from Risk Factors to Item 1B's anchor near the back of the
    filing — 673,015 chars, with MD&A, the financial statements and the controls
    items all filed under Risk Factors, at confidence 0.95 and no warning. Item
    1C (a two-line cross-reference) was 600,239 chars for the same reason.
  * Item 1B's end resolved 75,978 elements *before* its own start. An inverted
    pair yields nothing, so Item 1B and Item 5 were simply absent from
    ``document.sections``.

The over-capture is the more dangerous half — it is wrong text that reads as
right. That is why the invariant test below asserts both directions.

This is ordinary layout, not a malformed filing. ODP's 10-K puts Item 8 after
the signature page, where the F-pages conventionally live, so ``signatures``
was absorbing 188,606 chars of financial statements. The synthetic tests cover
that shape, since no ODP fixture is tracked.

Offline: the Morgan Stanley 10-K is a tracked fixture; the rest is inline HTML.
"""
from pathlib import Path

import pytest
from lxml import html as lxml_html

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.utils.anchor_targets import find_anchor_targets
from edgar.documents.utils.tree_traversal import precedes

pytestmark = pytest.mark.fast

MS_10K = Path(__file__).parents[2] / "fixtures" / "html" / "ms" / "10k" / "ms-10-k-2025-02-21.html"


@pytest.fixture(scope="module")
def ms_doc():
    assert MS_10K.exists(), f"committed Morgan Stanley 10-K fixture is missing: {MS_10K}"
    doc = parse_html(MS_10K.read_bytes().decode("utf-8", "replace"), ParserConfig(form="10-K"))
    yield doc
    del doc


def _text(doc, key):
    section = doc.sections.get(key)
    return "" if section is None else (section.text() or "")


class TestMorganStanleyTrailingItems:
    """The four sections the inverted boundaries silenced, and the two they flooded."""

    def test_item_1b_is_a_paragraph_not_absent(self, ms_doc):
        # Was absent entirely (inverted pair). The naive repair — ignore the
        # inverted end and run on — produced 26,330 chars ending in the
        # signature block, so the size is as load-bearing as the presence.
        text = _text(ms_doc, "part_i_item_1b")
        assert text, "Item 1B silently produced nothing"
        assert text.startswith("Unresolved Staff Comments")
        assert "written comments from the staff of the SEC" in text
        assert len(text) < 1000, f"Item 1B is one paragraph, got {len(text)} chars"

    def test_item_5_is_bounded_by_item_10(self, ms_doc):
        text = _text(ms_doc, "part_ii_item_5")
        assert text, "Item 5 silently produced nothing"
        assert text.startswith("Market for Registrant")
        assert "Issuer Purchases of Equity Securities" in text
        # Item 5 physically precedes Part III Item 10, which is where it must stop.
        assert "Directors, Executive Officers and Corporate Governance" not in text
        assert 2000 < len(text) < 6000, f"unexpected Item 5 size: {len(text)}"

    def test_item_1a_stops_at_the_next_physical_section(self, ms_doc):
        # 673,015 chars before the fix: everything from Risk Factors to the back
        # of the filing, indistinguishable from a correct extraction to a caller.
        text = _text(ms_doc, "part_i_item_1a")
        assert "Risk Factors" in text[:200]
        assert len(text) < 150_000, f"Item 1A over-captured: {len(text)} chars"
        for foreign in ("Unresolved Staff Comments",
                        "Report of Independent Registered Public Accounting Firm",
                        "Mine Safety Disclosures"):
            assert foreign not in text, f"Item 1A absorbed {foreign!r}"

    def test_item_1c_is_the_cybersecurity_cross_reference(self, ms_doc):
        # 600,239 chars before the fix; the filer defers the whole discussion.
        text = " ".join(_text(ms_doc, "part_i_item_1c").split())
        assert text.endswith(
            "Cybersecurity For a discussion of cybersecurity, see "
            "“Quantitative and Qualitative Disclosures about Risk— "
            "Operational Risk— Cybersecurity.”"
        ), text

    def test_item_9c_does_not_absorb_item_5(self, ms_doc):
        # Item 9C is followed physically by Item 1B, not by Item 10, so it used
        # to run through the trailing items and swallow Item 5's performance
        # graph.
        text = " ".join(_text(ms_doc, "part_ii_item_9c").split())
        assert text == ("Disclosure Regarding Foreign Jurisdictions That Prevent "
                        "Inspections Not applicable."), text


class TestBoundaryInvariant:
    """No boundary pair may be inverted, and none may run past its successor."""

    def test_no_inverted_boundaries(self, ms_doc):
        extractor = ms_doc._get_section_extractor()
        tree = extractor._tree
        inverted = []
        for name, boundary in extractor.section_boundaries.items():
            if not boundary.end_element_id:
                continue
            start = find_anchor_targets(tree, boundary.anchor_id)
            end = find_anchor_targets(tree, boundary.end_element_id)
            if start and end and precedes(end[0], start[0]):
                inverted.append(name)
        assert not inverted, f"end anchor precedes start anchor for: {inverted}"

    def test_sections_do_not_overlap(self, ms_doc):
        """Each section's end is the next section's start, in document order."""
        extractor = ms_doc._get_section_extractor()
        tree = extractor._tree
        order = {}
        for pos, element in enumerate(tree.iter()):
            order[element.get("id")] = pos
        spans = []
        for name, boundary in extractor.section_boundaries.items():
            start = order.get(boundary.anchor_id)
            end = order.get(boundary.end_element_id) if boundary.end_element_id else None
            if start is not None:
                spans.append((start, end, name))
        spans.sort()
        for (start, end, name), (next_start, _, next_name) in zip(spans, spans[1:]):
            assert end is not None, f"{name} runs to end-of-document but {next_name} follows it"
            assert end <= next_start, (
                f"{name} ends at {end}, past {next_name} which starts at {next_start}")


# Item numbering deliberately disagrees with physical placement: Item 8 sits
# after the signature page (the ODP shape), and Item 1B sits between Item 9 and
# Item 2 (the Morgan Stanley shape).
OUT_OF_ORDER_HTML = """
<html><body>
<div><a href="#a1">Item 1. Business</a><a href="#a1a">Item 1A. Risk Factors</a>
<a href="#a1b">Item 1B. Unresolved Staff Comments</a><a href="#a2">Item 2. Properties</a>
<a href="#a8">Item 8. Financial Statements</a><a href="#a9">Item 9. Changes in Accountants</a>
<a href="#sig">Signatures</a></div>
<div id="a1"><p>Item 1. Business</p><p>BUSINESS_BODY</p></div>
<div id="a1a"><p>Item 1A. Risk Factors</p><p>RISK_BODY</p></div>
<div id="a9"><p>Item 9. Changes in Accountants</p><p>ACCOUNTANTS_BODY</p></div>
<div id="a1b"><p>Item 1B. Unresolved Staff Comments</p><p>STAFF_BODY</p></div>
<div id="a2"><p>Item 2. Properties</p><p>PROPERTIES_BODY</p></div>
<div id="sig"><p>Signatures</p><p>SIGNATURES_BODY</p></div>
<div id="a8"><p>Item 8. Financial Statements</p><p>STATEMENTS_BODY</p></div>
</body></html>
"""


class TestOutOfOrderLayoutSynthetic:
    """The general rule, without depending on any one filer's fixture."""

    @pytest.fixture(scope="class")
    def doc(self):
        return parse_html(OUT_OF_ORDER_HTML, ParserConfig(form="10-K"))

    @pytest.mark.parametrize("key, own, foreign", [
        ("part_i_item_1a", "RISK_BODY", "ACCOUNTANTS_BODY"),
        ("part_ii_item_9", "ACCOUNTANTS_BODY", "STAFF_BODY"),
        ("part_i_item_1b", "STAFF_BODY", "PROPERTIES_BODY"),
        ("part_i_item_2", "PROPERTIES_BODY", "SIGNATURES_BODY"),
    ])
    def test_section_stops_at_its_physical_successor(self, doc, key, own, foreign):
        section = doc.sections.get(key)
        assert section is not None, f"{key} was not extracted"
        text = section.text() or ""
        assert own in text
        assert foreign not in text, f"{key} ran past its physical successor"

    def test_trailing_financial_statements_are_not_filed_under_signatures(self, doc):
        """The ODP shape: Item 8 physically follows the signature page."""
        signatures = doc.sections.get("signatures") or doc.sections.get("part_iv_signatures")
        if signatures is not None:
            assert "STATEMENTS_BODY" not in (signatures.text() or "")
        item_8 = doc.sections.get("part_ii_item_8")
        assert item_8 is not None and "STATEMENTS_BODY" in (item_8.text() or "")


SHARED_ANCHOR_HTML = """
<html><body>
<div><a href="#s1">Item 1B. Unresolved Staff Comments</a>
<a href="#s1">Item 1C. Cybersecurity</a><a href="#s2">Item 2. Properties</a></div>
<div id="s1"><p>Item 1B. Unresolved Staff Comments</p><p>None.</p>
<p>Item 1C. Cybersecurity</p><p>CYBER_BODY</p></div>
<div id="s2"><p>Item 2. Properties</p><p>PROPERTIES_BODY</p></div>
</body></html>
"""


def test_shared_anchor_still_ends_at_the_next_distinct_anchor():
    """GH #904: adjacent items sharing one anchor must not end on themselves.

    Sections sharing an anchor also share a document position, so the scan past
    equal anchors has to survive the switch from item order to document order —
    an end equal to the start is an empty span the slicer treats as unbounded,
    and the section ran to end-of-document.
    """
    doc = parse_html(SHARED_ANCHOR_HTML, ParserConfig(form="10-K"))
    extractor = doc._get_section_extractor()
    for key in ("part_i_item_1b", "part_i_item_1c"):
        boundary = extractor.section_boundaries.get(key)
        if boundary is None:
            continue
        assert boundary.end_element_id != boundary.anchor_id, (
            f"{key} ends on its own anchor")


def test_document_order_survives_a_tree_with_no_ids():
    """A section anchored by <a name> resolves in document order like any other."""
    html = """
    <html><body>
    <div><a href="#n1">Item 1. Business</a><a href="#n2">Item 2. Properties</a></div>
    <div><a name="n1"></a><p>Item 1. Business</p><p>BUSINESS_BODY</p></div>
    <div><a name="n2"></a><p>Item 2. Properties</p><p>PROPERTIES_BODY</p></div>
    </body></html>
    """
    doc = parse_html(html, ParserConfig(form="10-K"))
    item_1 = doc.sections.get("part_i_item_1")
    assert item_1 is not None
    text = item_1.text() or ""
    assert "BUSINESS_BODY" in text
    assert "PROPERTIES_BODY" not in text


def test_precedes_orders_elements_across_containers():
    tree = lxml_html.fromstring(
        "<html><body><div><p id='a'>A</p></div><div><p id='b'>B</p></div></body></html>")
    a = tree.xpath("//*[@id='a']")[0]
    b = tree.xpath("//*[@id='b']")[0]
    assert precedes(a, b)
    assert not precedes(b, a)
    assert not precedes(a, a)
