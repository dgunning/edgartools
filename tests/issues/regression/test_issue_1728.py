"""Regression test for GitHub Issue #1728 (the four wrong balance entries).

The static US-GAAP balance mapping, used when a filing's schema gives an element
no balance, invented a credit for two share counts and a debit for the operating
cash total, and had no entry for CostsAndExpenses. The FASB us-gaap 2025
taxonomy (https://xbrl.fasb.org/us-gaap/2025/elts/us-gaap-2025.xsd) declares:

    CostsAndExpenses                             monetaryItemType  debit
    CommonStockSharesIssued                      sharesItemType    no balance
    CommonStockSharesOutstanding                 sharesItemType    no balance
    NetCashProvidedByUsedInOperatingActivities   monetaryItemType  no balance

Checked against that schema, these were the only 3 of the mapping's 124 entries
that contradict it (110 agree, 11 concepts are not in the 2025 taxonomy).

Apple's FY2023 10-K (accession 0000320193-23-000106, fixture
tests/fixtures/xbrl/aapl/10k_2023) showed the invented values in
xbrl.facts.to_dataframe(). This fixes those entries only. Whether to report only
balances the filing itself declares is a separate decision, tracked on the issue
for 6.x.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1728
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.concepts import get_balance_type

APPLE_FY2023 = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "aapl" / "10k_2023"


@pytest.mark.fast
@pytest.mark.parametrize("concept,expected", [
    ("us-gaap:CostsAndExpenses", "debit"),
    ("us-gaap:CommonStockSharesIssued", None),
    ("us-gaap:CommonStockSharesOutstanding", None),
    ("us-gaap:NetCashProvidedByUsedInOperatingActivities", None),
    ("us-gaap_CommonStockSharesOutstanding", None),
])
def test_balance_mapping_matches_the_taxonomy(concept, expected):
    assert get_balance_type(concept) == expected


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
