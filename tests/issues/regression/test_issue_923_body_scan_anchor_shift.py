"""GH #923 part 1 — the body-header scan resolved every item to the previous item's anchor.

Novaworks nests an item's anchor *inside* its heading element::

    <p><b><i><a id="item1a"/>Item</i></b>&#160;<b><i>1A. Risk Factors</i></b></p>

``tree.iter()`` yields the heading before its own descendants, so when the header
matched, the scan's running ``last_anchor_id`` still held the *previous* item's
anchor. Every item resolved one slot late and the whole map shifted: on Foot
Locker's FY2024 10-K ``obj['Item 7']`` returned Item 6's five-year financial data
and the MD&A came back under ``Item 7A``.

The map stayed plausible — every anchor was real, distinct and in document order —
so nothing raised and the stale-anchor guard did not fire. That silence is the
reason this is worth a regression test rather than a fixture refresh.

Reported by g-carmichael, 2026-07-30. Bead edgartools-c9u9.
"""

import re

import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer


def _nested_anchor_header(anchor_id: str, num: str, title: str) -> str:
    """A heading carrying its own anchor inside its first bold span (Novaworks)."""
    return (
        f'<p style="margin: 0pt;"><b><i><a id="{anchor_id}" title="{anchor_id}" '
        f'href="#"/>Item</i></b>&#160;<b><i>{num}. {title}</i></b></p>'
    )


NESTED_ANCHOR_BODY = f"""
<html><body>
<div style="font-weight:700">PART I</div>
{_nested_anchor_header("item1", "1", "Business")}
<p>General. The Company operates athletic footwear stores.</p>
{_nested_anchor_header("item1a", "1A", "Risk Factors")}
<p>Risks Related to Our Business and Industry.</p>
{_nested_anchor_header("item1b", "1B", "Unresolved Staff Comments")}
<p>None.</p>
{_nested_anchor_header("item2", "2", "Properties")}
<p>Our properties consist of land and leased stores.</p>
{_nested_anchor_header("item3", "3", "Legal Proceedings")}
<p>Information regarding legal proceedings.</p>
</body></html>
"""


@pytest.mark.fast
def test_nested_anchor_resolves_to_its_own_item():
    """Each item takes the anchor inside its own heading, not the previous item's.

    Against the pre-fix scan this asserts the exact shift: item1a -> 'item1',
    item1b -> 'item1a', and so on down the filing.
    """
    mapping = TOCAnalyzer(form="10-K")._analyze_body_item_headers(NESTED_ANCHOR_BODY)

    assert mapping["part_i_item_1"] == "item1"
    assert mapping["part_i_item_1a"] == "item1a"
    assert mapping["part_i_item_1b"] == "item1b"
    assert mapping["part_i_item_2"] == "item2"
    assert mapping["part_i_item_3"] == "item3"


@pytest.mark.fast
def test_preceding_anchor_still_wins_when_heading_carries_none():
    """The Goldman/Citi shape — an empty anchor div *before* the heading — is
    unchanged. The nested lookup is a fallback-first refinement, not a
    replacement for the running anchor."""
    html = """
    <html><body>
    <div id="a7"></div><div style="font-weight:700">Item 7. Management's Discussion</div>
    <p>MD&amp;A prose.</p>
    <div id="a7a"></div><div style="font-weight:700">Item 7A. Quantitative Disclosures</div>
    <p>Market risk prose.</p>
    </body></html>
    """
    mapping = TOCAnalyzer(form="10-K")._analyze_body_item_headers(html)

    assert mapping["part_ii_item_7"] == "a7"
    assert mapping["part_ii_item_7a"] == "a7a"


@pytest.mark.fast
def test_inline_xbrl_id_is_not_mistaken_for_an_anchor():
    """A heading that tags an inline-XBRL fact carries a generated ``ix:`` id in
    its subtree. That id is not a navigable anchor, so the scan must ignore it
    and keep the real preceding anchor — on Foot Locker the unguarded lookup
    produced ``part_i_item_2 -> 'c125925000'``."""
    html = """
    <html><body>
    <div id="real_anchor"></div>
    <p style="font-weight:700">Item 1C. <ix:nonnumeric id="c125924990"
       name="cyd:CybersecurityRiskManagementTextBlock">Cybersecurity</ix:nonnumeric></p>
    <p>Cybersecurity risk management prose.</p>
    </body></html>
    """
    mapping = TOCAnalyzer(form="10-K")._analyze_body_item_headers(html)

    assert mapping["part_i_item_1c"] == "real_anchor"


