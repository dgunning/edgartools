"""
Internal SQLite schema and CRUD for the standardized financial database.

Not user-facing — use `edgar.financial_database.FinancialDatabase` instead.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


def _derive_fiscal_period(filing) -> str:
    """
    Derive a fiscal period string from a filing.

    Returns:
        '2024-FY' for 10-K, '2024-Q3' for 10-Q (based on period_of_report month).
    """
    form_type = getattr(filing, 'form', '10-K')
    period_of_report = getattr(filing, 'period_of_report', None)

    if not period_of_report:
        return 'unknown'

    # period_of_report is typically 'YYYY-MM-DD'
    try:
        dt = datetime.strptime(str(period_of_report), '%Y-%m-%d')
    except (ValueError, TypeError):
        return 'unknown'

    year = dt.year

    if form_type in ('10-K', '20-F', '40-F'):
        return f'{year}-FY'

    # For 10-Q: derive quarter from month
    month = dt.month
    # Map month to quarter (report end month)
    if month <= 3:
        quarter = 'Q1'
    elif month <= 6:
        quarter = 'Q2'
    elif month <= 9:
        quarter = 'Q3'
    else:
        quarter = 'Q4'

    return f'{year}-{quarter}'


class _FinancialDB:
    """
    Internal SQLite database for standardized financial metrics.

    Follows the connection pattern from ExperimentLedger:
    - Persistent connection for :memory: databases
    - File-based connection for disk databases
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from edgar.paths import get_financial_db_path
            db_path = str(get_financial_db_path())

        self.db_path = db_path
        self._persistent_conn = None
        if db_path == ':memory:':
            self._persistent_conn = sqlite3.connect(':memory:')
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        """Get a database connection."""
        if self._persistent_conn is not None:
            return self._persistent_conn
        return sqlite3.connect(self.db_path)

    def _init_database(self):
        """Create tables and indices if they don't exist."""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filing_registry (
                    accession_number TEXT PRIMARY KEY,
                    ticker           TEXT NOT NULL,
                    form_type        TEXT NOT NULL,
                    filing_date      TEXT NOT NULL,
                    period_of_report TEXT NOT NULL,
                    fiscal_period    TEXT NOT NULL,
                    company_name     TEXT,
                    extracted_at     TEXT NOT NULL,
                    metric_count     INTEGER,
                    extraction_notes TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS financial_metrics (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    accession_number TEXT NOT NULL,
                    ticker           TEXT NOT NULL,
                    fiscal_period    TEXT NOT NULL,
                    form_type        TEXT NOT NULL,
                    metric           TEXT NOT NULL,
                    value            REAL,
                    concept          TEXT,
                    confidence       REAL,
                    source           TEXT,
                    is_excluded      INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (accession_number) REFERENCES filing_registry(accession_number)
                )
            ''')

            # Indices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_registry_ticker ON filing_registry(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_registry_period ON filing_registry(fiscal_period)')
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_unique ON financial_metrics(accession_number, metric)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_ticker ON financial_metrics(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_period ON financial_metrics(fiscal_period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_metric ON financial_metrics(metric)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_period_metric ON financial_metrics(fiscal_period, metric)')

            conn.commit()

    def is_filing_known(self, accession_number: str) -> bool:
        """Check if a filing has already been processed."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM filing_registry WHERE accession_number = ?',
                (accession_number,)
            )
            return cursor.fetchone() is not None

    def record_filing(
        self,
        accession_number: str,
        ticker: str,
        form_type: str,
        filing_date: str,
        period_of_report: str,
        fiscal_period: str,
        company_name: str = '',
        metric_count: int = 0,
        extraction_notes: str = '',
    ):
        """Record a filing in the registry."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT OR REPLACE INTO filing_registry
                   (accession_number, ticker, form_type, filing_date,
                    period_of_report, fiscal_period, company_name,
                    extracted_at, metric_count, extraction_notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (accession_number, ticker, form_type, filing_date,
                 period_of_report, fiscal_period, company_name,
                 datetime.now().isoformat(), metric_count, extraction_notes)
            )
            conn.commit()

    def record_metrics(
        self,
        accession_number: str,
        ticker: str,
        fiscal_period: str,
        form_type: str,
        metrics: list,
    ):
        """
        Record a list of StandardizedMetric objects for a filing.

        Args:
            metrics: List of StandardizedMetric dataclass instances.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            for m in metrics:
                cursor.execute(
                    '''INSERT OR REPLACE INTO financial_metrics
                       (accession_number, ticker, fiscal_period, form_type,
                        metric, value, concept, confidence, source, is_excluded)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (accession_number, ticker, fiscal_period, form_type,
                     m.name, m.value, m.concept, m.confidence, m.source,
                     1 if m.is_excluded else 0)
                )
            conn.commit()

    def get_metrics(
        self,
        tickers: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
        periods: Optional[List[str]] = None,
        form_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> 'pd.DataFrame':
        """
        Query stored metrics into a tidy DataFrame.

        Args:
            tickers: Filter by ticker symbols (None = all).
            metrics: Filter by metric names (None = all).
            periods: Filter by fiscal periods like '2024-FY' (None = all).
            form_type: Filter by form type ('10-K', '10-Q', or None = all).
            min_confidence: Minimum confidence threshold.

        Returns:
            DataFrame with columns: ticker, fiscal_period, form_type, metric,
            value, concept, confidence, source, is_excluded, accession_number
        """
        import pandas as pd

        query = '''
            SELECT ticker, fiscal_period, form_type, metric,
                   value, concept, confidence, source, is_excluded,
                   accession_number
            FROM financial_metrics
            WHERE confidence >= ?
              AND is_excluded = 0
        '''
        params: list = [min_confidence]

        if tickers:
            placeholders = ','.join('?' * len(tickers))
            query += f' AND ticker IN ({placeholders})'
            params.extend(tickers)

        if metrics:
            placeholders = ','.join('?' * len(metrics))
            query += f' AND metric IN ({placeholders})'
            params.extend(metrics)

        if periods:
            placeholders = ','.join('?' * len(periods))
            query += f' AND fiscal_period IN ({placeholders})'
            params.extend(periods)

        if form_type:
            query += ' AND form_type = ?'
            params.append(form_type)

        query += ' ORDER BY ticker, fiscal_period, metric'

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame(columns=[
                'ticker', 'fiscal_period', 'form_type', 'metric',
                'value', 'concept', 'confidence', 'source',
                'is_excluded', 'accession_number'
            ])

        return pd.DataFrame([dict(r) for r in rows])

    def get_filing_metrics(self, ticker: str, fiscal_period: str) -> List[dict]:
        """Get all metric rows for a specific filing."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT * FROM financial_metrics
                   WHERE ticker = ? AND fiscal_period = ?
                   ORDER BY metric''',
                (ticker, fiscal_period)
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_info(self) -> Dict:
        """
        Get per-ticker summary statistics.

        Returns:
            Dict with 'tickers' (list of dicts with ticker, filing_count,
            latest_period, metric_count) and 'totals'.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Per-ticker stats from filing_registry
            cursor.execute('''
                SELECT ticker,
                       COUNT(*) as filing_count,
                       MAX(fiscal_period) as latest_period,
                       SUM(metric_count) as total_metrics
                FROM filing_registry
                GROUP BY ticker
                ORDER BY ticker
            ''')
            ticker_rows = [dict(r) for r in cursor.fetchall()]

            # Totals
            cursor.execute('SELECT COUNT(*) FROM filing_registry')
            total_filings = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM financial_metrics WHERE is_excluded = 0')
            total_metrics = cursor.fetchone()[0]

            return {
                'tickers': ticker_rows,
                'total_companies': len(ticker_rows),
                'total_filings': total_filings,
                'total_metrics': total_metrics,
            }

    def close(self):
        """Close persistent connection if any."""
        if self._persistent_conn:
            self._persistent_conn.close()
            self._persistent_conn = None
