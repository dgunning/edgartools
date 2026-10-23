"""
Inline ix:nonNumeric identifiers must not be classified as numeric facts.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1755

XBRLFact.numeric_value called float() on any value, so an ix:nonNumeric CIK such as
"0000051143" came back numeric as 51143.0. Only a fact with a unit (ix:nonFraction)
is numeric now, the rule the instance parser already applies.
"""
from pathlib import Path

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.types import XBRLFact

SYNTHETIC = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
<ix:nonNumeric name="t:Identifier" contextRef="c">0000000001</ix:nonNumeric>
<ix:nonFraction name="t:Count" contextRef="c" unitRef="u" decimals="0">1</ix:nonFraction>
</body></html>"""


def test_synthetic_identifier_is_not_numeric():
    facts = {f.concept: f for f in HTMLParser(ParserConfig()).parse(SYNTHETIC).xbrl_facts}
    ident, count = facts["t:Identifier"], facts["t:Count"]
    assert (ident.value, ident.is_numeric, ident.numeric_value) == ("0000000001", False, None)
    assert (count.is_numeric, count.numeric_value) == (True, 1.0)
    assert ident.to_dict()["is_numeric"] is False


def test_unitless_fact_model():
    assert XBRLFact(concept="dei:EntityCentralIndexKey", value="0000051143").numeric_value is None
    assert XBRLFact(concept="us-gaap:Revenues", value="1,234", unit_ref="usd").numeric_value == 1234.0


def test_ibm_cover_cik_is_text_and_share_count_is_numeric():
    # IBM FY2024 10-K primary document (tests/fixtures/xbrl/ibm/10k_2024/ibm-20241231.htm)
    html = Path("tests/fixtures/xbrl/ibm/10k_2024/ibm-20241231.htm").read_text(encoding="utf-8")
    facts = parse_html(html).xbrl_facts
    cik = next(f for f in facts if f.concept == "dei:EntityCentralIndexKey")
    shares = next(f for f in facts if f.concept == "dei:EntityCommonStockSharesOutstanding")
    assert (cik.value, cik.is_numeric) == ("0000051143", False)
    assert (shares.unit_ref, shares.numeric_value) == ("shares", 927_264_332.0)
    assert not any(f.is_numeric and not f.unit_ref for f in facts)
