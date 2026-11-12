"""
Inline XBRL facts resolve contexts, units and continuations across a document set.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1753

Inline XBRL 1.1 treats the documents of one submission as a single document set:
only one of them needs an ix:header. IBM's FY2024 10-K (accession
0000051143-25-000015) files its annual report as an inline EX-13
(ibm-20241231_d2.htm, the fixture's ix.htm) with no ix:header at all, so
parse_html on it alone gives 3,983 facts with no context. parse_inline_xbrl_set
indexes the definitions of every supplied document before reading any fact.

The fixture copies are pretty-printed and lack some root namespace declarations
the filed documents carry. Checked against the filed documents from SEC on
2026-11-12: every numeric fact, context and unit is identical, and only the
whitespace inside 135 escaped text blocks differs, so nothing here asserts on
text-block content.
"""
import warnings
from pathlib import Path

import pytest

from edgar.documents import parse_html, parse_inline_xbrl_set

IBM = Path("tests/fixtures/xbrl/ibm/10k_2024")
PRIMARY = "ibm-20241231.htm"
EXHIBIT = "ibm-20241231_d2.htm"


@pytest.fixture(scope="module")
def ibm_sources():
    return {
        PRIMARY: (IBM / "ibm-20241231.htm").read_text(encoding="utf-8"),
        EXHIBIT: (IBM / "ix.htm").read_text(encoding="utf-8"),
    }


@pytest.fixture(scope="module")
def ibm_set(ibm_sources):
    return parse_inline_xbrl_set(ibm_sources)


def _fact_key(facts):
    return [(f.fact_id, f.concept, f.value, f.context_ref, f.context, f.unit_ref, f.unit) for f in facts]


def test_exhibit_alone_cannot_resolve_its_references(ibm_sources):
    # The boundary: parse_html reads one document and is unchanged.
    facts = parse_html(ibm_sources[EXHIBIT]).xbrl_facts
    assert len(facts) == 3983
    assert sum(f.context is None for f in facts) == 3983
    assert sum(1 for f in facts if f.unit_ref and f.unit is None) == 3734


def test_exhibit_resolves_against_the_primary_document(ibm_set):
    exhibit = ibm_set[EXHIBIT].xbrl_facts
    assert list(ibm_set) == [PRIMARY, EXHIBIT]
    # Each document keeps only its own facts.
    assert (len(ibm_set[PRIMARY].xbrl_facts), len(exhibit)) == (241, 3983)
    assert all(f.context is not None for f in exhibit)
    with_unit = [f for f in exhibit if f.unit_ref]
    assert len(with_unit) == 3734
    assert all(f.unit is not None for f in with_unit)

    revenue = next(f for f in exhibit if f.fact_id == "f-204")
    assert (revenue.concept, revenue.context_ref, revenue.numeric_value, revenue.unit) == (
        "us-gaap:Revenues", "c-62", 29_813_000_000.0, "USD")
    # A member slice of revenue, not consolidated revenue.
    assert revenue.context["start_date"] == "2024-01-01"
    assert revenue.context["end_date"] == "2024-12-31"
    assert revenue.context["dimensions"] == {"srt:ProductOrServiceAxis": "us-gaap:TechnologyServiceMember"}


def test_primary_document_is_unchanged_by_the_set(ibm_sources, ibm_set):
    assert _fact_key(ibm_set[PRIMARY].xbrl_facts) == _fact_key(parse_html(ibm_sources[PRIMARY]).xbrl_facts)


def test_input_order_does_not_change_the_result(ibm_sources, ibm_set):
    reversed_set = parse_inline_xbrl_set({EXHIBIT: ibm_sources[EXHIBIT], PRIMARY: ibm_sources[PRIMARY]})
    assert list(reversed_set) == [EXHIBIT, PRIMARY]
    for name in (PRIMARY, EXHIBIT):
        assert _fact_key(reversed_set[name].xbrl_facts) == _fact_key(ibm_set[name].xbrl_facts)


# --- synthetic document sets ---------------------------------------------------

