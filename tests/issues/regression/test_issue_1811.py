"""Reproduce a retained FactQuery DataFrame surviving FactsView.clear_cache().

GitHub Issue: https://github.com/dgunning/edgartools/issues/1811

Source: Golub Capital BDC's March 31, 2025 10-Q, accession
0001476765-25-000040, checked in as gbdc-20250331_htm.xml.

The two in-memory instance documents below are explicitly STAGED subsets of
that one filing, not separately filed documents. Each copies one genuine
InterestPaidNet fact, its original context and unit, and its original footnote
resource, locator and arc. No financial value or source attribute is edited.

The parser merges facts additively. Both source facts reference fn-1; loading
the resource again in stage two currently stores it as fn-1#2. That inherited
collision behavior is retained and checked, not attributed to the cache bug.
Distinct contexts and periods prevent the two rows from being deduplicated.

The final assertion deliberately requires current data. It fails on the bug;
there is no skip, xfail, or assertion that treats stale output as success.
"""

from copy import deepcopy

import pytest
from lxml import etree

import edgar.xbrl.facts as facts_module
from edgar.xbrl import XBRL
from tests.paths import FIXTURES_DIR

pytestmark = [pytest.mark.reproduction, pytest.mark.fast]

_NS = {
    "i": "http://www.xbrl.org/2003/instance",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}
_XLINK = "{" + _NS["xlink"] + "}"
_XML = "{http://www.w3.org/XML/1998/namespace}"
_CONCEPT = "us-gaap:InterestPaidNet"
_NOTE_ROLE = "http://www.xbrl.org/2003/role/footnote"
_NOTE_TEXT = (
    "Includes cash paid or received for contractual interest rate swaps, which may have "
    "different contractual settlement dates among the (i) fixed interest leg, "
    "(ii) floating interest leg and (iii) the debt instrument."
)
_SOURCE_FACTS = (
    ("f-501", "c-1", 133282000, "2024-10-01", "2025-03-31"),
    ("f-502", "c-26", 71205000, "2023-10-01", "2024-03-31"),
)
_ROW_FIELDS = ("fact_id", "concept", "context_ref", "unit_ref", "numeric_value")


def _staged_documents():
    """Copy relevant original XML nodes; never parse the whole filing with XBRL."""
    source = FIXTURES_DIR / "xbrl" / "gbdc" / "gbdc-20250331_htm.xml"
    root = etree.parse(
        str(source), etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True),
    ).getroot()
    documents = []
    for fact_id, context_id, amount, start, end in _SOURCE_FACTS:
        matches = root.xpath("./*[@id=$fact_id]", fact_id=fact_id)
        assert len(matches) == 1
        fact = matches[0]
        assert fact.tag == f"{{{root.nsmap['us-gaap']}}}InterestPaidNet"
        assert (fact.get("contextRef"), fact.get("unitRef"), fact.get("decimals")) == (
            context_id, "usd", "-3",
        )
        assert int(fact.text.strip()) == amount
        context = root.find(f"i:context[@id='{context_id}']", _NS)
        assert context is not None
        assert context.findtext("i:entity/i:identifier", namespaces=_NS) == "0001476765"
        assert context.findtext("i:period/i:startDate", namespaces=_NS) == start
        assert context.findtext("i:period/i:endDate", namespaces=_NS) == end
        unit = root.find("i:unit[@id='usd']", _NS)
        assert unit is not None
        assert unit.findtext("i:measure", namespaces=_NS) == "iso4217:USD"

        locations = [
            (link, loc)
            for link in root.findall("link:footnoteLink", _NS)
            for loc in link.findall("link:loc", _NS)
            if loc.get(f"{_XLINK}href") == f"#{fact_id}"
        ]
        assert len(locations) == 1
        link, locator = locations[0]
        arcs = [arc for arc in link.findall("link:footnoteArc", _NS)
                if arc.get(f"{_XLINK}from") == locator.get(f"{_XLINK}label")]
        assert len(arcs) == 1
        arc = arcs[0]
        assert arc.get(f"{_XLINK}to") == "fn-1"
        notes = [note for note in link.findall("link:footnote", _NS)
                 if note.get(f"{_XLINK}label") == arc.get(f"{_XLINK}to")]
        assert len(notes) == 1
        note = notes[0]
        assert note.get(f"{_XLINK}role") == _NOTE_ROLE
        assert note.get(f"{_XML}lang") == "en-US"
        assert " ".join("".join(note.itertext()).split()) == _NOTE_TEXT

        staged = etree.Element(root.tag, attrib=dict(root.attrib), nsmap=root.nsmap)
        for node in (context, unit, fact):
            staged.append(deepcopy(node))
        staged_link = etree.SubElement(staged, link.tag, attrib=dict(link.attrib))
        for node in (locator, note, arc):
            staged_link.append(deepcopy(node))
        documents.append(etree.tostring(staged, encoding="unicode"))
        print(  # noqa: T201 - reproduction diagnostics
            f"Source: {fact_id} {_CONCEPT}; context={context_id}; value={amount}; "
            f"unit=usd/iso4217:USD; decimals=-3; {start} to {end}; note=fn-1"
        )

    print(f"Source note: role={_NOTE_ROLE}; lang=en-US; text={_NOTE_TEXT}")  # noqa: T201
    return documents


