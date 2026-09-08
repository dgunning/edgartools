"""
Regression tests for edgartools-jj77: two identifiers in the instance parser
that were built out of strings too loosely to tell filed facts apart, so facts
were dropped before any query ran.

GH #1295 -- the storage key. `_create_normalized_fact_key` joined its parts
with '_':

    element_id_context_ref[_instance_id]

'_' is legal inside an NCName, so a context legitimately named 'D20250630_1'
produced the same key as duplicate-occurrence 1 of context 'D20250630':

    (us-gaap:InventoryWriteDown, 'D20250630_1', no index)  -> ..._D20250630_1
    (us-gaap:InventoryWriteDown, 'D20250630',   index 1)   -> ..._D20250630_1

`facts_dict[key] = fact` then silently replaced one with the other. Naming the
quarterly context '<ytd>_1' is a common filer-agent convention, so this is not
an exotic construction: ClearOne's 10-Q lost 6 of its 590 facts, including the
QUARTER's revenue and net income, leaving only the six-month figures behind --
a consumer asking for Q2 revenue got no row at all.

GH #1293 -- the structural-element test. `_extract_facts` skipped any element
whose tag merely ENDED WITH 'context'/'unit'/'schemaRef'/..., so an issuer
concept named `ctso:NumberOfSharesInAunit` was discarded before its contextRef
was read. Two copies of that set existed and only one was right: the counting
pass at least compared the half-qualified '}unit'. Both are now one fully
qualified frozenset compared by equality, because a suffix cannot distinguish
a structural element from an issuer's concept -- only the expanded name can.

WHY THESE FIXTURES. The pre-existing fixture corpus exercises NEITHER bug: fact
counts were byte-identical across all 31 filing directories before and after
the fix. A corpus that cannot fail is not evidence (see the campaign's
mutation-probe lesson), so both filings are checked in as full, unmodified
filed instances, and every expectation below is derived by counting the raw
XML rather than by trusting the parser.
"""

from pathlib import Path

import pytest
from lxml import etree as ET

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.instance import InstanceParser

XBRLI_NS = "{http://www.xbrl.org/2003/instance}"

CLRO = Path("tests/fixtures/xbrl/clro/10q_2025q2/clro-20250630_htm.xml")
CTSO = Path("tests/fixtures/xbrl/ctso/10k_2024/ctso-20241231x10k_htm.xml")


def physical_fact_occurrences(instance_path: Path):
    """Count fact elements in the filed XML, independently of the parser.

    A fact is any non-structural element carrying a contextRef. This is the
    ground truth the parser is measured against; it must not call into
    edgar.xbrl, or it would agree with the bug.
    """
    root = ET.fromstring(instance_path.read_bytes())
    prefixes = {uri: pfx for pfx, uri in root.nsmap.items() if uri}
    facts = []
    for element in root.iter():
        if not isinstance(element.tag, str) or element.tag.startswith(XBRLI_NS):
            continue
        if element.get("contextRef") is None:
            continue
        namespace, name = element.tag[1:].split("}", 1)
        facts.append({
            "concept": f"{prefixes.get(namespace, '?')}:{name}",
            "context_ref": element.get("contextRef"),
            "fact_id": element.get("id"),
            "value": (element.text or "").strip(),
        })
    return facts


@pytest.fixture(scope="module")
def clro():
    return XBRL.from_files(instance_file=CLRO)


@pytest.fixture(scope="module")
def ctso():
    return XBRL.from_files(instance_file=CTSO)


def test_key_separates_a_filed_context_from_a_duplicate_index():
    """The two identities that used to share one key must not share one now."""
    parser = InstanceParser({}, {}, {}, {}, {}, {}, [], {})

    filed_context = parser._create_normalized_fact_key(
        "us-gaap:InventoryWriteDown", "D20250630_1")
    duplicate_index = parser._create_normalized_fact_key(
        "us-gaap:InventoryWriteDown", "D20250630", 1)

    assert filed_context != duplicate_index

    # The ':' -> '_' tolerance is load-bearing: XBRL.element_context_index is
    # keyed on the underscore spelling and looks facts up through this same
    # builder, so the two spellings must still agree.
    assert parser._create_normalized_fact_key("us-gaap:Assets", "c-1") == \
        parser._create_normalized_fact_key("us-gaap_Assets", "c-1")


def test_clro_keeps_every_filed_fact(clro):
    """gh #1295: 590 filed occurrences, 590 parsed. Was 584."""
    filed = physical_fact_occurrences(CLRO)
    assert len(filed) == 590, "fixture changed; re-derive the expectations below"
    assert len(clro.parser.facts) == len(filed)

    parsed_ids = {f.fact_id for f in clro.parser.facts.values() if f.fact_id}
    missing = [f for f in filed if f["fact_id"] and f["fact_id"] not in parsed_ids]
    assert missing == []


