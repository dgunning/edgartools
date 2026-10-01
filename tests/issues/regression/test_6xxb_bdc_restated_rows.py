"""Regression: a BDC portfolio no longer counts the same holdings twice.

Bead: edgartools-6xxb

``PortfolioInvestments.from_xbrl`` makes one row per ``InvestmentIdentifierAxis``
member. The members carry no hierarchy, so a filer's subtotals and a second
schedule's copies of its holdings looked like holdings too. Measured against
each filer's own balance-sheet total (``InvestmentOwnedAtFairValue``, no
dimension) on its latest 10-K, the rows summed high on all nine BDCs checked:

    FSK +48.4%  HTGC +21.0%  CSWC +18.9%  OBDC +17.7%  ARCC +15.7%
    MAIN +14.1% TSLX +5.9%   MSIF +5.6%   GBDC +2.0%

MAIN's FY2025 10-K (0001396440-26-000016) summed to 6,296,964,000 against a
reported 5,518,117,000. The restatements, each seen in real filings:

- company totals: HTGC's "Debt Investments ... and Total Phathom Pharmaceuticals, Inc.";
- parents of their own tranches: MAIN's "Bolder Panther Group, LLC | Secured Debt"
  (101,046,000) = "... 1.1" (101,046,000) + "... 1.2" (0) + "... 1.3" (0);
- one identifier spelled two ways: CSWC's "ITA HOLDINGS GROUP, LLC" / "ITA Holdings Group, LLC";
- cost-less copies from the affiliate roll-forward: OBDC's "Blue Owl Credit SLF LLC(c)".

TSLX was also wrong for a separate reason: a foreign holding is tagged in USD and
in its own currency, and the last fact won, so Hippo XPA Bidco counted
SEK 214,115,000 instead of USD 23,226,000.

After the fix MAIN is -0.13%, MSIF 0.00%, ARCC +0.28%, CSWC +0.46%, GBDC +0.70%,
HTGC +1.37%, TSLX +1.74%. OBDC (+6.4%) and FSK (+11.5%) still tag holdings in a
way no rule here recognises, so ``reconciliation_gap`` reports it.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.investments import (
    PortfolioInvestment,
    PortfolioInvestments,
    _exclude_restated_rows,
    _reported_total_fair_value,
)

AXIS = 'dim_us-gaap_InvestmentIdentifierAxis'
PERIOD = '2025-12-31'


def holding(identifier, fair_value, cost=None, principal=None):
    return PortfolioInvestment(
        identifier=identifier, company_name=identifier.split(' | ')[0], investment_type='First lien',
        fair_value=Decimal(fair_value), cost=None if cost is None else Decimal(cost),
        principal_amount=None if principal is None else Decimal(principal))


def identifiers(rows):
    return sorted(inv.identifier for inv in rows)


@pytest.mark.fast
def test_a_parent_equal_to_its_tranches_is_excluded():
    """MAIN: the parent restates its tranches."""
    rows = [
        holding('Bolder Panther Group, LLC | Secured Debt', 101_046_000),
        holding('Bolder Panther Group, LLC | Secured Debt 1.1', 101_046_000, cost=101_500_000),
        holding('Bolder Panther Group, LLC | Secured Debt 1.2', 0, cost=0),
        holding('Bolder Panther Group, LLC | Secured Debt 1.3', 0, cost=0),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert identifiers(kept) == ['Bolder Panther Group, LLC | Secured Debt 1.1',
                                 'Bolder Panther Group, LLC | Secured Debt 1.2',
                                 'Bolder Panther Group, LLC | Secured Debt 1.3']
    assert [(e.investment.identifier, e.reason) for e in excluded] == [
        ('Bolder Panther Group, LLC | Secured Debt', 'total of 3 row(s) that extend it')]


@pytest.mark.fast
def test_a_company_total_is_excluded_but_only_against_its_own_heading():
    """HTGC: 'Total X' covers X's rows under that heading, not X's warrants elsewhere."""
    heading = 'Debt Investments Drug Discovery & Development and '
    rows = [
        holding(heading + 'Total Phathom Pharmaceuticals, Inc.', 180_300_000),
        holding(heading + 'Phathom Pharmaceuticals, Inc. and Senior Secured Tranche 1', 147_700_000, cost=145_000_000),
        holding(heading + 'Phathom Pharmaceuticals, Inc. and Senior Secured Tranche 2', 32_600_000, cost=32_200_000),
        holding('Warrant Investments Drug Discovery & Development and Phathom Pharmaceuticals, Inc.', 900_000,
                cost=400_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert [e.investment.identifier for e in excluded] == [heading + 'Total Phathom Pharmaceuticals, Inc.']
    assert sum(inv.fair_value for inv in kept) == Decimal(181_200_000)


@pytest.mark.fast
def test_one_identifier_spelled_two_ways_counts_once():
    """CSWC: the copy with fewer fields goes."""
    rows = [
        holding('ITA HOLDINGS GROUP, LLC | First Lien - Term Loan C', 21_150_000, cost=21_100_000, principal=21_150_000),
        holding('ITA Holdings Group, LLC | First Lien - Term Loan C', 21_150_000, principal=21_150_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert identifiers(kept) == ['ITA HOLDINGS GROUP, LLC | First Lien - Term Loan C']
    assert excluded[0].reason == 'same identifier and fair value as another row'


@pytest.mark.fast
def test_a_costless_copy_of_a_costed_row_is_excluded():
    """OBDC: the affiliate roll-forward restates the holding under its own member."""
    rows = [
        holding('Blue Owl Credit SLF LLC | LLC Interest | Affiliated', 415_200_000, cost=421_353_000),
        holding('Blue Owl Credit SLF LLC(c)', 415_200_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert identifiers(kept) == ['Blue Owl Credit SLF LLC | LLC Interest | Affiliated']
    # Without its footnote mark "(c)" the copy is a prefix of the holding, so the
    # parent rule takes it first (edgartools-3vad); FSK's copy is no prefix.
    rows = [
        holding('Production Resource Group LLC | First lien senior secured loan', 61_500_000, cost=60_000_000),
        holding('Production Resource Group LLC 8', 61_500_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert identifiers(kept) == ['Production Resource Group LLC | First lien senior secured loan']
    assert excluded[0].reason == 'no cost, fair value equal to a costed row'


@pytest.mark.fast
def test_real_holdings_that_only_look_like_restatements_are_kept():
    """Silence check: nothing is dropped unless other rows account for its value exactly."""
    rows = [
        # A company whose name starts with "Total", with no rows to be the total of
        holding('Total Quality Logistics, LLC | First lien senior secured loan', 12_000_000, cost=12_100_000),
        # A parent that is not the sum of the rows extending it is a holding of its own
        holding('Acme Holdings, LLC', 5_000_000, cost=4_000_000),
        holding('Acme Holdings, LLC, Warrants', 1_000_000, cost=0),
        # Two costed tranches that happen to be worth the same
        holding('Beta Corp | Secured Debt 1', 7_500_000, cost=7_400_000),
        holding('Beta Corp | Secured Debt 2', 7_500_000, cost=7_450_000),
    ]
    kept, excluded = _exclude_restated_rows(rows)
    assert excluded == []
    assert len(kept) == 5


@pytest.mark.fast
def test_the_most_precise_reported_total_wins():
    """ARCC tags its total at decimals -6 and -5."""
    facts = [
        {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_instant': PERIOD,
         'numeric_value': 29_485_000_000.0, 'decimals': '-6', 'unit_ref': 'usd'},
        {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_instant': PERIOD,
         'numeric_value': 29_484_800_000.0, 'decimals': '-5', 'unit_ref': 'usd'},
        {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_instant': PERIOD, AXIS: 'A holding',
         'numeric_value': 1.0, 'decimals': '0', 'unit_ref': 'usd'},
    ]
    assert _reported_total_fair_value(facts, PERIOD) == (Decimal('29484800000.0'), 'usd')
    assert _reported_total_fair_value(facts, '2024-12-31') == (None, None)


def _fact(identifier, concept, value, unit):
    return {'concept': f'us-gaap:{concept}', AXIS: identifier, 'period_instant': PERIOD,
            'period_type': 'instant', 'numeric_value': value, 'unit_ref': unit}


@pytest.mark.fast
def test_the_reporting_currency_is_never_replaced_by_a_foreign_one():
    """TSLX: Hippo XPA Bidco is tagged in USD and SEK; the SEK fact came last and won."""
    hippo = 'Debt Investments Internet Services Hippo XPA Bidco AB Investment First-lien loan'
    facts = [
        {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_instant': PERIOD, 'period_type': 'instant',
         'numeric_value': 23_226_000.0, 'decimals': '-3', 'unit_ref': 'U_USD'},
        _fact(hippo, 'InvestmentOwnedAtFairValue', 23_226_000.0, 'U_USD'),
        _fact(hippo, 'InvestmentOwnedAtCost', 21_300_000.0, 'U_USD'),
        _fact(hippo, 'InvestmentOwnedAtFairValue', 214_115_000.0, 'U_SEK'),
    ]
    xbrl = SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog={})
    portfolio = PortfolioInvestments.from_xbrl(xbrl, include_untyped=True)

    assert [inv.fair_value for inv in portfolio] == [Decimal('23226000.0')]
    assert portfolio.reported_total_fair_value == Decimal('23226000.0')
    assert portfolio.reconciliation_gap == 0.0


@pytest.mark.fast
def test_the_gap_is_reported_not_hidden():
    """When the rows do not reach the reported total, the collection says so."""
    facts = [
        {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'period_instant': PERIOD, 'period_type': 'instant',
         'numeric_value': 100_000_000.0, 'decimals': '-3', 'unit_ref': 'usd'},
        _fact('Gamma LLC | First lien senior secured loan', 'InvestmentOwnedAtFairValue', 110_000_000.0, 'usd'),
        _fact('Gamma LLC | First lien senior secured loan', 'InvestmentOwnedAtCost', 108_000_000.0, 'usd'),
    ]
    xbrl = SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog={})
    portfolio = PortfolioInvestments.from_xbrl(xbrl, include_untyped=True)

    assert portfolio.reconciliation_gap == pytest.approx(0.10)
    assert 'WARNING: holdings sum +10.0% from the reported total' in portfolio.to_context()


@pytest.mark.network
def test_main_fy2025_reconciles_to_its_balance_sheet():
    """Ground truth: MAIN reports 5,518,117,000; the rows used to sum to 6,296,964,000."""
    from edgar import find

    portfolio = PortfolioInvestments.from_xbrl(find('0001396440-26-000016').xbrl(), include_untyped=True)
    assert portfolio.reported_total_fair_value == Decimal('5518117000.0')
    assert abs(portfolio.reconciliation_gap) < 0.002
    assert len(portfolio.excluded) == 76
