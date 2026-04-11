"""
Tests for FinancialDatabase — SQLite-backed standardized financial metrics.

Unit tests use :memory: SQLite (no network).
Integration tests are marked with @pytest.mark.network.
"""

import pytest
import pandas as pd

from edgar.financial_database import FinancialDatabase, PopulationResult
from edgar.xbrl.standardization.database.schema import _FinancialDB, _derive_fiscal_period
from edgar.standardized_financials import StandardizedMetric


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metric(name, value=1000.0, concept='us-gaap:Test', confidence=0.95,
                 source='tree', is_excluded=False):
    return StandardizedMetric(
        name=name, value=value, concept=concept,
        confidence=confidence, source=source, is_excluded=is_excluded,
    )


def _sample_metrics():
    """Return a small set of metrics for testing."""
    return [
        _make_metric('Revenue', 100_000_000.0, 'us-gaap:Revenue'),
        _make_metric('NetIncome', 20_000_000.0, 'us-gaap:NetIncomeLoss'),
        _make_metric('TotalAssets', 500_000_000.0, 'us-gaap:Assets'),
        _make_metric('Inventory', None, None, 0.0, 'unmapped'),
        _make_metric('COGS', None, None, 0.0, 'excluded', is_excluded=True),
    ]


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestFinancialDBSchema:

    def test_init_creates_tables(self):
        db = _FinancialDB(':memory:')
        with db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
        assert 'filing_registry' in tables
        assert 'financial_metrics' in tables

    def test_record_and_check_filing(self):
        db = _FinancialDB(':memory:')
        assert not db.is_filing_known('0001234-24-000001')

        db.record_filing(
            accession_number='0001234-24-000001',
            ticker='TEST',
            form_type='10-K',
            filing_date='2024-03-15',
            period_of_report='2024-12-31',
            fiscal_period='2024-FY',
            company_name='Test Corp',
            metric_count=3,
        )
        assert db.is_filing_known('0001234-24-000001')
        assert not db.is_filing_known('0009999-24-000001')

    def test_record_metrics(self):
        db = _FinancialDB(':memory:')
        db.record_filing(
            accession_number='0001234-24-000001',
            ticker='TEST',
            form_type='10-K',
            filing_date='2024-03-15',
            period_of_report='2024-12-31',
            fiscal_period='2024-FY',
        )

        metrics = _sample_metrics()
        db.record_metrics('0001234-24-000001', 'TEST', '2024-FY', '10-K', metrics)

        rows = db.get_filing_metrics('TEST', '2024-FY')
        assert len(rows) == 5
        names = {r['metric'] for r in rows}
        assert 'Revenue' in names
        assert 'COGS' in names

    def test_get_metrics_all(self):
        db = _FinancialDB(':memory:')
        db.record_filing(
            accession_number='acc1',
            ticker='AAA',
            form_type='10-K',
            filing_date='2024-03-15',
            period_of_report='2024-12-31',
            fiscal_period='2024-FY',
        )
        db.record_metrics('acc1', 'AAA', '2024-FY', '10-K', _sample_metrics())

        df = db.get_metrics()
        assert isinstance(df, pd.DataFrame)
        # Excluded metrics (COGS) and unmapped (Inventory) with confidence 0 are filtered
        # Only 3 have value and confidence > 0
        assert len(df) >= 3

    def test_get_metrics_filter_ticker(self):
        db = _FinancialDB(':memory:')
        for ticker, acc in [('AAA', 'acc1'), ('BBB', 'acc2')]:
            db.record_filing(
                accession_number=acc, ticker=ticker, form_type='10-K',
                filing_date='2024-03-15', period_of_report='2024-12-31',
                fiscal_period='2024-FY',
            )
            db.record_metrics(acc, ticker, '2024-FY', '10-K', [
                _make_metric('Revenue', 100.0),
            ])

        df = db.get_metrics(tickers=['AAA'])
        assert len(df) == 1
        assert df.iloc[0]['ticker'] == 'AAA'

    def test_get_metrics_filter_metric(self):
        db = _FinancialDB(':memory:')
        db.record_filing(
            accession_number='acc1', ticker='AAA', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY',
        )
        db.record_metrics('acc1', 'AAA', '2024-FY', '10-K', [
            _make_metric('Revenue', 100.0),
            _make_metric('NetIncome', 20.0),
        ])

        df = db.get_metrics(metrics=['Revenue'])
        assert len(df) == 1
        assert df.iloc[0]['metric'] == 'Revenue'

    def test_get_metrics_filter_period(self):
        db = _FinancialDB(':memory:')
        for period, acc in [('2024-FY', 'acc1'), ('2023-FY', 'acc2')]:
            db.record_filing(
                accession_number=acc, ticker='AAA', form_type='10-K',
                filing_date='2024-03-15', period_of_report='2024-12-31',
                fiscal_period=period,
            )
            db.record_metrics(acc, 'AAA', period, '10-K', [
                _make_metric('Revenue', 100.0),
            ])

        df = db.get_metrics(periods=['2024-FY'])
        assert len(df) == 1
        assert df.iloc[0]['fiscal_period'] == '2024-FY'

    def test_get_metrics_filter_form_type(self):
        db = _FinancialDB(':memory:')
        for form, acc in [('10-K', 'acc1'), ('10-Q', 'acc2')]:
            db.record_filing(
                accession_number=acc, ticker='AAA', form_type=form,
                filing_date='2024-03-15', period_of_report='2024-12-31',
                fiscal_period='2024-FY',
            )
            db.record_metrics(acc, 'AAA', '2024-FY', form, [
                _make_metric('Revenue', 100.0),
            ])

        df = db.get_metrics(form_type='10-K')
        assert len(df) == 1
        assert df.iloc[0]['form_type'] == '10-K'

    def test_get_metrics_min_confidence(self):
        db = _FinancialDB(':memory:')
        db.record_filing(
            accession_number='acc1', ticker='AAA', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY',
        )
        db.record_metrics('acc1', 'AAA', '2024-FY', '10-K', [
            _make_metric('Revenue', 100.0, confidence=0.95),
            _make_metric('NetIncome', 20.0, confidence=0.50),
        ])

        df = db.get_metrics(min_confidence=0.90)
        assert len(df) == 1
        assert df.iloc[0]['metric'] == 'Revenue'

    def test_get_info(self):
        db = _FinancialDB(':memory:')
        db.record_filing(
            accession_number='acc1', ticker='AAA', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY', metric_count=3,
        )
        db.record_filing(
            accession_number='acc2', ticker='BBB', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY', metric_count=2,
        )

        info = db.get_info()
        assert info['total_companies'] == 2
        assert info['total_filings'] == 2
        assert len(info['tickers']) == 2

    def test_close(self):
        db = _FinancialDB(':memory:')
        db.close()
        assert db._persistent_conn is None