@pytest.mark.parametrize(
    "concept, period, fact_id, context_ref, value",
    [
        # The quarter's own figures, all filed under a '<ytd>_1' context and
        # all previously overwritten by their six-month counterparts.
        ("us-gaap:InventoryWriteDown", "duration_2025-04-01_2025-06-30",
         "Tag461", "D20250630_1", 48000.0),
        ("us-gaap:InventoryWriteDown", "duration_2024-04-01_2024-06-30",
         "Tag459", "D20240630_1", -95000.0),
        ("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
         "duration_2025-04-01_2025-06-30", "Tag24", "D20250630_1", 1916000.0),
        ("us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
         "duration_2024-04-01_2024-06-30", "Tag27", "D20240630_1", 2304000.0),
        ("us-gaap:NetIncomeLoss", "duration_2025-04-01_2025-06-30",
         "Tag76", "D20250630_1", -4572000.0),
        ("us-gaap:NetIncomeLoss", "duration_2024-04-01_2024-06-30",
         "Tag39", "D20240630_1", -2820000.0),
    ],
)
def test_clro_quarterly_facts_are_queryable(clro, concept, period, fact_id,
                                            context_ref, value):
    """Each expectation is the filed fact, read out of the raw XML first."""
    filed = [f for f in physical_fact_occurrences(CLRO)
             if f["fact_id"] == fact_id]
    assert len(filed) == 1
    assert filed[0]["concept"] == concept
    assert filed[0]["context_ref"] == context_ref
    assert float(filed[0]["value"]) == value

    # Revenue and net income are also tagged per segment for the same quarter,
    # so the query legitimately returns the dimensional siblings too; this is
    # about the consolidated fact being reachable at all.
    rows = (clro.facts.query()
            .by_concept(concept, exact=True)
            .by_period_key(period)
            .execute())
    matched = [r for r in rows if r["fact_id"] == fact_id]
    assert len(matched) == 1, f"{fact_id} missing from {[r['fact_id'] for r in rows]}"
    assert matched[0]["numeric_value"] == value
    assert matched[0]["context_ref"] == context_ref


def test_clro_year_to_date_facts_are_not_displaced(clro):
    """The surviving side of the collision must stay put.

    The year-to-date figures were never missing -- they were what the quarter's
    key wrongly ended up holding. Fixing the key must not lose them in turn.
    """
    rows = (clro.facts.query()
            .by_concept("us-gaap:InventoryWriteDown", exact=True)
            .by_period_key("duration_2025-01-01_2025-06-30")
            .execute())
    assert {r["numeric_value"] for r in rows} == {320000.0}


def test_ctso_keeps_a_concept_whose_name_ends_in_unit(ctso):
    """gh #1293: ctso:NumberOfSharesInAunit is a fact, not an xbrli:unit."""
    filed = [f for f in physical_fact_occurrences(CTSO)
             if f["concept"] == "ctso:NumberOfSharesInAunit"]
    assert len(filed) == 1, "the filing reports this exactly once"

    rows = (ctso.facts.query()
            .by_concept("ctso:NumberOfSharesInAunit", exact=True)
            .execute())
    assert len(rows) == 1
    assert rows[0]["fact_id"] == filed[0]["fact_id"] == "Narr_or4kIBdD_kCg8BCeB9SCvQ"
    assert rows[0]["numeric_value"] == 1.0


def test_ctso_keeps_every_filed_fact(ctso):
    """1633 filed occurrences, 1633 parsed. Was 1632."""
    filed = physical_fact_occurrences(CTSO)
    assert len(filed) == 1633, "fixture changed; re-derive the expectations above"
    assert len(ctso.parser.facts) == len(filed)


def test_structural_elements_are_still_skipped(ctso):
    """The looser test was at least skipping contexts and units; so must this.

    A genuine xbrli:unit or xbrli:context must never surface as a fact -- that
    is what the suffix check was there for, and it is the thing a fully
    qualified comparison could plausibly regress.
    """
    concepts = {f.element_id for f in ctso.parser.facts.values()}
    assert not any(c.endswith(":unit") or c.endswith(":context") for c in concepts)
    assert "xbrli:unit" not in concepts and "xbrli:context" not in concepts
    # Every stored fact carries the contextRef that makes it a fact.
    assert all(f.context_ref for f in ctso.parser.facts.values())
