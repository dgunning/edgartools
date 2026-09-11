"""
Verification for BDC portfolio industry recovery and sector normalization.

37 of the 160 filings in the 2025Q2 DERA file tag no industry dimension, yet
most write the industry into the Investment Identifier member. The parser
now returns those spans, both paths fall back to them and then to a peer
filer's tag for the same issuer, and one table folds the filers' spellings
into a sector.

Fixtures are slices of the real 2025Q2 file: Sixth Street's Automotive and
Business Services groupings, 45 PennantPark rows with a labelled Industry
field, a Main Street row whose issuer Stellus tags, three Vista rows nothing
can resolve, and the three Software spellings from five tagged filers. All
224 columns are kept so the empty-standard-column trap stays represented.
"""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from edgar.bdc.datasets import BDCDataset, _clean_soi_dataframe, _soi_dimension_depth, _soi_industry
from edgar.bdc.industry import (
    INDUSTRY_SOURCES,
    SECTOR_ALIASES,
    clean_industry_label,
    issuer_key,
    normalize_sector,
)
from edgar.bdc.investments import (
    PortfolioInvestment,
    PortfolioInvestments,
    _parse_investment_identifier,
    grouping_industries,
    identifier_industry,
    issuer_from_identifier,
    parse_investment_identifier,
)

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).parent.parent / 'fixtures' / 'bdc'
IDENTIFIER = 'Investment, Identifier Axis'

SIXTH_STREET = '0000950170-25-061008'   # 10-Q for 2025-03-31
PENNANTPARK = '0000950170-25-069165'    # 10-Q for 2025-03-31
MAIN_STREET = '0001396440-25-000068'
VISTA = '0000950170-25-066695'

# Sixth Street Specialty Lending, 10-Q for the quarter ended 2025-03-31: the
# two Truck-Lite Co., LLC positions on the schedule, read from the filing.
TRUCK_LITE_TERM_LOAN = 42_713_000
TRUCK_LITE_REVOLVER = 281_000
CLARIENCE_CLASS_A_UNITS = 820_000     # Truck-Lite's parent, under Equity and Other Investments
SIXTH_STREET_TOTAL_INVESTMENTS = 3_412_032_000    # undimensioned InvestmentOwnedAtFairValue
PENNANTPARK_TOTAL_INVESTMENTS = 1_213_610_000
# PennantPark Investment Corp, same quarter: JF Holdings Corp. first lien.
JF_HOLDINGS_FIRST_LIEN = 49_375_000

TRUCK_LITE = (
    'Debt Investments Automotive Truck-Lite Co., LLC Investment First-lien loan ($42,824 par, '
    'due 2/2031) Initial Acquisition Date 02/13/2024 Reference Rate and Spread SOFR + 5.75% '
    'Interest Rate 10.06%'
)
JF_HOLDINGS = (
    'Investments in Controlled, Affiliated Portfolio Companies - 98.1% First Lien Secured Debt '
    '- 24.3% Issuer Name JF Holdings Corp. Maturity 07/31/2026 Industry Distribution Current '
    'Coupon 10.35% Basis Point Spread Above Index 3M SOFR+605'
)


@pytest.fixture(scope='module')
def soi() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / 'soi_2025q2_sample.tsv', sep='\t', low_memory=False)


@pytest.fixture(scope='module')
def numbers() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / 'num_2025q2_sample.tsv', sep='\t', low_memory=False)


def dataset(frame: pd.DataFrame, numbers: pd.DataFrame = None) -> BDCDataset:
    empty = pd.DataFrame()
    return BDCDataset(
        year=2025, quarter=2, submissions=empty, presentation=empty,
        numbers=empty if numbers is None else numbers, soi=frame,
    )