# ---------------------------------------------------------------------------
# Fiscal period derivation
# ---------------------------------------------------------------------------

class TestFiscalPeriodDerivation:

    def test_10k_derives_fy(self):
        class FakeFiling:
            form = '10-K'
            period_of_report = '2024-12-31'
        assert _derive_fiscal_period(FakeFiling()) == '2024-FY'

    def test_10q_q1(self):
        class FakeFiling:
            form = '10-Q'
            period_of_report = '2024-03-31'
        assert _derive_fiscal_period(FakeFiling()) == '2024-Q1'

    def test_10q_q2(self):
        class FakeFiling:
            form = '10-Q'
            period_of_report = '2024-06-30'
        assert _derive_fiscal_period(FakeFiling()) == '2024-Q2'

    def test_10q_q3(self):
        class FakeFiling:
            form = '10-Q'
            period_of_report = '2024-09-30'
        assert _derive_fiscal_period(FakeFiling()) == '2024-Q3'

    def test_10q_q4(self):
        class FakeFiling:
            form = '10-Q'
            period_of_report = '2024-12-31'
        assert _derive_fiscal_period(FakeFiling()) == '2024-Q4'

    def test_missing_period(self):
        class FakeFiling:
            form = '10-K'
            period_of_report = None
        assert _derive_fiscal_period(FakeFiling()) == 'unknown'

    def test_20f_derives_fy(self):
        class FakeFiling:
            form = '20-F'
            period_of_report = '2024-03-31'
        assert _derive_fiscal_period(FakeFiling()) == '2024-FY'


# ---------------------------------------------------------------------------
# FinancialDatabase (public API) unit tests
# ---------------------------------------------------------------------------

