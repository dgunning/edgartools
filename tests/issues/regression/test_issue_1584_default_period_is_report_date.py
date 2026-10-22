"""Regression: with no period, ``from_xbrl`` reads the schedule at the report date.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1584

The default took ``max()`` over every instant that carries an investment-axis
fair value. BlackRock TCP Capital's 10-Q for 2026-03-31 (0001193125-26-210632)
tags its controlled-affiliates roll-forward on the fiscal-year context, so the
latest instant was 2026-12-31, nine months past the report date: 10 rows summing
to $140,396,441, about a tenth of the book, with no reported total and no
warning. The default is now the filing's own report date
(``xbrl.period_of_report``) when holdings are tagged on it, and the latest
instant only when they are not.

Offline tests stub the facts the way test_issue_1324 does.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.investments import PortfolioInvestments


def _fact(identifier, instant, value):
    return {
        'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_type': 'instant',
        'period_instant': instant, 'numeric_value': float(value), 'value': str(value),
        'unit_ref': 'usd', 'dim_us-gaap_InvestmentIdentifierAxis': identifier,
    }


FACTS = [
    _fact('Alpha Corp, First Lien Term Loan', '2026-03-31', 1000),
    _fact('Beta LLC, First Lien Term Loan', '2026-03-31', 2000),
    _fact('Alpha Corp, First Lien Term Loan', '2026-12-31', 900),
]


def _xbrl(facts, **attrs):
    return SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog={}, **attrs)


@pytest.mark.fast
def test_the_report_date_wins_over_a_later_instant():
    portfolio = PortfolioInvestments.from_xbrl(_xbrl(FACTS, period_of_report='2026-03-31'))
    assert portfolio.period == '2026-03-31'
    assert sorted((i.identifier, i.fair_value) for i in portfolio) == [
        ('Alpha Corp, First Lien Term Loan', Decimal('1000')), ('Beta LLC, First Lien Term Loan', Decimal('2000'))]


@pytest.mark.fast
def test_the_latest_instant_stays_the_default_when_the_report_date_has_no_holdings():
    assert PortfolioInvestments.from_xbrl(_xbrl(FACTS, period_of_report='2026-06-30')).period == '2026-12-31'
    assert PortfolioInvestments.from_xbrl(_xbrl(FACTS)).period == '2026-12-31'


@pytest.mark.network
@pytest.mark.vcr
def test_tcpc_q1_2026_reads_its_march_schedule():
    """Ground truth: BlackRock TCP Capital 10-Q for 2026-03-31, accession 0001193125-26-210632."""
    from edgar import find

    portfolio = PortfolioInvestments.from_xbrl(find('0001193125-26-210632').xbrl())
    assert portfolio.period == '2026-03-31'
    assert len(portfolio) == 331
    assert sum(i.fair_value for i in portfolio if i.fair_value is not None) == Decimal('1400458176')
    assert portfolio.reported_total_fair_value == Decimal('1388668517')