class TestIdentifierIndustry:
    """The four placements a filer uses, on real identifier strings."""

    @pytest.mark.parametrize('identifier, expected', [
        # PennantPark: a labelled field, closed by the next field or the end
        (JF_HOLDINGS, 'Distribution'),
        ('Investments in Controlled, Affiliated Portfolio Companies - 77.8% Common Equity - 23.0% '
         'Issuer Name AKW Holdings Limited - Common Equity Industry Healthcare, Education and Childcare',
         'Healthcare, Education and Childcare'),
        # West Bay: DERA glued the next field to the label
        ('Investment Debt Investments - 100.0% United States - 100.0% 1st Lien/Senior Secured Debt - '
         '100.0% Airwavz Solutions, Inc. Industry Wireless Telecommunication Services Interest Rate '
         '10.19% Reference Rateand Sp', 'Wireless Telecommunication Services'),
        # Pipe-delimited: SLR and AB
        ('Bank Debt/Senior Secured Loans | AAH Topco., LLC | Diversified Consumer Services | S+525 | '
         '0.75% | 9.67%| 1/2024 | 12/2027', 'Diversified Consumer Services'),
        ('Canadian Corporate Debt | 1st Lien/Senior Secured Debt | Syntax Systems Ltd | Digital '
         'Infrastructure & Services | Term Loan | 9.45% (S + 5.00%', 'Digital Infrastructure & Services'),
        # Schedule grouping ahead of the company: Sixth Street, BlackRock
        (TRUCK_LITE, 'Automotive'),
        ('Debt Investments Aerospace & Defense Arcline FM Holdings, LLC (Fairbanks Morse, LLC) '
         'Instrument First Lien Term Loan Ref SOFR(Q) Spread 4.50% Total Coupon 8.80% Maturity 6/28/2028',
         'Aerospace & Defense'),
        # Between the company and the instrument: Fidus, Saratoga
        ('Non-control/Non-affiliate Investments Donovan Food Brokerage, LLC Business Services First '
         'Lien Debt Variable Index Spread (S + 6.00%) Variable Index Floor (2.00%) Rate Cash 10.29% '
         'Rate PIK 0.00% Investment date 2/23/2024 Maturity 2/23/2029', 'Business Services'),
        ('Affiliate investments - 10.3% - ETU Holdings, Inc. - Corporate Education Software - First '
         'Lien Term Loan (3M USD TERM SOFR+9.00%), 13.47% Cash, 8/18/2027', 'Corporate Education Software'),
    ])
    def test_industry_is_read_from_the_identifier(self, identifier, expected):
        assert identifier_industry(identifier) == expected

    @pytest.mark.parametrize('identifier', [
        'Debt Investments Automotive',                      # the grouping row itself
        'Cash and Cash Equivalents - 10.1% BlackRock Federal FD Institutional 81 Current Coupon 5.03%',
        'Portfolio Company Any Hour LLC First Lien Delayed Draw Term Loan',   # company, no industry
        'ADMI Corp. (aka Aspen Dental) First and Second Lien Debt Original Purchase Date 3/6/2024 '
        'SOFR Spread 3.75% Interest Rate 8.22% Due 12/23/2027',
        'AAC Holdings, Inc., Common Stock',
        'Accelerate360 Holdings, LLC Undrawn Commitment',
        'Banff Merger Sub, Inc.',
        '',
    ])
    def test_nothing_is_invented(self, identifier):
        assert identifier_industry(identifier) is None

    def test_none_is_not_a_string(self):
        assert identifier_industry(None) is None

    def test_a_truncated_label_is_not_a_fragment(self):
        """DERA cuts identifiers at 255 characters; the tail is not an industry."""
        head = ('Investments in Non-Controlled, Non-Affiliated Portfolio Companies - 148.3% First Lien '
                'Secured Debt - 78.4% Issuer Name Some Long Company Name Holdings, LLC Maturity 06/30/2029 ')
        head = head.replace('Some Long Company Name', 'Some Long Company Name' + 'x' * (
            255 - len(head + 'Industry Healthcare, Education and Childcare Cur')))
        truncated = (head + 'Industry Healthcare, Education and Childcare Current Coupon 11.30%')[:255]
        assert truncated.endswith('Cur'), truncated[-20:]
        assert identifier_industry(truncated) is None
        assert identifier_industry(head + 'Industry Healthcare, Education and Childcare Current Coupon 11.30%') == \
            'Healthcare, Education and Childcare'

    def test_axis_prefix_is_ignored(self):
        assert identifier_industry(f'us-gaap:InvestmentIdentifierAxis: {TRUCK_LITE}') == 'Automotive'

    def test_grouping_rows_name_the_filers_vocabulary(self, soi):
        ids = soi.loc[soi['adsh'] == SIXTH_STREET, IDENTIFIER].dropna().unique()
        groupings = grouping_industries(ids)
        assert 'Automotive' in groupings
        assert not any('Truck-Lite' in grouping or 'IRGSE' in grouping for grouping in groupings)
        assert grouping_industries([
            'Debt Investments Business Services', 'Debt Investments Automotive', TRUCK_LITE,
            'Controlled Affiliated Investments IRGSE Holding Corp.', 'Software First and Second Lien Debt',
            'Vitesse Systems, Secured Debt 1',
        ]) == ('Business Services', 'Automotive', 'Software')

    def test_a_filers_own_grouping_beats_the_table(self):
        """"Retail and Consumer Products" is Sixth Street's spelling, not the table's."""
        identifier = ('Debt Investments Retail and Consumer Products Sunbit Receivables Trust IV Investment '
                      'First-lien loan ($33,000 par, due 4/2028) Initial Acquisition Date 04/19/2024')
        assert identifier_industry(identifier, candidates=('Retail and Consumer Products',)) == \
            'Retail and Consumer Products'

    def test_parser_returns_the_industry_with_the_company(self):
        parsed = parse_investment_identifier(f'us-gaap:InvestmentIdentifierAxis: {TRUCK_LITE}')
        identifier, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {TRUCK_LITE}'
        )
        assert parsed.industry == 'Automotive'
        assert (parsed.identifier, parsed.company_name, parsed.investment_type) == (identifier, company, investment_type)