def _rows(records):
    return sorted(tuple(record[field] for field in _ROW_FIELDS) for record in records)


def test_retained_query_dataframe_refreshes_after_facts_view_clear_cache():
    print(f"Imported FactQuery module: {facts_module.__file__}")  # noqa: T201
    first_document, second_document = _staged_documents()
    expected = [
        (fact_id, _CONCEPT, context_id, "usd", amount)
        for fact_id, context_id, amount, _, _ in _SOURCE_FACTS
    ]
    xbrl = XBRL()
    xbrl.parser.parse_instance_content(first_document)
    first_fact = next(iter(xbrl.parser.facts.values()))
    view = xbrl.facts
    query = view.query().by_concept(_CONCEPT, exact=True)
    warm_rows = _rows(query.to_dataframe().to_dict("records"))
    assert warm_rows == expected[:1]

    xbrl.parser.parse_instance_content(second_document)
    view.clear_cache()

    # The source and live APIs must be current before the diagnostic assertion.
    raw_facts = {fact.fact_id: fact for fact in xbrl.parser.facts.values()}
    assert set(raw_facts) == {"f-501", "f-502"}
    assert raw_facts["f-501"] is first_fact
    for fact_id, context_id, amount, start, end in _SOURCE_FACTS:
        fact = raw_facts[fact_id]
        assert (fact.element_id, fact.context_ref, fact.numeric_value, fact.unit_ref) == (
            _CONCEPT, context_id, amount, "usd",
        )
        assert str(fact.decimals) == "-3"
        assert xbrl.contexts[context_id].period["startDate"] == start
        assert xbrl.contexts[context_id].period["endDate"] == end
    assert xbrl.units["usd"]["measure"] == "iso4217:USD"
    live_notes = {}
    for fact_id, note_key in (("f-501", "fn-1"), ("f-502", "fn-1#2")):
        notes = xbrl.get_footnotes_for_fact(fact_id)
        live_notes[fact_id] = [note.footnote_id for note in notes]
        assert live_notes[fact_id] == [note_key]
        assert notes[0].related_fact_ids == [fact_id]
        assert " ".join(notes[0].text.split()) == _NOTE_TEXT
        assert (notes[0].role, notes[0].lang) == (_NOTE_ROLE, "en-US")

    view_rows = _rows(view.get_facts())
    executed_rows = _rows(query.execute())
    fresh_rows = _rows(view.query().by_concept(_CONCEPT, exact=True).to_dataframe().to_dict("records"))
    retained_rows = _rows(query.to_dataframe().to_dict("records"))
    assert view_rows == expected
    assert executed_rows == expected
    assert fresh_rows == expected
    print(f"Live facts: {len(raw_facts)}; live footnotes: {live_notes}")  # noqa: T201
    print(f"Warm retained DataFrame: {warm_rows}")  # noqa: T201
    print(f"After clear_cache: view={view_rows}; retained execute={executed_rows}")  # noqa: T201
    print(f"After clear_cache: fresh DataFrame={fresh_rows}; retained DataFrame={retained_rows}")  # noqa: T201

    assert retained_rows == expected, (
        "FactsView.clear_cache() must refresh DataFrames on retained queries; "
        "the same query's execute() and a fresh query already return both source facts."
    )
