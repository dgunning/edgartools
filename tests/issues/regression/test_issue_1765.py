"""
Facts reported with @precision get the decimals it implies, and unknown accuracy
no longer outranks a stated one.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1765

XBRL 2.1 §4.6.6 has a consumer infer decimals from @precision:
``decimals = precision - floor(log10(abs(value))) - 1``. The instance parser
read only @decimals, so a precision fact carried ``decimals=None``, and duplicate
selection scored None as 0, above every negative decimals. A fact stated to two
significant digits beat the same fact stated to the million.

The EDGAR Filer Manual forbids @precision on SEC facts, so no SEC filing uses
it. The first test takes a real instance, IBM's 10-K for fiscal 2024 (accession
0000051143-25-000015, the tracked EDGAR-extracted instance
``tests/fixtures/xbrl/ibm/10k_2024/ibm-20241231_htm.xml``), restates its filed
total assets of 137,175,000,000 at 2024-12-31 (fact f-394, decimals -6) with
the equivalent precision="6", and adds a duplicate rounded to two significant
digits. The balance sheet must keep the filed amount. The other tests are the
issue's minimal synthetic instance and the §4.6.6 arithmetic.
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import decimals_from_precision

IBM_DIR = Path(__file__).parents[2] / "fixtures" / "xbrl" / "ibm" / "10k_2024"
FILED = '<us-gaap:Assets contextRef="c-73" decimals="-6" id="f-394" unitRef="usd">137175000000</us-gaap:Assets>'


@pytest.fixture(scope="module")
def ibm_with_precision(tmp_path_factory):
    text = (IBM_DIR / "ibm-20241231_htm.xml").read_text(encoding="utf-8")
    assert FILED in text
    restated = (
        '<us-gaap:Assets contextRef="c-73" precision="2" id="f-394-p2" unitRef="usd">140000000000</us-gaap:Assets>'
        '<us-gaap:Assets contextRef="c-73" precision="6" id="f-394" unitRef="usd">137175000000</us-gaap:Assets>'
    )
    path = tmp_path_factory.mktemp("ibm") / "ibm-20241231_htm.xml"
    path.write_text(text.replace(FILED, restated), encoding="utf-8")
    return XBRL.from_files(
        instance_file=path,
        presentation_file=IBM_DIR / "ibm-20241231_pre.xml",
        label_file=IBM_DIR / "ibm-20241231_lab.xml",
        calculation_file=IBM_DIR / "ibm-20241231_cal.xml",
    )


def test_ibm_total_assets_keep_the_more_precise_fact(ibm_with_precision):
    rows = ibm_with_precision.get_statement("BalanceSheet")
    assets = next(r for r in rows if r["concept"] == "us-gaap_Assets" and not r.get("is_dimension"))
    assert assets["values"]["instant_2024-12-31"] == 137_175_000_000
    assert assets["decimals"]["instant_2024-12-31"] == -6
    assert assets["values"]["instant_2023-12-31"] == 135_241_000_000


def test_ibm_precision_is_kept_and_decimals_inferred(ibm_with_precision):
    facts = {f.fact_id: f for f in ibm_with_precision._facts.values() if f.fact_id in ("f-394", "f-394-p2")}
    assert (facts["f-394"].precision, facts["f-394"].decimals) == ("6", "-6")
    assert (facts["f-394-p2"].precision, facts["f-394-p2"].decimals) == ("2", "-10")


def test_issue_synthetic_instance(tmp_path):
    instance = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2024"
  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
 <xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
 <us-gaap:Assets contextRef="C1" unitRef="usd" precision="2">2000000</us-gaap:Assets>
 <us-gaap:Assets contextRef="C1" unitRef="usd" decimals="-3">2000000</us-gaap:Assets>
 <us-gaap:Liabilities contextRef="C1" unitRef="usd" precision="0">5</us-gaap:Liabilities>
</xbrli:xbrl>"""
    path = tmp_path / "instance.xml"
    path.write_text(instance, encoding="utf-8")
    x = XBRL.from_files(instance_file=path)
    assets = [f for f in x._facts.values() if f.element_id == "us-gaap:Assets"]
    assert sorted(f.decimals for f in assets) == ["-3", "-5"]
    assert XBRL._select_most_precise_fact(assets).decimals == "-3"
    # precision="0": nothing is known about the accuracy (§4.6.4). It never wins.
    liabilities = next(f for f in x._facts.values() if f.element_id == "us-gaap:Liabilities")
    assert (liabilities.precision, liabilities.decimals) == ("0", None)
    assert XBRL._get_fact_precision(liabilities) < XBRL._get_fact_precision(assets[0])


@pytest.mark.parametrize("precision,value,expected", [
    ("2", "2000000", -5),
    ("6", "137175000000", -6),
    ("3", "0.012345", 4),
    ("4", "-1234.5", 0),
    ("INF", "1.5", "INF"),
    ("5", "0", "INF"),
    ("0", "2000000", None),
    ("x", "2000000", None),
    ("3", "n/a", None),
])
def test_decimals_from_precision(precision, value, expected):
    assert decimals_from_precision(precision, value) == expected


def test_inline_reader_keeps_precision():
    from edgar.documents import parse_html
    html = (
        '<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance">'
        '<body><div style="display:none"><ix:header><ix:resources>'
        '<xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1'
        '</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2024-12-31</xbrli:instant>'
        '</xbrli:period></xbrli:context><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure>'
        '</xbrli:unit></ix:resources></ix:header></div>'
        '<p>Assets <ix:nonFraction name="us-gaap:Assets" contextRef="C1" unitRef="usd" precision="2" '
        'format="ixt:num-dot-decimal">2,000,000</ix:nonFraction></p></body></html>')
    fact = next(f for f in parse_html(html).xbrl_facts if f.concept == "us-gaap:Assets")
    assert (fact.value, fact.precision, fact.decimals) == ("2000000", "2", None)
    assert fact.to_dict()["precision"] == "2"
