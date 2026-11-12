"""Regression test for issue #1784: the filer's own industry breakdown, and coverage you can see.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1784

Ares Capital's FY2025 10-K (accession 0001287750-26-000006) tags no industry on
any of its 1,417 holdings, so ``filter(industry='software')`` returned 0 rows
with no warning and ``by_industry()`` put the whole portfolio in one ``None``
row. The filing does report its fair value by industry: 23
``InvestmentOwnedAtFairValue`` facts dimensioned by
``EquitySecuritiesByIndustryAxis`` alone, summing to the 29,484.8M reported
total, with Software and Services at 7,032.3M (49.12% of net assets, filed).

``reported_industry_breakdown()`` returns those subtotals, ``to_context()``
always says how many positions have an industry, and an industry filter that
matches nothing while holdings lack an industry warns instead of implying zero
exposure. ``by_industry()`` and ``filter()`` populations are unchanged.
"""
import json
import logging
import math
from decimal import Decimal

import pytest

from edgar import Filing
from edgar.bdc.investments import (
    REPORTED_INDUSTRY_COLUMNS,
    PortfolioInvestment,
    PortfolioInvestments,
    _reported_industry_rows,
    _reported_total_fair_value,
)

AXIS = 'dim_us-gaap_EquitySecuritiesByIndustryAxis'
FV = 'us-gaap:InvestmentOwnedAtFairValue'
PCT = 'us-gaap:InvestmentOwnedPercentOfNetAssets'


def _fact(concept, value, member, period='2025-12-31', unit='usd', decimals='-5', **extra):
    fact = {'concept': concept, 'numeric_value': value, 'period_instant': period,
            'unit_ref': unit, 'decimals': decimals, AXIS: member}
    fact.update(extra)
    return fact


def _holding(name, fair_value, industry=None):
    return PortfolioInvestment(identifier=name, company_name=name, investment_type='First lien',
                               fair_value=Decimal(fair_value), industry=industry,
                               industry_source='axis' if industry else None)


# ---------------------------------------------------------------- offline

@pytest.mark.fast
def test_only_industry_only_usd_facts_at_the_period_count_once():
    facts = [
        _fact(FV, 600.0, 'x:SoftwareMember', dimension_member_label='Software'),
        _fact(FV, 600.0, 'x:SoftwareMember', dimension_member_label='Software'),   # identical duplicate
        _fact(FV, 400.0, 'us-gaap:HealthcareSectorMember', dimension_member_label='Health Care'),
        _fact(PCT, 0.25, 'x:SoftwareMember', unit='number', decimals='4'),
        _fact(FV, 999.0, 'x:SoftwareMember', period='2024-12-31'),                 # earlier period
        _fact(FV, 77.0, 'x:SoftwareMember', unit='eur'),                           # not USD
        _fact(FV, 55.0, 'x:SoftwareMember', **{'dim_us-gaap_InvestmentTypeAxis': 'x:DebtMember'}),  # two axes
        {'concept': FV, 'numeric_value': 1000.0, 'period_instant': '2025-12-31', 'unit_ref': 'usd'},  # total
    ]
    rows = _reported_industry_rows(facts, '2025-12-31')
    assert [(label, value) for label, value, _ in rows] == [('Software', 600.0), ('Health Care', 400.0)]
    assert rows[0][2] == 0.25
    assert math.isnan(rows[1][2])  # not filed, never derived


@pytest.mark.fast
def test_breakdown_frame_attrs_and_filtered_subset():
    rows = _reported_industry_rows([
        _fact(FV, 600.0, 'x:SoftwareMember', dimension_member_label='Software'),
        _fact(FV, 390.0, 'x:RetailMember'),
    ], '2025-12-31')
    portfolio = PortfolioInvestments([_holding('Acme', 990)], period='2025-12-31',
                                     reported_total_fair_value=Decimal('1000'), reported_industry_rows=rows)
    df = portfolio.reported_industry_breakdown()
    assert list(df.columns) == REPORTED_INDUSTRY_COLUMNS
    assert df['industry'].tolist() == ['Software', 'Retail']  # member label made readable
    assert df['pct_of_reported_total'].tolist() == [0.6, 0.39]
    assert df.attrs == {'sum_fair_value': 990.0, 'reported_total_fair_value': 1000.0, 'difference': -10.0}

    subset = portfolio.filter(company_name='Acme')
    assert len(subset) == 1
    assert subset.reported_industry_breakdown().empty


@pytest.mark.fast
def test_no_breakdown_is_an_empty_frame_with_the_columns():
    df = PortfolioInvestments([_holding('Acme', 10)]).reported_industry_breakdown()
    assert df.empty
    assert list(df.columns) == REPORTED_INDUSTRY_COLUMNS
    assert df.attrs['sum_fair_value'] is None


@pytest.mark.fast
def test_context_states_exact_industry_coverage():
    holdings = [_holding(f'Co {i}', 100 - i) for i in range(299)] + [_holding('Soft', 1, 'Software')]
    context = PortfolioInvestments(holdings).to_context(detail='minimal')
    assert 'Industry known for 1 of 300 positions' in context
    assert 'Industry known for 0 of 0 positions' in PortfolioInvestments([]).to_context(detail='minimal')


