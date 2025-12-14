"""
Distribution Report parsing for 10-D filings.

Extracts common metrics from EX-99.x HTML exhibits across all ABS types.
Since distribution report formats vary significantly by issuer, this module
focuses on extracting commonly available high-level metrics while providing
access to raw tables for detailed analysis.
"""

import re
from dataclasses import dataclass
from datetime import date
from functools import cached_property
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

__all__ = ['DistributionReport', 'DistributionMetrics', 'ReportTable']


@dataclass
class DistributionMetrics:
    """
    Common metrics extracted from distribution reports.

    Not all fields will be populated for every filing - availability
    depends on the issuer's report format.
    """
    # Dates
    distribution_date: Optional[date] = None
    collection_period_start: Optional[date] = None
    collection_period_end: Optional[date] = None
    record_date: Optional[date] = None

    # Balances
    beginning_pool_balance: Optional[float] = None
    ending_pool_balance: Optional[float] = None
    original_pool_balance: Optional[float] = None

    # Distributions
    total_principal_distributed: Optional[float] = None
    total_interest_distributed: Optional[float] = None
    total_distribution: Optional[float] = None

    # Pool statistics
    pool_factor: Optional[float] = None

    # Delinquencies (as percentage or amount)
    delinquent_30_59_days: Optional[float] = None
    delinquent_60_89_days: Optional[float] = None
    delinquent_90_plus_days: Optional[float] = None
    total_delinquent: Optional[float] = None

    # Losses
    net_losses: Optional[float] = None
    cumulative_net_losses: Optional[float] = None

    def __rich__(self):
        """Rich console representation."""
        from rich import box
        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column("Label", style="grey70")
        table.add_column("Value")

        # Dates
        if self.distribution_date:
            table.add_row("Distribution Date", self.distribution_date.strftime("%B %d, %Y"))
        if self.collection_period_start and self.collection_period_end:
            table.add_row("Collection Period",
                         f"{self.collection_period_start.strftime('%m/%d/%y')} - {self.collection_period_end.strftime('%m/%d/%y')}")

        # Balances
        if self.beginning_pool_balance is not None:
            table.add_row("Beginning Balance", f"${self.beginning_pool_balance:,.2f}")
        if self.ending_pool_balance is not None:
            table.add_row("Ending Balance", f"${self.ending_pool_balance:,.2f}")
        if self.pool_factor is not None:
            table.add_row("Pool Factor", f"{self.pool_factor:.4f}")

        # Distributions
        if self.total_principal_distributed is not None:
            table.add_row("Principal Distributed", f"${self.total_principal_distributed:,.2f}")
        if self.total_interest_distributed is not None:
            table.add_row("Interest Distributed", f"${self.total_interest_distributed:,.2f}")
        if self.total_distribution is not None:
            table.add_row("Total Distribution", f"${self.total_distribution:,.2f}")

        # Delinquencies
        if self.total_delinquent is not None:
            table.add_row("Total Delinquent", f"${self.total_delinquent:,.2f}")

        # Losses
        if self.net_losses is not None:
            table.add_row("Net Losses", f"${self.net_losses:,.2f}")
        if self.cumulative_net_losses is not None:
            table.add_row("Cumulative Net Losses", f"${self.cumulative_net_losses:,.2f}")

        return Panel(table, title="Distribution Metrics", box=box.ROUNDED)


@dataclass
class ReportTable:
    """
    A table extracted from the distribution report.

    Provides both raw data and attempts to identify the table's purpose.
    """
    index: int
    rows: List[List[str]]
    label: Optional[str] = None  # Detected table purpose

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return max(len(row) for row in self.rows) if self.rows else 0

    @property
    def header(self) -> List[str]:
        """First row, often the header."""
        return self.rows[0] if self.rows else []

    def to_dataframe(self):
        """Convert to pandas DataFrame."""
        import pandas as pd

        if not self.rows:
            return pd.DataFrame()

        # Use first row as header if it looks like headers
        if self.rows and len(self.rows) > 1:
            return pd.DataFrame(self.rows[1:], columns=self.rows[0])
        return pd.DataFrame(self.rows)

    def __repr__(self):
        label_str = f" ({self.label})" if self.label else ""
        return f"ReportTable(index={self.index}, rows={self.num_rows}, cols={self.num_cols}{label_str})"


