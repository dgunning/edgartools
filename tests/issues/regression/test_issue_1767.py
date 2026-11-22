"""Regression: footnoteArc arcroles were ignored when reading an XBRL instance.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1767

``InstanceParser._extract_footnotes`` never read ``xlink:arcrole``, so an arc
with any arcrole that reached a ``link:footnote`` was stored as an ordinary
footnote: the issue's ``http://example.com/arcrole/fact-other`` arc from fact2
gave fact2 ``footnotes=['fn1']``. Only fact-footnote arcs (or arcs with no
arcrole) now attach a footnote, the rule the two inline footnote readers
already applied (``edgar.xbrl.footnote_links.is_fact_footnote_arcrole``).

Partly fixed: a fact-explanatoryFact arc (fact to fact) is still not recorded
anywhere -- there is no fact-to-fact relationship model -- and is no longer
mistaken for an undefined footnote either.
"""
import pytest

from edgar.xbrl import XBRL

ISSUE_INSTANCE = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:link="http://www.xbrl.org/2003/linkbase"
 xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:us-gaap="http://fasb.org/us-gaap/2024">
 <xbrli:context id="c1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
 <us-gaap:Assets id="fact1" contextRef="c1" unitRef="usd" decimals="0">100</us-gaap:Assets>
 <us-gaap:Liabilities id="fact2" contextRef="c1" unitRef="usd" decimals="0">60</us-gaap:Liabilities>
 <us-gaap:StockholdersEquity id="fact3" contextRef="c1" unitRef="usd" decimals="0">40</us-gaap:StockholdersEquity>
 <link:footnoteLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:label="f1" xlink:href="#fact1"/>
  <link:loc xlink:type="locator" xlink:label="f2" xlink:href="#fact2"/>
  <link:loc xlink:type="locator" xlink:label="f3" xlink:href="#fact3"/>
  <link:footnote xlink:type="resource" xlink:label="fn1" xlink:role="http://www.xbrl.org/2003/role/footnote" xml:lang="en-US">Note text</link:footnote>
  <link:footnote xlink:type="resource" xlink:label="fn2" xlink:role="http://www.xbrl.org/2003/role/footnote" xml:lang="en-US">Standard note</link:footnote>
  <link:footnoteArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2009/arcrole/fact-explanatoryFact" xlink:from="f1" xlink:to="f2"/>
  <link:footnoteArc xlink:type="arc" xlink:arcrole="http://example.com/arcrole/fact-other" xlink:from="f2" xlink:to="fn1"/>
  <link:footnoteArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" xlink:from="f3" xlink:to="fn2"/>
 </link:footnoteLink>
</xbrli:xbrl>"""


def _facts(xbrl):
    return {fact.fact_id: fact for fact in xbrl.parser.facts.values()}


@pytest.mark.fast
def test_a_custom_arcrole_is_not_an_ordinary_footnote(tmp_path):
    path = tmp_path / "fixture.xml"
    path.write_text(ISSUE_INSTANCE, encoding="utf-8")
    xbrl = XBRL.from_files(instance_file=path)
    facts = _facts(xbrl)

    # The fact-other arc no longer makes fn1 a footnote of fact2.
    assert facts["fact2"].footnotes == []
    assert xbrl.footnotes["fn1"].related_fact_ids == []
    # The resource itself is still read.
    assert xbrl.footnotes["fn1"].text == "Note text"

    # The fact-to-fact arc attaches nothing to either fact.
    assert facts["fact1"].footnotes == []

    # A fact-footnote arc in the same link still attaches.
    assert facts["fact3"].footnotes == ["fn2"]
    assert xbrl.footnotes["fn2"].related_fact_ids == ["fact3"]
    assert [fn.text for fn in xbrl.get_footnotes_for_fact("fact3")] == ["Standard note"]

    # No amount changes.
    assert [facts[f].value for f in ("fact1", "fact2", "fact3")] == ["100", "60", "40"]


@pytest.mark.fast
def test_an_arc_without_an_arcrole_still_reads_as_a_footnote(tmp_path):
    """Permissive legacy input: the attribute is required, but older filings omit it."""
    instance = ISSUE_INSTANCE.replace(
        'xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" ', '')
    path = tmp_path / "fixture.xml"
    path.write_text(instance, encoding="utf-8")
    xbrl = XBRL.from_files(instance_file=path)
    assert _facts(xbrl)["fact3"].footnotes == ["fn2"]


@pytest.mark.fast
def test_npk_standard_footnote_still_attaches():
    """National Presto 10-Q Q1 2026, 0001437749-26-017365: SG&A of $7,821,000
    (c146051379) carries "Excludes depreciation and amortization." through a
    fact-footnote arc, read by hand from npk20260331_10q_htm.xml."""
    from pathlib import Path

    fixture = (Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "npk" / "10q_2026q1"
               / "npk20260331_10q_htm.xml")
    xbrl = XBRL.from_files(instance_file=fixture)
    fact = _facts(xbrl)["c146051379"]
    assert fact.element_id == "us-gaap:SellingGeneralAndAdministrativeExpense"
    assert fact.value == "7821000"
    assert [fn.text for fn in xbrl.get_footnotes_for_fact("c146051379")] == [
        "Excludes depreciation and amortization."]