class TestIssuerKeys:

    @pytest.mark.parametrize('name, expected', [
        ('Truck-Lite Co., LLC', 'truck lite'),
        ('TRUCK-LITE CO LLC [Member]', 'truck lite'),
        ('Channel Partners Intermediateco, LLC', 'channel partners intermediateco'),
        ('Renew Financial LLC (f/k/a Renewable Funding, LLC)', 'renew financial'),
        ('Holdings, LLC', 'holdings'),
        ('LLC', None),
        (None, None),
    ])
    def test_issuer_key(self, name, expected):
        assert issuer_key(name) == expected

    @pytest.mark.parametrize('identifier, expected', [
        (TRUCK_LITE, 'truck lite'),
        ('AAC Holdings, Inc., Common Stock', 'aac holdings'),
        ('Acronis International', 'acronis international'),
        ('Controlled Affiliates, 36th Street Capital Partners Holdings, LLC, Membership Units',
         '36th street capital partners holdings'),
        ('Cash and Cash Equivalents - 10.1%', None),
        ('Debt Investments Automotive', None),
    ])
    def test_issuer_from_identifier(self, identifier, expected):
        assert issuer_from_identifier(identifier) == expected


class TestSectorNormalization:

    @pytest.mark.parametrize('industry, sector', [
        ('Software Sector', 'Software'),
        ('Software And Services', 'Software'),
        ('Software & Services', 'Software'),
        ('Healthcare Sector', 'Healthcare'),
        ('Health Care Providers & Services Sector', 'Healthcare'),
        ('Healthcare & Pharmaceuticals', 'Healthcare'),
        ('Automotive Sector', 'Automotive'),
        ('Aerospace Defense', 'Aerospace and Defense'),
        ('Chemicals, Plastics & Rubber', 'Chemicals, Plastics and Rubber'),
        ('IT Services Sector', 'IT Services'),
    ])
    def test_spellings_fold_into_one_sector(self, industry, sector):
        assert normalize_sector(industry) == sector

    def test_unknown_labels_pass_through_as_their_own_sector(self):
        assert normalize_sector('Underwater Basket Weaving Sector') == 'Underwater Basket Weaving'
        assert normalize_sector('Retail and Consumer Products') == 'Retail and Consumer Products'
        assert normalize_sector('Marketing Orchestration Software') == 'Marketing Orchestration Software'

    def test_empty_is_none(self):
        assert normalize_sector(None) is None
        assert normalize_sector('') is None
        assert normalize_sector('   ') is None

    def test_every_sector_maps_to_itself(self):
        for sector in set(SECTOR_ALIASES.values()):
            assert normalize_sector(sector) == sector, sector

    @pytest.mark.parametrize('raw, expected', [
        ('Healthcare Sector [Member]', 'Healthcare Sector'),
        ('http://fasb.org/us-gaap/2024#HealthcareSectorMember', 'Healthcare Sector'),
        ('us-gaap:SoftwareSectorMember', 'Software Sector'),
        ('Chemicals Sector', 'Chemicals Sector'),
    ])
    def test_member_spellings_become_labels(self, raw, expected):
        assert clean_industry_label(raw) == expected


