"""
Regression tests for edgartools-0c1q.15 (cluster C): footnote resolution.

Three defects in one function, `InstanceParser._extract_footnotes`:

  .1  gh #1169 — a footnoteArc's `xlink:from` names a `link:loc` label, which
      must be dereferenced through the locator's `xlink:href` to reach the fact.
      edgartools used the LOCATOR LABEL as the fact id, so the relationship was
      lost silently: the footnote parsed fine and carried ids no fact has.
  .7  gh #1230 — footnote text was taken from descendant `<div>`s only when any
      existed, dropping direct-child and sibling text, and `findall('.//div')`
      returns nested divs as well as their ancestors while `itertext()` already
      descends, so nested text was captured twice. No separator was inserted
      between blocks, so what survived ran together.
  05gk gh #1190 — resources were keyed document-globally on `xlink:label`, but a
      footnoteArc resolves within its own `link:footnoteLink`, so two extended
      links may legitimately reuse a label. This one is MISATTRIBUTION rather
      than loss: a caller gets a real footnote belonging to a different fact.

Ground truth comes from checked-in fixtures, so these run offline.

Coverage note, recorded deliberately: 18,686 of the 18,699 footnote locators in
the fixture corpus have `xlink:label` equal to their href fragment, so the
locator indirection resolves BY COINCIDENCE almost everywhere. The 13 that do
not are all in Coca-Cola FY2011 and JPMorgan FY2012, which is why those two
carry `.1`. No fixture reuses a footnote label across two footnoteLinks, so
05gk is covered synthetically only.
"""

from pathlib import Path

import pytest

from edgar.xbrl.parsers import XBRLParser
from edgar.xbrl.xbrl import XBRL

KO_DIR = Path("tests/fixtures/xbrl/ko/10k_2012")        # KO FY2011 10-K
JPM_DIR = Path("tests/fixtures/xbrl/jpm/10k_2013")      # JPM FY2012 10-K
MSFT_DIR = Path("tests/fixtures/xbrl/msft/10k_2015")    # label == fragment
UNP_DIR = Path("tests/fixtures/xbrl/unp")               # six footnoteLinks
GBDC_DIR = Path("tests/fixtures/xbrl/gbdc")             # nested XHTML divs

# Coca-Cola's six locators all suffix the fact id with "_lbl"; the fact ids
# themselves are present in the instance.
KO_FACT_IDS = {
    "Fact-983ED02C9F7A424EBE815702548224C3",
    "Fact-DC0D970779F23CD66F815702815A064C",
    "Fact-86429A7BAD952E9BEEF15702548C63C8",
    "Fact-B1E8C3391B4ECFDC604F57028150F60C",
    "Fact-DA3F8C6E02ACD7C17168570254780E5A",
    "Fact-EF50158421312F1197F157028150BDF8",
}
KO_FOOTNOTE = "Footnote-C21AF6E6239A85C179A2D2B1F6BACC3B_lbl"


@pytest.fixture(scope="module")
def ko():
    return XBRL.from_directory(KO_DIR)


@pytest.fixture(scope="module")
def jpm():
    return XBRL.from_directory(JPM_DIR)


@pytest.fixture(scope="module")
def msft():
    return XBRL.from_directory(MSFT_DIR)


@pytest.fixture(scope="module")
def unp():
    return XBRL.from_directory(UNP_DIR)


@pytest.fixture(scope="module")
def gbdc():
    return XBRL.from_directory(GBDC_DIR)