HEADER = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body><ix:header><ix:resources>
<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{cik}</xbrli:identifier>
</xbrli:entity><xbrli:period><xbrli:instant>{instant}</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:resources></ix:header>
<ix:continuation id="cont1"> continued text</ix:continuation>
<p><ix:nonFraction name="t:Primary" contextRef="{cid}" unitRef="usd" decimals="0">5</ix:nonFraction></p>
</body></html>"""

EXHIBIT_DOC = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
<p><ix:nonFraction name="t:Cash" contextRef="c1" unitRef="usd" decimals="0">1,234</ix:nonFraction></p>
<p><ix:nonNumeric name="t:Note" contextRef="c1" continuedAt="cont1">Start of note</ix:nonNumeric></p>
</body></html>"""


def _primary(cid="c1", cik="0000000001", instant="2024-12-31"):
    return HEADER.format(cid=cid, cik=cik, instant=instant)


def test_synthetic_set_resolves_context_unit_and_continuation():
    docs = parse_inline_xbrl_set({"primary.htm": _primary(), "ex13.htm": EXHIBIT_DOC})
    cash, note = docs["ex13.htm"].xbrl_facts
    assert (cash.numeric_value, cash.unit, cash.context["instant"]) == (1234.0, "USD", "2024-12-31")
    assert note.value == "Start of note continued text"
    assert [f.concept for f in docs["primary.htm"].xbrl_facts] == ["t:Primary"]


def test_id_defined_in_two_documents_is_ambiguous():
    sources = {"a.htm": _primary(cik="0000000001"), "b.htm": _primary(cik="0000000002"),
               "ex13.htm": EXHIBIT_DOC}
    results = []
    for order in (sources, dict(reversed(list(sources.items())))):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            docs = parse_inline_xbrl_set(order)
        messages = [str(w.message) for w in caught]
        assert len(messages) == 1
        # The context, the unit and the continuation are each defined twice.
        assert "context 'c1' in a.htm, b.htm" in messages[0]
        assert "unit 'usd' in a.htm, b.htm" in messages[0]
        assert "continuation 'cont1' in a.htm, b.htm" in messages[0]
        cash, note = docs["ex13.htm"].xbrl_facts
        assert (cash.context, cash.unit) == (None, None)
        assert note.value == "Start of note"
        results.append({name: _fact_key(doc.xbrl_facts) for name, doc in docs.items()})
    assert results[0] == results[1]


def test_id_defined_twice_in_one_document_is_ambiguous():
    doubled = _primary().replace("</ix:resources>", """<xbrli:context id="c1"><xbrli:entity>
<xbrli:identifier scheme="http://www.sec.gov/CIK">0000000009</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:instant>2023-12-31</xbrli:instant></xbrli:period></xbrli:context></ix:resources>""")
    with pytest.warns(UserWarning, match=r"context 'c1' in primary\.htm, primary\.htm"):
        docs = parse_inline_xbrl_set({"primary.htm": doubled, "ex13.htm": EXHIBIT_DOC})
    assert docs["ex13.htm"].xbrl_facts[0].context is None
    # The unit is still defined once, so it still resolves.
    assert docs["ex13.htm"].xbrl_facts[0].unit == "USD"


def test_continuation_cycle_across_documents_terminates():
    first = """<html><body><ix:continuation id="k1" continuedAt="k2"> one</ix:continuation>
<ix:nonNumeric name="t:Note" contextRef="c1" continuedAt="k1">start</ix:nonNumeric></body></html>"""
    second = '<html><body><ix:continuation id="k2" continuedAt="k1"> two</ix:continuation></body></html>'
    docs = parse_inline_xbrl_set({"a.htm": first, "b.htm": second})
    assert docs["a.htm"].xbrl_facts[0].value == "start one two"


@pytest.mark.parametrize("sources, error, message", [
    (["<html></html>"], TypeError, "mapping of attachment name to HTML"),
    ({}, ValueError, "at least one document"),
    ({"a.htm": b"<html></html>"}, TypeError, "HTML for 'a.htm' must be str, got bytes"),
    ({1: "<html></html>"}, TypeError, "Document names must be str"),
])
def test_bad_input_raises_a_useful_error(sources, error, message):
    with pytest.raises(error, match=message):
        parse_inline_xbrl_set(sources)
