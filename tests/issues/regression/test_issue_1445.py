"""
Mapped face-statement tags were also listed in exclusions.py, and
ReverseIndex.lookup() checks the exclusion first, so basic and diluted EPS, the
receivables, inventory and payables changes, comprehensive income and the
cash-flow cash totals got no standard concept on any statement.

The tags left excluded are the ones whose mapping is wrong or would collide:
the continuing and discontinued per-share amounts (they map to the EPS
concepts), comprehensive income including noncontrolling interest (it shares
ComprehensiveIncomeNet with the parent total), OCI components mapped to the OCI
total, and the preferred share counts (they map to common share concepts).

Coca-Cola FY2023 10-K (0000021344-24-000009) and Apple FY2023 10-K
(0000320193-23-000106) are fixtures; Synchrony FY2025 10-K
(0001601712-26-000006) carries the disposal-group cash total.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1445
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization.exclusions import EXCLUDED_TAGS
from edgar.xbrl.standardization.reverse_index import get_reverse_index

FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"

UNEXCLUDED = {
    "EarningsPerShareBasic": "EarningsPerShareBasic",
    "EarningsPerShareDiluted": "EarningsPerShareDiluted",
    "IncreaseDecreaseInAccountsReceivable": "ChangeInReceivables",
    "IncreaseDecreaseInAccountsAndOtherReceivables": "ChangeInReceivables",
    "IncreaseDecreaseInAccountsPayable": "ChangeInPayables",
    "IncreaseDecreaseInInventories": "ChangeInInventory",
    "ComprehensiveIncomeNetOfTax": "ComprehensiveIncomeNet",
    "OtherComprehensiveIncomeLossNetOfTax": "OtherComprehensiveIncomeLoss",
    "OtherComprehensiveIncomeLossNetOfTaxPortionAttributableToParent": "OtherComprehensiveIncomeLoss",
    "CashAndCashEquivalentsPeriodIncreaseDecrease": "NetChangeInCash",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations":
        "CashAndCashEquivalents",
}

STILL_EXCLUDED = [
    "IncomeLossFromContinuingOperationsPerBasicShare",
    "IncomeLossFromDiscontinuedOperationsNetOfTaxPerDilutedShare",
    "ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossAfterReclassificationAndTaxParent",
    "PreferredStockSharesIssued",
]


def _plain_row(df, concept):
    rows = df[(df["concept"] == f"us-gaap_{concept}") & (df["dimension"] == False)]  # noqa: E712
    assert len(rows) == 1, f"{concept}: {len(rows)} plain rows"
    return rows.iloc[0]


@pytest.mark.fast
@pytest.mark.parametrize("tag", sorted(UNEXCLUDED))
def test_unexcluded_tag_resolves_to_its_mapping(tag):
    assert tag not in EXCLUDED_TAGS
    result = get_reverse_index().lookup(f"us-gaap:{tag}")
    assert result is not None
    assert result.standard_concepts[0] == UNEXCLUDED[tag]


@pytest.mark.fast
@pytest.mark.parametrize("tag", STILL_EXCLUDED)
def test_colliding_tags_stay_excluded(tag):
    assert tag in EXCLUDED_TAGS
    assert get_reverse_index().lookup(f"us-gaap:{tag}") is None


@pytest.mark.fast
def test_coca_cola_eps_and_comprehensive_income_are_standardized():
    xbrl = XBRL.from_directory(FIXTURES / "ko" / "10k_2024")
    income = xbrl.statements.income_statement().to_dataframe()
    basic = _plain_row(income, "EarningsPerShareBasic")
    diluted = _plain_row(income, "EarningsPerShareDiluted")
    assert basic["standard_concept"] == "EarningsPerShareBasic"
    assert basic["2023-12-31 (FY)"] == 2.48
    assert diluted["standard_concept"] == "EarningsPerShareDiluted"
    assert diluted["2023-12-31 (FY)"] == 2.47

    comprehensive = xbrl.statements.comprehensive_income().to_dataframe()
    total = _plain_row(comprehensive, "ComprehensiveIncomeNetOfTax")
    assert total["standard_concept"] == "ComprehensiveIncomeNet"
    assert total["2023-12-31 (FY)"] == 11_334_000_000
    # The including-NCI total stays unmapped, so ComprehensiveIncomeNet names one row
    plain = comprehensive[comprehensive["dimension"] == False]  # noqa: E712
    assert (plain["standard_concept"] == "ComprehensiveIncomeNet").sum() == 1


@pytest.mark.fast
def test_apple_working_capital_changes_are_standardized():
    xbrl = XBRL.from_directory(FIXTURES / "aapl" / "10k_2023")
    cash_flow = xbrl.statements.cash_flow_statement().to_dataframe()
    expected = {
        "IncreaseDecreaseInAccountsReceivable": ("ChangeInReceivables", -1_688_000_000),
        "IncreaseDecreaseInInventories": ("ChangeInInventory", -1_618_000_000),
        "IncreaseDecreaseInAccountsPayable": ("ChangeInPayables", -1_889_000_000),
    }
    for concept, (standard_concept, value) in expected.items():
        row = _plain_row(cash_flow, concept)
        assert row["standard_concept"] == standard_concept
        assert row["label"] != standard_concept
        assert row["2023-09-30 (FY)"] == value


@pytest.mark.fast
def test_ibm_eps_keeps_one_row_per_concept():
    # IBM files continuing and discontinued per-share lines beside EPS; they stay excluded
    xbrl = XBRL.from_directory(FIXTURES / "ibm" / "10k_2024")
    income = xbrl.statements.income_statement().to_dataframe()
    plain = income[income["dimension"] == False]  # noqa: E712
    assert (plain["standard_concept"] == "EarningsPerShareBasic").sum() == 1
    assert (plain["standard_concept"] == "EarningsPerShareDiluted").sum() == 1


@pytest.mark.network
def test_synchrony_disposal_group_cash_total_is_standardized():
    from edgar import find

    filing = find("0001601712-26-000006")
    cash_flow = filing.xbrl().statements.cash_flow_statement().to_dataframe()
    total = _plain_row(
        cash_flow, "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations")
    assert total["standard_concept"] == "CashAndCashEquivalents"
    assert total["2025-12-31 (FY)"] == 15_017_000_000
