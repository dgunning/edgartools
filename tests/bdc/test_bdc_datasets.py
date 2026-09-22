"""
Verification for the SEC DERA BDC data set column resolution.

The SOI extract's headers are XBRL labels. When the SEC relocated the data sets
in 2026 the fair value, cost and shares headers switched from the us-gaap
standard labels to one filer's custom labels, and the standard-label columns
stayed in the file with every cell empty. `summary_by_industry()` then summed
the empty column and reported $0 for every industry.

The fixture is a slice of the real 2024Q4 file: Ares Capital's 23 industry
subtotals for 2024-09-30 and 2023-12-31 plus 60 line items and its Ivy Hill
position, and
Stellus Capital Investment Corp, which tags industry subtotals on the axis and
line items on the extensible enumeration. Both deliberately-empty standard
columns are kept.
"""
import logging
from pathlib import Path

import pandas as pd
import pytest

from edgar.bdc.datasets import (
    BDCDataset,
    ScheduleOfInvestmentsData,
    _clean_industry_label,
    _clean_soi_dataframe,
    _soi_field,
)

pytestmark = pytest.mark.fast

FIXTURE = Path(__file__).parent.parent / 'fixtures' / 'bdc' / 'soi_2024q4_sample.tsv'
ARCC = 1287750
STELLUS = 1551901

# Ground truth from ARCC's 10-Q for the quarter ended 2024-09-30
# (accession 0001287750-24-000054), read from the filed XBRL by industry member.
ARCC_SOFTWARE_AND_SERVICES = 6_572_000_000
ARCC_HEALTHCARE = 3_329_300_000
ARCC_TOTAL_INVESTMENTS = 25_918_200_000
ARCC_INDUSTRY_COUNT = 23

# Stellus Capital Investment Corp 10-Q for 2024-09-30 (0001558370-24-014910):
# the Business Services Sector subtotal on the Industry Sector axis.
STELLUS_BUSINESS_SERVICES = 220_739_114


@pytest.fixture(scope='module')
def soi() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, sep='\t', low_memory=False)


def dataset(frame: pd.DataFrame) -> BDCDataset:
    empty = pd.DataFrame()
    return BDCDataset(year=2024, quarter=4, submissions=empty, numbers=empty, presentation=empty, soi=frame)


class TestRelocatedHeaders:
    """The relocated files carry the dollars under custom labels."""

    def test_fixture_reproduces_the_trap(self, soi):
        assert soi['Investment Owned, Fair Value'].notna().sum() == 0
        assert soi['Investment Owned, Cost'].notna().sum() == 0
        assert soi['Initial fair value of Investment'].notna().sum() > 500

    def test_fair_value_resolves_to_the_populated_header(self, soi):
        fair_value = _soi_field(soi, 'fair_value')
        assert fair_value.notna().sum() == soi['Initial fair value of Investment'].notna().sum()
        assert fair_value.name == 'fair_value'

    def test_cost_and_shares_resolve(self, soi):
        assert _soi_field(soi, 'cost').notna().sum() == soi['Adjusted cost basis'].notna().sum()
        assert _soi_field(soi, 'shares').notna().sum() == soi['Investment shares'].notna().sum()

    def test_legacy_layout_still_resolves(self, soi):
        """Files downloaded before the relocation carried the standard label."""
        legacy = soi.drop(columns=['Investment Owned, Fair Value']).rename(
            columns={'Initial fair value of Investment': 'Investment Owned, Fair Value'}
        )
        assert _soi_field(legacy, 'fair_value').sum() == _soi_field(soi, 'fair_value').sum()

    def test_cleaned_frame_has_one_column_per_field(self, soi):
        cleaned = _clean_soi_dataframe(soi.copy())
        for field in ('fair_value', 'cost', 'shares', 'principal', 'industry'):
            assert field in cleaned.columns, field
        assert 'Initial fair value of Investment' not in cleaned.columns
        assert 'Investment Owned, Fair Value' not in cleaned.columns
        assert 'Industry Sector Axis' not in cleaned.columns
        assert cleaned['fair_value'].notna().sum() == soi['Initial fair value of Investment'].notna().sum()
        # The documented one-liner works on the cleaned frame
        by_industry = cleaned.groupby('industry')['fair_value'].sum()
        assert by_industry['Software And Services'] > 0


