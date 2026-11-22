"""XBRL footnotes are read from the inline document when the extracted instance drops them.

Bead: edgartools-s21p2 (no GitHub issue).

Great Elm Capital Corp's FY2024 10-K (0000950170-25-036517) parsed zero
footnotes. The cause is on SEC's side: the instance SEC extracted from the
inline 10-K, ``gecc-20241231_htm.xml``, has no ``footnoteLink`` at all, while
the inline document ``gecc-20241231.htm`` carries 56 ``ix:footnote`` and 56
fact-footnote ``ix:relationship`` elements. Every neighbouring GECC filing's
instance has its footnoteArcs, and edgartools read footnotes only from the
instance, so this filing lost every footnote -- and with them the
"Investment was on non-accrual status as of period end." flag that
``extract_nonaccrual`` follows to New Wilkie Energy's loan.

The fix reads ``ix:footnote``/``ix:relationship`` from the inline document,
lazily and only when the instance produced no footnotes. A filing whose instance
has footnotes is untouched (GECC's 10-Q 0000950170-24-119231 still parses 41).
"""
from types import SimpleNamespace

import pytest

from edgar.xbrl.models import Fact
from edgar.xbrl.parsers.instance import InstanceParser
from edgar.xbrl.xbrl import XBRL, XBRLAttachments
from tests._offline_filings import offline_filing

GECC_10K = "0000950170-25-036517"   # FY2024, period 2024-12-31
GECC_10Q = "0000950170-24-119231"   # period 2024-09-30, instance has footnoteArcs

NONACCRUAL_FOOTNOTE = "FNT_d8e2f309-4a8b-4d89-82e5-e4c96b9e2e90"
# us-gaap:InvestmentOwnedAtFairValue, New Wilkie Energy 1st Lien loan, 1,322 (thousands)
NEW_WILKIE_FAIR_VALUE_FACT = "F_c3251ca4-5176-494f-a999-cf14e257c311"

IX_DOC = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:us-gaap="http://fasb.org/us-gaap/2024" xml:lang="en-US">
<body>
  <ix:nonFraction id="F_1" name="us-gaap:InvestmentOwnedAtFairValue" contextRef="C_1">100</ix:nonFraction>
  <ix:nonFraction id="F_2" name="us-gaap:InvestmentOwnedAtCost" contextRef="C_1">200</ix:nonFraction>
  <div><ix:footnote id="FN_a" xml:lang="en-GB"><span>Investment was on</span> <span>non-accrual status.</span></ix:footnote></div>
  <div><ix:footnote id="FN_b" continuedAt="CONT_b"><span>Percentage of class held.</span></ix:footnote></div>
  <div><ix:continuation id="CONT_b"><span>&#8220;</span></ix:continuation></div>
  <div><ix:footnote id="FN_c"><p>Unlinked footnote.</p></ix:footnote></div>
  <ix:header><ix:hidden/><ix:resources/>
    <ix:relationship arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" fromRefs="F_1 F_2" toRefs="FN_a"/>
    <ix:relationship fromRefs="F_1" toRefs="FN_b"/>
    <ix:relationship arcrole="http://www.xbrl.org/2009/arcrole/fact-explanatoryFact" fromRefs="F_2" toRefs="F_1"/>
  </ix:header>