class TestPortfolioInvestment:

    def test_sector_follows_industry(self):
        inv = PortfolioInvestment(identifier='x', company_name='X', investment_type='Loan',
                                  industry='Software Sector', industry_source='axis')
        assert inv.sector == 'Software'
        assert inv.industry_source in INDUSTRY_SOURCES

    def test_no_industry_means_no_source_and_no_empty_string(self):
        inv = PortfolioInvestment(identifier='x', company_name='X', investment_type='Loan')
        assert inv.industry is None and inv.industry_source is None and inv.sector is None
        blank = PortfolioInvestment(identifier='x', company_name='X', investment_type='Loan',
                                    industry='  ', industry_source='axis')
        assert blank.industry is None and blank.industry_source is None

    def test_unknown_source_is_refused(self):
        with pytest.raises(ValueError, match='industry_source'):
            PortfolioInvestment(identifier='x', company_name='X', investment_type='Loan',
                                industry='Software', industry_source='guess')

    def test_filter_and_by_industry(self):
        investments = PortfolioInvestments([
            PortfolioInvestment(identifier='a', company_name='A', investment_type='Loan',
                                fair_value=Decimal(300), industry='Software Sector', industry_source='axis'),
            PortfolioInvestment(identifier='b', company_name='B', investment_type='Loan',
                                fair_value=Decimal(100), industry='Software & Services', industry_source='identifier'),
            PortfolioInvestment(identifier='c', company_name='C', investment_type='Loan',
                                fair_value=Decimal(50), industry='Healthcare Sector', industry_source='peer'),
            PortfolioInvestment(identifier='d', company_name='D', investment_type='Loan', fair_value=Decimal(50)),
        ], period='2025-03-31')

        assert len(investments.filter(industry='software')) == 2      # both spellings, via the sector
        assert len(investments.filter(industry='Software Sector')) == 1
        assert len(investments.filter(industry='nothing')) == 0
        assert investments.industry_coverage == 0.75

        by_sector = investments.by_industry().set_index('sector')
        assert by_sector.loc['Software', 'total_fair_value'] == 400
        assert by_sector.loc['Software', 'num_investments'] == 2
        assert by_sector.loc['Software', 'pct_of_portfolio'] == 0.8
        assert by_sector.index[-1] is None and by_sector.loc[None, 'total_fair_value'] == 50
        by_industry = investments.by_industry(by='industry')
        assert list(by_industry['industry'][:2]) == ['Software Sector', 'Software & Services']
        assert PortfolioInvestments([]).by_industry().empty
        with pytest.raises(ValueError):
            investments.by_industry(by='colour')

    def test_dataframe_carries_the_new_columns(self):
        inv = PortfolioInvestment(identifier='x', company_name='X', investment_type='Loan',
                                  industry='Software Sector', industry_source='axis')
        row = PortfolioInvestments([inv]).to_dataframe().iloc[0]
        assert (row['industry'], row['sector'], row['industry_source']) == ('Software Sector', 'Software', 'axis')


