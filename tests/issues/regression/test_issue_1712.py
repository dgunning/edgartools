"""Regression: clean_industry_label keeps every member of a multi-member enumeration value.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1712

`clean_industry_label` split on the last '#' of the whole string, so a value
holding several whitespace-separated expanded-name URIs kept only the last
member, and a URI with a scheme other than http was not read at all. A
multi-member value now returns every label joined with '; ' in source order,
has no single sector (never `normalize_sector` of the joined string), and is
never the donor when a peer position or another filer's issuer fills a missing
industry.

Measured 2026-11-11 on the DERA BDC data sets 2024Q3-2025Q4 plus the 2026
monthly sets: ~32,000 'Investment, Industry Sector [Extensible Enumeration]'
values from 15 BDCs, 0 with more than one member. This guards against silently
dropping data if a filer starts writing them; every single-member result is
unchanged.
"""
from pathlib import Path

import pandas as pd

from edgar.bdc.datasets import _resolve_industry, _soi_industry
from edgar.bdc.industry import clean_industry_label, is_multi_member_industry, issuer_key
from edgar.bdc.investments import PortfolioInvestment, _fill_industries

FIXTURE = Path(__file__).parents[2] / 'fixtures' / 'bdc' / 'soi_2025q4_whitehorse_1712.tsv'
ENUM = 'Investment, Industry Sector [Extensible Enumeration]'
ISSUER = 'Investment, Issuer Name Axis'
HEALTH = 'http://fasb.org/us-gaap/2024#HealthcareSectorMember'
TECH = 'http://fasb.org/us-gaap/2024#TechnologySectorMember'
MULTI = f'{HEALTH} {TECH}'


def test_issue_inputs():
    assert clean_industry_label(MULTI) == 'Healthcare Sector; Technology Sector'
    assert clean_industry_label('http://www.example.com/20240331#ITServicesMember') == 'ITServices'
    assert clean_industry_label('urn:example:2024#SoftwareSectorMember') == 'Software Sector'


def test_single_member_forms_unchanged():
    assert clean_industry_label(HEALTH) == 'Healthcare Sector'
    assert clean_industry_label('Healthcare Sector [Member]') == 'Healthcare Sector'
    assert clean_industry_label('us-gaap:HealthcareSectorMember') == 'Healthcare Sector'
    assert clean_industry_label('Software and Services') == 'Software and Services'
    assert clean_industry_label(None) is None
    assert issuer_key('Truck-Lite Co., LLC') == 'truck lite'


def test_multi_member_has_no_sector_per_filing():
    label = clean_industry_label(MULTI)
    assert is_multi_member_industry(label, 'enumeration')
    assert not is_multi_member_industry('Healthcare Sector', 'enumeration')
    assert not is_multi_member_industry('A; B', 'identifier')
    holding = PortfolioInvestment('Acme', 'Acme', 'loan', industry=label, industry_source='enumeration')
    assert holding.industry == 'Healthcare Sector; Technology Sector'
    assert holding.sector is None
    single = PortfolioInvestment('Acme', 'Acme', 'loan', industry='Healthcare Sector', industry_source='enumeration')
    assert single.sector == 'Healthcare'


def test_multi_member_is_not_a_peer_donor_per_filing():
    investments = {
        'a': {'identifier': 'a', 'company_name': 'Acme Inc', 'industry': clean_industry_label(MULTI),
              'industry_source': 'enumeration'},
        'b': {'identifier': 'b', 'company_name': 'Acme, Inc.'},
    }
    _fill_industries(investments)
    assert investments['a']['industry'] == 'Healthcare Sector; Technology Sector'
    assert 'industry' not in investments['b']


def test_single_member_is_still_a_peer_donor_per_filing():
    investments = {
        'a': {'identifier': 'a', 'company_name': 'Acme Inc', 'industry': 'Healthcare Sector',
              'industry_source': 'enumeration'},
        'b': {'identifier': 'b', 'company_name': 'Acme, Inc.'},
    }
    _fill_industries(investments)
    assert investments['b']['industry'] == 'Healthcare Sector'
    assert investments['b']['industry_source'] == 'peer'


def _two_filer_frame(donor_value):
    return pd.DataFrame({
        'adsh': ['filer-1', 'filer-2'],
        ENUM: [donor_value, None],
        ISSUER: ['Acme Inc', 'Acme, Inc.'],
    })


def test_multi_member_is_not_a_peer_donor_across_filers():
    df = _two_filer_frame(MULTI)
    resolved = _resolve_industry(df, [ENUM])
    assert resolved.loc[0, 'industry'] == 'Healthcare Sector; Technology Sector'
    assert pd.isna(resolved.loc[1, 'industry'])
    assert pd.isna(resolved.loc[1, 'industry_source'])
    sectors = _soi_industry(df)['sector']
    assert pd.isna(sectors[0]) and pd.isna(sectors[1])


def test_single_member_is_still_a_peer_donor_across_filers():
    df = _two_filer_frame(HEALTH)
    resolved = _resolve_industry(df, [ENUM])
    assert resolved.loc[1, 'industry'] == 'Healthcare Sector'
    assert resolved.loc[1, 'industry_source'] == 'peer'
    assert _soi_industry(df)['sector'][1] == 'Healthcare'


def test_real_single_member_control_whitehorse():
    """WhiteHorse Finance 10-Q 0001104659-25-108820 (DERA 2025Q4): the 'Real Estates' debt holding,
    $21,016,000 cost, carries enumeration ...20250930#RealEstatesMember and axis 'Real Estates [Member]'."""
    df = pd.read_csv(FIXTURE, sep='\t')
    assert df.loc[0, 'adsh'] == '0001104659-25-108820'
    assert clean_industry_label(df.loc[0, ENUM]) == 'Real Estates'
    axis = _soi_industry(df).iloc[0]
    assert (axis['industry'], axis['industry_source'], axis['sector']) == ('Real Estates', 'axis', 'Real Estate')
    enum = _soi_industry(df.drop(columns=['Industry Sector Axis'])).iloc[0]
    assert (enum['industry'], enum['industry_source'], enum['sector']) == ('Real Estates', 'enumeration', 'Real Estate')
