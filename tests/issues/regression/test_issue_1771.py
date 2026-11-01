"""Footnote attachment must not rescan every fact for every relationship.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1771

Golub Capital BDC's March 31, 2025 10-Q (0001476765-25-000040) contains
48,629 footnote relationships. Count fact visits rather than elapsed time so
the performance regression is deterministic, and retain the real filing's
interest-paid amount and its contractual interest-rate-swap explanation.
"""

import pytest
from lxml import etree

from edgar.xbrl.parsers import InstanceParser, XBRLParser
from tests.paths import FIXTURES_DIR

pytestmark = pytest.mark.fast


class _CountedFacts(dict):
    """Count actual fact enumeration without changing the stored Fact objects."""

    def __init__(self):
        super().__init__()
        self.value_visits = 0

    def values(self):
        for fact in super().values():
            self.value_visits += 1
            yield fact


def _parser(facts=None):
    return InstanceParser(
        contexts={}, facts={} if facts is None else facts, units={}, footnotes={},
        calculation_trees={}, entity_info={}, reporting_periods=[], context_period_map={},
    )


def _instance(*parts):
    return f"""<xbrl xmlns="http://www.xbrl.org/2003/instance"
        xmlns:test="https://example.com/test"
        xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
        xmlns:link="http://www.xbrl.org/2003/linkbase"
        xmlns:xlink="http://www.w3.org/1999/xlink">
      <context id="c1">
        <entity><identifier scheme="http://www.sec.gov/CIK">0000000000</identifier></entity>
        <period><instant>2025-03-31</instant></period>
      </context>
      <unit id="usd"><measure>iso4217:USD</measure></unit>
      {''.join(parts)}
    </xbrl>"""


def _fact(concept, fact_id, value=1):
    id_attribute = '' if fact_id is None else f' id="{fact_id}"'
    return (f'<test:{concept} contextRef="c1" unitRef="usd"{id_attribute}>'
            f'{value}</test:{concept}>')


def _link(*parts):
    return f'<link:footnoteLink xlink:type="extended">{"".join(parts)}</link:footnoteLink>'


def _note(label, text="A note.", lang="en-US"):
    return (f'<link:footnote xlink:label="{label}" xlink:type="resource" '
            f'xlink:role="http://www.xbrl.org/2003/role/footnote" xml:lang="{lang}">'
            f'{text}</link:footnote>')


def _loc(label, fact_id):
    return f'<link:loc xlink:label="{label}" xlink:href="#{fact_id}" xlink:type="locator"/>'


def _arc(from_ref, to_ref, order=1):
    return (f'<link:footnoteArc xlink:from="{from_ref}" xlink:to="{to_ref}" '
            f'xlink:type="arc" order="{order}"/>')


@pytest.mark.parametrize("fact_count,repetitions", [(8, 3), (64, 8)])
def test_attachment_visits_facts_once_across_repeated_arcs_and_links(fact_count, repetitions):
    facts = _CountedFacts()
    parser = _parser(facts)
    targets = [fact_count - 2, fact_count - 1]
    root = etree.fromstring(_instance(
        *(_fact(f"Item{i}", f"f{i}") for i in range(fact_count)),
        *(_link(
            _note("n"),
            *(_arc(f"f{i}", "n") for _ in range(repetitions) for i in targets),
        ) for _ in range(2)),
    ))
    parser._extract_facts(root)

    parser._extract_footnotes(root)

    expected_ids = [f"f{i}" for _ in range(repetitions) for i in targets]
    assert parser.footnotes["n"].related_fact_ids == expected_ids
    assert parser.footnotes["n#2"].related_fact_ids == expected_ids
    for i in targets:
        assert facts[f"test_Item{i}|c1"].footnotes == ["n", "n#2"]
    assert facts.value_visits == fact_count


def test_first_match_uses_final_fact_order_after_concept_context_rekeying():
    parser = _parser()
    parser.parse_instance_content(_instance(
        _fact("A", "dup", 10),
        _fact("B", "dup", 20),
        _fact("A", "other", 30),
        _link(_loc("target", "dup"), _note("n1"), _note("n2"),
              _arc("target", "n2", order=2), _arc("target", "n1", order=1),
              _arc("target", "n2", order=0)),
    ))

    # The second A rekeys the first A behind B. Indexing XML order would pick A.
    assert list(parser.facts) == ["test_B|c1", "test_A|c1|0", "test_A|c1|1"]
    first, second, third = parser.facts.values()
    assert (first.fact_id, first.numeric_value, first.footnotes) == ("dup", 20, ["n2", "n1"])
    assert (second.fact_id, second.numeric_value, second.footnotes) == ("dup", 10, [])
    assert (third.fact_id, third.numeric_value, third.footnotes) == ("other", 30, [])
    assert parser.footnotes["n2"].related_fact_ids == ["dup", "dup"]
    assert parser.footnotes["n1"].related_fact_ids == ["dup"]


def test_parser_reuse_indexes_replaced_and_surviving_facts_after_merge():
    parser = _parser()
    parser.parse_instance_content(_instance(
        _fact("A", "shared", 10), _fact("B", "surviving", 20),
        _link(_note("n"), _arc("shared", "n"), _arc("surviving", "n")),
    ))
    replaced = parser.facts["test_A|c1"]
    surviving = parser.facts["test_B|c1"]

    parser.parse_instance_content(_instance(
        _fact("A", "shared", 30), _fact("C", "surviving", 40),
        _link(_note("n", "Second document."),
              _arc("shared", "n"), _arc("surviving", "n")),
    ))

    current = parser.facts["test_A|c1"]
    assert current is not replaced
    assert (current.numeric_value, current.footnotes) == (30, ["n#2"])
    assert (replaced.numeric_value, replaced.footnotes) == (10, ["n"])
    assert parser.facts["test_B|c1"] is surviving
    assert surviving.footnotes == ["n", "n#2"]
    assert parser.facts["test_C|c1"].footnotes == []
    assert parser.footnotes["n"].text == "A note."
    assert parser.footnotes["n#2"].text == "Second document."
    assert parser.footnotes["n#2"].related_fact_ids == ["shared", "surviving"]