def _fact(identifier, concept='us-gaap:InvestmentOwnedAtFairValue', value=1_000_000, **extra):
    fact = {
        'concept': concept, 'period_type': 'instant', 'period_instant': '2025-03-31',
        'numeric_value': value if concept != 'us-gaap:InvestmentIndustrySectorExtensibleEnumeration' else None,
        'value': value, 'dim_us-gaap_InvestmentIdentifierAxis': identifier,
    }
    fact.update(extra)
    return fact


class TestFromXbrlSources:
    """Every source in the chain, on one stubbed filing."""

    def test_axis_enumeration_identifier_peer_and_none(self):
        facts = [
            _fact('Alpha Software, LLC, First lien senior secured loan',
                  **{'dim_us-gaap_IndustrySectorAxis': 'us-gaap:SoftwareSectorMember'}),
            _fact('Beta Health, Inc., First lien senior secured loan'),
            _fact('Beta Health, Inc., First lien senior secured loan',
                  concept='us-gaap:InvestmentIndustrySectorExtensibleEnumeration',
                  value='http://fasb.org/us-gaap/2024#HealthcareSectorMember'),
            _fact(TRUCK_LITE, value=TRUCK_LITE_TERM_LOAN),
            _fact('Debt Investments Automotive', value=TRUCK_LITE_TERM_LOAN),   # the grouping subtotal
            _fact('Alpha Software, LLC, Second lien senior secured loan'),       # same issuer, untagged
            _fact('Gamma Widgets Corp., First lien senior secured loan'),        # nothing to recover
        ]
        xbrl = SimpleNamespace(facts=SimpleNamespace(get_facts=lambda: facts), element_catalog={})
        investments = PortfolioInvestments.from_xbrl(xbrl)
        by_company = {inv.identifier: inv for inv in investments}

        alpha = by_company['Alpha Software, LLC, First lien senior secured loan']
        assert (alpha.industry, alpha.industry_source) == ('Software Sector', 'axis')
        beta = by_company['Beta Health, Inc., First lien senior secured loan']
        assert (beta.industry, beta.industry_source) == ('Healthcare Sector', 'enumeration')
        truck = by_company[TRUCK_LITE]
        assert (truck.industry, truck.industry_source, truck.company_name) == ('Automotive', 'identifier', 'Truck-Lite Co., LLC')
        assert truck.fair_value == TRUCK_LITE_TERM_LOAN
        alpha_second = by_company['Alpha Software, LLC, Second lien senior secured loan']
        assert (alpha_second.industry, alpha_second.industry_source) == ('Software Sector', 'peer')
        gamma = by_company['Gamma Widgets Corp., First lien senior secured loan']
        assert gamma.industry is None and gamma.industry_source is None
        assert by_company['Debt Investments Automotive'].industry is None

        by_sector = investments.by_industry().set_index('sector')
        assert by_sector.loc['Software', 'num_investments'] == 2
        assert by_sector.loc['Automotive', 'total_fair_value'] == TRUCK_LITE_TERM_LOAN


