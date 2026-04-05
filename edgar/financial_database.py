"""
FinancialDatabase — SQLite-backed store of standardized financial metrics.

Extracts cross-company comparable metrics from SEC filings and stores them
for fast querying across 10 years of history.

Usage:
    from edgar import FinancialDatabase

    db = FinancialDatabase()
    db.populate(tickers=["AAPL", "MSFT"], n_annual=3, n_quarterly=1)

    df = db.query(tickers=["AAPL"], metrics=["Revenue", "NetIncome"])
    wide = FinancialDatabase.pivot(df)
    print(wide)
"""

import logging
import time
from typing import Dict, List, Optional, Union

import pandas as pd
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.xbrl.standardization.database.schema import _FinancialDB
from edgar.xbrl.standardization.database.populator import (
    PopulationResult,
    PopulationTickerResult,
    populate_ticker,
)

log = logging.getLogger(__name__)

__all__ = ['FinancialDatabase', 'PopulationResult']


class FinancialDatabase:
    """
    SQLite-backed store of standardized financial metrics across companies.

    Provides:
    - `populate()` / `update()` — extract metrics from SEC filings
    - `query()` — filter by ticker, metric, period, form type
    - `pivot()` — wide-format DataFrame
    - `get_filing()` — reconstruct StandardizedFinancials from stored data
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Open or create a financial database.

        Args:
            db_path: Path to SQLite file. None → ~/.edgar/financial_data.db.
                     Use ':memory:' for in-memory (testing).
        """
        self._db = _FinancialDB(db_path)

    def populate(
        self,
        tickers: Optional[List[str]] = None,
        n_annual: int = 10,
        n_quarterly: int = 4,
        show_progress: bool = True,
    ) -> PopulationResult:
        """
        Extract and store standardized metrics for companies.

        Skips filings already in the database (idempotent).

        Args:
            tickers: List of ticker symbols. None → all configured companies.
            n_annual: Number of annual filings (10-K) per company.
            n_quarterly: Number of quarterly filings (10-Q) per company.
            show_progress: Show rich progress bar.

        Returns:
            PopulationResult with extraction counts.
        """
        if tickers is None:
            tickers = self._get_configured_tickers()

        result = PopulationResult(tickers_attempted=len(tickers))
        start = time.time()

        if show_progress:
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TextColumn("{task.fields[status]}"),
                ) as progress:
                    task = progress.add_task(
                        "Populating...",
                        total=len(tickers),
                        status="",
                    )
                    for ticker in tickers:
                        progress.update(task, description=f"[cyan]{ticker}[/]", status="extracting...")
                        ticker_result = populate_ticker(
                            ticker, self._db, n_annual, n_quarterly,
                        )
                        result.filings_extracted += ticker_result.filings_extracted
                        result.filings_skipped += ticker_result.filings_skipped
                        result.filings_failed += ticker_result.filings_failed
                        result.errors.extend(ticker_result.errors)

                        status = f"{ticker_result.filings_extracted} new"
                        if ticker_result.filings_skipped:
                            status += f", {ticker_result.filings_skipped} skip"
                        progress.update(task, advance=1, status=status)
            except ImportError:
                show_progress = False

        if not show_progress:
            for ticker in tickers:
                ticker_result = populate_ticker(
                    ticker, self._db, n_annual, n_quarterly,
                )
                result.filings_extracted += ticker_result.filings_extracted
                result.filings_skipped += ticker_result.filings_skipped
                result.filings_failed += ticker_result.filings_failed
                result.errors.extend(ticker_result.errors)

        result.elapsed_seconds = time.time() - start
        return result

    def update(
        self,
        tickers: Optional[List[str]] = None,
        show_progress: bool = True,
    ) -> PopulationResult:
        """
        Incremental update — only adds new filings not yet in the database.

        Same as populate() but with smaller window (2 annual + 2 quarterly)
        since we only expect recent filings to be new.
        """
        return self.populate(
            tickers=tickers,
            n_annual=2,
            n_quarterly=2,
            show_progress=show_progress,
        )

    def query(
        self,
        tickers: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
        periods: Optional[List[str]] = None,
        form_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> pd.DataFrame:
        """
        Query stored metrics into a tidy DataFrame.

        Args:
            tickers: Filter by ticker symbols (None = all).
            metrics: Filter by metric names (None = all).
            periods: Filter by fiscal periods like '2024-FY' (None = all).
            form_type: Filter by '10-K' or '10-Q' (None = all).
            min_confidence: Minimum confidence threshold.

        Returns:
            DataFrame with columns: ticker, fiscal_period, form_type, metric,
            value, concept, confidence, source, is_excluded, accession_number
        """
        return self._db.get_metrics(
            tickers=tickers,
            metrics=metrics,
            periods=periods,
            form_type=form_type,
            min_confidence=min_confidence,
        )

    def get_filing(
        self,
        ticker: str,
        fiscal_period: str,
    ) -> Optional['StandardizedFinancials']:
        """
        Reconstruct a StandardizedFinancials object from stored data.

        Args:
            ticker: Company ticker symbol.
            fiscal_period: e.g. '2024-FY' or '2024-Q3'.

        Returns:
            StandardizedFinancials or None if no data found.
        """
        from edgar.standardized_financials import StandardizedFinancials, StandardizedMetric

        rows = self._db.get_filing_metrics(ticker, fiscal_period)
        if not rows:
            return None

        metrics = {}
        for row in rows:
            metrics[row['metric']] = StandardizedMetric(
                name=row['metric'],
                value=row['value'],
                concept=row['concept'],
                confidence=row['confidence'] or 0.0,
                source=row['source'] or '',
                is_excluded=bool(row['is_excluded']),
            )

        # Get company name and form type from filing registry
        company_name = ticker
        form_type = ''
        with self._db._connect() as conn:
            import sqlite3
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT company_name, form_type FROM filing_registry
                   WHERE ticker = ? AND fiscal_period = ? LIMIT 1''',
                (ticker, fiscal_period)
            )
            reg = cursor.fetchone()
            if reg:
                company_name = reg['company_name'] or ticker
                form_type = reg['form_type'] or ''

        return StandardizedFinancials(
            metrics=metrics,
            company_name=company_name,
            ticker=ticker,
            form_type=form_type,
            fiscal_period=fiscal_period,
        )

    @staticmethod
    def pivot(df: pd.DataFrame) -> pd.DataFrame:
        """
        Pivot a tidy query result to wide format (metrics as columns).

        Args:
            df: DataFrame from query() with 'ticker', 'fiscal_period', 'metric', 'value'.

        Returns:
            DataFrame with (ticker, fiscal_period) as index, metrics as columns.
        """
        if df.empty:
            return df
        return df.pivot_table(
            index=['ticker', 'fiscal_period'],
            columns='metric',
            values='value',
            aggfunc='first',
        ).reset_index()

    def info(self) -> dict:
        """Per-ticker summary: filing count, latest period, metric count."""
        return self._db.get_info()

    def __rich__(self):
        info = self.info()
        title = (
            f"FinancialDatabase — "
            f"{info['total_companies']} companies | "
            f"{info['total_filings']} filings | "
            f"{info['total_metrics']} metrics"
        )
        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("Ticker", style="cyan")
        table.add_column("Filings", justify="right")
        table.add_column("Latest Period")
        table.add_column("Metrics", justify="right")

        for t in info['tickers']:
            table.add_row(
                t['ticker'],
                str(t['filing_count']),
                t['latest_period'] or '—',
                str(t['total_metrics'] or 0),
            )

        return table

    def _repr_html_(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        info = self.info()
        return (
            f"FinancialDatabase("
            f"{info['total_companies']} companies | "
            f"{info['total_filings']} filings | "
            f"{info['total_metrics']} metrics)"
        )

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def _get_configured_tickers() -> List[str]:
        """Get all company tickers from the standardization config."""
        try:
            from edgar.xbrl.standardization.config_loader import get_config
            config = get_config()
            return sorted(config.companies.keys())
        except Exception:
            return []
