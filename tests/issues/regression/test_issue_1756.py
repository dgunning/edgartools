"""Regression: inline-parsed XBRLFact objects had no fact id and lost their footnotes.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1756

``edgar.documents`` never read a fact's ``id`` and never read ``ix:footnote``
or ``ix:relationship``, so ``Document.xbrl_facts`` could not be joined to the
XBRL instance path's facts and lost every fact footnote. In Bristol Myers
Squibb's Q1 2026 10-Q (0000014272-26-000010) both cost-of-goods facts, f-57
($3,421M) and f-58 ($3,033M), carry fn-1 "Excludes amortization of acquired
intangible assets" in the filing and lost it here.

Facts now carry ``fact_id`` and ``footnotes`` (footnote ids), and
``Document.xbrl_footnotes`` maps each id to the same ``Footnote`` model
``XBRL.footnotes`` uses. The relationship rule, footnote text and language are
the instance parser's own (``edgar.xbrl.footnote_links``), so both paths agree.
"""
from pathlib import Path

import pytest

from edgar.documents import parse_html
from edgar.xbrl.parsers.instance import InstanceParser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"
META_10K = FIXTURES / "meta" / "10k" / "meta-10-k-2025-01-30.html"
LNG_10K = FIXTURES / "lng" / "10k" / "lng-10-k-2026-02-26.html"


def _facts_by_id(doc):
    return {fact.fact_id: fact for fact in doc.xbrl_facts}


@pytest.mark.fast
def test_meta_dividend_facts_keep_their_id_and_footnote():
    """META 10-K FY2024, 0001326801-25-000017: the two DividendsCommonStock
    facts ($5,121M) carry fn-1, read by hand from meta-20241231.htm."""
    doc = parse_html(META_10K.read_text(encoding="utf-8"))
    facts = _facts_by_id(doc)

    for fact_id, context_ref in (("f-239", "c-37"), ("f-240", "c-1")):
        fact = facts[fact_id]
        assert fact.concept == "us-gaap:DividendsCommonStock"
        assert fact.context_ref == context_ref
        assert fact.value == "5121000000"
        assert fact.footnotes == ["fn-1"]

    footnote = doc.xbrl_footnotes["fn-1"]
    assert footnote.footnote_id == "fn-1"
    assert footnote.text == "Our dividend program began in the first quarter of 2024."
    assert footnote.lang == "en-US"
    assert footnote.role == "http://www.xbrl.org/2003/role/footnote"
    assert footnote.related_fact_ids == ["f-239", "f-240"]

    # A footnote is a resource: it is not in the fact list, and a fact with no
    # relationship has an empty list rather than None.
    assert all(fact.concept for fact in doc.xbrl_facts)
    assert sum(1 for fact in doc.xbrl_facts if fact.footnotes) == 2
    assert facts["f-1"].footnotes == []
    assert facts["f-239"].to_dict()["fact_id"] == "f-239"
    assert facts["f-239"].to_dict()["footnotes"] == ["fn-1"]


@pytest.mark.fast
@pytest.mark.parametrize("path", [META_10K, LNG_10K], ids=["meta", "lng"])
def test_documents_path_agrees_with_the_instance_parsers_inline_reader(path):
    """One rule, two trees: the HTML tree and the XML tree give the same footnotes."""
    html = path.read_text(encoding="utf-8")
    doc = parse_html(html)

    reference = InstanceParser({}, {}, {}, {}, {}, {}, [], {})
    reference.extract_inline_footnotes(html)

    def view(footnotes):
        return {key: (fn.text, fn.lang, fn.role, sorted(fn.related_fact_ids))
                for key, fn in footnotes.items()}

    assert view(doc.xbrl_footnotes) == view(reference.footnotes)
    assert len(doc.xbrl_footnotes) == {"meta": 1, "lng": 51}[path.parts[-3]]


INLINE = """<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2024" xml:lang="en-US">
<body><div style="display:none"><ix:header><ix:resources>
<xbrli:context id="c1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier>
</xbrli:entity><xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:resources>
<ix:relationship fromRefs="a" toRefs="fn1"/>
<ix:relationship arcrole="http://www.xbrl.org/2009/arcrole/fact-explanatoryFact" fromRefs="b" toRefs="a"/>
<ix:relationship arcrole="http://example.com/arcrole/other" fromRefs="b" toRefs="fn1"/>
<ix:relationship fromRefs="b" toRefs="missing"/>
</ix:header></div>
<p><ix:nonFraction id="a" name="us-gaap:Assets" contextRef="c1" unitRef="usd" decimals="0">100</ix:nonFraction>
<ix:nonFraction id="b" name="us-gaap:Liabilities" contextRef="c1" unitRef="usd" decimals="0">60</ix:nonFraction>
<ix:nonFraction name="us-gaap:Equity" contextRef="c1" unitRef="usd" decimals="0">40</ix:nonFraction></p>
<p><ix:footnote id="fn1">First <span>part</span></ix:footnote></p>
</body></html>"""


@pytest.mark.fast
def test_only_fact_footnote_relationships_to_a_footnote_attach():
    """An absent arcrole is fact-footnote; another arcrole or a target that is
    not a footnote is not an ordinary footnote and attaches nothing."""
    doc = parse_html(INLINE)
    facts = {fact.concept: fact for fact in doc.xbrl_facts}

    assert facts["us-gaap:Assets"].fact_id == "a"
    assert facts["us-gaap:Assets"].footnotes == ["fn1"]
    assert facts["us-gaap:Liabilities"].footnotes == []
    # No id filed: none is invented.
    assert facts["us-gaap:Equity"].fact_id is None

    footnote = doc.xbrl_footnotes["fn1"]
    assert footnote.text == "First part"
    assert footnote.role == "http://www.xbrl.org/2003/role/footnote"
    assert footnote.lang == "en-US"
    assert footnote.related_fact_ids == ["a"]


@pytest.mark.fast
def test_a_document_without_footnotes_has_an_empty_lookup():
    doc = parse_html("<html><body><p>No inline XBRL here.</p></body></html>")
    assert doc.xbrl_footnotes == {}


@pytest.mark.network
@pytest.mark.vcr
def test_bmy_cost_of_goods_keeps_its_amortization_footnote():
    """The reported filing: BMY 10-Q Q1 2026, 0000014272-26-000010."""
    from edgar import find

    doc = parse_html(find("0000014272-26-000010").html())
    facts = _facts_by_id(doc)

    for fact_id, context_ref, value in (("f-57", "c-1", "3421000000"),
                                        ("f-58", "c-15", "3033000000")):
        fact = facts[fact_id]
        assert fact.concept == "us-gaap:CostOfGoodsAndServicesSold"
        assert fact.context_ref == context_ref
        assert fact.value == value
        assert fact.footnotes == ["fn-1"]

    footnote = doc.xbrl_footnotes["fn-1"]
    assert footnote.text == "Excludes amortization of acquired intangible assets"
    assert footnote.related_fact_ids == ["f-57", "f-58"]
    assert list(doc.xbrl_footnotes) == ["fn-1"]
