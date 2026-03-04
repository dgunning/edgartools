"""
Verification for the StandardizedFinancials API.

Unit tests (no network) test the data structures and formatting.
Integration tests (network) verify end-to-end extraction from real filings.
"""

import pytest
from edgar.standardized_financials import (
    StandardizedMetric,
    StandardizedFinancials,
    _format_value,
    _calculate_derived_metrics,
    METRIC_SECTIONS,
    ALL_METRICS,
)


# ---------------------------------------------------------------------------
# Unit tests — no network
# ---------------------------------------------------------------------------

class TestStandardizedMetric:

    def test_has_value_true(self):
        m = StandardizedMetric(name='Revenue', value=100.0, concept='us-gaap:Revenues',
                               confidence=0.95, source='tree')
        assert m.has_value is True

    def test_has_value_false_when_none(self):
        m = StandardizedMetric(name='Revenue', value=None, concept=None,
                               confidence=0.0, source='unmapped')
        assert m.has_value is False

    def test_has_value_false_when_excluded(self):
        m = StandardizedMetric(name='Inventory', value=None, concept=None,
                               confidence=0.0, source='excluded', is_excluded=True)
        assert m.has_value is False

    def test_repr_with_value(self):
        m = StandardizedMetric(name='Revenue', value=394_328_000_000, concept='c',
                               confidence=0.95, source='tree')
        r = repr(m)
        assert 'Revenue' in r
        assert '394.3B' in r

    def test_repr_excluded(self):
        m = StandardizedMetric(name='Inventory', value=None, concept=None,
                               confidence=0.0, source='excluded', is_excluded=True)
        assert 'excluded' in repr(m)

    def test_repr_none(self):
        m = StandardizedMetric(name='Goodwill', value=None, concept=None,
                               confidence=0.0, source='unmapped')
        assert 'None' in repr(m)


class TestFormatValue:

    def test_billions(self):
        assert _format_value(394_328_000_000) == '394.3B'

    def test_millions(self):
        assert _format_value(42_500_000) == '42.5M'

    def test_thousands(self):
        assert _format_value(5_200) == '5.2K'

    def test_small(self):
        assert _format_value(42) == '42'

    def test_negative(self):
        assert _format_value(-10_000_000_000) == '-10.0B'

    def test_none(self):
        assert _format_value(None) == '—'