def _instance(*footnote_links: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:link="http://www.xbrl.org/2003/linkbase"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <context id="c1">
    <entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
    <period><instant>2024-12-31</instant></period>
  </context>
  <unit id="usd"><measure>iso4217:USD</measure></unit>
  {"".join(footnote_links)}
</xbrl>"""


def _footnote_link(body: str) -> str:
    return f'<link:footnoteLink xlink:type="extended">{body}</link:footnoteLink>'


def _loc(label: str, href: str) -> str:
    return (f'<link:loc xlink:type="locator" xlink:href="{href}" '
            f'xlink:label="{label}"/>')


def _footnote(label: str, content: str) -> str:
    return (f'<link:footnote xlink:type="resource" xlink:label="{label}" '
            f'xlink:role="http://www.xbrl.org/2003/role/footnote" '
            f'xml:lang="en-US">{content}</link:footnote>')


def _footnote_arc(frm: str, to: str) -> str:
    return ('<link:footnoteArc xlink:type="arc" '
            'xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" '
            f'xlink:from="{frm}" xlink:to="{to}"/>')


def _parse(content: str) -> XBRLParser:
    parser = XBRLParser()
    parser.parse_instance_content(content)
    return parser


# ---------------------------------------------------------------------------
# .1 — the locator label was used as the fact id
# ---------------------------------------------------------------------------

def test_locator_is_dereferenced_to_the_fact_id(ko):
    """
    Coca-Cola labels each locator with the fact id plus a `_lbl` suffix, so the
    label is not the fact id. All six related ids were unresolvable before;
    all six name real facts now.
    """
    footnote = ko.footnotes[KO_FOOTNOTE]

    assert set(footnote.related_fact_ids) == KO_FACT_IDS


def test_related_fact_ids_name_facts_that_exist(ko):
    """The ids are not merely different — they resolve. Zero of six did before."""
    real_ids = {fact.fact_id for fact in ko.parser.facts.values() if fact.fact_id}
    footnote = ko.footnotes[KO_FOOTNOTE]

    assert set(footnote.related_fact_ids) <= real_ids


def test_the_facts_carry_the_footnote_back(ko):
    """The linkage is bidirectional: no fact carried a footnote before."""
    facts_with_footnotes = [f for f in ko.parser.facts.values() if f.footnotes]

    assert len(facts_with_footnotes) == 6
    assert all(f.footnotes == [KO_FOOTNOTE] for f in facts_with_footnotes)


def test_get_footnotes_for_fact_reaches_the_note(ko):
    """The public API the reporter used. It returned nothing at all."""
    footnotes = ko.get_footnotes_for_fact("Fact-983ED02C9F7A424EBE815702548224C3")

    assert len(footnotes) == 1
    assert footnotes[0].text.startswith("1 Basic net income per share")


def test_jpm_two_footnotes_partition_their_facts(jpm):
    """
    A second filing with the same locator style, and two footnotes rather than
    one, so the arcs have to land on the right resource as well as the right
    fact. Seven arcs split four and three.
    """
    real_ids = {fact.fact_id for fact in jpm.parser.facts.values() if fact.fact_id}
    counts = sorted(len(fn.related_fact_ids) for fn in jpm.footnotes.values())

    assert counts == [3, 4]
    for footnote in jpm.footnotes.values():
        assert set(footnote.related_fact_ids) <= real_ids


def test_synthetic_locator_indirection():
    """The construct from gh #1169, small enough to read in full."""
    content = _instance(_footnote_link(
        _loc("loc-fact-1", "#fact-1")
        + _footnote("fn-1", "See note.")
        + _footnote_arc("loc-fact-1", "fn-1")
    ))

    parser = _parse(content)

    assert parser.footnotes["fn-1"].related_fact_ids == ["fact-1"]


def test_an_arc_without_a_locator_still_uses_its_label():
    """
    Not every filer routes through a locator. When `xlink:from` names no
    locator the label is the fact reference, which is how this worked for the
    filings where it worked at all.
    """
    content = _instance(_footnote_link(
        _footnote("fn-1", "See note.") + _footnote_arc("fact-1", "fn-1")
    ))

    parser = _parse(content)

    assert parser.footnotes["fn-1"].related_fact_ids == ["fact-1"]


@pytest.mark.parametrize(
    "company,footnotes,facts_with_footnotes,related",
    [("msft", 17, 139, 142), ("unp", 6, 20, 20), ("gbdc", 90, 18270, 48629)],
)
def test_filings_where_label_equals_fragment_are_unchanged(
        request, company, footnotes, facts_with_footnotes, related):
    """
    18,686 of the corpus's 18,699 locators have label == fragment, so they
    resolved by coincidence. Dereferencing properly must give those the same
    answer they already had.
    """
    xbrl = request.getfixturevalue(company)

    assert len(xbrl.footnotes) == footnotes
    assert sum(1 for f in xbrl.parser.facts.values() if f.footnotes) == facts_with_footnotes
    assert sum(len(fn.related_fact_ids) for fn in xbrl.footnotes.values()) == related


# ---------------------------------------------------------------------------
# .7 — mixed content was dropped and duplicated at once
# ---------------------------------------------------------------------------

def test_text_outside_a_div_is_not_dropped(gbdc):
    """
    Golub's footnote 44 opens with a sentence that sits outside any `<div>`.
    Because the element contains divs elsewhere, the old code took the divs only
    and the sentence vanished; the value began mid-table with `Gross additions`.
    """
    text = gbdc.footnotes["fn-44"].text

    assert text.startswith("As defined in the 1940 Act")


def test_the_table_body_survives(gbdc):
    """A portfolio company named in the table the old code dropped entirely."""
    assert "Abita Brewing Co. LLC" in gbdc.footnotes["fn-44"].text


def test_nested_div_text_appears_exactly_once(gbdc):
    """
    `findall('.//div')` returns a nested div and its ancestor, and `itertext()`
    already descends, so this sentence was emitted twice.
    """
    text = gbdc.footnotes["fn-44"].text
    phrase = "Gross additions could include increases in the cost basis"

    assert text.count(phrase) == 1


def test_blocks_are_separated_rather_than_run_together(gbdc):
    """
    Without a separator the last word of one block glued to the first of the
    next: `follows:Portfolio`. Both sides must be present and unglued.
    """
    text = gbdc.footnotes["fn-44"].text

    assert "follows:Portfolio" not in text
    assert "were as follows:" in text
    assert "Portfolio Company" in text


def test_synthetic_mixed_content_keeps_every_part_in_order():
    """Lead text, a block, and tail text — the old code returned only the block."""
    content = _instance(_footnote_link(_footnote(
        "fn-1",
        'Lead text.<xhtml:div>Block text.</xhtml:div>Tail text.',
    )))

    parser = _parse(content)
    text = parser.footnotes["fn-1"].text

    assert "Lead text." in text
    assert "Block text." in text
    assert "Tail text." in text
    assert text.index("Lead text.") < text.index("Block text.") < text.index("Tail text.")


def test_synthetic_nested_divs_are_not_duplicated():
    """The duplication half, isolated."""
    content = _instance(_footnote_link(_footnote(
        "fn-1",
        '<xhtml:div>Outer <xhtml:div>Inner</xhtml:div></xhtml:div>',
    )))

    parser = _parse(content)
    text = parser.footnotes["fn-1"].text

    assert text.count("Inner") == 1
    assert text.count("Outer") == 1


def test_a_footnote_without_markup_is_still_plain_text():
    """The common case — no XHTML at all — keeps working."""
    content = _instance(_footnote_link(_footnote("fn-1", "Just a sentence.")))

    parser = _parse(content)

    assert parser.footnotes["fn-1"].text == "Just a sentence."


# ---------------------------------------------------------------------------
# 05gk — resources were keyed document-globally
# ---------------------------------------------------------------------------

def test_two_links_reusing_a_label_do_not_collide():
    """
    The reported shape from gh #1190: two extended links each define `fn-1`.
    The second used to replace the first, so an arc in the first link returned
    the second link's text — a real footnote belonging to a different fact.
    """
    content = _instance(
        _footnote_link(
            _loc("loc-a", "#fact-a")
            + _footnote("fn-1", "English note.")
            + _footnote_arc("loc-a", "fn-1")
        ),
        _footnote_link(
            _loc("loc-b", "#fact-b")
            + _footnote("fn-1", "French note.")
            + _footnote_arc("loc-b", "fn-1")
        ),
    )

    parser = _parse(content)
    texts = {fn.text: fn.related_fact_ids for fn in parser.footnotes.values()}

    assert texts["English note."] == ["fact-a"]
    assert texts["French note."] == ["fact-b"]


def test_a_reused_label_keeps_both_resources(unp):
    """
    Both resources must survive, and each must be reachable by its own key.
    Union Pacific files six footnoteLinks with unique labels, so the ordinary
    case keeps one entry per label.
    """
    assert len(unp.footnotes) == 6
    assert all(key == fn.footnote_id for key, fn in unp.footnotes.items())


def test_unique_labels_across_links_keep_their_plain_keys():
    """No synthetic suffix appears unless there is an actual collision."""
    content = _instance(
        _footnote_link(_footnote("fn-1", "One.") + _footnote_arc("fact-a", "fn-1")),
        _footnote_link(_footnote("fn-2", "Two.") + _footnote_arc("fact-b", "fn-2")),
    )

    parser = _parse(content)

    assert set(parser.footnotes) == {"fn-1", "fn-2"}