# --- GH #923 part 2 — a glued title initial read as an item suffix -----------
#
# TOC rows split the label and the title across cells (<td>Item 4</td>
# <td>Mine Safety Disclosures</td>) and text_content() joins them with no
# separator, so "Item 4Mine Safety Disclosures" normalized to Item 4M. Foot
# Locker's FY2013 10-K emitted a full set of codes that do not exist in Reg S-K
# — 2P, 3L, 4M, 5M, 6S, 7M, 8C, 10D, 11E, 12S, 13C, 14P, 15E — each letter the
# initial of its own title. Bead edgartools-7g9r.

@pytest.mark.fast
@pytest.mark.parametrize(
    "text, expected",
    [
        # Glued title: the initial is not a suffix.
        ("Item 2Properties", "Item 2"),
        ("Item 4Mine Safety Disclosures", "Item 4"),
        ("Item 10Directors, Executive Officers and Corporate Governance", "Item 10"),
        ("Item 15Exhibits and Financial Statement Schedules", "Item 15"),
        # Real suffixes survive, separated or not.
        ("Item 1A. Risk Factors", "Item 1A"),
        ("Item 1B Unresolved Staff Comments", "Item 1B"),
        ("ITEM 7A. Quantitative and Qualitative Disclosures", "Item 7A"),
        ("Item 1B", "Item 1B"),
        # A genuinely glued suffix keeps its letter — the title's initial is
        # uppercase, so it cannot be confused with a lowercase continuation.
        ("Item 1ARisk Factors", "Item 1A"),
    ],
)
def test_glued_title_initial_is_not_an_item_suffix(text, expected):
    assert TOCAnalyzer._item_label_from_text(text) == expected


@pytest.mark.fast
def test_non_item_text_still_returns_none():
    """The helper must not claim text that does not open with an item label."""
    assert TOCAnalyzer._item_label_from_text("Risk Factors") is None
    assert TOCAnalyzer._item_label_from_text("PART II") is None


@pytest.mark.network
def test_foot_locker_2013_emits_only_valid_item_codes():
    """No item code outside Reg S-K's shape, and no phantom duplicate items."""
    from edgar import find

    items = find("0001144204-14-019510").obj().items

    invalid = [i for i in items if not re.fullmatch(r"Item \d+[A-C]?", i)]
    assert invalid == [], f"item codes that do not exist in Reg S-K: {invalid}"

    # The phantoms doubled up on the real items; each number appears once.
    assert len(items) == len(set(items))
    for phantom in ("Item 2P", "Item 3L", "Item 4M", "Item 8C", "Item 10D", "Item 15E"):
        assert phantom not in items


@pytest.mark.network
def test_foot_locker_items_open_on_their_own_headings():
    """The reported filing: every item must open with its own Item heading.

    Pre-fix, 13 of 18 sections opened on a different item — ``Item 7`` returned
    'Item 6. Selected Financial Data' and Items 2 and 9B were missing entirely.
    """
    from edgar import find

    obj = find("0001437749-25-009620").obj()

    # The two items the shift dropped off the map are back.
    assert "Item 2" in obj.items
    assert "Item 9B" in obj.items

    expected_openings = {
        "Item 1": "Item 1. Business",
        "Item 1A": "Item 1A. Risk Factors",
        "Item 2": "Item 2. Properties",
        "Item 5": "Item 5. Market for the Company",
        "Item 6": "Item 6. Selected Financial Data",
        "Item 7": "Item 7. Management",
        "Item 7A": "Item 7A. Quantitative and Qualitative Disclosures",
        "Item 8": "Item 8. Consolidated Financial Statements",
        "Item 9A": "Item 9A. Controls and Procedures",
    }
    for key, opening in expected_openings.items():
        body = obj[key]
        assert body, f"{key} returned nothing"
        # Filings separate "Item" from its number with a non-breaking space.
        normalized = " ".join(body[:220].replace("\xa0", " ").split())
        # Item 1 shares Part I's anchor in Novaworks filings, so its body opens
        # with the "PART I" divider ahead of the item heading. That is correct,
        # and it is the only place a divider may precede the heading.
        normalized = re.sub(r"^PART [IVX]+\s+", "", normalized)
        assert normalized.startswith(opening), (
            f"{key} opened with {normalized[:70]!r}, expected {opening!r}"
        )
