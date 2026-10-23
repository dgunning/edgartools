"""Regression test for GH #1689: synthesized totals added members in different units.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1689

``XBRL._compute_synthetic_total()`` builds a plain row from one axis's members
when a concept has no undimensioned fact. It summed the members whatever their
unit, and returned the first member's fact and context as the source of the sum,
with nothing marking the value as computed. A mixed-unit axis now gives no
total, and a sum is returned as computed, with no borrowed fact or context and
the precision of its least precise component.

Ground truth: Microsoft 10-K for FY2024 (0000950170-24-087843), role
DisclosureComponentsOfLongtermDebtParentheticalDetail. us-gaap:DebtInstrumentFaceAmount
at 2024-06-30 is filed only per debt instrument, thirteen facts in U_USD and one
of 4,100,000,000 in U_EUR. The plain row read 104,900,000,000 "USD", the EUR
amount included.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.xbrl import XBRL

MSFT_10K = Path("tests/fixtures/xbrl/msft/10k_2024")
MSFT_DEBT_ROLE = ("http://www.microsoft.com/20240630/taxonomy/role/"
                  "DisclosureComponentsOfLongtermDebtParentheticalDetail")


def _facts(axis, rows):
    out = []
    for cid, member, value, unit, decimals in rows:
        fact = SimpleNamespace(numeric_value=value, unit_ref=unit, context_ref=cid,
                               decimals=decimals, fact_id=f"fact-{cid}")
        out.append((cid, {"fact": fact, "dimension_info": [{"dimension": axis, "member": member}]}))
    return out


@pytest.mark.fast
def test_members_in_different_currencies_are_not_added():
    facts = _facts("srt:CurrencyAxis", [
        ("c1", "currency:MXN", 327e6, "mxn", "-6"),
        ("c2", "currency:USD", 19e6, "usd", "-6")])
    assert XBRL()._compute_synthetic_total(facts, "us-gaap_DebtInstrumentFaceAmount") is None


@pytest.mark.fast
def test_a_sum_is_marked_computed_and_borrows_no_source():
    facts = _facts("srt:StatementGeographicalAxis", [
        ("c1", "srt:AmericasMember", 300e6, "usd", "-6"),
        ("c2", "srt:EuropeMember", 100e6, "usd", "-5")])
    result = XBRL()._compute_synthetic_total(facts, "us-gaap_Revenues")
    assert result["total"] == 400e6
    assert result["computed"] is True
    assert result["fact"] is None and result["context_id"] is None
    assert result["component_context_ids"] == ["c1", "c2"]
    assert result["unit_ref"] == "usd"
    assert result["decimals"] == -6  # the least precise component


@pytest.mark.fast
def test_a_single_filed_member_is_not_computed():
    facts = _facts("srt:StatementGeographicalAxis", [("c1", "srt:AmericasMember", 300e6, "usd", "-6")])
    result = XBRL()._compute_synthetic_total(facts, "us-gaap_Revenues")
    assert result["computed"] is False
    assert result["context_id"] == "c1"
    assert result["fact"].fact_id == "fact-c1"


@pytest.mark.fast
def test_microsoft_face_amount_does_not_add_euros_to_dollars():
    xbrl = XBRL.from_directory(MSFT_10K)
    query = xbrl.facts.query().by_concept("us-gaap:DebtInstrumentFaceAmount", exact=True).to_dataframe()
    assert query.loc[query["unit_ref"] == "U_EUR", "numeric_value"].tolist() == [4_100_000_000.0]

    plain = [row for row in xbrl.get_statement(MSFT_DEBT_ROLE)
             if row["concept"] == "us-gaap_DebtInstrumentFaceAmount" and not row.get("is_dimension")]
    assert len(plain) == 1
    assert "instant_2024-06-30" not in plain[0]["values"]  # was 104,900,000,000