def test_reused_locator_and_resource_labels_resolve_within_each_link():
    parser = _parser()
    parser.parse_instance_content(_instance(
        _fact("A", "a"), _fact("B", "b"),
        _link(_loc("target", "a"), _note("n", "First note."), _arc("target", "n")),
        _link(_loc("target", "b"), _note("n", "Deuxieme note.", lang="fr"),
              _arc("target", "n")),
    ))

    assert parser.facts["test_A|c1"].footnotes == ["n"]
    assert parser.facts["test_B|c1"].footnotes == ["n#2"]
    assert parser.footnotes["n"].related_fact_ids == ["a"]
    second_note = parser.footnotes["n#2"]
    assert (second_note.footnote_id, second_note.text, second_note.lang) == (
        "n#2", "Deuxieme note.", "fr",
    )
    assert second_note.related_fact_ids == ["b"]
    assert second_note.role == "http://www.xbrl.org/2003/role/footnote"


def test_missing_targets_keep_reverse_ids_and_missing_resources_are_skipped(caplog):
    parser = _parser()
    with caplog.at_level("DEBUG"):
        parser.parse_instance_content(_instance(
            _fact("A", "a"),
            _link(_note("n"), _loc("unresolved", "missing-fact"),
                  _arc("unresolved", "n"), _arc("a", "absent"), _arc("a", "absent"),
                  '<link:footnoteArc xlink:to="n"/>',
                  '<link:footnoteArc xlink:from="a"/>', _arc("a", "n")),
        ))

    assert list(parser.footnotes) == ["n"]
    assert parser.footnotes["n"].related_fact_ids == ["missing-fact", "a"]
    assert parser.facts["test_A|c1"].footnotes == ["n"]
    assert caplog.messages.count("Footnote arc references undefined footnote: absent") == 1


@pytest.mark.parametrize("links", [
    "",
    _link(_note("n")),
    _link(_note("n"), '<link:footnoteArc xlink:to="n"/>'),
    _link(_note("n"), '<link:footnoteArc xlink:from="a"/>'),
    _link(_note("n"), _arc("", "n")),
    _link(_note("n"), _arc("a", "")),
    _link(_note("n"), _arc("a", "undefined")),
], ids=["no-links", "no-arcs", "no-from", "no-to", "empty-from", "empty-to", "missing-resource"])
def test_no_fact_enumeration_without_an_attachable_relationship(links):
    facts = _CountedFacts()
    parser = _parser(facts)
    root = etree.fromstring(_instance(_fact("A", "a"), links))
    parser._extract_facts(root)

    parser._extract_footnotes(root)

    assert facts.value_visits == 0
    assert facts["test_A|c1"].footnotes == []
    assert all(note.related_fact_ids == [] for note in parser.footnotes.values())


def test_empty_and_missing_fact_ids_keep_endpoint_guards_and_locator_fallback():
    parser = _parser()
    parser.parse_instance_content(_instance(
        _fact("NoId", None), _fact("EmptyId", ""), _fact("Fallback", "fallback"),
        _link(_note("n"), _loc("fallback", ""), _loc("", ""),
              '<link:footnoteArc xlink:to="n"/>', _arc("", "n"),
              _arc("fallback", "n")),
    ))

    assert parser.facts["test_NoId|c1"].fact_id is None
    assert parser.facts["test_NoId|c1"].footnotes == []
    assert parser.facts["test_EmptyId|c1"].fact_id == ""
    assert parser.facts["test_EmptyId|c1"].footnotes == []
    assert parser.facts["test_Fallback|c1"].footnotes == ["n"]
    assert parser.footnotes["n"].related_fact_ids == ["fallback"]


def test_gbdc_interest_paid_keeps_its_contractual_swap_footnote():
    """GBDC 10-Q, accession 0001476765-25-000040, six months to 2025-03-31."""
    parser = XBRLParser()
    instance_file = FIXTURES_DIR / "xbrl" / "gbdc" / "gbdc-20250331_htm.xml"
    parser.parse_instance_content(instance_file.read_text(encoding="utf-8"))

    assert len(parser.facts) == 21393
    assert len(parser.footnotes) == 90
    assert sum(len(note.related_fact_ids) for note in parser.footnotes.values()) == 48629
    assert sum(bool(fact.footnotes) for fact in parser.facts.values()) == 18270
    interest_paid = next(fact for fact in parser.facts.values() if fact.fact_id == "f-501")
    assert (interest_paid.element_id, interest_paid.context_ref) == ("us-gaap:InterestPaidNet", "c-1")
    assert interest_paid.numeric_value == 133282000
    assert interest_paid.unit_ref == "usd"
    assert parser.units["usd"]["measure"] == "iso4217:USD"
    assert interest_paid.footnotes == ["fn-1"]
    note = parser.footnotes["fn-1"]
    assert "f-501" in note.related_fact_ids
    assert " ".join(note.text.split()) == (
        "Includes cash paid or received for contractual interest rate swaps, which may have "
        "different contractual settlement dates among the (i) fixed interest leg, "
        "(ii) floating interest leg and (iii) the debt instrument."
    )
