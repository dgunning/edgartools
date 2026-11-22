"""
A typed dimension member filed as xsi:nil is nil, not the typed element's name.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1751

BXP's 10-Q for the quarter ended 2026-06-30 (accession 0001037540-26-000034)
has four contexts, c-348 to c-351, whose
us-gaap:StatementOfIncomeLocationBalanceAxis member is
`<us-gaap:QName.domain xsi:nil="true"/>`. The instance parser stored the
child's tag, `{http://fasb.org/us-gaap/2026}QName.domain`, as the member, and
it leaked into `dim_` columns and statement labels
("Unconsolidated Joint Ventures - {http_//fasb.org/us-gaap/2026}QName.domain").

The member is now '' with the axis kept, and `Context.nil_dimensions` records
the nil (the inline extractor records it the same way). Display labels show
"(nil)", as the SEC's rendering of the filing does. The nil check is the shared
`edgar.xmltools.is_xsi_nil` from GH #1757.

Fixture: tests/fixtures/xbrl/bxp/10q_2026q2/bxp-20260630_htm.xml, the
filing's extracted instance as published by SEC.
"""
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.xbrl import XBRL

BXP = Path("tests/fixtures/xbrl/bxp/10q_2026q2/bxp-20260630_htm.xml")
AXIS = "us-gaap:StatementOfIncomeLocationBalanceAxis"
COLUMN = "dim_us-gaap_StatementOfIncomeLocationBalanceAxis"
NIL_CONTEXTS = ["c-348", "c-349", "c-350", "c-351"]


@pytest.fixture(scope="module")
def bxp():
    return XBRL.from_files(instance_file=BXP)


def test_nil_typed_member_keeps_the_axis_with_no_value(bxp):
    for context_id in NIL_CONTEXTS:
        context = bxp.contexts[context_id]
        assert context.dimensions == {"dei:LegalEntityAxis": "bxp:UnconsolidatedJointVenturesMember", AXIS: ""}
        assert context.nil_dimensions == [AXIS]
    # No other context in the filing is nil-qualified.
    assert sum(1 for c in bxp.contexts.values() if c.nil_dimensions) == 4


def test_the_six_nil_qualified_facts_keep_their_values(bxp):
    df = bxp.facts.to_dataframe()
    rows = df[df[COLUMN].notna()].sort_values(["concept", "context_ref"])
    assert list(zip(rows["concept"], rows["context_ref"], rows["numeric_value"], rows[COLUMN], strict=True)) == [
        ("us-gaap:DepreciationAndAmortization", "c-348", -900000.0, ""),
        ("us-gaap:DepreciationAndAmortization", "c-349", -3000000.0, ""),
        ("us-gaap:DepreciationAndAmortization", "c-350", -1900000.0, ""),
        ("us-gaap:DepreciationAndAmortization", "c-351", -4400000.0, ""),
        ("us-gaap:UnrealizedGainLossOnDerivatives", "c-349", 1300000.0, ""),
        ("us-gaap:UnrealizedGainLossOnDerivatives", "c-351", 3500000.0, ""),
    ]
    assert not df.astype(str).apply(lambda col: col.str.contains("QName.domain")).any().any()


def test_nil_qualified_and_unqualified_amounts_stay_apart(bxp):
    # Q2 2026 D&A of the unconsolidated joint ventures: 29,447,000 without the
    # typed axis, -900,000 with it (R49 of the filing).
    rows = (bxp.query(include_contexts=True)
            .by_concept("us-gaap:DepreciationAndAmortization", exact=True)
            .by_dimension("dei:LegalEntityAxis", "bxp:UnconsolidatedJointVenturesMember")
            .by_custom(lambda r: r.get("period_start") == "2026-04-01" and r.get("period_end") == "2026-06-30")
            .execute())
    assert sorted((r["numeric_value"], AXIS in bxp.contexts[r["context_ref"]].dimensions) for r in rows) == [
        (-900000.0, True), (29447000.0, False)]


def test_display_label_says_nil(bxp):
    df = bxp.facts.to_dataframe()
    row = df[(df["context_ref"] == "c-348") & (df["concept"] == "us-gaap:DepreciationAndAmortization")].iloc[0]
    assert "(nil)" in row["full_dimension_label"]
    info = bxp._find_facts_for_element("us-gaap_DepreciationAndAmortization")["c-348"]["dimension_info"]
    assert [d["member_label"] for d in info if d["dimension"] == AXIS] == ["(nil)"]


INLINE = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance"><body>
<ix:header><ix:resources>
<xbrli:context id="nil"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier><xbrli:segment>
<xbrldi:typedMember dimension="us-gaap:StatementOfIncomeLocationBalanceAxis"><us-gaap:QName.domain xs:nil="true"></us-gaap:QName.domain></xbrldi:typedMember>
</xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:context id="dated"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier><xbrli:segment>
<xbrldi:typedMember dimension="t:DateAxis"><t:d>2026-09-27</t:d></xbrldi:typedMember>
</xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
</ix:resources></ix:header>
<ix:nonFraction name="t:A" contextRef="nil" unitRef="u" decimals="0">1</ix:nonFraction>
<ix:nonFraction name="t:B" contextRef="dated" unitRef="u" decimals="0">2</ix:nonFraction>
</body></html>"""


def test_inline_extractor_records_the_same_nil():
    facts = {f.concept: f for f in HTMLParser(ParserConfig()).parse(INLINE).xbrl_facts}
    assert facts["t:A"].context["dimensions"] == {AXIS: ""}
    assert facts["t:A"].context["nil_dimensions"] == [AXIS]
    assert facts["t:B"].context["dimensions"] == {"t:DateAxis": "2026-09-27"}
    assert "nil_dimensions" not in facts["t:B"].context


@pytest.mark.network
def test_bxp_income_statement_row_label():
    from edgar import find

    labels = find("0001037540-26-000034").xbrl().statements.income_statement().to_dataframe()["label"]
    assert "Unconsolidated Joint Ventures - (nil)" in set(labels)
    assert not labels.str.contains("QName.domain").any()
