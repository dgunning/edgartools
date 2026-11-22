"""Regression: an affiliation line tagged under a custom and a us-gaap member counts once.

Bead: edgartools-m4qnb (a 6.0.0rc1 regression from edgartools-jv32z)

With no undimensioned investments total, ``extract_nonaccrual()`` adds up the
balance sheet's affiliation lines. SLR HC BDC's 10-Q for 2026-06-30
(0001193125-26-332723) tags its non-affiliated investments, $96,665K, under
both ``ck0001832148:NonControlledNonAffiliatedInvestmentsMember`` and
``us-gaap:InvestmentUnaffiliatedIssuerMember``, so 6.0.0rc1 read the portfolio
as $193,330K and the rate at half, 1.63%. The filing prints "Total Investments
... $96,665" and RQM+ Corp on non-accrual at $3,160K: 3.27%.
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _affiliation_split_total

AXIS = 'dim_us-gaap_InvestmentIssuerAffiliationAxis'
FV = 'us-gaap:InvestmentOwnedAtFairValue'


def _fact(member, value):
    return {'concept': FV, 'period_instant': '2026-06-30', 'numeric_value': value, 'decimals': '-3', AXIS: member}


def test_a_custom_member_restating_the_us_gaap_line_is_not_added():
    facts = [_fact('ck0001832148:NonControlledNonAffiliatedInvestmentsMember', 96665000.0),
             _fact('us-gaap:InvestmentUnaffiliatedIssuerMember', 96665000.0)]
    # One line left, and one line is never taken for the whole portfolio
    assert _affiliation_split_total(facts, '2026-06-30') is None


def test_a_restated_line_beside_a_real_second_line_is_counted_once():
    facts = [_fact('ck0001832148:NonControlledNonAffiliatedInvestmentsMember', 96665000.0),
             _fact('us-gaap:InvestmentUnaffiliatedIssuerMember', 96665000.0),
             _fact('us-gaap:InvestmentAffiliatedIssuerControlledMember', 1644000.0)]
    assert _affiliation_split_total(facts, '2026-06-30') == Decimal('98309000.0')


def test_a_real_split_still_adds():
    """Kayne DL 2021 10-Q for 2026-03-31 (0001193125-26-216809): 353,406,000 + 1,644,000."""
    facts = [_fact('us-gaap:InvestmentUnaffiliatedIssuerMember', 353406000.0),
             _fact('us-gaap:InvestmentAffiliatedIssuerControlledMember', 1644000.0)]
    assert _affiliation_split_total(facts, '2026-06-30') == Decimal('355050000.0')


@pytest.mark.network
@pytest.mark.vcr
def test_slr_hc_bdc_rate_uses_its_total_once():
    """SLR HC BDC 10-Q for 2026-06-30 (0001193125-26-332723)."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001193125-26-332723'), period='2026-06-30')
    assert result.total_portfolio_fair_value == Decimal('96665000')
    assert result.nonaccrual_fair_value == Decimal('3160000')
    assert round(result.nonaccrual_rate, 4) == 0.0327