class TestDatasetIndustryFallbacks:
    """The DERA path on the 2025Q2 slice."""

    def test_fixture_filings_tag_no_industry(self, soi):
        for adsh in (SIXTH_STREET, PENNANTPARK, MAIN_STREET, VISTA):
            rows = soi[soi['adsh'] == adsh]
            assert rows['Industry Sector Axis'].isna().all(), adsh
            assert rows['Investment, Industry Sector [Extensible Enumeration]'].isna().all(), adsh

    def test_truck_lite_is_automotive_from_the_identifier(self, soi):
        resolved = _soi_industry(soi)
        truck = soi[soi[IDENTIFIER].str.contains('Truck-Lite', na=False)]
        assert len(truck) == 2
        assert set(resolved.loc[truck.index, 'industry']) == {'Automotive'}
        assert set(resolved.loc[truck.index, 'industry_source']) == {'identifier'}
        assert set(resolved.loc[truck.index, 'sector']) == {'Automotive'}
        grouping = soi[soi[IDENTIFIER] == 'Debt Investments Automotive']
        assert len(grouping) == 1
        assert resolved.loc[grouping.index, 'industry'].isna().all()

    def test_sixth_street_automotive_exposure(self, soi):
        """Two Truck-Lite loans at one depth and the Clarience units at another are all line items."""
        summary = dataset(soi[soi['adsh'] == SIXTH_STREET]).summary_by_industry().set_index('industry')
        assert summary.loc['Automotive', 'total_fair_value'] == \
            TRUCK_LITE_TERM_LOAN + TRUCK_LITE_REVOLVER + CLARIENCE_CLASS_A_UNITS
        assert summary.loc['Automotive', 'num_investments'] == 3
        # The "Debt Investments Automotive" grouping row carries the same dollars and is not counted
        grouping = soi[soi[IDENTIFIER] == 'Debt Investments Automotive']
        assert grouping['Initial fair value of Investment'].iloc[0] == TRUCK_LITE_TERM_LOAN + TRUCK_LITE_REVOLVER

    def test_pennantpark_reads_the_labelled_field(self, soi):
        resolved = _soi_industry(soi)
        pnnt = soi[soi['adsh'] == PENNANTPARK]
        labelled = pnnt[pnnt[IDENTIFIER].str.contains('Industry', na=False)]
        assert len(labelled) == 45
        assert (resolved.loc[labelled.index, 'industry_source'] == 'identifier').mean() > 0.9
        jf = pnnt[pnnt[IDENTIFIER] == JF_HOLDINGS]
        assert len(jf) == 1
        assert resolved.loc[jf.index[0], 'industry'] == 'Distribution'
        assert soi.loc[jf.index[0], 'Initial fair value of Investment'] == JF_HOLDINGS_FIRST_LIEN
        rollups = pnnt[~pnnt[IDENTIFIER].str.contains('Industry', na=False)]
        assert resolved.loc[rollups.index, 'industry'].isna().all()

    def test_peer_propagation_from_a_tagged_filer(self, soi):
        resolved = _soi_industry(soi)
        row = soi[soi[IDENTIFIER] == 'Channel Partners Intermediateco, LLC, Secured Debt 1']
        assert len(row) == 1 and row['adsh'].iloc[0] == MAIN_STREET
        assert resolved.loc[row.index[0], 'industry'] == 'Retail Sector'
        assert resolved.loc[row.index[0], 'industry_source'] == 'peer'
        assert resolved.loc[row.index[0], 'sector'] == 'Retail'
        suppliers = soi[soi['Investment, Issuer Name Axis'].str.contains('Channel Partners', na=False)]
        assert set(suppliers['name']) == {'STELLUS CAPITAL INVESTMENT CORP', 'STELLUS PRIVATE CREDIT BDC'}
        assert set(resolved.loc[suppliers.index, 'industry_source']) == {'axis'}

    def test_silence_when_nothing_can_be_recovered(self, soi):
        resolved = _soi_industry(soi)
        acronis = soi[soi[IDENTIFIER] == 'Acronis International']
        assert len(acronis) == 1
        assert resolved.loc[acronis.index[0], 'industry'] is pd.NA or pd.isna(resolved.loc[acronis.index[0], 'industry'])
        assert pd.isna(resolved.loc[acronis.index[0], 'industry_source'])
        assert pd.isna(resolved.loc[acronis.index[0], 'sector'])
        assert (resolved['industry'].isna() == resolved['industry_source'].isna()).all()
        assert not (resolved['industry'].fillna('x') == '').any()

    def test_cleaned_frame_carries_source_and_sector(self, soi):
        cleaned = _clean_soi_dataframe(soi.copy())
        columns = list(cleaned.columns)
        position = columns.index('industry')
        assert columns[position:position + 3] == ['industry', 'industry_source', 'sector']
        assert set(cleaned['industry_source'].dropna()) <= set(INDUSTRY_SOURCES)
        # The documented one-liner works on the cleaned frame
        assert cleaned.groupby('sector')['fair_value'].sum()['Automotive'] == \
            TRUCK_LITE_TERM_LOAN + TRUCK_LITE_REVOLVER + CLARIENCE_CLASS_A_UNITS

    def test_sector_merges_the_software_spellings(self, soi):
        by_industry = dataset(soi).summary_by_industry().set_index('industry')
        spellings = ['Software Sector', 'Software And Services', 'Software & Services']
        for spelling in spellings:
            assert spelling in by_industry.index, spelling
        by_sector = dataset(soi).summary_by_industry(by='sector').set_index('sector')
        assert list(by_sector.columns) == ['total_fair_value', 'num_bdcs', 'num_investments']
        software_rows = by_industry[[normalize_sector(label) == 'Software' for label in by_industry.index]]
        assert set(software_rows.index) >= set(spellings)
        assert by_sector.loc['Software', 'total_fair_value'] == software_rows['total_fair_value'].sum()
        assert by_sector.loc['Software', 'num_investments'] == software_rows['num_investments'].sum()
        assert by_sector.loc['Software', 'num_bdcs'] == 5
        assert 'Software Sector' not in by_sector.index

    def test_summary_by_industry_default_keeps_raw_labels(self, soi):
        summary = dataset(soi).summary_by_industry()
        assert list(summary.columns) == ['industry', 'total_fair_value', 'num_bdcs', 'num_investments']
        with pytest.raises(ValueError):
            dataset(soi).summary_by_industry(by='colour')


