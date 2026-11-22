"""Regression: a subtotal that repeats its one holding's cost is excluded again.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1583

#1506 kept any row with its own cost over a single extending row, so that ARCC's
two Proofpoint loans (same fair value, different cost) both count. PhenixFIN
tags each company subtotal with the same fair value and cost as its only
holding, so its Q2 2026 10-Q (0001213900-26-085667) kept 16 subtotals as
holdings, and New Mountain's FY2025 10-K (0001496099-26-000008) kept ACI
Parent's preferred twice. A costed row over one row is now excluded when that
row states the same cost under a longer label; a row that adds only a counter
("... loan 1", "... One") is still a separate holding.
"""
from decimal import Decimal

import pytest

from edgar.bdc.investments import PortfolioInvestment, PortfolioInvestments, _exclude_restated_rows


def holding(identifier, fair_value, cost=None):
    return PortfolioInvestment(
        identifier=identifier, company_name=identifier.split(' - ')[0], investment_type='First lien',
        fair_value=Decimal(fair_value), cost=None if cost is None else Decimal(cost))


@pytest.mark.fast
def test_a_subtotal_repeating_its_holdings_cost_is_excluded():
    rows = [
        holding('Non-Controlled/Non-Affiliated Investments - Power Stop LLC', 4_500_000, cost=4_400_000),
        holding('Non-Controlled/Non-Affiliated Investments - Power Stop LLC - Term Loan', 4_500_000,
                cost=4_400_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert [i.identifier for i in kept] == ['Non-Controlled/Non-Affiliated Investments - Power Stop LLC - Term Loan']
    assert [e.reason for e in excluded] == ['total of 1 row(s) that extend it']


@pytest.mark.fast
def test_twins_that_differ_only_by_a_counter_are_both_kept():
    """ARCC's Nordic Ferry loans share fair value and cost; only " 1" tells them apart."""
    rows = [
        holding('Nordic Ferry Infrastructure AS | Senior subordinated loan', 100_000, cost=100_000),
        holding('Nordic Ferry Infrastructure AS | Senior subordinated loan 1', 100_000, cost=100_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert excluded == []
    assert len(kept) == 2


@pytest.mark.fast
def test_a_non_accrual_copy_of_a_holding_counts_once():
    """New Mountain's FY2025 10-K lists ACI Parent's preferred again under a non-accrual label."""
    rows = [
        holding('ACI Parent Inc. | Preferred shares', 2_087_000, cost=20_124_000),
        holding('ACI Parent Inc. | Preferred shares | Non-accrual status', 2_087_000, cost=20_124_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert [i.identifier for i in kept] == ['ACI Parent Inc. | Preferred shares | Non-accrual status']
    assert [e.investment.identifier for e in excluded] == ['ACI Parent Inc. | Preferred shares']


@pytest.mark.network
@pytest.mark.vcr
def test_phenixfin_subtotals_are_not_holdings():
    """Ground truth: PhenixFIN 10-Q for 2026-06-30, accession 0001213900-26-085667."""
    from edgar import find

    portfolio = PortfolioInvestments.from_xbrl(find('0001213900-26-085667').xbrl(), period='2026-06-30')
    assert len(portfolio) == 68
    assert sum(i.fair_value or 0 for i in portfolio) == Decimal('801552171')
    assert 'Non-Controlled/Non-Affiliated Investments - JFL-NGS-WCS Partners, LLC' not in {
        i.identifier for i in portfolio}

