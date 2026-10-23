"""Regression test for GH #1759: the STANDARD view dropped nested dimension members.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1759

``XBRL._get_valid_dimensional_members()`` allowed only the direct children of a
'*Domain*' node under an axis, and every view but DETAILED drops dimensional
facts whose member is not allowed. A face line the filer nests under a member
vanished: Tesla's Automotive sales, regulatory credits and leasing sit under
AutomotiveRevenuesMember. Every member the presentation tree nests under the
axis now counts, and a synthesized total adds only the outermost members, so a
member is never added to its own sub-members.

Ground truth:
- Tesla 10-Q for 2024-06-30 (0001628280-24-032662, fixture tests/fixtures/xbrl/tsla):
  Q2 2024 revenue, Automotive sales 18,530,000,000, regulatory credits
  890,000,000, leasing 458,000,000; cost of Automotive sales 15,962,000,000.
- Raymond James 10-Q for 2026-06-30 (0000720005-26-000070): the equity
  statement has no undimensioned total at 2026-03-31. Its components sit under
  ParentMember; the STANDARD beginning balance read 43,000,000 (the
  noncontrolling interest alone). Total shareholders' equity at 2026-03-31 is
  12,610,000,000 as filed on the balance sheet of the 10-Q for 2026-03-31
  (0000720005-26-000051).
- Coca-Cola 10-K FY2024 (fixture tests/fixtures/xbrl/ko/10k_2024): no common
  stock component of StockholdersEquityIncludingPortionAttributableToNoncontrolling
  Interest is filed, so adding the other components gave a 2021 year-end total
  of 23,100,000,000 against 24,860,000,000 filed. A balance whose presented
  components are not all filed is now left blank.
- Disney 10-K FY2025 (0001744489-25-000155, fixture tests/fixtures/xbrl/dis/10k_2025),
  derivatives note: gross fair value of derivatives 275 million in other current
  assets and 635 million in other assets at 2025-09-27; the table also presents
  two liability locations, which never carry an asset concept. The asset total
  of 910 million keeps its value.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar import find
from edgar.xbrl import XBRL

TSLA_10Q = Path("tests/fixtures/xbrl/tsla")
TSLA_ROLE = "http://www.tesla.com/role/ConsolidatedStatementsofOperations"
KO_10K = Path("tests/fixtures/xbrl/ko/10k_2024")
DIS_10K = Path("tests/fixtures/xbrl/dis/10k_2025")
KO_EQUITY = "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"


@pytest.mark.fast
def test_nested_members_are_valid():
    xbrl = XBRL.from_directory(TSLA_10Q)
    valid = xbrl._get_valid_dimensional_members(xbrl.presentation_trees[TSLA_ROLE])
    assert {"tsla_AutomotiveRevenuesMember", "tsla_AutomotiveSalesMember",
            "tsla_AutomotiveRegulatoryCreditsMember", "tsla_AutomotiveLeasingMember"} \
        <= valid["srt_ProductOrServiceAxis"]

    parents = xbrl._get_dimensional_member_parents(xbrl.presentation_trees[TSLA_ROLE])
    axis = parents["srt_ProductOrServiceAxis"]
    assert axis["tsla_AutomotiveSalesMember"] == "tsla_AutomotiveRevenuesMember"
    assert axis["tsla_AutomotiveRevenuesMember"] is None


@pytest.mark.fast
def test_tesla_standard_view_keeps_the_nested_face_lines():
    xbrl = XBRL.from_directory(TSLA_10Q)
    df = xbrl.statements.income_statement().to_dataframe(view="standard")
    revenue = df[df["concept"] == "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"]
    by_label = dict(zip(revenue["label"], revenue["2024-06-30 (Q2)"], strict=True))
    assert by_label["Automotive sales"] == 18_530_000_000
    assert by_label["Automotive regulatory credits"] == 890_000_000
    assert by_label["Automotive leasing"] == 458_000_000
    cost = df[df["concept"] == "us-gaap_CostOfRevenue"]
    assert dict(zip(cost["label"], cost["2024-06-30 (Q2)"], strict=True))["Automotive sales"] == 15_962_000_000


@pytest.mark.fast
def test_synthesized_total_skips_members_inside_another():
    def fact(cid, member, value):
        return (cid, {"fact": SimpleNamespace(numeric_value=value, unit_ref="usd", context_ref=cid,
                                              decimals="-6"),
                      "dimension_info": [{"dimension": "srt:ProductOrServiceAxis", "member": member}]})

    facts = [fact("c1", "tsla:AutomotiveRevenuesMember", 19_878e6),
             fact("c2", "tsla:AutomotiveSalesMember", 18_530e6),
             fact("c3", "tsla:EnergyGenerationAndStorageMember", 3_014e6)]
    parents = {"srt_ProductOrServiceAxis": {
        "tsla_AutomotiveRevenuesMember": None,
        "tsla_AutomotiveSalesMember": "tsla_AutomotiveRevenuesMember",
        "tsla_EnergyGenerationAndStorageMember": None}}
    result = XBRL()._compute_synthetic_total(facts, "us-gaap_Revenues", parents)
    assert result["total"] == 19_878e6 + 3_014e6


def _balance_facts(members):
    return [(f"c{i}", {"fact": SimpleNamespace(numeric_value=value, unit_ref="usd", context_ref=f"c{i}",
                                               decimals="-6"),
                       "dimension_info": [{"dimension": "us-gaap:StatementEquityComponentsAxis", "member": member}]})
            for i, (member, value) in enumerate(members)]


EQUITY_PARENTS = {"us-gaap_StatementEquityComponentsAxis": {
    "us-gaap_EquityComponentDomain": None,
    "us-gaap_ParentMember": None,
    "us-gaap_CommonStockMember": "us-gaap_ParentMember",
    "us-gaap_RetainedEarningsMember": "us-gaap_ParentMember",
    "us-gaap_NoncontrollingInterestMember": None}}


def _instant_xbrl(count):
    xbrl = XBRL()
    xbrl.parser.contexts = {f"c{i}": SimpleNamespace(period={"type": "instant", "instant": "2021-12-31"})
                     for i in range(count)}
    return xbrl


@pytest.mark.fast
def test_balance_with_an_unfiled_presented_component_has_no_total():
    facts = _balance_facts([("us-gaap:RetainedEarningsMember", 69_094e6),
                            ("us-gaap:NoncontrollingInterestMember", 1_861e6)])
    assert _instant_xbrl(2)._compute_synthetic_total(facts, KO_EQUITY, EQUITY_PARENTS) is None


@pytest.mark.fast
def test_balance_sums_when_every_presented_component_is_filed():
    facts = _balance_facts([("us-gaap:CommonStockMember", 1_760e6),
                            ("us-gaap:RetainedEarningsMember", 69_094e6),
                            ("us-gaap:NoncontrollingInterestMember", 1_861e6)])
    result = _instant_xbrl(3)._compute_synthetic_total(facts, KO_EQUITY, EQUITY_PARENTS)
    assert result["total"] == 1_760e6 + 69_094e6 + 1_861e6


@pytest.mark.fast
def test_a_flow_still_sums_the_components_it_touches():
    # Net income reaches retained earnings and the noncontrolling interest only;
    # the other components are zeros, not gaps.
    facts = _balance_facts([("us-gaap:RetainedEarningsMember", 9_542e6),
                            ("us-gaap:NoncontrollingInterestMember", 29e6)])
    xbrl = XBRL()
    xbrl.parser.contexts = {cid: SimpleNamespace(period={"type": "duration", "startDate": "2021-01-01",
                                                  "endDate": "2021-12-31"}) for cid, _ in facts}
    assert xbrl._compute_synthetic_total(facts, "us-gaap_ProfitLoss", EQUITY_PARENTS)["total"] == 9_571e6


LOCATION = "us-gaap:BalanceSheetLocationAxis"
LOCATION_PARENTS = {"us-gaap_BalanceSheetLocationAxis": {
    "us-gaap_BalanceSheetLocationDomain": None,
    "us-gaap_OtherCurrentAssetsMember": None,
    "us-gaap_OtherAssetsMember": None,
    "us-gaap_AccruedLiabilitiesMember": None,
    "us-gaap_OtherLiabilitiesMember": None}}
GROSS_ASSETS = "us-gaap_DerivativeAssetFairValueGrossAssetIncludingNotSubjectToMasterNettingArrangement"


def _location_xbrl(facts_by_context):
    """An XBRL whose contexts sit on BalanceSheetLocationAxis; facts_by_context maps id -> (member, date)."""
    xbrl = XBRL()
    xbrl.parser.contexts = {cid: SimpleNamespace(period={"type": "instant", "instant": date},
                                                 dimensions={"us-gaap:BalanceSheetLocationAxis": member})
                            for cid, (member, date) in facts_by_context.items()}
    xbrl._element_context_index = {GROSS_ASSETS: list(facts_by_context)}
    return xbrl


def _location_facts(members):
    return [(f"c{i}", {"fact": SimpleNamespace(numeric_value=value, unit_ref="usd", context_ref=f"c{i}",
                                               decimals="-6"),
                       "dimension_info": [{"dimension": LOCATION, "member": member}]})
            for i, (member, value) in enumerate(members)]


@pytest.mark.fast
def test_locations_that_never_carry_the_concept_do_not_veto_the_sum():
    facts = _location_facts([("us-gaap:OtherCurrentAssetsMember", 275e6), ("us-gaap:OtherAssetsMember", 635e6)])
    xbrl = _location_xbrl({"c0": ("us-gaap:OtherCurrentAssetsMember", "2025-09-27"),
                           "c1": ("us-gaap:OtherAssetsMember", "2025-09-27")})
    assert xbrl._compute_synthetic_total(facts, GROSS_ASSETS, LOCATION_PARENTS)["total"] == 910e6


@pytest.mark.fast
def test_a_member_that_carries_the_concept_elsewhere_vetoes_the_sum():
    # Golub's unaffiliated issuers: no fact at this date, but filed at others, so
    # the two affiliated members are a partial.
    facts = _location_facts([("us-gaap:OtherCurrentAssetsMember", 275e6), ("us-gaap:OtherAssetsMember", 635e6)])
    xbrl = _location_xbrl({"c0": ("us-gaap:OtherCurrentAssetsMember", "2025-09-27"),
                           "c1": ("us-gaap:OtherAssetsMember", "2025-09-27"),
                           "c9": ("us-gaap:OtherLiabilitiesMember", "2024-09-28")})
    assert xbrl._compute_synthetic_total(facts, GROSS_ASSETS, LOCATION_PARENTS) is None


@pytest.mark.fast
def test_disney_gross_derivative_assets_keep_their_total():
    xbrl = XBRL.from_directory(DIS_10K)
    role = next(r for r in xbrl.presentation_trees
                if r.endswith("DerivativeInstrumentsGrossFairValueofDerivativePositionsDetail"))
    rows = [r for r in xbrl.get_statement(role) if r["concept"] == GROSS_ASSETS and not r.get("is_dimension")]
    assert rows[0]["values"]["instant_2025-09-27"] == 910_000_000  # 275 + 635; blank before narrowing


@pytest.mark.fast
def test_coca_cola_partial_equity_balances_are_blank():
    df = XBRL.from_directory(KO_10K).statements.statement_of_equity().to_dataframe(view="standard")
    rows = df[(df["concept"] == KO_EQUITY) & ~df["dimension"]]
    assert len(rows) == 2
    assert rows["2021-12-31 (FY)"].isna().all()  # end of 2021 was 23,100M against 24,860M filed


@pytest.mark.network
def test_raymond_james_beginning_equity_is_the_whole_total():
    xbrl = find("0000720005-26-000070").xbrl()
    eq = xbrl.statements.statement_of_equity().to_dataframe(view="standard")
    row = eq[(eq["label"] == "Balance beginning of period") & (eq["dimension"] == False)]  # noqa: E712
    assert row["2026-06-30 (Q3)"].iloc[0] == 12_610_000_000  # was 43,000,000