class TestSummaryByCompany:

    def test_filed_totals_and_line_item_counts(self, soi, numbers):
        summary = dataset(soi, numbers).summary_by_company()
        assert list(summary.columns) == ['cik', 'name', 'form', 'filed', 'num_investments', 'total_fair_value']
        by_name = summary.set_index('name')
        assert by_name.loc['SIXTH STREET SPECIALTY LENDING, INC.', 'total_fair_value'] == SIXTH_STREET_TOTAL_INVESTMENTS
        assert by_name.loc['PENNANTPARK INVESTMENT CORP', 'total_fair_value'] == PENNANTPARK_TOTAL_INVESTMENTS
        # 42 of the 53 PennantPark rows in the slice sit at the depth where its line items live
        assert by_name.loc['PENNANTPARK INVESTMENT CORP', 'num_investments'] == 42
        assert summary['total_fair_value'].is_monotonic_decreasing

    def test_falls_back_to_summing_line_items(self, soi):
        """Without a filed total the line items are summed, and the grouping rows above them are not."""
        summary = dataset(soi).summary_by_company().set_index('name')
        sixth = soi[soi['adsh'] == SIXTH_STREET]
        depth = _soi_dimension_depth(soi).loc[sixth.index]
        line_items = sixth[depth == depth.mode().iloc[0]]
        assert depth.mode().iloc[0] == 2 and len(line_items) == 16
        assert 'Debt Investments Automotive' not in set(line_items[IDENTIFIER])
        assert summary.loc['SIXTH STREET SPECIALTY LENDING, INC.', 'total_fair_value'] == \
            line_items['Initial fair value of Investment'].sum()
        assert summary.loc['SIXTH STREET SPECIALTY LENDING, INC.', 'num_investments'] == 16

    def test_empty_dataset(self):
        assert dataset(pd.DataFrame()).summary_by_company().empty
