"""
Inline XBRL facts carry their xsi:nil state, found by namespace, not prefix.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1757

`Document.xbrl_facts` had no nil field and never read the nil attribute, so a
fact filed nil came back as `value == ''` with nothing telling it apart from an
element with empty content. AAR CORP's 10-Q 0001104659-26-111786 binds the XML
Schema instance namespace to `xs` as well as `xsi` and files its two
`us-gaap:PreferredStockValue` facts as `xs:nil="true"`.

`XBRLFact.is_nil` now mirrors `Fact.is_nil` on the instance path (#1254), and
both paths read it through one helper, `edgar.xmltools.is_xsi_nil`, which
resolves the prefix against the in-scope namespace declarations. Nil is read
before the value is interpreted, so a format such as `fixed-zero` cannot turn a
nil fact into an amount.
"""
from pathlib import Path

import pytest
from lxml import etree

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.types import XBRLFact
from edgar.xbrl import XBRL

IBM = Path("tests/fixtures/xbrl/ibm/10k_2024")

XSI = "http://www.w3.org/2001/XMLSchema-instance"
TR4 = "http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"

SYNTHETIC = f"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xsi="{XSI}" xmlns:xs="{XSI}"
 xmlns:other="http://example.com/not-xsi" xmlns:ixt="{TR4}"><body>
<ix:nonFraction name="t:XsPrefix" contextRef="c" unitRef="u" xs:nil="true"></ix:nonFraction>
<ix:nonFraction name="t:XsiOne" contextRef="c" unitRef="u" xsi:nil=" 1 "></ix:nonFraction>
<ix:nonFraction name="t:XsiFalse" contextRef="c" unitRef="u" decimals="0" xsi:nil="false">5</ix:nonFraction>
<ix:nonFraction name="t:WrongNamespace" contextRef="c" unitRef="u" other:nil="true"></ix:nonFraction>
<ix:nonFraction name="t:Unbound" contextRef="c" unitRef="u" nope:nil="true"></ix:nonFraction>
<div xmlns:n="{XSI}"><ix:nonFraction name="t:LocalBinding" contextRef="c" unitRef="u" n:nil="true"></ix:nonFraction></div>
<ix:nonFraction name="t:NilFixedZero" contextRef="c" unitRef="u" format="ixt:fixed-zero" scale="6" sign="-" xsi:nil="true"></ix:nonFraction>
<ix:nonFraction name="t:FixedZero" contextRef="c" unitRef="u" decimals="0" format="ixt:fixed-zero">-</ix:nonFraction>
</body></html>"""


def _facts(html):
    return {f.concept: f for f in HTMLParser(ParserConfig()).parse(html).xbrl_facts}


def test_nil_is_read_by_namespace_whatever_the_prefix():
    facts = _facts(SYNTHETIC)
    nil = {name for name, fact in facts.items() if fact.is_nil}
    assert nil == {"t:XsPrefix", "t:XsiOne", "t:LocalBinding", "t:NilFixedZero"}
    assert facts["t:XsiFalse"].numeric_value == 5.0


def test_nil_is_not_transformed_scaled_or_signed():
    facts = _facts(SYNTHETIC)
    nil = facts["t:NilFixedZero"]
    assert (nil.value, nil.numeric_value, nil.is_numeric) == ("", None, False)
    # The format, scale and sign stay as filed metadata.
    assert (nil.format, nil.scale, nil.sign) == ("ixt:fixed-zero", "6", "-")
    # The same format on a non-nil fact still maps to zero.
    assert (facts["t:FixedZero"].value, facts["t:FixedZero"].numeric_value) == ("0", 0.0)
    assert nil.to_dict()["is_nil"] is True
    assert facts["t:FixedZero"].to_dict()["is_nil"] is False


def test_fact_model_default_and_nil_has_no_numeric_value():
    assert XBRLFact(concept="us-gaap:Revenues", value="1").is_nil is False
    assert XBRLFact(concept="us-gaap:Revenues", value="123", unit_ref="usd", is_nil=True).numeric_value is None


def test_helper_reads_expanded_name_on_an_xml_tree():
    from edgar.xmltools import is_xsi_nil

    root = etree.fromstring(f'<r xmlns:xs="{XSI}"><a xs:nil="true"/><b xs:nil="0"/><c/></r>')
    assert [is_xsi_nil(child) for child in root] == [True, False, False]


def test_ibm_inline_and_instance_paths_agree_on_nil():
    # IBM FY2024 10-K, accession 0000051143-25-000015: the inline document and
    # its extracted instance in the tracked fixture. Commitments and
    # contingencies (f-424, c-73) is filed xsi:nil on the balance sheet.
    inline = parse_html((IBM / "ix.htm").read_text(encoding="utf-8")).xbrl_facts
    inline_nil = sorted((f.concept, f.context_ref) for f in inline if f.is_nil)
    xbrl = XBRL.from_directory(IBM)
    instance_nil = sorted((f.element_id.replace("_", ":", 1), f.context_ref)
                          for f in xbrl._facts.values() if f.is_nil)
    assert inline_nil == instance_nil == [
        ("ibm:BusinessAcquisitionPurchasePriceAllocationGoodwillExpectedTaxDeductiblePercent", "c-362"),
        ("us-gaap:CommitmentsAndContingencies", "c-73"),
        ("us-gaap:CommitmentsAndContingencies", "c-74"),
        ("us-gaap:ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsExercisesInPeriodTotalIntrinsicValue",
         "c-875"),
    ]
    commitments = next(f for f in inline
                       if f.concept == "us-gaap:CommitmentsAndContingencies" and f.context_ref == "c-73")
    assert (commitments.value, commitments.numeric_value, commitments.unit_ref) == ("", None, "usd")
    assert sum(1 for f in inline if not f.is_nil) == len(inline) - 4


@pytest.mark.network
def test_aar_preferred_stock_filed_with_xs_prefix_is_nil():
    from edgar import find

    filing = find("0001104659-26-111786")
    facts = [f for f in filing.parse().xbrl_facts if f.concept == "us-gaap:PreferredStockValue"]
    assert sorted((f.context_ref, f.is_nil, f.value, f.numeric_value) for f in facts) == [
        ("As_Of_5_31_2026_VLLYpglH9UmKSlBYcpXZIg", True, "", None),
        ("As_Of_8_31_2026_RKa0U921gE29Ycy6p0__VQ", True, "", None),
    ]
