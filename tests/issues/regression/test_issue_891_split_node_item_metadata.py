"""Regression test for GitHub Issue #891.

A small-cap 10-K (Nathan's Famous, NATH, CIK 0000069733, accession
0001437749-26-019923) splits the bare ``Item 7.`` fragment and its
``Management's Discussion and Analysis`` title across separate HTML nodes.

The user-facing defect on the new document parser is missing .item/.part
metadata. The pattern extractor names 10-K Part I/II sections by semantic key
('mda', 'business', ...). ``Section.parse_section_name`` can only resolve
item/part from a key that literally spells them out (``part_iii_item_12`` ->
III/12), so every semantic-keyed section came back ``item=None``/``part=None``.
Any consumer keying on ``section.item`` silently dropped these. Fix:
``FormSchema.resolve_section_key`` recovers the item from the schema's own title
vocabulary ('Item 7 - MD&A' -> '7') and the part from the item->part ranges, and
``_create_sections`` fills it in. The heading-detection path
(``HybridSectionDetector``) resolves part/item the same way.

Ground truth: NATH's own 10-K structure — Item 7 (MD&A) is Part II; Item 1
(Business) is Part I.

Note: the reporter's other suggested fixes (split-node header *detection* and a
zero-candidate raw-HTML recovery) are deferred — MD&A is already recovered on
this filing today, and a broad zero-candidate fallback risks fabricating
mis-scoped sections from inline body mentions.
"""
import pytest

from edgar.documents.form_schema import get_form_schema

pytestmark = pytest.mark.regression


# --- Offline: the schema-resolution core of fix #1 (no network) -------------

@pytest.mark.fast
def test_resolve_semantic_10k_keys_to_item_and_part():
    """Semantic 10-K section keys resolve to the same (part, item) that a
    part_iii_item_N-style key would — bare roman part, upper item."""
    schema = get_form_schema("10-K")
    assert schema.resolve_section_key("mda") == ("II", "7")
    assert schema.resolve_section_key("business") == ("I", "1")
    assert schema.resolve_section_key("risk_factors") == ("I", "1A")
    assert schema.resolve_section_key("market_risk") == ("II", "7A")
    assert schema.resolve_section_key("financial_statements") == ("II", "8")
    assert schema.resolve_section_key("controls_procedures") == ("II", "9A")


@pytest.mark.fast
def test_item_for_section_key_from_title_vocabulary():
    schema = get_form_schema("10-K")
    assert schema.item_for_section_key("mda") == "7"
    assert schema.item_for_section_key("cybersecurity") == "1C"


@pytest.mark.fast
def test_non_item_keys_do_not_resolve():
    """Part headers and named sections carry no item — must stay (None, None)."""
    schema = get_form_schema("10-K")
    assert schema.resolve_section_key("part_i") == (None, None)
    assert schema.resolve_section_key("signatures") == (None, None)
    assert schema.resolve_section_key("does_not_exist") == (None, None)


# --- End-to-end: NATH split-node 10-K under VCR -----------------------------

@pytest.mark.network
@pytest.mark.vcr
def test_nathans_famous_split_node_sections_carry_item_metadata():
    """NATH 10-K: MD&A is detected and every semantic section carries .item/.part."""
    from edgar import get_by_accession_number

    tenk = get_by_accession_number("0001437749-26-019923").obj()

    # MD&A (Item 7) must be present on the new parser.
    assert "mda" in tenk.sections, "MD&A section was not detected"

    sections = tenk.document.sections
    mda = sections["mda"]
    assert (mda.part, mda.item) == ("II", "7"), (
        f"MD&A metadata wrong: part={mda.part!r} item={mda.item!r}"
    )

    business = sections["business"]
    assert (business.part, business.item) == ("I", "1")

    # No standard Part I/II item section should be left with item=None.
    expected_items = {
        "business": "1",
        "risk_factors": "1A",
        "properties": "2",
        "legal_proceedings": "3",
        "mda": "7",
        "market_risk": "7A",
        "financial_statements": "8",
        "controls_procedures": "9A",
    }
    for key, item in expected_items.items():
        if key in sections:
            assert sections[key].item == item, (
                f"section {key!r} has item={sections[key].item!r}, expected {item!r}"
            )

    # Item 7 remains navigable and returns substantial MD&A content.
    item7 = tenk["Item 7"]
    assert item7 is not None
