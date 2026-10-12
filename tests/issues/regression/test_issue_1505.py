"""Regression: a costed loan is not dropped as the "total" of a sibling worth the same.

GH #1505, bead edgartools-smuqk

``_exclude_restated_rows`` dropped a row when the rows extending its identifier
summed to its fair value, comparing fair value only. ARCC's 10-Q for the quarter
ended 2026-06-30 (0001628280-26-050307) has two Proofpoint second-lien loans,
both worth 50,500,000:

    Proofpoint, Inc. | Second lien senior secured loan     cost 52,600,000
    Proofpoint, Inc. | Second lien senior secured loan 1   cost 51,600,000

The first was excluded as the total of the second, as were two 100,000 pairs
(RMS HoldCo II, Nordic Ferry), leaving the kept rows 50,700,000 below the
filing's reported total. A parent over a single row that states its own cost is
now kept. Measured on 16 BDC 10-Qs, only ARCC changes: 1,444 -> 1,447 rows,
gap -50.7M -> 0.
"""
from decimal import Decimal

import pytest

from edgar.bdc.investments import PortfolioInvestment, PortfolioInvestments, _exclude_restated_rows


def holding(identifier, fair_value, cost=None):
    return PortfolioInvestment(
        identifier=identifier, company_name=identifier.split(' | ')[0], investment_type='Second lien',
        fair_value=Decimal(fair_value), cost=None if cost is None else Decimal(cost))


@pytest.mark.fast
def test_a_costed_row_is_not_the_total_of_one_sibling():
    rows = [
        holding('Proofpoint, Inc. | Second lien senior secured loan', 50_500_000, cost=52_600_000),
        holding('Proofpoint, Inc. | Second lien senior secured loan 1', 50_500_000, cost=51_600_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert excluded == []
    assert len(kept) == 2


@pytest.mark.fast
def test_a_costless_header_over_one_row_is_still_excluded():
    """ARCC's five cost-less headers (APG, Bragg Live Food, ...) stay excluded."""
    rows = [
        holding('APG Intermediate Holdings Corporation', 1_000_000),
        holding('APG Intermediate Holdings Corporation | First lien senior secured loan', 1_000_000,
                cost=990_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert [e.investment.identifier for e in excluded] == ['APG Intermediate Holdings Corporation']
    assert [e.reason for e in excluded] == ['total of 1 row(s) that extend it']


@pytest.mark.network
def test_arcc_keeps_proofpoint_and_reconciles():
    """Ground truth: ARCC reports 29,349,300,000; the kept rows summed to 29,298,600,000."""
    from edgar import find

    portfolio = PortfolioInvestments.from_xbrl(find('0001628280-26-050307').xbrl())
    proofpoint = [i for i in portfolio
                  if i.identifier == 'Proofpoint, Inc. | Second lien senior secured loan']
    assert [(i.fair_value, i.cost) for i in proofpoint] == [(Decimal('50500000'), Decimal('52600000'))]
    assert len(portfolio) == 1447
    assert portfolio.reported_total_fair_value == Decimal('29349300000')
    assert sum(i.fair_value for i in portfolio) == portfolio.reported_total_fair_value
