"""Regression test for GitHub Issue #1728.

A filing imports the us-gaap and srt taxonomies, so its element catalog has no
balance for any standard concept, and the balance column fell back to a
hand-written table of 124 concepts. Four of its entries were wrong; those were
fixed first. Balances for standard concepts now come from a bundled table of the
FASB element declarations (edgar/xbrl/data/taxonomy_elements.parquet, us-gaap
2011-2026 and srt 2018-2026). The FASB us-gaap 2026 taxonomy
(https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-2026.xsd) declares:

    CostsAndExpenses                             monetaryItemType  debit
    CommonStockSharesIssued                      sharesItemType    no balance
    CommonStockSharesOutstanding                 sharesItemType    no balance
    NetCashProvidedByUsedInOperatingActivities   monetaryItemType  no balance
    InterestAndFeeIncomeLoansAndLeases           monetaryItemType  credit
    InterestExpenseDeposits                      monetaryItemType  debit
    InterestIncomeExpenseNet                     monetaryItemType  credit

and the 2017 schema declares SalesRevenueNet (deprecated in 2018) credit.

Comcast's 10-Q (accession 0001628280-26-049360) reports 135 us-gaap concepts in
USD; 87 had no balance on any fact before, and only the operating cash total,
which the taxonomy declares without one, has none now.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1728
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.concepts import get_balance_type

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
APPLE_FY2023 = FIXTURES / "xbrl" / "aapl" / "10k_2023"
JPM_FY2023 = FIXTURES / "xbrl" / "jpm" / "10k_2024"
COMCAST_USD_CONCEPTS = FIXTURES / "issues" / "regression" / "issue_1728" / "cmcsa_10q_usd_concepts.txt"


@pytest.mark.fast
@pytest.mark.parametrize("concept,expected", [
    ("us-gaap:CostsAndExpenses", "debit"),
    ("us-gaap:CommonStockSharesIssued", None),
    ("us-gaap:CommonStockSharesOutstanding", None),
    ("us-gaap:NetCashProvidedByUsedInOperatingActivities", None),
    ("us-gaap_CommonStockSharesOutstanding", None),
    ("us-gaap_InterestIncomeExpenseNet", "credit"),
    ("us_gaap_InterestExpenseDeposits", "debit"),
    ("us-gaap:SalesRevenueNet", "credit"),
    ("aapl:SomeExtension", None),
])
def test_balance_matches_the_taxonomy(concept, expected):
    assert get_balance_type(concept) == expected


@pytest.mark.fast
def test_comcast_usd_concepts_all_have_their_declared_balance():
    concepts = COMCAST_USD_CONCEPTS.read_text().split()
    assert len(concepts) == 135
    without_balance = [c for c in concepts if get_balance_type(c) is None]
    assert without_balance == ["us-gaap:NetCashProvidedByUsedInOperatingActivities"]


@pytest.mark.fast
def test_apple_fy2023_facts_carry_no_invented_balance():
    df = XBRL.from_directory(APPLE_FY2023).facts.to_dataframe()

    def balances(local_name):
        rows = df[df["concept"].str.split("[:_]", n=1, regex=True).str[-1] == local_name]
        assert not rows.empty, local_name
        return set(rows["balance"].dropna())

    assert balances("CommonStockSharesOutstanding") == set()
    assert balances("NetCashProvidedByUsedInOperatingActivities") == set()
    # Apple's own schema declares Assets debit, which the fix does not touch.
    assert balances("Assets") == {"debit"}


@pytest.mark.fast
def test_bank_statement_and_calculation_balances_come_from_the_taxonomy():
    """JPMorgan Chase FY2023 10-K, accession 0000019617-24-000225."""
    xbrl = XBRL.from_directory(JPM_FY2023)

    facts = xbrl.facts.to_dataframe()
    first = facts.drop_duplicates("concept").set_index("concept")["balance"]
    assert first["us-gaap:InterestAndFeeIncomeLoansAndLeases"] == "credit"
    assert first["us-gaap:InterestExpenseDeposits"] == "debit"
    assert first["us-gaap:InterestIncomeExpenseNet"] == "credit"

    income = xbrl.statements.income_statement().to_dataframe()
    rows = income.set_index("concept")["balance"]
    assert set(rows.loc[["us-gaap_InterestIncomeExpenseNet"]]) == {"credit"}

    calc_balances = {node.balance_type
                     for tree in xbrl.calculation_trees.values()
                     for element_id, node in tree.all_nodes.items()
                     if element_id == "us-gaap_InterestExpenseDeposits"}
    assert calc_balances == {"debit"}