class TestStandardizedFinancials:

    @pytest.fixture
    def sample_sf(self):
        """Build a StandardizedFinancials with known values for testing."""
        metrics = {}
        # Income
        metrics['Revenue'] = StandardizedMetric('Revenue', 394_328_000_000, 'us-gaap:Revenues', 0.95, 'tree')
        metrics['COGS'] = StandardizedMetric('COGS', 223_546_000_000, 'us-gaap:CostOfGoodsAndServicesSold', 0.95, 'tree')
        metrics['SGA'] = StandardizedMetric('SGA', 26_252_000_000, 'us-gaap:SellingGeneralAndAdministrativeExpense', 0.95, 'tree')
        metrics['OperatingIncome'] = StandardizedMetric('OperatingIncome', 119_437_000_000, 'us-gaap:OperatingIncomeLoss', 0.95, 'tree')
        metrics['PretaxIncome'] = StandardizedMetric('PretaxIncome', 119_103_000_000, 'us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxes', 0.95, 'tree')
        metrics['NetIncome'] = StandardizedMetric('NetIncome', 93_736_000_000, 'us-gaap:NetIncomeLoss', 0.95, 'tree')
        # Cash Flow
        metrics['OperatingCashFlow'] = StandardizedMetric('OperatingCashFlow', 118_254_000_000, 'c', 0.95, 'tree')
        metrics['Capex'] = StandardizedMetric('Capex', -10_959_000_000, 'c', 0.95, 'tree')
        metrics['FreeCashFlow'] = StandardizedMetric('FreeCashFlow', 107_295_000_000, 'Derived', 0.95, 'derived')
        metrics['DepreciationAmortization'] = StandardizedMetric('DepreciationAmortization', 11_519_000_000, 'c', 0.80, 'facts')
        metrics['StockBasedCompensation'] = StandardizedMetric('StockBasedCompensation', 11_688_000_000, 'c', 0.80, 'facts')
        metrics['DividendsPaid'] = StandardizedMetric('DividendsPaid', -15_025_000_000, 'c', 0.95, 'tree')
        # Balance Sheet
        metrics['TotalAssets'] = StandardizedMetric('TotalAssets', 352_583_000_000, 'c', 0.95, 'tree')
        metrics['CashAndEquivalents'] = StandardizedMetric('CashAndEquivalents', 29_965_000_000, 'c', 0.95, 'tree')
        metrics['AccountsReceivable'] = StandardizedMetric('AccountsReceivable', 60_985_000_000, 'c', 0.95, 'tree')
        metrics['Inventory'] = StandardizedMetric('Inventory', 6_331_000_000, 'c', 0.95, 'tree')
        metrics['Goodwill'] = StandardizedMetric('Goodwill', None, None, 0.0, 'unmapped')
        metrics['IntangibleAssets'] = StandardizedMetric('IntangibleAssets', None, None, 0.0, 'unmapped')
        metrics['TangibleAssets'] = StandardizedMetric('TangibleAssets', None, None, 0.0, 'derived')
        metrics['ShortTermDebt'] = StandardizedMetric('ShortTermDebt', 15_807_000_000, 'c', 0.85, 'tree')
        metrics['LongTermDebt'] = StandardizedMetric('LongTermDebt', 95_281_000_000, 'c', 0.95, 'tree')
        metrics['NetDebt'] = StandardizedMetric('NetDebt', 81_123_000_000, 'Derived', 0.95, 'derived')
        metrics['AccountsPayable'] = StandardizedMetric('AccountsPayable', 62_611_000_000, 'c', 0.95, 'tree')
        metrics['WeightedAverageSharesDiluted'] = StandardizedMetric('WeightedAverageSharesDiluted', 15_408_095_000, 'c', 0.95, 'tree')

        return StandardizedFinancials(
            metrics=metrics,
            company_name='Apple Inc',
            ticker='AAPL',
            form_type='10-K',
            fiscal_period='2024-FY',
        )

    def test_getitem(self, sample_sf):
        m = sample_sf['Revenue']
        assert m.value == 394_328_000_000

    def test_getitem_missing(self, sample_sf):
        with pytest.raises(KeyError):
            sample_sf['NonexistentMetric']

    def test_contains(self, sample_sf):
        assert 'Revenue' in sample_sf
        assert 'Nonexistent' not in sample_sf

    def test_len(self, sample_sf):
        assert len(sample_sf) == 24

    def test_property_access(self, sample_sf):
        assert sample_sf.revenue == 394_328_000_000
        assert sample_sf.capex == -10_959_000_000
        assert sample_sf.net_income == 93_736_000_000

    def test_property_access_missing_attr(self, sample_sf):
        with pytest.raises(AttributeError):
            _ = sample_sf.nonexistent_thing

    def test_income_metrics(self, sample_sf):
        income = sample_sf.income_metrics
        names = [m.name for m in income]
        assert 'Revenue' in names
        assert 'NetIncome' in names

    def test_cashflow_metrics(self, sample_sf):
        cf = sample_sf.cashflow_metrics
        names = [m.name for m in cf]
        assert 'OperatingCashFlow' in names
        assert 'FreeCashFlow' in names

    def test_balance_sheet_metrics(self, sample_sf):
        bs = sample_sf.balance_sheet_metrics
        names = [m.name for m in bs]
        assert 'TotalAssets' in names
        assert 'LongTermDebt' in names

    def test_mapped_count(self, sample_sf):
        # Goodwill, IntangibleAssets, TangibleAssets are None → not mapped
        assert sample_sf.mapped_count >= 20

    def test_total_count(self, sample_sf):
        # No excluded metrics in sample_sf
        assert sample_sf.total_count == 24

    def test_coverage_pct(self, sample_sf):
        pct = sample_sf.coverage_pct
        assert 80 <= pct <= 100

    def test_to_dict(self, sample_sf):
        d = sample_sf.to_dict()
        assert 'Revenue' in d
        assert d['Revenue']['value'] == 394_328_000_000
        assert d['Revenue']['source'] == 'tree'

    def test_to_dataframe(self, sample_sf):
        df = sample_sf.to_dataframe()
        assert len(df) == 24
        assert 'metric' in df.columns
        assert 'value' in df.columns
        rev_row = df[df['metric'] == 'Revenue']
        assert rev_row.iloc[0]['value'] == 394_328_000_000

    def test_str(self, sample_sf):
        s = str(sample_sf)
        assert 'Apple Inc' in s
        assert 'AAPL' in s
        assert '10-K' in s

    def test_rich(self, sample_sf):
        table = sample_sf.__rich__()
        assert table is not None
        # Render to string to verify it doesn't error
        from edgar.richtools import repr_rich
        rendered = repr_rich(table)
        assert 'Revenue' in rendered
        assert 'Income Statement' in rendered


