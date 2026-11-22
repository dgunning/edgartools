"""Regression: a grand total tagged as an identifier member is the rate denominator.

Bead: edgartools-cpd1b

With no balance-sheet total and no affiliation lines, ``extract_nonaccrual()``
summed every ``InvestmentIdentifierAxis`` row, subtotals and totals included.
Oxford Square's 10-Q for 2026-03-31 (0001213900-26-050934) tags its total as
the member "Investments in Securities" = $235,372,463 and summed to
$1,298,773,567, so its rate read 0.67%. Its text states one preferred equity
holding (~$5.2M) and one debt investment (~$3.5M) on non-accrual.

Across the latest 10-K and 10-Q of 351 active BDCs, 10 fell back to the sum;
5 tag such a total, each matching the filing's printed "Total Investments"
(Muzinich BDC $214,085,177 against an $819M sum, PhenixFIN $301,637,310
against $1.21B).
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _identifier_grand_total

DIM = 'dim_us-gaap_InvestmentIdentifierAxis'
FV = 'us-gaap:InvestmentOwnedAtFairValue'


def _fact(member, value):
    return {'concept': FV, 'period_instant': '2026-03-31', 'numeric_value': value, DIM: member}


def test_the_member_named_for_the_portfolio_is_the_total():
    facts = [_fact('Investments in Securities', 235372463.0),
             _fact('Investments in Securities and Cash Equivalents', 276009547.0),
             _fact('Net Assets', 131570928.0),
             _fact('Preferred Stock', 5324800.0),
             _fact('Investments - non-controlled/non-affiliated - Corporate Bond Investments', 29520346.0)]
    assert _identifier_grand_total(facts, '2026-03-31') == Decimal('235372463.0')


def test_a_total_with_its_percentage_of_net_assets_counts():
    assert _identifier_grand_total([_fact('Total Investments - 148.3%', 7270.0)], '2026-03-31') == Decimal('7270.0')


def test_two_different_totals_are_not_guessed_between():
    facts = [_fact('Investments', 100.0), _fact('Total Investments', 120.0)]
    assert _identifier_grand_total(facts, '2026-03-31') is None


@pytest.mark.network
@pytest.mark.vcr
def test_oxford_square_rate_uses_its_tagged_total():
    """Oxford Square 10-Q for 2026-03-31 (0001213900-26-050934)."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001213900-26-050934'))
    assert result.total_portfolio_fair_value == Decimal('235372463')
    assert result.total_source == 'identifier_total'
    assert result.nonaccrual_fair_value == Decimal('8760097')
    assert round(result.nonaccrual_rate, 3) == 0.037
