"""
Dimension members in a context's xbrli:scenario must be read, not dropped.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1763

The context parser read xbrldi members only under entity/segment, so a fact whose
StatementScenarioAxis member sat in xbrli:scenario got empty dimensions and competed
with the real undimensioned total for its period.

Partial fix: only the scenario's dimension members are read. Context still has no
scenario field, and parsers/definition.py still defaults a missing
xbrldt:contextElement to 'segment'; both remain open on the issue.

No real SEC filing is cited: EDGAR Filer Manual 6.5.3 bars xbrli:scenario in EDGAR
contexts, so the defect bites non-EDGAR instances (ESEF, hand-built, other regulators).
"""
from edgar.xbrl.parsers.coordinator import XBRLParser

CONTEXTS = """
 <xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="C2"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
  <xbrli:scenario><xbrldi:explicitMember dimension="us-gaap:StatementScenarioAxis">us-gaap:ScenarioForecastMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
 <xbrli:context id="C3"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier>
  <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">t:WestMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
  <xbrli:scenario><xbrldi:typedMember dimension="t:ScenarioIdAxis"><t:id>pro-forma</t:id></xbrldi:typedMember></xbrli:scenario></xbrli:context>
"""

INSTANCE = f"""<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:us-gaap="http://fasb.org/us-gaap/2024" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:t="http://example.com/t">
{CONTEXTS}
 <xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
 <us-gaap:Revenues contextRef="C1" unitRef="USD" decimals="0">800</us-gaap:Revenues>
 <us-gaap:Revenues contextRef="C2" unitRef="USD" decimals="0">900</us-gaap:Revenues>
</xbrli:xbrl>"""


def _parser():
    p = XBRLParser()
    p.parse_instance_content(INSTANCE)
    return p


def test_scenario_explicit_member_is_a_dimension():
    p = _parser()
    assert p.contexts["C1"].dimensions == {}
    assert p.contexts["C2"].dimensions == {"us-gaap:StatementScenarioAxis": "us-gaap:ScenarioForecastMember"}


def test_segment_and_scenario_members_are_both_read():
    assert _parser().contexts["C3"].dimensions == {
        "us-gaap:StatementBusinessSegmentsAxis": "t:WestMember",
        "t:ScenarioIdAxis": "pro-forma",
    }


def test_forecast_fact_no_longer_reads_as_the_undimensioned_total():
    from edgar.xbrl import XBRL
    x = XBRL()
    x.parser = _parser()
    found = {f["fact"].context_ref: f for f in x._find_facts_for_element("us-gaap_Revenues").values()}
    assert found["C1"]["dimension_info"] == []
    assert found["C2"]["fact"].value == "900"
    assert found["C2"]["dimension_info"] != []
