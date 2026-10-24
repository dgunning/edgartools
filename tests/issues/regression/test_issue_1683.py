"""Regression test for GH #1683: statements summed per-share and percentage amounts.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1683

When a concept has no undimensioned fact, ``XBRL._compute_synthetic_total()``
adds the members of one axis into a plain row. Its guard against ratios read
the element catalog's data type, which is only known for the filer's own
extension concepts, so us-gaap:EarningsPerShareBasic passed untyped and
Constellation Brands' FY2021 basic EPS came out as 19.92: Class A 10.44 plus
Class B 9.48. The guard now reads the facts' units, which every concept has.

Ground truth: Constellation Brands 10-K for FY ended 2022-02-28
(0000016918-22-000069), basic EPS filed per class only: FY2021 Class A 10.44,
Class B 9.48 (unit usdPerShare); no undimensioned EPS fact.
"""
import math
from types import SimpleNamespace

import pytest

from edgar import find
from edgar.xbrl import XBRL


def _facts(axis, rows):
    out = []
    for cid, member, value, unit in rows:
        fact = SimpleNamespace(numeric_value=value, unit_ref=unit, context_ref=cid,
                               decimals="2", fact_id=f"fact-{cid}")
        out.append((cid, {"fact": fact, "dimension_info": [{"dimension": axis, "member": member}]}))
    return out


def _xbrl_with_units():
    xbrl = XBRL()
    xbrl.parser.units.update({
        "usd": {"type": "simple", "measure": "iso4217:USD"},
        "usdPerShare": {"type": "divide", "numerator": ["iso4217:USD"], "denominator": ["shares"]},
        "number": {"type": "simple", "measure": "xbrli:pure"},
    })
    return xbrl


@pytest.mark.fast
def test_per_share_members_are_not_summed():
    xbrl = _xbrl_with_units()
    facts = _facts("us-gaap:StatementClassOfStockAxis", [
        ("c1", "us-gaap:CommonClassAMember", 10.44, "usdPerShare"),
        ("c2", "us-gaap:CommonClassBMember", 9.48, "usdPerShare")])
    assert xbrl._compute_synthetic_total(facts, "us-gaap_EarningsPerShareBasic") is None


@pytest.mark.fast
def test_percentage_members_are_not_summed():
    xbrl = _xbrl_with_units()
    facts = _facts("srt:ProductOrServiceAxis", [
        ("c1", "kmx:UsedVehicleSalesMember", 0.8, "number"),
        ("c2", "kmx:WholesaleVehicleSalesMember", 0.15, "number")])
    assert xbrl._compute_synthetic_total(facts, "kmx_ItemAsPercentOfNetSalesAndOperatingRevenues") is None


@pytest.mark.fast
def test_currency_members_still_sum():
    xbrl = _xbrl_with_units()
    facts = _facts("srt:ProductOrServiceAxis", [
        ("c1", "us-gaap:ServiceMember", 52_677e6, "usd"),
        ("c2", "us-gaap:ProductMember", 6_089e6, "usd")])
    assert xbrl._compute_synthetic_total(facts, "us-gaap_CostOfGoodsAndServicesSold")["total"] == 58_766e6


@pytest.mark.network
def test_constellation_brands_eps_has_no_invented_total():
    xbrl = find("0000016918-22-000069").xbrl()
    df = xbrl.statements.income_statement().to_dataframe(presentation=False, standard=False)
    basic = df[df["concept"] == "us-gaap_EarningsPerShareBasic"]
    plain = basic[basic["dimension"] == False]  # noqa: E712
    classes = basic[basic["dimension"] == True]  # noqa: E712
    assert len(plain) == 1
    assert math.isnan(plain["2021-02-28 (FY)"].iloc[0])  # was 19.92
    assert sorted(classes["2021-02-28 (FY)"].tolist()) == [9.48, 10.44]
