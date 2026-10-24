"""Regression test for GH #1703: synthesized plain rows summed overlapping members.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1703

When a concept has no undimensioned fact, ``XBRL._compute_synthetic_total()``
adds one axis's members into the plain row. In DETAILED view (the default for
``to_dataframe()``) and on statements built without dimensions it took every
fact of the concept, from every disclosure, so a consolidated figure was added
to the parent-only figure of the same concept. The plain row now adds only the
members the statement's own presentation tree declares, in every view; facts on
other axes count only when the statement declares none of the concept's axes,
and then never on entity, consolidation, scenario, restatement or related-party
axes.

Ground truth:
- Deutsche Bank 20-F FY2024 (0001159508-25-000020), consolidated statement of
  cash flows (R12): net cash from operating activities 2024 EUR -28,584 million
  (dei:LegalEntityAxis = db:consolidatedBankEntityMember); the parent-only note
  (R257) files EUR -29,917 million for DeutscheBankAGMember. The DETAILED plain
  row read -58,501 million. Total liabilities 2024-12-31 EUR 1,309,168 million (R9).
- JPMorgan Chase 10-K FY2025 (0001628280-26-008131): consolidated VIE memo
  "All other liabilities" 691 million at 2025-12-31 (R5); DETAILED read 14,347
  million (parent company 13,656 plus 691). RepaymentsOfShortTermDebt has only
  srt:ParentCompanyMember facts for 2025 and 2024, which are not the
  consolidated line.
- Microsoft 10-K FY2024 (fixture tests/fixtures/xbrl/msft/10k_2024): the
  balance sheet presents no equity axis, and its 2021-06-30 equity components
  include the AOCI total (1,822 million) beside its three parts; the plain row
  read 143,810 million against 141,988 million filed. A subtotal beside its
  parts on an undeclared axis now leaves the row blank.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar import find
from edgar.xbrl import XBRL

MSFT_10K = Path("tests/fixtures/xbrl/msft/10k_2024")


def _fact(cid, axis, member, value):
    return (cid, {"fact": SimpleNamespace(numeric_value=value, unit_ref="eur", context_ref=cid, decimals="-6"),
                  "dimension_info": [{"dimension": axis, "member": member}]})


DB_FACTS = [_fact("c1", "dei:LegalEntityAxis", "db:consolidatedBankEntityMember", -28_584e6),
            _fact("c2", "dei:LegalEntityAxis", "db:DeutscheBankAGMember", -29_917e6)]


@pytest.mark.fast
def test_only_the_statements_own_members_are_added():
    declared = {"dei_LegalEntityAxis": {"db_consolidatedBankEntityMember": None}}
    result = XBRL()._compute_synthetic_total(DB_FACTS, "ifrs-full_CashFlowsFromUsedInOperatingActivities", declared)
    assert result["total"] == -28_584e6
    assert result["computed"] is False


@pytest.mark.fast
def test_entity_members_are_never_summed_without_a_declared_scope():
    assert XBRL()._compute_synthetic_total(DB_FACTS, "ifrs-full_CashFlowsFromUsedInOperatingActivities") is None


@pytest.mark.fast
def test_declared_axis_is_preferred_over_a_larger_note_axis():
    facts = DB_FACTS[:1] + [_fact(f"s{i}", "ifrs-full:StructuredEntitiesAxis", f"db:Entity{i}Member", 1e6)
                            for i in range(5)]
    declared = {"dei_LegalEntityAxis": {"db_consolidatedBankEntityMember": None}}
    result = XBRL()._compute_synthetic_total(facts, "ifrs-full_Liabilities", declared)
    assert result["total"] == -28_584e6


@pytest.mark.fast
def test_an_undeclared_additive_axis_still_sums():
    facts = [_fact("c1", "srt:ProductOrServiceAxis", "us-gaap:ServiceMember", 52_677e6),
             _fact("c2", "srt:ProductOrServiceAxis", "us-gaap:ProductMember", 6_089e6)]
    assert XBRL()._compute_synthetic_total(facts, "us-gaap_CostOfGoodsAndServicesSold")["total"] == 58_766e6
    # Three members, none the sum of others: still a disjoint breakdown.
    facts.append(_fact("c3", "srt:ProductOrServiceAxis", "x:LicensingMember", 1_000e6))
    assert XBRL()._compute_synthetic_total(facts, "us-gaap_CostOfGoodsAndServicesSold")["total"] == 59_766e6


@pytest.mark.fast
def test_an_undeclared_axis_with_a_subtotal_beside_its_parts_has_no_sum():
    # Microsoft's 2021-06-30 equity components on the balance sheet, which
    # presents no equity axis: the AOCI member 1,822 is the sum of its three
    # sub-components, so adding all six counts AOCI twice (143,810 against a
    # filed 141,988).
    members = [("CommonStockIncludingAdditionalPaidInCapitalMember", 83_111e6), ("RetainedEarningsMember", 57_055e6),
               ("AccumulatedOtherComprehensiveIncomeMember", 1_822e6),
               ("AccumulatedGainLossNetCashFlowHedgeParentMember", -19e6),
               ("AccumulatedNetUnrealizedInvestmentGainLossMember", 3_222e6),
               ("msft:AccumulatedTranslationAdjustmentAndOtherMember", -1_381e6)]
    facts = [_fact(f"c{i}", "us-gaap:StatementEquityComponentsAxis", m if ":" in m else f"us-gaap:{m}", v)
             for i, (m, v) in enumerate(members)]
    assert XBRL()._compute_synthetic_total(facts, "us-gaap_StockholdersEquity") is None


@pytest.mark.fast
def test_zeros_are_no_subtotal_and_a_counterparty_subtotal_is():
    from edgar.xbrl.xbrl import _contains_a_subtotal

    # Golub's swap schedule: zero members are part of no double count.
    assert not _contains_a_subtotal([0.0, 0.0, 0.0, 0.0])
    # Golub's forward contracts: "Macquarie Bank Limited" 2,302 beside its six contracts.
    macquarie = [2_302e3, 80e3, 495e3, 805e3, 70e3, 485e3, 367e3]
    assert _contains_a_subtotal(macquarie + [0.0] * 8)


@pytest.mark.fast
def test_microsoft_balance_sheet_equity_2021_is_not_a_double_count():
    xbrl = XBRL.from_directory(MSFT_10K)
    rows = xbrl.get_statement(xbrl.statements.balance_sheet().role_or_type)
    equity = next(r for r in rows if r["concept"] == "us-gaap_StockholdersEquity" and not r.get("is_dimension"))
    assert equity["values"].get("instant_2021-06-30") is None  # was 143,810,000,000


def _plain(df, concept):
    return df[(df["concept"] == concept) & (df["dimension"] != True)]  # noqa: E712


@pytest.mark.network
def test_deutsche_bank_operating_cash_flow_is_the_consolidated_figure():
    xbrl = find("0001159508-25-000020").xbrl()
    for view in (None, "standard", "summary"):
        df = xbrl.statements.cash_flow_statement().to_dataframe(view=view)
        row = _plain(df, "ifrs-full_CashFlowsFromUsedInOperatingActivities").iloc[0]
        assert row["2024-12-31 (FY)"] == -28_584_000_000  # DETAILED was -58,501,000,000
        assert row["2022-12-31 (FY)"] == -2_113_000_000
    liabilities = _plain(xbrl.statements.balance_sheet().to_dataframe(), "ifrs-full_Liabilities")
    assert liabilities["2024-12-31"].tolist() == [1_309_168_000_000]


@pytest.mark.network
def test_jpm_parent_company_amounts_stay_off_the_consolidated_rows():
    xbrl = find("0001628280-26-008131").xbrl()
    other = _plain(xbrl.statements.balance_sheet().to_dataframe(), "us-gaap_OtherLiabilities")
    assert other["2025-12-31"].tolist() == [691_000_000]  # was 14,347,000,000
    repayments = _plain(xbrl.statements.cash_flow_statement().to_dataframe(), "us-gaap_RepaymentsOfShortTermDebt")
    assert repayments["2024-12-31 (FY)"].isna().all()  # was -999,000,000, a parent-only figure


@pytest.mark.network
@pytest.mark.parametrize("accession, concept, face_total", [
    # Schwab 10-Q 2026-06-30: face parents 1,825 + 1,215 + 333 + 342; the plain row added their children too (6,755).
    ("0000316709-26-000031", "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", 3_715_000_000),
    # KB Home 10-Q 2026-08-31: construction and land costs 1,078,590 thousand; the detailed row added the
    # housing detail inside it (2,154,194).
    ("0000795266-26-000071", "us-gaap_CostOfGoodsAndServicesSold", -1_078_590_000),
])
def test_a_parent_row_and_its_children_are_not_added_twice(accession, concept, face_total):
    statement = find(accession).xbrl().statements.income_statement()
    for view in ("standard", "detailed"):
        df = statement.to_dataframe(view=view)
        period = next(c for c in df.columns if str(c).startswith("2026"))
        assert df.loc[(df["concept"] == concept) & ~df["dimension"], period].tolist() == [face_total], view
