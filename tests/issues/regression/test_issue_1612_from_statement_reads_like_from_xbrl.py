"""Regression: ``from_statement`` returns what ``from_xbrl`` returns for the same filing.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1612

``from_statement`` re-parsed the statement's dimension labels on its own: with
no member candidates, without ``from_xbrl``'s exclusions, and from whichever
role ``schedule_of_investments()`` found. On six BDC 10-Qs for 2026-06-30 it
named 380 of 1,654 paired positions differently, kept BCSF's joint-venture
holdings, and returned nothing for CCAP (every label typed ``Unknown``), HTGC
and TSLX (a derivatives role was found). It now hands the statement's filing to
``from_xbrl``, so the two entry points cannot drift apart again.

The offline test stubs the facts the way test_issue_1324 does; the network test
replays test_issue_1587's Hercules cassette.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.investments import PortfolioInvestments


def _fact(identifier, value):
    return {
        'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_type': 'instant',
        'period_instant': '2026-06-30', 'numeric_value': float(value), 'value': str(value),
        'unit_ref': 'usd', 'dim_us-gaap_InvestmentIdentifierAxis': identifier,
    }


def _rows(portfolio):
    return sorted((i.identifier, i.company_name, i.investment_type, i.fair_value) for i in portfolio)


@pytest.mark.fast
def test_from_statement_reads_the_statements_filing_through_from_xbrl():
    facts = [_fact('Alpha Corp, First Lien Term Loan', 1000), _fact('Beta LLC, Common Equity', 2000)]
    xbrl = SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog={},
                           period_of_report='2026-06-30')
    from_statement = PortfolioInvestments.from_statement(SimpleNamespace(xbrl=xbrl))
    from_xbrl = PortfolioInvestments.from_xbrl(xbrl)
    assert from_statement.period == from_xbrl.period == '2026-06-30'
    assert _rows(from_statement) == _rows(from_xbrl)
    assert len(from_statement) == 2


@pytest.fixture
def vcr_cassette_name():
    return 'test_hercules_non_accruals_are_named_by_company'


@pytest.mark.network
@pytest.mark.vcr
def test_hercules_statement_reads_its_holdings():
    """Ground truth: Hercules Capital 10-Q for 2026-06-30, accession 0001280784-26-000042."""
    from edgar import find

    xbrl = find('0001280784-26-000042').xbrl()
    portfolio = PortfolioInvestments.from_statement(xbrl.statements.schedule_of_investments())
    assert portfolio.period == '2026-06-30'
    assert len(portfolio) == 364
    assert sum(i.fair_value for i in portfolio if i.fair_value is not None) == Decimal('4608670000')
    assert _rows(portfolio) == _rows(PortfolioInvestments.from_xbrl(xbrl))