class TestSummaryByIndustry:

    def test_arcc_industry_exposure_matches_the_filing(self, soi):
        summary = dataset(soi[soi['cik'] == ARCC]).summary_by_industry()
        by_industry = summary.set_index('industry')

        assert by_industry.loc['Software And Services', 'total_fair_value'] == ARCC_SOFTWARE_AND_SERVICES
        assert by_industry.loc['Healthcare Sector', 'total_fair_value'] == ARCC_HEALTHCARE
        assert len(summary) == ARCC_INDUSTRY_COUNT
        # The industry subtotals partition the portfolio
        assert summary['total_fair_value'].sum() == ARCC_TOTAL_INVESTMENTS
        assert (summary['num_bdcs'] == 1).all()

    def test_prior_period_comparatives_are_excluded(self, soi):
        arcc = soi[soi['cik'] == ARCC]
        assert (arcc['ddate'] == '2023-12-31').sum() > 0, 'fixture must carry comparatives'
        summary = dataset(arcc).summary_by_industry()
        assert summary['total_fair_value'].sum() == ARCC_TOTAL_INVESTMENTS

    def test_axis_wins_over_enumeration_within_one_filing(self, soi):
        """Stellus tags subtotals on the axis and line items on the enumeration."""
        stellus = soi[soi['cik'] == STELLUS]
        assert stellus['Investment, Industry Sector [Extensible Enumeration]'].notna().sum() > 100
        summary = dataset(stellus).summary_by_industry().set_index('industry')
        assert summary.loc['Business Services Sector', 'total_fair_value'] == STELLUS_BUSINESS_SERVICES

    def test_enumeration_serves_a_filing_without_the_axis(self, soi):
        stellus = soi[soi['cik'] == STELLUS].drop(columns=['Industry Sector Axis'])
        summary = dataset(stellus).summary_by_industry().set_index('industry')
        assert 'Business Services Sector' in summary.index
        assert summary.loc['Business Services Sector', 'num_bdcs'] == 1

    def test_columns_and_order(self, soi):
        summary = dataset(soi).summary_by_industry()
        assert list(summary.columns) == ['industry', 'total_fair_value', 'num_bdcs', 'num_investments']
        assert summary['total_fair_value'].is_monotonic_decreasing
        assert summary['num_bdcs'].max() == 2

    def test_missing_fair_value_warns_and_keeps_counts(self, soi, caplog):
        """The silence check: an unresolvable column is named, not zeroed."""
        no_fair_value = soi.drop(columns=[
            'Initial fair value of Investment', 'Investments, Fair Value Disclosure',
        ], errors='ignore')
        with caplog.at_level(logging.WARNING, logger='edgar.bdc.datasets'):
            summary = dataset(no_fair_value).summary_by_industry()
        assert 'total_fair_value' not in summary.columns
        assert summary['num_bdcs'].max() == 2
        assert 'fair_value' in caplog.text
        assert 'Investment Owned, Fair Value' in caplog.text

    def test_empty_dataset(self):
        assert dataset(pd.DataFrame()).summary_by_industry().empty


class TestSearchAndTopCompanies:

    def test_search_returns_fair_values(self, soi):
        results = ScheduleOfInvestmentsData(soi).search('Ivy Hill')
        assert not results.empty
        assert results['fair_value'].iloc[0] > 1_000_000_000

    def test_top_companies_totals_are_not_zero(self, soi):
        top = ScheduleOfInvestmentsData(soi).top_companies(5)
        assert (top['total_fair_value'] > 0).all()


class TestIndustryLabels:

    @pytest.mark.parametrize('raw, expected', [
        ('Healthcare Sector [Member]', 'Healthcare Sector'),
        ('Media Broadcasting Subscription Member', 'Media Broadcasting Subscription'),
        ('http://fasb.org/us-gaap/2024#HealthcareSectorMember', 'Healthcare Sector'),
        ('http://stelluscapital.com/20240930#BusinessServicesSectorMember', 'Business Services Sector'),
        ('Chemicals Sector', 'Chemicals Sector'),
    ])
    def test_three_spellings_become_one(self, raw, expected):
        assert _clean_industry_label(raw) == expected

    def test_non_strings_pass_through(self):
        assert _clean_industry_label(None) is None
        assert pd.isna(_clean_industry_label(float('nan')))