class DistributionReport:
    """
    Parser for 10-D distribution report exhibits (EX-99.x).

    Extracts common metrics from HTML distribution reports across all ABS types.
    Since report formats vary significantly by issuer, this class:

    1. Extracts commonly available high-level metrics (dates, balances, distributions)
    2. Provides access to labeled tables for detailed analysis
    3. Gracefully handles missing data

    Example:
        >>> ten_d = filing.obj()
        >>> report = ten_d.distribution_report
        >>> report.metrics.distribution_date
        datetime.date(2025, 11, 17)
        >>> report.metrics.ending_pool_balance
        117428397.26
        >>> report.tables  # List of ReportTable objects
        [ReportTable(index=0, rows=6, cols=4 (Header)),
         ReportTable(index=1, rows=77, cols=4 (Dates/Summary)), ...]
    """

    # Patterns for detecting table purposes
    TABLE_PATTERNS = {
        'dates': r'(collection|distribution|accrual|record)\s*(period|date)',
        'balances': r'(pool|note|certificate|collateral)\s*(balance|factor)',
        'distributions': r'(principal|interest)\s*(distribut|payment)',
        'delinquencies': r'(delinquen|past\s*due|30.*(59|60)|60.*(89|90))',
        'losses': r'(loss|write.?off|default|charge.?off)',
        'notes': r'(class|tranche|note)\s*(a|b|c|\d)',
        'reserve': r'(reserve|credit\s*enhancement)',
        'waterfall': r'(waterfall|priority|available\s*funds)',
    }

    # Patterns for extracting dates
    DATE_PATTERNS = [
        r'(\d{1,2}/\d{1,2}/\d{2,4})',  # MM/DD/YY or MM/DD/YYYY
        r'(\d{1,2}-\d{1,2}-\d{2,4})',  # MM-DD-YY or MM-DD-YYYY
        r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',  # Month DD, YYYY
    ]

    # Patterns for extracting money amounts
    MONEY_PATTERN = r'\$?\s*([\d,]+\.?\d*)'

    def __init__(self, html_content: str):
        """
        Initialize distribution report parser.

        Args:
            html_content: Raw HTML content from EX-99.x exhibit
        """
        self._html = html_content
        self._soup = BeautifulSoup(html_content, 'html.parser')
        self._tables: Optional[List[ReportTable]] = None
        self._metrics: Optional[DistributionMetrics] = None

    @cached_property
    def tables(self) -> List[ReportTable]:
        """
        Extract and label all significant tables from the report.

        Returns:
            List of ReportTable objects with detected labels
        """
        tables = []
        html_tables = self._soup.find_all('table')

        for i, html_table in enumerate(html_tables):
            rows = self._extract_table_rows(html_table)

            # Skip tiny tables (likely formatting)
            if len(rows) < 2:
                continue

            # Detect table purpose
            label = self._detect_table_label(rows)

            tables.append(ReportTable(index=i, rows=rows, label=label))

        return tables

    def _extract_table_rows(self, table: Tag) -> List[List[str]]:
        """Extract rows from an HTML table."""
        rows = []
        for tr in table.find_all('tr'):
            cells = []
            for cell in tr.find_all(['td', 'th']):
                text = cell.get_text(strip=True)
                # Normalize whitespace
                text = ' '.join(text.split())
                cells.append(text)
            if any(cells):  # Skip empty rows
                rows.append(cells)
        return rows

    def _detect_table_label(self, rows: List[List[str]]) -> Optional[str]:
        """Detect the purpose of a table based on its content."""
        # Combine first few rows for pattern matching
        sample_text = ' '.join(' '.join(row) for row in rows[:5]).lower()

        for label, pattern in self.TABLE_PATTERNS.items():
            if re.search(pattern, sample_text, re.IGNORECASE):
                return label

        return None

    @cached_property
    def metrics(self) -> DistributionMetrics:
        """
        Extract common metrics from the distribution report.

        Returns:
            DistributionMetrics with populated fields where data was found
        """
        metrics = DistributionMetrics()

        # Get all text for searching
        all_text = self._soup.get_text(separator='\n')

        # Extract dates
        self._extract_dates(metrics, all_text)

        # Extract from ALL tables - data may be in any table regardless of label
        for table in self.tables:
            self._extract_metrics_from_any_table(metrics, table)

        return metrics

    def _extract_dates(self, metrics: DistributionMetrics, text: str):
        """Extract date information from report text."""
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Distribution date
            if 'distribution date' in line_lower and metrics.distribution_date is None:
                date_val = self._find_date_in_context(lines, i)
                if date_val:
                    metrics.distribution_date = date_val

            # Collection period
            if 'collection' in line_lower and 'period' in line_lower:
                # Look for date range pattern
                range_match = re.search(
                    r'(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
                    line
                )
                if range_match:
                    metrics.collection_period_start = self._parse_date(range_match.group(1))
                    metrics.collection_period_end = self._parse_date(range_match.group(2))

            # Record date
            if 'record date' in line_lower and metrics.record_date is None:
                date_val = self._find_date_in_context(lines, i)
                if date_val:
                    metrics.record_date = date_val

    def _find_date_in_context(self, lines: List[str], line_idx: int) -> Optional[date]:
        """Find a date near the given line index."""
        # Check current line and next few lines
        for offset in range(3):
            if line_idx + offset < len(lines):
                for pattern in self.DATE_PATTERNS:
                    match = re.search(pattern, lines[line_idx + offset])
                    if match:
                        return self._parse_date(match.group(1))
        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats."""
        from datetime import datetime

        date_str = date_str.strip()

        formats = [
            '%m/%d/%y',
            '%m/%d/%Y',
            '%m-%d-%y',
            '%m-%d-%Y',
            '%B %d, %Y',
            '%B %d %Y',
            '%b %d, %Y',
            '%b %d %Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _extract_metrics_from_any_table(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract metrics from any table by scanning all rows."""
        # Check if this table contains "per $1,000" data - skip for balance extraction
        is_per_thousand = any(
            'per $1,000' in ' '.join(row).lower() or 'per $1000' in ' '.join(row).lower()
            for row in table.rows[:5]
        )

        for row in table.rows:
            row_text = ' '.join(row).lower()

            # Skip per-$1000 rows for balance/distribution extraction
            if is_per_thousand:
                # Only extract date info from per-$1000 tables
                self._try_extract_dates_from_row(metrics, row, row_text)
                continue

            # Extract balance metrics
            self._try_extract_balance_from_row(metrics, row, row_text)

            # Extract delinquency metrics
            self._try_extract_delinquency_from_row(metrics, row, row_text)

            # Extract loss metrics
            self._try_extract_loss_from_row(metrics, row, row_text)

            # Extract distribution metrics (from actual dollar tables, not per-$1000)
            self._try_extract_distribution_from_row(metrics, row, row_text)

            # Extract date metrics
            self._try_extract_dates_from_row(metrics, row, row_text)

    def _try_extract_balance_from_row(self, metrics: DistributionMetrics, row: List[str], row_text: str):
        """Try to extract balance metrics from a row."""
        # Beginning/starting pool balance
        if metrics.beginning_pool_balance is None:
            if ('beginning' in row_text or 'start' in row_text) and ('balance' in row_text or 'pool' in row_text):
                val = self._extract_large_money_from_row(row)
                if val:
                    metrics.beginning_pool_balance = val

            # Pattern: "Pool Balance at MM/DD/YY" (beginning of period)
            elif 'pool balance at' in row_text and '25' in row_text:
                # This could be beginning or ending - check date context
                val = self._extract_large_money_from_row(row)
                if val and metrics.beginning_pool_balance is None:
                    metrics.beginning_pool_balance = val

        # Ending pool balance
        if metrics.ending_pool_balance is None:
            if ('ending' in row_text or 'end of period' in row_text or 'end of' in row_text) and ('balance' in row_text or 'pool' in row_text):
                val = self._extract_large_money_from_row(row)
                if val:
                    metrics.ending_pool_balance = val

        # Original balance
        if metrics.original_pool_balance is None:
            if 'original' in row_text and ('balance' in row_text or 'pool' in row_text or 'class' in row_text):
                val = self._extract_large_money_from_row(row)
                if val:
                    metrics.original_pool_balance = val

        # Pool factor (percentage)
        if metrics.pool_factor is None:
            if 'pool factor' in row_text:
                val = self._extract_percentage_from_row(row)
                if val:
                    metrics.pool_factor = val

    def _try_extract_delinquency_from_row(self, metrics: DistributionMetrics, row: List[str], row_text: str):
        """Try to extract delinquency metrics from a row."""
        if '30' in row_text or '31' in row_text:
            if ('60' in row_text or '59' in row_text) and 'day' in row_text:
                if metrics.delinquent_30_59_days is None:
                    val = self._extract_large_money_from_row(row)
                    if val:
                        metrics.delinquent_30_59_days = val

        if '60' in row_text or '61' in row_text:
            if ('90' in row_text or '89' in row_text) and 'day' in row_text:
                if metrics.delinquent_60_89_days is None:
                    val = self._extract_large_money_from_row(row)
                    if val:
                        metrics.delinquent_60_89_days = val

        if ('90' in row_text or '91' in row_text) and ('+' in row_text or 'over' in row_text or '120' in row_text):
            if 'day' in row_text:
                if metrics.delinquent_90_plus_days is None:
                    val = self._extract_large_money_from_row(row)
                    if val:
                        metrics.delinquent_90_plus_days = val

        # Total delinquent - be careful with generic "total" as it appears many places
        if metrics.total_delinquent is None:
            if 'total' in row_text and ('delinq' in row_text or 'past due' in row_text):
                val = self._extract_large_money_from_row(row)
                if val:
                    metrics.total_delinquent = val

    def _try_extract_loss_from_row(self, metrics: DistributionMetrics, row: List[str], row_text: str):
        """Try to extract loss metrics from a row."""
        if 'net' in row_text and ('loss' in row_text or 'write' in row_text or 'charge' in row_text):
            if 'cumulative' in row_text:
                if metrics.cumulative_net_losses is None:
                    val = self._extract_large_money_from_row(row)
                    if val:
                        metrics.cumulative_net_losses = val
            else:
                if metrics.net_losses is None:
                    val = self._extract_large_money_from_row(row)
                    if val:
                        metrics.net_losses = val

    def _try_extract_distribution_from_row(self, metrics: DistributionMetrics, row: List[str], row_text: str):
        """Try to extract distribution metrics from a row."""
        # Principal payments/distributions (not per-$1000)
        if metrics.total_principal_distributed is None:
            if 'principal' in row_text and ('payment' in row_text or 'paid' in row_text):
                val = self._extract_large_money_from_row(row)
                if val:
                    metrics.total_principal_distributed = val

        # Interest payments/distributions
        if metrics.total_interest_distributed is None:
            if 'interest' in row_text and ('payment' in row_text or 'paid' in row_text or 'distribut' in row_text):
                val = self._extract_large_money_from_row(row)
                if val:
                    metrics.total_interest_distributed = val

    def _try_extract_dates_from_row(self, metrics: DistributionMetrics, row: List[str], row_text: str):
        """Try to extract date metrics from a row."""
        if 'distribution date' in row_text and metrics.distribution_date is None:
            date_val = self._find_date_in_row(row)
            if date_val:
                metrics.distribution_date = date_val

        if 'record date' in row_text and metrics.record_date is None:
            date_val = self._find_date_in_row(row)
            if date_val:
                metrics.record_date = date_val

        if 'collection' in row_text and 'period' in row_text:
            if metrics.collection_period_start is None:
                for cell in row:
                    range_match = re.search(
                        r'(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
                        cell
                    )
                    if range_match:
                        metrics.collection_period_start = self._parse_date(range_match.group(1))
                        metrics.collection_period_end = self._parse_date(range_match.group(2))
                        break

    def _extract_large_money_from_row(self, row: List[str]) -> Optional[float]:
        """Extract a significant money value from a table row (>= $1000)."""
        for cell in reversed(row):
            match = re.search(self.MONEY_PATTERN, cell)
            if match:
                try:
                    value_str = match.group(1).replace(',', '')
                    value = float(value_str)
                    # Only accept values >= 1000 (skip per-$1000 factors and small numbers)
                    if value >= 1000:
                        return value
                except ValueError:
                    continue
        return None

    def _extract_percentage_from_row(self, row: List[str]) -> Optional[float]:
        """Extract a percentage value from a row."""
        for cell in reversed(row):
            # Look for number followed by % or just a small decimal
            match = re.search(r'(\d+\.?\d*)\s*%?', cell.replace(',', ''))
            if match:
                try:
                    value = float(match.group(1))
                    # Reasonable percentage range
                    if 0 <= value <= 100:
                        return value
                except ValueError:
                    continue
        return None

    def _extract_from_table(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract metrics from a specific table based on its label."""
        if not table.label:
            return

        if table.label == 'balances':
            self._extract_balance_metrics(metrics, table)
        elif table.label == 'distributions':
            self._extract_distribution_metrics(metrics, table)
        elif table.label == 'delinquencies':
            self._extract_delinquency_metrics(metrics, table)
        elif table.label == 'losses':
            self._extract_loss_metrics(metrics, table)
        elif table.label == 'dates':
            self._extract_date_metrics(metrics, table)

    def _extract_balance_metrics(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract balance-related metrics from a table."""
        for row in table.rows:
            row_text = ' '.join(row).lower()

            # Pool balance patterns
            if 'beginning' in row_text and ('balance' in row_text or 'pool' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.beginning_pool_balance is None:
                    metrics.beginning_pool_balance = val

            if ('ending' in row_text or 'end of period' in row_text) and ('balance' in row_text or 'pool' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.ending_pool_balance is None:
                    metrics.ending_pool_balance = val

            if 'original' in row_text and ('balance' in row_text or 'pool' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.original_pool_balance is None:
                    metrics.original_pool_balance = val

            # Pool factor
            if 'pool factor' in row_text or 'note factor' in row_text:
                val = self._extract_number_from_row(row)
                if val and metrics.pool_factor is None:
                    metrics.pool_factor = val

    def _extract_distribution_metrics(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract distribution-related metrics from a table."""
        for row in table.rows:
            row_text = ' '.join(row).lower()

            if 'principal' in row_text and ('distribut' in row_text or 'paid' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.total_principal_distributed is None:
                    metrics.total_principal_distributed = val

            if 'interest' in row_text and ('distribut' in row_text or 'paid' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.total_interest_distributed is None:
                    metrics.total_interest_distributed = val

            if 'total' in row_text and 'distribut' in row_text:
                val = self._extract_money_from_row(row)
                if val and metrics.total_distribution is None:
                    metrics.total_distribution = val

    def _extract_delinquency_metrics(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract delinquency-related metrics from a table."""
        for row in table.rows:
            row_text = ' '.join(row).lower()

            if '30' in row_text and ('59' in row_text or '60' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.delinquent_30_59_days is None:
                    metrics.delinquent_30_59_days = val

            if '60' in row_text and ('89' in row_text or '90' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.delinquent_60_89_days is None:
                    metrics.delinquent_60_89_days = val

            if '90' in row_text and ('+' in row_text or 'plus' in row_text or 'over' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.delinquent_90_plus_days is None:
                    metrics.delinquent_90_plus_days = val

            if 'total' in row_text and ('delinq' in row_text or 'past due' in row_text):
                val = self._extract_money_from_row(row)
                if val and metrics.total_delinquent is None:
                    metrics.total_delinquent = val

    def _extract_loss_metrics(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract loss-related metrics from a table."""
        for row in table.rows:
            row_text = ' '.join(row).lower()

            if 'net' in row_text and ('loss' in row_text or 'write' in row_text):
                if 'cumulative' in row_text:
                    val = self._extract_money_from_row(row)
                    if val and metrics.cumulative_net_losses is None:
                        metrics.cumulative_net_losses = val
                else:
                    val = self._extract_money_from_row(row)
                    if val and metrics.net_losses is None:
                        metrics.net_losses = val

    def _extract_date_metrics(self, metrics: DistributionMetrics, table: ReportTable):
        """Extract date-related metrics from a dates table."""
        for row in table.rows:
            row_text = ' '.join(row).lower()

            if 'distribution date' in row_text and metrics.distribution_date is None:
                date_val = self._find_date_in_row(row)
                if date_val:
                    metrics.distribution_date = date_val

            if 'record date' in row_text and metrics.record_date is None:
                date_val = self._find_date_in_row(row)
                if date_val:
                    metrics.record_date = date_val

            # Collection period as date range
            if 'collection' in row_text and 'period' in row_text:
                for cell in row:
                    range_match = re.search(
                        r'(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
                        cell
                    )
                    if range_match:
                        metrics.collection_period_start = self._parse_date(range_match.group(1))
                        metrics.collection_period_end = self._parse_date(range_match.group(2))
                        break

    def _find_date_in_row(self, row: List[str]) -> Optional[date]:
        """Find a date value in a table row."""
        for cell in row:
            for pattern in self.DATE_PATTERNS:
                match = re.search(pattern, cell)
                if match:
                    return self._parse_date(match.group(1))
        return None

    def _extract_money_from_row(self, row: List[str]) -> Optional[float]:
        """Extract a money value from a table row."""
        # Look for money values in reverse order (usually value is on the right)
        for cell in reversed(row):
            match = re.search(self.MONEY_PATTERN, cell)
            if match:
                try:
                    value_str = match.group(1).replace(',', '')
                    value = float(value_str)
                    # Skip very small values that are likely percentages or factors
                    if value > 100:  # Reasonable threshold for dollar amounts
                        return value
                except ValueError:
                    continue
        return None

    def _extract_number_from_row(self, row: List[str]) -> Optional[float]:
        """Extract a numeric value from a table row (for factors, percentages)."""
        for cell in reversed(row):
            # Look for decimal numbers
            match = re.search(r'(\d+\.?\d*)', cell.replace(',', ''))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    def get_tables_by_label(self, label: str) -> List[ReportTable]:
        """Get all tables with a specific label."""
        return [t for t in self.tables if t.label == label]

    @property
    def significant_tables(self) -> List[ReportTable]:
        """Get tables with more than 5 rows (likely data tables)."""
        return [t for t in self.tables if t.num_rows > 5]

    def __repr__(self):
        return f"DistributionReport(tables={len(self.tables)}, significant={len(self.significant_tables)})"

    def __rich__(self):
        """Rich console representation."""
        from rich import box
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        # Table summary
        table_summary = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
        table_summary.add_column("Table", style="cyan")
        table_summary.add_column("Rows", justify="right")
        table_summary.add_column("Label", style="green")

        for t in self.significant_tables[:10]:
            table_summary.add_row(
                str(t.index),
                str(t.num_rows),
                t.label or "-"
            )

        if len(self.significant_tables) > 10:
            table_summary.add_row("...", "", f"+{len(self.significant_tables) - 10} more")

        content = Group(
            self.metrics.__rich__(),
            Text("\nTables:", style="bold"),
            table_summary,
        )

        return Panel(
            content,
            title=Text("Distribution Report", style="bold deep_sky_blue1"),
            box=box.ROUNDED,
        )