class TestFinancialDatabase:

    def test_create_in_memory(self):
        db = FinancialDatabase(':memory:')
        assert str(db) == 'FinancialDatabase(0 companies | 0 filings | 0 metrics)'

    def test_query_empty(self):
        db = FinancialDatabase(':memory:')
        df = db.query()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_info_empty(self):
        db = FinancialDatabase(':memory:')
        info = db.info()
        assert info['total_companies'] == 0
        assert info['total_filings'] == 0
        assert info['total_metrics'] == 0

    def test_get_filing_none_when_missing(self):
        db = FinancialDatabase(':memory:')
        result = db.get_filing('AAPL', '2024-FY')
        assert result is None

    def test_get_filing_reconstructs(self):
        db = FinancialDatabase(':memory:')
        # Insert data directly via internal db
        db._db.record_filing(
            accession_number='acc1', ticker='AAA', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY', company_name='Test Corp',
        )
        db._db.record_metrics('acc1', 'AAA', '2024-FY', '10-K', [
            _make_metric('Revenue', 100_000_000.0),
            _make_metric('NetIncome', 20_000_000.0),
        ])

        sf = db.get_filing('AAA', '2024-FY')
        assert sf is not None
        assert sf.ticker == 'AAA'
        assert sf.fiscal_period == '2024-FY'
        assert sf.company_name == 'Test Corp'
        assert sf['Revenue'].value == 100_000_000.0
        assert sf.revenue == 100_000_000.0
        assert sf.net_income == 20_000_000.0

    def test_pivot(self):
        db = FinancialDatabase(':memory:')
        db._db.record_filing(
            accession_number='acc1', ticker='AAA', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY',
        )
        db._db.record_metrics('acc1', 'AAA', '2024-FY', '10-K', [
            _make_metric('Revenue', 100.0),
            _make_metric('NetIncome', 20.0),
        ])

        df = db.query()
        wide = FinancialDatabase.pivot(df)
        assert 'Revenue' in wide.columns
        assert 'NetIncome' in wide.columns
        assert len(wide) == 1
        assert wide.iloc[0]['Revenue'] == 100.0

    def test_pivot_empty(self):
        db = FinancialDatabase(':memory:')
        df = db.query()
        wide = FinancialDatabase.pivot(df)
        assert len(wide) == 0

    def test_str_repr(self):
        db = FinancialDatabase(':memory:')
        s = str(db)
        assert 'FinancialDatabase' in s
        assert '0 companies' in s

    def test_rich_rendering(self):
        db = FinancialDatabase(':memory:')
        db._db.record_filing(
            accession_number='acc1', ticker='AAA', form_type='10-K',
            filing_date='2024-03-15', period_of_report='2024-12-31',
            fiscal_period='2024-FY', metric_count=2,
        )
        table = db.__rich__()
        assert table is not None


# ---------------------------------------------------------------------------
# PopulationResult
# ---------------------------------------------------------------------------

class TestPopulationResult:

    def test_str(self):
        r = PopulationResult(
            tickers_attempted=2,
            filings_extracted=10,
            filings_skipped=2,
            filings_failed=1,
            elapsed_seconds=15.5,
        )
        s = str(r)
        assert '2 tickers' in s
        assert '10 extracted' in s
        assert '15.5s' in s


# ---------------------------------------------------------------------------
# Integration tests (network required)
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestFinancialDatabaseIntegration:

    def test_populate_single_ticker(self):
        db = FinancialDatabase(':memory:')
        result = db.populate(tickers=['AAPL'], n_annual=1, n_quarterly=0, show_progress=False)

        assert result.tickers_attempted == 1
        assert result.filings_extracted >= 1

        df = db.query(tickers=['AAPL'], metrics=['Revenue'])
        assert len(df) >= 1
        assert df.iloc[0]['value'] > 0

    def test_populate_idempotent(self):
        db = FinancialDatabase(':memory:')
        r1 = db.populate(tickers=['MSFT'], n_annual=1, n_quarterly=0, show_progress=False)
        r2 = db.populate(tickers=['MSFT'], n_annual=1, n_quarterly=0, show_progress=False)

        assert r1.filings_extracted >= 1
        assert r2.filings_skipped >= 1
        assert r2.filings_extracted == 0

    def test_get_filing_from_populated(self):
        db = FinancialDatabase(':memory:')
        db.populate(tickers=['AAPL'], n_annual=1, n_quarterly=0, show_progress=False)

        info = db.info()
        assert info['total_companies'] >= 1

        # Find the fiscal period that was stored
        ticker_info = [t for t in info['tickers'] if t['ticker'] == 'AAPL']
        assert len(ticker_info) == 1
        period = ticker_info[0]['latest_period']

        sf = db.get_filing('AAPL', period)
        assert sf is not None
        assert sf.ticker == 'AAPL'
        assert sf.revenue is not None or sf.total_assets is not None
