"""
A nil fact must not outrank a valued duplicate in precision ranking.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1750

A nil numeric fact parses as value '', numeric_value None, decimals None. A missing
decimals scored 0, above a valued duplicate's decimals="-6" (-6), so the blank fact won.
"""
from edgar.xbrl import XBRL
from edgar.xbrl.parsers.coordinator import XBRLParser

INSTANCE = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:us-gaap="http://fasb.org/us-gaap/2024" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
 <xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
 <us-gaap:Liabilities contextRef="C1" unitRef="usd" xsi:nil="true"/>
 <us-gaap:Liabilities contextRef="C1" unitRef="usd" decimals="-6">500</us-gaap:Liabilities>
</xbrli:xbrl>"""


def _facts():
    p = XBRLParser()
    p.parse_instance_content(INSTANCE)
    return list(p.facts.values())


def test_nil_fact_scores_below_valued_fact():
    nil, valued = _facts()
    assert XBRL._get_fact_precision(nil) < XBRL._get_fact_precision(valued) == -6


def test_valued_fact_selected_over_nil_in_either_order():
    facts = _facts()
    for ordered in (facts, facts[::-1]):
        best = XBRL._select_most_precise_fact(ordered)
        assert (best.value, best.numeric_value, best.decimals) == ('500', 500.0, '-6')


def test_precision_ordering_otherwise_unchanged():
    class F:
        def __init__(self, decimals, value='1', numeric_value=1.0):
            self.decimals, self.value, self.numeric_value = decimals, value, numeric_value

    assert XBRL._get_fact_precision(F('INF')) == 1_000_000
    assert XBRL._get_fact_precision(F(None)) == 0
    assert XBRL._get_fact_precision(F('-3')) == -3
    assert XBRL._get_fact_precision(F('bad')) == 0
    assert XBRL._select_most_precise_fact([F('-6'), F('INF'), F(0)]).decimals == 'INF'
