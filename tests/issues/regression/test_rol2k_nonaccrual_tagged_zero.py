"""Regression: a filer's tagged zero reads as a 0% non-accrual rate, not unknown.

Bead: edgartools-rol2k

A BDC with no non-accruals often has no footnote to read but tags an amount or
count of zero, as us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus
(Stone Point, Fortress, Kennedy Lewis, Overland) or a concept of its own (AGL,
CCS IX, Crestline, SL Investment Fund II). Neither the custom-concept nor the
aggregate layer read them, so the filing read ``'none'``, unknown. Across the
latest 10-K or 10-Q of 179 active BDCs, these 8 now read ``'tagged_zero'``.

A recognized non-accrual footnote outranks a tagged zero: Antares Strategic
Credit tags PortfolioCompaniesNonAccrual = 0 beside "Position is on
non-accrual status".
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from edgar.bdc.nonaccrual import _extract_nonaccrual_from_xbrl, _tagged_zero

P = '2025-12-31'
TOTAL = {'concept': 'us-gaap:InvestmentOwnedAtFairValue', 'numeric_value': 2_882_954_000.0, 'period_instant': P}


def _fact(concept, value, instant=P, **extra):
    return {'concept': concept, 'numeric_value': value, 'period_instant': instant, **extra}


def _xbrl(footnotes=None):
    return SimpleNamespace(footnotes=footnotes or {}, element_catalog={})


@pytest.mark.parametrize("concept", [
    'us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus',
    'ck0002011498:NumberPortfolioCompanyInvestmentOnNonAccrualStatus',
    'ck0002017636:InvestmentsOnNonAccrualStatus',
])
def test_a_zero_amount_or_count_is_a_tagged_zero(concept):
    assert _tagged_zero([_fact(concept, 0.0)], P) is True


def test_a_non_zero_beside_a_zero_is_not():
    facts = [_fact('us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus', 0.0),
             _fact('xx:NumberOfInvestmentsOnNonAccrualStatus', 2.0)]
    assert _tagged_zero(facts, P) is False


@pytest.mark.parametrize("fact", [
    # a zero that does not say "no non-accruals"
    _fact('us-gaap:FinancingReceivableNonaccrualNoAllowance', 0.0),
    _fact('us-gaap:FinancingReceivableNonaccrualInterestIncome', 0.0),
    _fact('nmfc:InvestmentOwnedNonaccrualThresholdPeriodPastDue', 0.0),
    # another date, or one holding
    _fact('us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus', 0.0, instant='2024-12-31'),
    _fact('us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus', 0.0,
          **{'dim_us-gaap_InvestmentIdentifierAxis': 'Acme Corp'}),
])
def test_other_zeros_are_not_a_tagged_zero(fact):
    assert _tagged_zero([fact], P) is False


def test_a_tagged_zero_reads_zero_percent():
    facts = [TOTAL, _fact('us-gaap:FinancingReceivableRecordedInvestmentNonaccrualStatus', 0.0)]
    result = _extract_nonaccrual_from_xbrl(_xbrl(), period=P, all_facts=facts)
    assert result.extraction_method == 'tagged_zero'
    assert result.nonaccrual_rate == 0.0
    assert result.num_nonaccrual == 0
    assert result.evidence_level == 'aggregate'
    assert result.warnings == []


def test_a_recognized_footnote_outranks_a_tagged_zero():
    flag = SimpleNamespace(text='Position is on non-accrual status.', lang='en-US', related_fact_ids=['gone'])
    facts = [TOTAL, _fact('ck0001993402:PortfolioCompaniesNonAccrual', 0.0)]
    result = _extract_nonaccrual_from_xbrl(_xbrl({'fn': flag}), period=P, all_facts=facts)
    assert result.extraction_method == 'none'
    assert result.nonaccrual_rate is None
    assert result.num_nonaccrual is None


def test_without_any_signal_the_result_is_still_unknown():
    result = _extract_nonaccrual_from_xbrl(_xbrl(), period=P, all_facts=[TOTAL])
    assert result.extraction_method == 'none'
    assert result.num_nonaccrual is None


@pytest.mark.network
@pytest.mark.vcr
def test_stone_point_reads_its_tagged_zero():
    """Stone Point Credit Corp 10-K for 2025-12-31 (0001193125-26-096955).

    The filing prints a "Non-accrual" row of dashes against $2,882,954K of
    investments and says "As of both December 31, 2025 and 2024, no
    investments were on non-accrual status"; it tags
    FinancingReceivableRecordedInvestmentNonaccrualStatus = 0.
    """
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001193125-26-096955'))
    assert result.extraction_method == 'tagged_zero'
    assert result.total_portfolio_fair_value == Decimal('2882954000')
    assert result.nonaccrual_rate == 0.0
    assert result.num_nonaccrual == 0