class TestDerivedMetrics:

    def test_free_cash_flow(self):
        metrics = {
            'OperatingCashFlow': StandardizedMetric('OperatingCashFlow', 100_000, 'c', 0.95, 'tree'),
            'Capex': StandardizedMetric('Capex', -20_000, 'c', 0.95, 'tree'),
        }
        _calculate_derived_metrics(metrics)
        assert metrics['FreeCashFlow'].value == 80_000  # 100K - abs(-20K)
        assert metrics['FreeCashFlow'].source == 'derived'

    def test_tangible_assets(self):
        metrics = {
            'TotalAssets': StandardizedMetric('TotalAssets', 500_000, 'c', 0.95, 'tree'),
            'IntangibleAssets': StandardizedMetric('IntangibleAssets', 100_000, 'c', 0.85, 'tree'),
        }
        _calculate_derived_metrics(metrics)
        assert metrics['TangibleAssets'].value == 400_000

    def test_net_debt(self):
        metrics = {
            'ShortTermDebt': StandardizedMetric('ShortTermDebt', 10_000, 'c', 0.85, 'tree'),
            'LongTermDebt': StandardizedMetric('LongTermDebt', 90_000, 'c', 0.95, 'tree'),
            'CashAndEquivalents': StandardizedMetric('CashAndEquivalents', 30_000, 'c', 0.95, 'tree'),
        }
        _calculate_derived_metrics(metrics)
        assert metrics['NetDebt'].value == 70_000  # 10K + 90K - 30K

    def test_net_debt_without_short_term(self):
        metrics = {
            'ShortTermDebt': StandardizedMetric('ShortTermDebt', None, None, 0.0, 'unmapped'),
            'LongTermDebt': StandardizedMetric('LongTermDebt', 90_000, 'c', 0.95, 'tree'),
            'CashAndEquivalents': StandardizedMetric('CashAndEquivalents', 30_000, 'c', 0.95, 'tree'),
        }
        _calculate_derived_metrics(metrics)
        assert metrics['NetDebt'].value == 60_000  # 0 + 90K - 30K

    def test_derived_missing_components(self):
        metrics = {
            'OperatingCashFlow': StandardizedMetric('OperatingCashFlow', None, None, 0.0, 'unmapped'),
            'Capex': StandardizedMetric('Capex', None, None, 0.0, 'unmapped'),
        }
        _calculate_derived_metrics(metrics)
        assert metrics['FreeCashFlow'].value is None


class TestMetricSections:

    def test_all_metrics_count(self):
        assert len(ALL_METRICS) == 24

    def test_no_duplicates(self):
        assert len(ALL_METRICS) == len(set(ALL_METRICS))

    def test_sections_cover_all(self):
        section_metrics = set()
        for metrics in METRIC_SECTIONS.values():
            section_metrics.update(metrics)
        assert section_metrics == set(ALL_METRICS)


# ---------------------------------------------------------------------------
# Integration tests — network required
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestStandardizedFinancialsIntegration:

    def test_apple_standardized_financials(self):
        from edgar import Company
        sf = Company("AAPL").get_standardized_financials()
        assert sf is not None
        assert sf.ticker == 'AAPL'
        assert sf.form_type == '10-K'
        # Apple revenue should be > $300B
        assert sf.revenue is not None
        assert sf.revenue > 300_000_000_000
        # Coverage should be reasonable
        assert sf.coverage_pct >= 60

    def test_apple_sign_conventions(self):
        from edgar import Company
        sf = Company("AAPL").get_standardized_financials()
        assert sf is not None
        # Capex should be negative (outflow)
        if sf.capex is not None:
            assert sf.capex < 0, f"Capex should be negative, got {sf.capex}"
        # DividendsPaid should be negative (outflow)
        if sf.dividends_paid is not None:
            assert sf.dividends_paid < 0, f"DividendsPaid should be negative, got {sf.dividends_paid}"

    def test_apple_derived_metrics(self):
        from edgar import Company
        sf = Company("AAPL").get_standardized_financials()
        assert sf is not None
        # FreeCashFlow = OperatingCashFlow - abs(Capex)
        if sf.operating_cash_flow is not None and sf.capex is not None:
            expected_fcf = sf.operating_cash_flow - abs(sf.capex)
            assert sf.free_cash_flow == pytest.approx(expected_fcf, rel=0.01)

    def test_apple_dataframe_export(self):
        from edgar import Company
        sf = Company("AAPL").get_standardized_financials()
        assert sf is not None
        df = sf.to_dataframe()
        assert len(df) == 24
        assert 'Revenue' in df['metric'].values

    def test_apple_quarterly(self):
        from edgar import Company
        sf = Company("AAPL").get_quarterly_standardized_financials()
        assert sf is not None
        assert sf.form_type == '10-Q'
        assert sf.revenue is not None

    def test_jpm_excluded_metrics(self):
        from edgar import Company
        sf = Company("JPM").get_standardized_financials()
        assert sf is not None
        # Banking companies should have Inventory excluded
        inv = sf['Inventory']
        assert inv.is_excluded, "Inventory should be excluded for banks"