</body>
</html>
"""


def _parser_with_facts():
    facts = {
        "us-gaap_InvestmentOwnedAtFairValue|C_1": Fact(
            element_id="us-gaap:InvestmentOwnedAtFairValue", context_ref="C_1", value="100", fact_id="F_1"),
        "us-gaap_InvestmentOwnedAtCost|C_1": Fact(
            element_id="us-gaap:InvestmentOwnedAtCost", context_ref="C_1", value="200", fact_id="F_2"),
    }
    footnotes = {}
    parser = InstanceParser({}, facts, {}, footnotes, {}, {}, [], {})
    return parser, facts, footnotes


def test_inline_footnotes_are_read_like_a_footnote_link():
    parser, facts, footnotes = _parser_with_facts()

    assert parser.extract_inline_footnotes(IX_DOC) == 3

    assert list(footnotes) == ["FN_a", "FN_b", "FN_c"]
    assert footnotes["FN_a"].text == "Investment was on non-accrual status."
    assert footnotes["FN_a"].lang == "en-GB"
    assert footnotes["FN_a"].role == "http://www.xbrl.org/2003/role/footnote"
    assert footnotes["FN_a"].related_fact_ids == ["F_1", "F_2"]
    # A continuation carries on the same text, with no break.
    assert footnotes["FN_b"].text == "Percentage of class held.“"
    # xml:lang is inherited from <html>.
    assert footnotes["FN_b"].lang == "en-US"
    assert footnotes["FN_b"].related_fact_ids == ["F_1"]
    assert footnotes["FN_c"].related_fact_ids == []

    assert facts["us-gaap_InvestmentOwnedAtFairValue|C_1"].footnotes == ["FN_a", "FN_b"]
    # The explanatory-fact relationship links fact to fact, not to a footnote.
    assert facts["us-gaap_InvestmentOwnedAtCost|C_1"].footnotes == ["FN_a"]


def test_inline_footnotes_never_replace_instance_footnotes():
    parser, facts, footnotes = _parser_with_facts()
    footnotes["existing"] = object()

    assert parser.extract_inline_footnotes(IX_DOC) == 0
    assert list(footnotes) == ["existing"]
    assert facts["us-gaap_InvestmentOwnedAtFairValue|C_1"].footnotes == []


def test_a_document_without_fact_footnote_relationships_adds_nothing():
    parser, _, footnotes = _parser_with_facts()
    doc = IX_DOC.replace('<ix:relationship fromRefs="F_1" toRefs="FN_b"/>', '').replace(
        'arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" ', 'arcrole="http://example.com/other" ')

    assert parser.extract_inline_footnotes(doc) == 0
    assert footnotes == {}


def test_the_inline_document_is_the_one_the_instance_was_extracted_from():
    def attachment(document, document_type):
        return SimpleNamespace(document=document, document_type=document_type,
                               extension=document[document.rfind('.'):],
                               content="<xbrl></xbrl>" if document.endswith('.xml') else "")

    primary = attachment("gecc-20241231.htm", "10-K")
    exhibit = attachment("gecc-ex21_1.htm", "EX-21.1")
    instance = attachment("gecc-20241231_htm.xml", "XML")
    attachments = SimpleNamespace(documents=[primary, exhibit], data_files=[instance])

    assert XBRLAttachments(attachments).inline_document() is primary

    # A non-inline filing's instance (no _htm.xml suffix) has no source document.
    plain = SimpleNamespace(documents=[primary], data_files=[attachment("gecc-20241231.xml", "EX-101.INS")])
    assert XBRLAttachments(plain).inline_document() is None


def test_footnotes_load_from_the_inline_document_on_first_use():
    xbrl = XBRL()
    xbrl.parser.facts["us-gaap_InvestmentOwnedAtFairValue|C_1"] = Fact(
        element_id="us-gaap:InvestmentOwnedAtFairValue", context_ref="C_1", value="100", fact_id="F_1")
    reads = []

    class Document:
        document = "x.htm"

        @property
        def content(self):
            reads.append(1)
            return IX_DOC

    xbrl._inline_footnote_document = Document()

    assert [f.footnote_id for f in xbrl.get_footnotes_for_fact("F_1")] == ["FN_a", "FN_b"]
    assert len(xbrl.footnotes) == 3
    assert len(xbrl.get_facts_with_footnotes()) == 1
    assert reads == [1]


@pytest.mark.network
@pytest.mark.vcr
def test_gecc_fy2024_10k_footnotes_come_from_the_inline_document():
    from edgar.bdc import extract_nonaccrual

    filing = offline_filing(GECC_10K)

    # extract_nonaccrual parses the XBRL from individually fetched files (the
    # submission is over 20 MB) and then loads the whole submission for its
    # period of report; the second parse below reads that submission from memory.
    # Both paths are covered without fetching anything twice.
    result = extract_nonaccrual(filing)
    assert result.extraction_method == "footnote"
    assert [inv.company_name for inv in result.investments] == ["New Wilkie Energy"]
    assert result.investments[0].fair_value == 1_322_000
    assert result.investments[0].cost == 4_821_000

    xbrl = filing.xbrl()
    footnotes = xbrl.footnotes
    assert len(footnotes) == 56
    footnote = footnotes[NONACCRUAL_FOOTNOTE]
    assert footnote.text == "Investment was on non-accrual status as of period end."
    assert NEW_WILKIE_FAIR_VALUE_FACT in footnote.related_fact_ids
    assert len(footnote.related_fact_ids) == 5
    assert [f.footnote_id for f in xbrl.get_footnotes_for_fact(NEW_WILKIE_FAIR_VALUE_FACT)
            if f.footnote_id == NONACCRUAL_FOOTNOTE] == [NONACCRUAL_FOOTNOTE]


@pytest.mark.network
@pytest.mark.vcr
def test_gecc_10q_instance_footnotes_are_unchanged():
    xbrl = offline_filing(GECC_10Q).xbrl()

    assert getattr(xbrl, "_inline_footnote_document", None) is None  # no fallback armed
    footnotes = xbrl.footnotes
    assert len(footnotes) == 41
    assert footnotes["FNT_5d59c280-bf7e-419d-adf3-0ecc8aa1503a"].text == (
        "Distributions were from distributable earnings for each of the periods presented.")