@pytest.mark.fast
def test_empty_industry_filter_warns_when_industries_are_missing(caplog):
    portfolio = PortfolioInvestments([_holding('Acme', 10), _holding('Beta', 5, 'Retail')])
    with caplog.at_level(logging.WARNING, logger='edgar.bdc.investments'):
        assert len(portfolio.filter(industry='software')) == 0
    assert 'does not mean zero exposure' in caplog.text
    assert 'reported_industry_breakdown()' in caplog.text
    assert '1 of 2 holdings have no industry' in caplog.text

    caplog.clear()
    complete = PortfolioInvestments([_holding('Beta', 5, 'Retail')])
    with caplog.at_level(logging.WARNING, logger='edgar.bdc.investments'):
        assert len(complete.filter(industry='software')) == 0
        assert len(portfolio.filter(industry='retail')) == 1
    assert caplog.text == ''


# ---------------------------------------------------------------- real filings, from extracted facts
#
# tests/fixtures/bdc/industry_breakdown_1784/ holds the fact rows these filings
# report for the two concepts read here, verbatim from SEC (see its README).
# The portfolio is built the way from_xbrl builds it: the reported total and
# the breakdown at the report date, with no holdings.

def _from_fixture(name):
    from tests.paths import FIXTURES_DIR

    data = json.loads((FIXTURES_DIR / 'bdc' / 'industry_breakdown_1784' / name).read_text())
    period = data['period_of_report']
    reported_total, _ = _reported_total_fair_value(data['facts'], period)
    portfolio = PortfolioInvestments([], period=period, reported_total_fair_value=reported_total,
                                     reported_industry_rows=_reported_industry_rows(data['facts'], period))
    return data, portfolio


@pytest.mark.fast
def test_arcc_fy2025_reported_industry_breakdown():
    """Ares Capital 10-K for 2025-12-31, accession 0001287750-26-000006."""
    data, portfolio = _from_fixture('arcc_10k_0001287750-26-000006.json')
    assert data['accession_no'] == '0001287750-26-000006'
    assert portfolio.reported_total_fair_value == Decimal('29484800000')

    df = portfolio.reported_industry_breakdown()
    assert list(df.columns) == REPORTED_INDUSTRY_COLUMNS
    assert len(df) == 23
    assert df['fair_value'].sum() == 29_484_800_000
    assert df.attrs == {'sum_fair_value': 29_484_800_000, 'reported_total_fair_value': 29_484_800_000,
                        'difference': 0}

    software = df[df['industry'] == 'Software and Services'].iloc[0]
    assert software['fair_value'] == 7_032_300_000
    assert round(software['pct_of_reported_total'], 4) == 0.2385   # calculated
    assert software['pct_of_net_assets'] == 0.4912                 # filed, as a fraction

    # The prior year's 22 subtotals are in the filing but never used.
    prior = [f for f in data['facts'] if f['period_instant'] == '2024-12-31' and AXIS in f and f['concept'] == FV]
    assert len(prior) == 22
    assert len(_reported_industry_rows(data['facts'], '2024-12-31')) == 22
    assert 'Reported industry breakdown: 23 industries' in portfolio.to_context()


@pytest.mark.fast
def test_fsk_fy2025_reported_industry_breakdown():
    """FS KKR 10-K for 2025-12-31, accession 0001628280-26-011734: rounded subtotals."""
    _, portfolio = _from_fixture('fsk_10k_0001628280-26-011734.json')
    df = portfolio.reported_industry_breakdown()
    assert len(df) == 24
    assert df.iloc[0]['industry'] == 'Software & Services'
    assert df.iloc[0]['fair_value'] == 2_134_000_000
    assert df['pct_of_net_assets'].isna().all()   # not filed on these members, never derived
    assert df.attrs == {'sum_fair_value': 13_009_000_000, 'reported_total_fair_value': 13_008_600_000,
                        'difference': 400_000}


@pytest.mark.fast
def test_main_street_reports_no_breakdown():
    """Main Street 10-K for 2025-12-31, accession 0001396440-26-000016: no industry subtotals."""
    _, portfolio = _from_fixture('main_10k_0001396440-26-000016.json')
    assert portfolio.reported_total_fair_value == Decimal('5518117000')
    df = portfolio.reported_industry_breakdown()
    assert df.empty
    assert list(df.columns) == REPORTED_INDUSTRY_COLUMNS


# ---------------------------------------------------------------- network

@pytest.mark.network
@pytest.mark.vcr
def test_fsk_has_holding_industries_and_a_separate_breakdown():
    """FS KKR 10-K for 2025-12-31, accession 0001628280-26-011734.

    617 of 654 holdings carry an industry, and the filing also reports 24
    industry subtotals. The breakdown is the filer's, not a regrouping of
    rows, and a filtered subset does not inherit it.
    """
    filing = Filing(cik=1422183, company='FS KKR Capital Corp', form='10-K',
                    filing_date='2026-02-25', accession_no='0001628280-26-011734')
    portfolio = PortfolioInvestments.from_xbrl(filing.xbrl())
    assert len(portfolio) == 654
    assert 'Industry known for 617 of 654 positions' in portfolio.to_context(detail='minimal')

    df = portfolio.reported_industry_breakdown()
    assert len(df) == 24
    assert df.attrs['difference'] == 400_000

    software = portfolio.filter(industry='software')
    assert len(software) == 142
    assert software.reported_industry_breakdown().empty
