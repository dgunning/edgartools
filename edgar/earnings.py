"""
8-K Earnings Release Table Parser

Extracts financial tables from 8-K EX-99.1 press release exhibits.

Note: 8-K filings typically contain only DEI (Document and Entity Information)
XBRL metadata, not full financial statements in XBRL format. Actual financial
data is in HTML tables within EX-99.1 exhibits.

This module uses the edgartools Document parser to handle complex HTML table
structures with colspan/rowspan patterns common in SEC filings.

Features:
- Automatic statement classification (Income Statement, Balance Sheet, etc.)
- Smart column collapsing (removes spacer cells)
- Currency symbol merging ($13,674 instead of $ | 13674)
- Multi-level header preservation
- Rich terminal display
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from functools import cached_property
from html import escape as html_escape
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import pandas as pd

from edgar.documents import parse_html

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
_QUARTER_PATTERN = re.compile(r'(Dec|Sep|Jun|Mar)\w*\s*\d+,?\s*(\d{4})')
_YEAR_PATTERN = re.compile(r'\b(19|20)\d{2}\b')
_SCALE_BILLIONS = re.compile(r'\b(in\s+)?billions?\b', re.IGNORECASE)
_SCALE_MILLIONS = re.compile(r'\b(in\s+)?millions?\b', re.IGNORECASE)
_SCALE_THOUSANDS = re.compile(r'\b(in\s+)?thousands?\b', re.IGNORECASE)

if TYPE_CHECKING:
    from edgar.attachments import Attachment, Attachments
    from edgar._filings import Filing

__all__ = [
    'EarningsRelease',
    'FinancialTable',
    'RowType',
    'Scale',
    'StatementType',
    'get_earnings_tables',
    'find_earnings_exhibit',
]


class Scale(Enum):
    """Financial statement scale factors."""
    UNITS = 1
    THOUSANDS = 1_000
    MILLIONS = 1_000_000
    BILLIONS = 1_000_000_000

    @classmethod
    def detect(cls, text: str) -> 'Scale':
        """
        Detect scale from text like 'in thousands' or 'in millions'.

        Uses word boundary matching to avoid false positives.
        Prioritizes larger units (billions > millions > thousands).
        """
        if _SCALE_BILLIONS.search(text):
            return cls.BILLIONS
        elif _SCALE_MILLIONS.search(text):
            return cls.MILLIONS
        elif _SCALE_THOUSANDS.search(text):
            return cls.THOUSANDS
        return cls.UNITS

    def __str__(self) -> str:
        return self.name.lower()


class StatementType(Enum):
    """Classification of financial statement tables."""
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    SEGMENT_DATA = "segment_data"
    EPS_RECONCILIATION = "eps_reconciliation"
    GAAP_RECONCILIATION = "gaap_reconciliation"
    KEY_METRICS = "key_metrics"
    GUIDANCE = "guidance"
    DEFINITIONS = "definitions"
    UNKNOWN = "unknown"


class RowType(Enum):
    """Classification of individual rows in a financial table."""
    AMOUNT = "amount"           # Dollar amounts (revenue, expenses, income)
    PER_SHARE = "per_share"     # Per-share values (EPS, dividends per share)
    SHARES = "shares"           # Share counts (outstanding, weighted average)
    PERCENTAGE = "percentage"   # Ratios and percentages (margins, rates)
    OTHER = "other"             # Labels, headers, or unclassifiable rows


# Keywords for statement classification
# "Strong" keywords score 2 (single match is sufficient for classification).
# Regular keywords score 1 (need 2+ matches). Total score >= 2 triggers match.
_STRONG_KEYWORDS = {
    StatementType.INCOME_STATEMENT: [
        'gross profit', 'operating income', 'operating loss',
        'income before taxes', 'income before provision',
        'income from operations', 'loss from operations',
        'provision for income taxes', 'income tax expense',
        'diluted earnings per share', 'diluted loss per share',
    ],
    StatementType.BALANCE_SHEET: [
        'total assets', 'total liabilities',
        "stockholders' equity", "shareholders' equity",
    ],
    StatementType.CASH_FLOW: [
        'cash flows from operating', 'cash flows from investing',
        'cash flows from financing',
    ],
}

_STATEMENT_KEYWORDS = {
    StatementType.INCOME_STATEMENT: [
        'net revenue', 'gross profit', 'operating income', 'cost of sales',
        'operating expenses', 'income before taxes', 'provision for taxes',
        'net sales', 'total revenues', 'total revenue', 'cost of revenue',
        'cost of goods sold', 'income from operations', 'net income',
        'net interest income', 'total interest income', 'income tax expense',
        'selling, general', 'revenue', 'net loss', 'operating loss',
        'diluted earnings', 'basic earnings', 'earnings per share',
        'loss per share', 'interest expense', 'noninterest income',
        'noninterest expense', 'loss from operations', 'loss before',
        'pretax income', 'pre-tax income', 'income before provision',
        'provision for credit', 'provision for income',
    ],
    StatementType.BALANCE_SHEET: [
        'total assets', 'total liabilities', 'stockholders', 'current assets',
        'current liabilities', 'property, plant', 'accounts receivable',
        'accounts payable', 'long-term debt', 'total equity',
        "shareholders' equity",
    ],
    StatementType.CASH_FLOW: [
        'cash flows', 'operating activities', 'investing activities',
        'financing activities', 'cash and cash equivalents, beginning',
        'cash and cash equivalents, end', 'depreciation and amortization',
        'capital expenditures',
    ],
    StatementType.SEGMENT_DATA: [
        'client computing', 'data center', 'foundry', 'segment revenue',
        'business unit', 'operating segment'
    ],
    StatementType.EPS_RECONCILIATION: [
        'gaap earnings per share', 'non-gaap earnings per share',
        'earnings (loss) per share attributable', 'diluted eps'
    ],
    StatementType.GAAP_RECONCILIATION: [
        'gaap to non-gaap', 'reconciliation', 'non-gaap adjustment'
    ],
    StatementType.GUIDANCE: [
        'outlook', 'guidance', 'q1 2026', 'q2 2026', 'q3 2026', 'q4 2026',
        'first quarter', 'next quarter'
    ],
    StatementType.DEFINITIONS: [
        'definition', 'usefulness to management', 'non-gaap adjustment or measure'
    ],
}

# Title/header patterns for high-confidence classification
_TITLE_PATTERNS = {
    StatementType.INCOME_STATEMENT: [
        'statement of operations', 'statement of income', 'statement of earnings',
        'results of operations', 'statements of operations', 'statements of income',
        'statements of earnings', 'income statement', 'profit and loss',
        'consolidated results', 'summary of operations', 'operating results',
    ],
    StatementType.BALANCE_SHEET: [
        'balance sheet', 'financial position', 'financial condition',
    ],
    StatementType.CASH_FLOW: [
        'cash flow', 'cash flows',
    ],
}

_ROW_TYPE_PATTERNS = {
    RowType.PER_SHARE: [
        'per share', 'per common share', 'per diluted share', 'per basic share',
        'earnings per share', 'loss per share', 'income per share',
        'per ads', 'per ordinary share', 'per adr',
    ],
    RowType.SHARES: [
        'shares outstanding', 'shares used', 'weighted average',
        'weighted-average', 'share count', 'number of shares',
        'diluted shares', 'basic shares', 'common shares',
    ],
    RowType.PERCENTAGE: [
        'margin', 'as a percentage', 'as a % of', 'effective tax rate',
        'growth rate', 'yield',
    ],
}


def _classify_row_type(label: str) -> RowType:
    """Classify a row's type based on its label text."""
    label_lower = label.lower()
    for row_type, patterns in _ROW_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in label_lower:
                return row_type
    return RowType.AMOUNT


# ── Period header parsing ──────────────────────────────────────────────────

# Regex for "Three Months Ended June 30, 2025" style headers
_DURATION_HEADER = re.compile(
    r'(?:(?P<word>Three|Six|Nine|Twelve)\s+Months|(?P<n>\d+)\s+Months|'
    r'(?P<qy>Quarter|Year))\s+'
    r'Ended\s*[-–—]?\s*'
    r'(?P<month>\w+)\s+(?P<day>\d{1,2}),?\s*(?P<year>\d{4})',
    re.IGNORECASE,
)

# Regex for bare date headers like "December 31, 2024"
_BARE_DATE = re.compile(
    r'^(?P<month>January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+(?P<day>\d{1,2}),?\s*(?P<year>\d{4})$',
    re.IGNORECASE,
)

_MONTH_NUMBERS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
    'oct': 10, 'nov': 11, 'dec': 12,
}

_WORD_TO_MONTHS = {
    'three': 3, 'six': 6, 'nine': 9, 'twelve': 12,
}


def _parse_period_header(header: str) -> Dict[str, object]:
    """Parse a column header into period components.

    Returns dict with keys: period_type, period_start, period_end,
    fiscal_year, fiscal_period, duration_months.
    All values are None if the header cannot be parsed.
    """
    empty = {
        'period_type': None, 'period_start': None, 'period_end': None,
        'fiscal_year': None, 'fiscal_period': None, 'duration_months': None,
    }

    header = header.strip()
    if not header or header.startswith('Col_'):
        return empty

    # Try duration pattern first
    m = _DURATION_HEADER.search(header)
    if m:
        month_name = m.group('month').lower()
        month_num = _MONTH_NUMBERS.get(month_name)
        if month_num is None:
            return empty
        day = int(m.group('day'))
        year = int(m.group('year'))
        try:
            period_end = date(year, month_num, day)
        except ValueError:
            return empty

        # Determine duration in months
        word = (m.group('word') or '').lower()
        qy = (m.group('qy') or '').lower()
        n_str = m.group('n')
        if word in _WORD_TO_MONTHS:
            duration_months = _WORD_TO_MONTHS[word]
        elif n_str:
            duration_months = int(n_str)
        elif qy == 'quarter':
            duration_months = 3
        elif qy == 'year':
            duration_months = 12
        else:
            duration_months = 3  # default

        # Compute period_start: go back duration_months, day 1
        # e.g. 3 months ended June 30 → start April 1
        start_month = month_num - duration_months + 1
        start_year = year
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        period_start = date(start_year, start_month, 1)

        fiscal_year = period_end.year
        fiscal_period = _duration_to_fiscal_period(duration_months, month_num)

        return {
            'period_type': 'duration',
            'period_start': period_start,
            'period_end': period_end,
            'fiscal_year': fiscal_year,
            'fiscal_period': fiscal_period,
            'duration_months': duration_months,
        }

    # Try bare date (instant / balance sheet)
    m = _BARE_DATE.match(header)
    if m:
        month_name = m.group('month').lower()
        month_num = _MONTH_NUMBERS.get(month_name)
        if month_num is None:
            return empty
        day = int(m.group('day'))
        year = int(m.group('year'))
        try:
            period_end = date(year, month_num, day)
        except ValueError:
            return empty

        return {
            'period_type': 'instant',
            'period_start': None,
            'period_end': period_end,
            'fiscal_year': year,
            'fiscal_period': None,
            'duration_months': None,
        }

    return empty


def _duration_to_fiscal_period(duration_months: int, end_month: int) -> str:
    """Map duration and ending month to fiscal period label."""
    if duration_months >= 12:
        return 'FY'
    if duration_months == 3:
        q_map = {3: 'Q1', 6: 'Q2', 9: 'Q3', 12: 'Q4'}
        return q_map.get(end_month, f'Q{(end_month - 1) // 3 + 1}')
    if duration_months == 6:
        return 'H1' if end_month <= 6 else 'H2'
    if duration_months == 9:
        return '9M'
    return f'{duration_months}M'


# ── Label-to-concept mapping ──────────────────────────────────────────────

_CONCEPT_REVERSE_MAP: Optional[Dict[str, str]] = None


def _load_concept_reverse_map() -> Dict[str, str]:
    """Build a reverse lookup from lowercase display label → first XBRL tag."""
    global _CONCEPT_REVERSE_MAP
    if _CONCEPT_REVERSE_MAP is not None:
        return _CONCEPT_REVERSE_MAP

    mapping_path = Path(__file__).parent / 'xbrl' / 'standardization' / 'concept_mappings.json'
    reverse: Dict[str, str] = {}
    try:
        with open(mapping_path) as f:
            mappings = json.load(f)
        for display_label, tags in mappings.items():
            if display_label.startswith('_'):
                continue
            if isinstance(tags, list) and tags:
                # Use colon notation: "us-gaap_Revenue" → "us-gaap:Revenue"
                tag = tags[0].replace('_', ':', 1)
                key = display_label.strip().lower()
                if key not in reverse:
                    reverse[key] = tag
    except (OSError, json.JSONDecodeError):
        pass

    _CONCEPT_REVERSE_MAP = reverse
    return reverse


def _label_to_concept(label: str) -> str:
    """Map a row label to an XBRL concept name.

    Tries exact case-insensitive match against concept_mappings.json.
    Falls back to a PascalCase normalized form of the label.
    """
    reverse = _load_concept_reverse_map()
    key = label.strip().lower()

    # Exact match
    if key in reverse:
        return reverse[key]

    # Fallback: normalize to PascalCase
    # "Net sales" → "NetSales", "Adj. EBITDA" → "AdjEbitda"
    words = re.sub(r'[^a-zA-Z0-9\s]', '', label).split()
    return ''.join(w.capitalize() for w in words) if words else label


# ── Unit mapping from RowType ─────────────────────────────────────────────

_ROW_TYPE_UNITS = {
    RowType.AMOUNT: 'USD',
    RowType.PER_SHARE: 'USD/shares',
    RowType.SHARES: 'shares',
    RowType.PERCENTAGE: 'pure',
    RowType.OTHER: 'USD',
}


@dataclass
class FinancialTable:
    """A parsed financial table from an earnings release."""

    dataframe: pd.DataFrame
    """The parsed table data as a DataFrame."""

    scale: Scale = Scale.UNITS
    """Detected scale factor (thousands, millions, etc.)."""

    title: Optional[str] = None
    """Table title if detected."""

    statement_type: StatementType = StatementType.UNKNOWN
    """Classified statement type."""

    periods: List[str] = field(default_factory=list)
    """Period labels found in the table."""

    raw_index: int = 0
    """Original index in document (for debugging)."""

    row_types: dict = field(default_factory=dict)
    """Mapping of row label → RowType for each row."""

    def __bool__(self) -> bool:
        """FinancialTable is truthy if it has data."""
        return not self.dataframe.empty

    def get_row_type(self, label: str) -> RowType:
        """Get the RowType for a given row label."""
        return self.row_types.get(label, RowType.AMOUNT)

    @property
    def per_share_rows(self) -> pd.DataFrame:
        """Return only per-share rows (EPS, dividends per share, etc.)."""
        mask = [self.get_row_type(str(idx)) == RowType.PER_SHARE for idx in self.dataframe.index]
        return self.dataframe.loc[mask]

    @property
    def scaled_dataframe(self) -> pd.DataFrame:
        """Return DataFrame with numeric values scaled by the detected scale factor.

        Only AMOUNT rows are scaled. PER_SHARE, SHARES, and PERCENTAGE rows
        are left unchanged since they should not be multiplied by the table's
        scale factor.
        """
        if self.scale == Scale.UNITS:
            return self.dataframe.copy()

        df = self.dataframe.copy()
        # Only scale AMOUNT rows — skip PER_SHARE, SHARES, PERCENTAGE
        skip_labels = {str(idx) for idx in df.index
                       if self.get_row_type(str(idx)) != RowType.AMOUNT}

        for col_idx in range(len(df.columns)):
            col_series = df.iloc[:, col_idx]
            numeric = pd.to_numeric(col_series, errors='coerce')
            mask = numeric.notna()
            # Zero out mask for non-amount rows
            for label in skip_labels:
                if label in df.index:
                    mask[label] = False
            df.iloc[mask.values, col_idx] = numeric[mask] * self.scale.value
        return df

    def __repr__(self) -> str:
        shape = self.dataframe.shape
        type_str = self.statement_type.value
        return f"FinancialTable({type_str}, {shape[0]}×{shape[1]}, scale={self.scale})"

    # =========================================================================
    # Display Methods (Use Case 1: Nice display in SAAS app)
    # =========================================================================

    def to_html(self, include_title: bool = True, classes: str = "financial-table") -> str:
        """
        Export table as HTML for web display.

        Args:
            include_title: Include statement type as caption
            classes: CSS classes for the table element

        Returns:
            HTML string ready for embedding in web pages (XSS-safe)
        """
        df = self._display_dataframe()

        caption = ""
        if include_title:
            title = self.statement_type.value.replace('_', ' ').title()
            if self.scale != Scale.UNITS:
                title += f" (in {self.scale.name.lower()})"
            # XSS protection: escape title before embedding in HTML
            caption = f"<caption>{html_escape(title)}</caption>"

        def format_float(x):
            """Format float with safe integer comparison."""
            if pd.isna(x):
                return "-"
            if abs(x - round(x)) < 1e-9:
                return f"{int(round(x)):,}"
            return f"{x:,.2f}"

        html = df.to_html(classes=classes, na_rep="-", float_format=format_float)

        # Insert caption after opening <table ...> tag
        if caption:
            html = re.sub(r'(<table[^>]*>)', rf'\1\n{caption}', html, count=1)

        return html

    def to_json(self, include_metadata: bool = True) -> str:
        """
        Export table as JSON for API responses.

        Args:
            include_metadata: Include scale, periods, statement_type

        Returns:
            JSON string with data and optional metadata
        """
        import json

        df = self._display_dataframe()

        result = {
            "data": df.to_dict(orient="index")
        }

        if include_metadata:
            result["metadata"] = {
                "statement_type": self.statement_type.value,
                "scale": self.scale.name.lower(),
                "scale_factor": self.scale.value,
                "periods": self.periods,
                "title": self.title,
                "shape": list(self.dataframe.shape)
            }

        return json.dumps(result, indent=2, default=str)

    # =========================================================================
    # AI Input Methods (Use Case 2: Feed to AI for analysis)
    # =========================================================================

    def to_markdown(self, include_context: bool = True) -> str:
        """
        Export table as Markdown for AI analysis input.

        Produces a compact, AI-friendly format with context about
        what the numbers represent.

        Args:
            include_context: Include header with scale and period info

        Returns:
            Markdown string optimized for AI consumption
        """
        lines = []

        if include_context:
            title = self.statement_type.value.replace('_', ' ').title()
            lines.append(f"## {title}")
            if self.scale != Scale.UNITS:
                lines.append(f"*All values in {self.scale.name.lower()}*")
            lines.append("")

        df = self._display_dataframe()
        lines.append(df.to_markdown())

        return "\n".join(lines)

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns AI-optimized text representation for language models.

        Produces a compact representation with all necessary context
        for AI analysis, including scale interpretation hints.

        Args:
            detail: Level of detail - 'minimal', 'standard', or 'full'

        Returns:
            String optimized for LLM input
        """
        lines = []

        # Header with context
        title = self.statement_type.value.replace('_', ' ').title()
        lines.append(f"=== {title} ===")

        scale_hint = ""
        if self.scale == Scale.MILLIONS:
            scale_hint = " (multiply by 1,000,000 for actual USD)"
        elif self.scale == Scale.THOUSANDS:
            scale_hint = " (multiply by 1,000 for actual USD)"
        elif self.scale == Scale.BILLIONS:
            scale_hint = " (multiply by 1,000,000,000 for actual USD)"

        if scale_hint:
            lines.append(f"Scale: {self.scale.name}{scale_hint}")

        if self.periods and detail != 'minimal':
            lines.append(f"Periods: {', '.join(str(p) for p in self.periods[:4])}")

        lines.append("")

        # Table format based on detail level
        df = self._display_dataframe()

        if detail == 'minimal':
            # Just key metrics
            key_rows = ['Net revenue', 'Revenue', 'Gross profit', 'Operating income',
                       'Net income', 'Net income (loss)', 'Earnings (loss) per share']
            df_filtered = df[df.index.isin(key_rows) | df.index.str.contains('revenue|income|eps', case=False)]
            if not df_filtered.empty:
                df = df_filtered
            lines.append(df.head(10).to_string())
        elif detail == 'full':
            lines.append(df.to_string())
        else:  # standard
            lines.append(df.head(15).to_string())
            if len(df) > 15:
                lines.append(f"... ({len(df) - 15} more rows)")

        return "\n".join(lines)

    def to_csv(self) -> str:
        """
        Export table as CSV string.

        Returns:
            CSV string with clean column names
        """
        df = self._display_dataframe()
        return df.to_csv()

    # =========================================================================
    # Facts DataFrame (Use Case 4: Merge with XBRL facts)
    # =========================================================================

    def to_facts_dataframe(self) -> pd.DataFrame:
        """Convert table to a facts DataFrame matching the EntityFacts.to_dataframe() schema.

        Each row × column cell becomes one record with columns:
        concept, label, value, numeric_value, unit, period_type,
        period_start, period_end, fiscal_year, fiscal_period.

        AMOUNT rows are scaled by the table's scale factor; PER_SHARE,
        SHARES, and PERCENTAGE rows are left unscaled.
        """
        records = []
        df = self.dataframe

        for col in df.columns:
            period_info = _parse_period_header(str(col))

            for idx_label in df.index:
                label = str(idx_label)
                row_type = self.get_row_type(label)

                raw_val = df.at[idx_label, col]
                # Skip non-numeric cells (headers, subtitles, NaN)
                numeric_val = None
                if isinstance(raw_val, (int, float)):
                    numeric_val = float(raw_val)
                elif raw_val is not None:
                    try:
                        numeric_val = float(raw_val)
                    except (ValueError, TypeError):
                        pass
                if numeric_val is None:
                    continue

                # Apply scaling only to AMOUNT rows
                if row_type == RowType.AMOUNT and self.scale != Scale.UNITS:
                    numeric_val = numeric_val * self.scale.value

                records.append({
                    'concept': _label_to_concept(label),
                    'label': label,
                    'value': str(raw_val),
                    'numeric_value': numeric_val,
                    'unit': _ROW_TYPE_UNITS.get(row_type, 'USD'),
                    'period_type': period_info['period_type'],
                    'period_start': period_info['period_start'],
                    'period_end': period_info['period_end'],
                    'fiscal_year': period_info['fiscal_year'],
                    'fiscal_period': period_info['fiscal_period'],
                })

        if not records:
            return pd.DataFrame(columns=[
                'concept', 'label', 'value', 'numeric_value', 'unit',
                'period_type', 'period_start', 'period_end',
                'fiscal_year', 'fiscal_period',
            ])
        return pd.DataFrame(records)

    # =========================================================================
    # AI Cleanup Support (Use Case 3: Standardization)
    # =========================================================================

    def get_raw_labels(self) -> List[str]:
        """
        Get the raw row labels for AI-based standardization.

        Returns:
            List of original row labels as they appear in the filing
        """
        return list(self.dataframe.index)

    def with_standardized_labels(self, label_mapping: Optional[dict] = None) -> 'FinancialTable':
        """
        Create a new FinancialTable with standardized row labels.

        Use this after AI has suggested label mappings to create
        a cleaned version of the table.

        Args:
            label_mapping: Dict mapping original labels to standard labels
                          e.g., {"Net revenue": "Revenue",
                                 "Cost of sales": "Cost of Revenue"}
                          If None or empty, returns a copy unchanged.

        Returns:
            New FinancialTable with renamed index labels
        """
        df = self.dataframe.copy()

        if label_mapping:
            df.index = df.index.map(lambda x: label_mapping.get(x, x))

        return FinancialTable(
            dataframe=df,
            scale=self.scale,
            title=self.title,
            statement_type=self.statement_type,
            periods=self.periods,
            raw_index=self.raw_index
        )

    def with_clean_columns(self, column_names: Optional[List[str]] = None) -> 'FinancialTable':
        """
        Create a new FinancialTable with cleaner column names.

        Args:
            column_names: Optional list of new column names.
                         If None, auto-cleans existing names.

        Returns:
            New FinancialTable with renamed columns
        """
        df = self.dataframe.copy()

        if column_names:
            df.columns = column_names[:len(df.columns)]
        else:
            # Auto-clean: "Three Months Ended - Dec 27, 2025" -> "Q4 2025"
            clean_cols = []
            for col in df.columns:
                col_str = str(col)
                # Extract year and quarter info
                if "Three Months" in col_str or "Quarter" in col_str:
                    # Try to extract date
                    match = re.search(r'(Dec|Sep|Jun|Mar)\w*\s*\d+,?\s*(\d{4})', col_str)
                    if match:
                        month, year = match.groups()
                        q_map = {"Dec": "Q4", "Sep": "Q3", "Jun": "Q2", "Mar": "Q1"}
                        clean_cols.append(f"{q_map.get(month[:3], 'Q?')} {year}")
                    else:
                        clean_cols.append(col_str[:15])
                elif "Twelve Months" in col_str or "Year" in col_str:
                    match = re.search(r'(\d{4})', col_str)
                    if match:
                        clean_cols.append(f"FY {match.group(1)}")
                    else:
                        clean_cols.append(col_str[:15])
                else:
                    clean_cols.append(col_str[:15] if len(col_str) > 15 else col_str)
            df.columns = clean_cols

        return FinancialTable(
            dataframe=df,
            scale=self.scale,
            title=self.title,
            statement_type=self.statement_type,
            periods=self.periods,
            raw_index=self.raw_index
        )

    def _display_dataframe(self) -> pd.DataFrame:
        """Get DataFrame with clean column names for display."""
        return self.with_clean_columns().dataframe

    # =========================================================================
    # Rich Display
    # =========================================================================

    def __rich__(self):
        """Rich console display."""
        from rich.table import Table

        # Create title
        title_parts = [self.statement_type.value.replace('_', ' ').title()]
        if self.scale != Scale.UNITS:
            title_parts.append(f"(in {self.scale.name.lower()})")
        title = " ".join(title_parts)

        # Create table
        table = Table(title=title, show_header=True, header_style="bold")

        # Add columns
        table.add_column("Item", style="cyan", no_wrap=False)
        for col in self.dataframe.columns:
            # Clean and shorten column names for display
            col_name = str(col)
            col_name = col_name.replace("Three Months Ended - ", "Q ")
            col_name = col_name.replace("Twelve Months Ended - ", "FY ")
            col_name = col_name.replace("Quarter Ended ", "Q ")
            col_name = col_name.replace(",\n", " ")
            col_name = col_name.replace("\n", " ")
            if len(col_name) > 15:
                col_name = col_name[:12] + "..."
            table.add_column(col_name, justify="right")

        # Add rows (limit to 20 for display)
        for idx, row in self.dataframe.head(20).iterrows():
            row_values = [str(idx)]
            for val in row:
                if pd.isna(val) or val is None:
                    row_values.append("-")
                elif isinstance(val, float):
                    if abs(val - round(val)) < 1e-9:
                        row_values.append(f"{int(round(val)):,}")
                    else:
                        row_values.append(f"{val:,.2f}")
                else:
                    row_values.append(str(val))
            table.add_row(*row_values)

        if len(self.dataframe) > 20:
            table.add_row(f"... ({len(self.dataframe) - 20} more rows)", *["" for _ in self.dataframe.columns])

        return table


@dataclass
class _CleanColumn:
    """Internal: A logical column extracted from the table."""
    header: str
    parent_header: Optional[str] = None

    @property
    def full_header(self) -> str:
        if self.parent_header and self.parent_header != self.header:
            return f"{self.parent_header} - {self.header}"
        return self.header


class EarningsRelease:
    """
    Parser for 8-K earnings release exhibits.

    Uses the edgartools Document parser to handle complex HTML table structures
    with colspan/rowspan patterns common in SEC filings.

    Example:
        >>> from edgar import Company
        >>> from edgar.earnings import EarningsRelease
        >>>
        >>> filing = Company("AAPL").get_filings(form="8-K")[0]
        >>> earnings = EarningsRelease.from_filing(filing)
        >>> if earnings:
        ...     # Access specific statements
        ...     print(earnings.income_statement.dataframe)
        ...     print(earnings.balance_sheet.dataframe)
        ...
        ...     # Rich display in terminal
        ...     from rich import print
        ...     print(earnings.income_statement)
    """

    def __init__(self, attachment: 'Attachment'):
        self.attachment = attachment
        self._document = None
        self._tables: Optional[List[FinancialTable]] = None
        self._scale: Optional[Scale] = None

    @classmethod
    def from_filing(cls, filing: 'Filing') -> Optional['EarningsRelease']:
        """
        Find and wrap the EX-99.1 earnings exhibit from a filing.

        Args:
            filing: An SEC Filing object (typically an 8-K)

        Returns:
            EarningsRelease if an EX-99 exhibit is found, None otherwise.
        """
        exhibit = find_earnings_exhibit(filing.attachments)
        if exhibit:
            return cls(exhibit)
        return None

    @property
    def document(self):
        """Get the parsed Document."""
        if self._document is None:
            try:
                html_content = self.attachment.content
                if html_content is None:
                    logger.warning(f"Attachment content is None for {self.attachment.document}")
                    return None
                if isinstance(html_content, bytes):
                    html_content = html_content.decode('utf-8', errors='ignore')
                self._document = parse_html(html_content)
            except (AttributeError, ValueError, TypeError) as e:
                logger.error(f"Failed to parse attachment content: {e}")
                return None
        return self._document

    @property
    def detected_scale(self) -> Scale:
        """Detect the primary scale used in the document."""
        if self._scale is None:
            text = self.document.text()
            self._scale = Scale.detect(text)
        return self._scale

    @property
    def tables(self) -> List[FinancialTable]:
        """All extracted tables (including definitions, etc.)."""
        if self._tables is None:
            self._tables = self._extract_tables()
        return self._tables

    @property
    def financial_tables(self) -> List[FinancialTable]:
        """Only tables with actual financial data (excludes definitions)."""
        return [t for t in self.tables if t.statement_type != StatementType.DEFINITIONS]

    def get_financial_tables(self, min_rows: int = 3, min_cols: int = 2) -> List[FinancialTable]:
        """
        Get financial tables filtered by minimum size.

        Args:
            min_rows: Minimum rows for a table to be included
            min_cols: Minimum columns for a table to be included

        Returns:
            List of FinancialTable objects meeting the size criteria.
        """
        return [
            t for t in self.financial_tables
            if t.dataframe.shape[0] >= min_rows and t.dataframe.shape[1] >= min_cols
        ]

    @property
    def income_statement(self) -> Optional[FinancialTable]:
        """Get the primary income statement table."""
        candidates = [t for t in self.tables if t.statement_type == StatementType.INCOME_STATEMENT]
        if candidates:
            return max(candidates, key=lambda t: t.dataframe.shape[0])
        return None

    @property
    def balance_sheet(self) -> Optional[FinancialTable]:
        """Get the balance sheet table."""
        for t in self.tables:
            if t.statement_type == StatementType.BALANCE_SHEET:
                return t
        return None

    @property
    def cash_flow_statement(self) -> Optional[FinancialTable]:
        """Get the cash flow statement table."""
        for t in self.tables:
            if t.statement_type == StatementType.CASH_FLOW:
                return t
        return None

    @property
    def segment_data(self) -> Optional[FinancialTable]:
        """Get segment/business unit breakdown table."""
        for t in self.tables:
            if t.statement_type == StatementType.SEGMENT_DATA:
                return t
        return None

    @property
    def eps_reconciliation(self) -> Optional[FinancialTable]:
        """Get EPS GAAP to Non-GAAP reconciliation table."""
        for t in self.tables:
            if t.statement_type == StatementType.EPS_RECONCILIATION:
                return t
        return None

    @property
    def guidance(self) -> Optional[FinancialTable]:
        """Get forward guidance table if present."""
        for t in self.tables:
            if t.statement_type == StatementType.GUIDANCE:
                return t
        return None

    def to_facts_dataframe(self) -> pd.DataFrame:
        """Combine all financial tables into a single facts DataFrame.

        Returns a DataFrame matching the EntityFacts.to_dataframe() schema
        with an extra ``source_statement`` column for disambiguation.
        """
        frames = []
        for table in self.financial_tables:
            df = table.to_facts_dataframe()
            if not df.empty:
                df['source_statement'] = table.statement_type.value
                frames.append(df)
        if not frames:
            cols = [
                'concept', 'label', 'value', 'numeric_value', 'unit',
                'period_type', 'period_start', 'period_end',
                'fiscal_year', 'fiscal_period', 'source_statement',
            ]
            return pd.DataFrame(columns=cols)
        return pd.concat(frames, ignore_index=True)

    def _extract_tables(self) -> List[FinancialTable]:
        """Extract and classify all tables from the document."""
        tables = []
        doc_scale = Scale.UNITS  # Safe default — per-table detection is primary

        for idx, table_node in enumerate(self.document.tables):
            df = _extract_clean_dataframe(table_node)

            if df.empty or df.shape[0] < 2:
                logger.debug(f"Skipping table {idx}: empty or insufficient rows (shape={df.shape})")
                continue

            statement_type = _classify_statement(table_node, df)
            scale = _detect_table_scale(table_node, df, doc_scale)
            title = _extract_title(table_node)

            # Detect periods using year pattern (handles any year from 1900-2099)
            periods = [c for c in df.columns
                      if c and str(c).strip() and _YEAR_PATTERN.search(str(c))]

            row_types = {str(idx_label): _classify_row_type(str(idx_label))
                         for idx_label in df.index}

            table = FinancialTable(
                dataframe=df,
                scale=scale,
                title=title,
                statement_type=statement_type,
                periods=periods,
                raw_index=idx,
                row_types=row_types,
            )
            tables.append(table)

        return tables

    def __repr__(self) -> str:
        n_financial = len(self.financial_tables)
        return f"EarningsRelease({self.attachment.document}, {n_financial} financial tables)"

    def __rich__(self):
        """Rich console display showing available statements."""
        from rich.table import Table

        summary = Table(title=f"Earnings Release: {self.attachment.document}", show_header=True)
        summary.add_column("Statement Type", style="cyan")
        summary.add_column("Shape", justify="right")
        summary.add_column("Scale", justify="center")
        summary.add_column("Columns", style="dim")

        for t in self.financial_tables:
            shape_str = f"{t.dataframe.shape[0]}×{t.dataframe.shape[1]}"
            scale_str = t.scale.name.lower() if t.scale != Scale.UNITS else "-"
            cols = ", ".join(str(c)[:20] for c in t.dataframe.columns[:2])
            if len(t.dataframe.columns) > 2:
                cols += "..."
            summary.add_row(
                t.statement_type.value.replace('_', ' ').title(),
                shape_str,
                scale_str,
                cols
            )

        return summary

    def summary(self) -> str:
        """Return a text summary of available statements."""
        lines = [f"Earnings Release: {self.attachment.document}"]
        lines.append(f"Scale: {self.detected_scale}")
        lines.append(f"Tables: {len(self.financial_tables)} financial")
        lines.append("")

        if self.income_statement:
            lines.append(f"✓ Income Statement: {self.income_statement.dataframe.shape}")
        if self.balance_sheet:
            lines.append(f"✓ Balance Sheet: {self.balance_sheet.dataframe.shape}")
        if self.cash_flow_statement:
            lines.append(f"✓ Cash Flow: {self.cash_flow_statement.dataframe.shape}")
        if self.segment_data:
            lines.append(f"✓ Segment Data: {self.segment_data.dataframe.shape}")
        if self.eps_reconciliation:
            lines.append(f"✓ EPS Reconciliation: {self.eps_reconciliation.dataframe.shape}")
        if self.guidance:
            lines.append(f"✓ Guidance: {self.guidance.dataframe.shape}")

        return "\n".join(lines)

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns AI-optimized text representation for language models.

        Produces a comprehensive earnings summary suitable for AI analysis,
        including key financial statements with scale context.

        Args:
            detail: Level of detail - 'minimal', 'standard', or 'full'
                   - minimal: Just income statement key metrics
                   - standard: Income statement + balance sheet summary
                   - full: All available statements

        Returns:
            String optimized for LLM input
        """
        lines = [f"=== Earnings Release ==="]
        lines.append(f"Document: {self.attachment.document}")
        lines.append(f"Scale: {self.detected_scale.name.lower()}")
        lines.append("")

        # Always include income statement if available
        if self.income_statement:
            lines.append(self.income_statement.to_context(detail=detail))
            lines.append("")

        if detail in ('standard', 'full') and self.balance_sheet:
            lines.append(self.balance_sheet.to_context(detail='minimal' if detail == 'standard' else detail))
            lines.append("")

        if detail == 'full':
            if self.cash_flow_statement:
                lines.append(self.cash_flow_statement.to_context(detail='standard'))
                lines.append("")
            if self.segment_data:
                lines.append(self.segment_data.to_context(detail='minimal'))
                lines.append("")

        return "\n".join(lines)


def get_earnings_tables(filing: 'Filing') -> List[FinancialTable]:
    """
    Convenience function to get all financial tables from an 8-K filing.

    Args:
        filing: An SEC Filing object (typically an 8-K)

    Returns:
        List of FinancialTable objects, empty list if no earnings exhibit found.
    """
    earnings = EarningsRelease.from_filing(filing)
    if earnings:
        return earnings.financial_tables
    return []


def find_earnings_exhibit(attachments: 'Attachments') -> Optional['Attachment']:
    """
    Find the EX-99.1 (or similar) earnings press release exhibit.

    Args:
        attachments: Attachments collection from a filing

    Returns:
        The earnings exhibit Attachment if found, None otherwise.
    """
    exhibit_patterns = [
        r'EX-99\.1',
        r'EX-99\.01',
        r'EX-99',
    ]

    for pattern in exhibit_patterns:
        for attachment in attachments:
            desc = (attachment.description or "").upper()
            doc = (attachment.document or "").lower()

            if re.search(pattern, desc, re.IGNORECASE):
                if any(x in doc for x in ['.xsd', '.xml', '_lab.', '_pre.', '_def.', '_cal.']):
                    continue
                if attachment.is_html():
                    return attachment

            if re.search(r'ex-?99', doc, re.IGNORECASE) and attachment.is_html():
                return attachment

    return None


# =============================================================================
# Internal functions
# =============================================================================

def _classify_statement(table_node, df: pd.DataFrame) -> StatementType:
    """Classify the statement type based on title, row labels, and content."""
    # 1. Check table title/headers for explicit statement names
    header_text = ''
    if table_node.caption:
        header_text += table_node.caption.lower() + ' '
    if table_node.headers:
        for header_row in table_node.headers:
            for cell in header_row:
                header_text += (cell.content or '').lower() + ' '

    for stmt_type, patterns in _TITLE_PATTERNS.items():
        for pattern in patterns:
            if pattern in header_text:
                return stmt_type

    # 2. Keyword matching on row labels (expanded range)
    labels = []
    for row in table_node.rows[:20]:
        for cell in row.cells:
            content = (cell.content or "").strip()
            if content and len(content) > 3:
                labels.append(content.lower())
                break

    if hasattr(df, 'index'):
        labels.extend([str(x).lower() for x in df.index[:20]])

    labels_text = ' '.join(labels)

    # Weighted scoring: strong keywords score 2, regular score 1. Threshold = 2.
    best_type = None
    best_score = 0
    for stmt_type, keywords in _STATEMENT_KEYWORDS.items():
        strong = _STRONG_KEYWORDS.get(stmt_type, [])
        score = 0
        for kw in keywords:
            if kw in labels_text:
                score += 2 if kw in strong else 1
        if score >= 2 and score > best_score:
            best_score = score
            best_type = stmt_type

    if best_type is not None:
        return best_type

    for kw in _STATEMENT_KEYWORDS[StatementType.DEFINITIONS]:
        if kw in labels_text:
            return StatementType.DEFINITIONS

    return StatementType.UNKNOWN


def _detect_table_scale(table_node, df: pd.DataFrame, default_scale: Scale) -> Scale:
    """Detect scale from table caption, headers, early content, footer, or index labels."""
    # 1. Check caption
    if table_node.caption:
        scale = Scale.detect(table_node.caption)
        if scale != Scale.UNITS:
            return scale

    # 2. Check headers
    if table_node.headers:
        for header_row in table_node.headers:
            for cell in header_row:
                content = cell.content.lower()
                if 'million' in content:
                    return Scale.MILLIONS
                elif 'thousand' in content:
                    return Scale.THOUSANDS
                elif 'billion' in content:
                    return Scale.BILLIONS

    # 3. Check first 3 data rows
    for row in table_node.rows[:3]:
        for cell in row.cells:
            content = cell.content.lower()
            if 'in millions' in content or '(millions)' in content:
                return Scale.MILLIONS
            elif 'in thousands' in content or '(thousands)' in content:
                return Scale.THOUSANDS
            elif 'in billions' in content or '(billions)' in content:
                return Scale.BILLIONS

    # 4. Check footer rows
    if table_node.footer:
        for row in table_node.footer:
            for cell in row.cells:
                content = cell.content.lower()
                if 'million' in content:
                    return Scale.MILLIONS
                elif 'thousand' in content:
                    return Scale.THOUSANDS
                elif 'billion' in content:
                    return Scale.BILLIONS

    # 5. Check DataFrame index labels (e.g. "(In millions, except per share data)")
    if hasattr(df, 'index'):
        for label in df.index[:5]:
            label_lower = str(label).lower()
            if 'in millions' in label_lower or '(millions)' in label_lower:
                return Scale.MILLIONS
            elif 'in thousands' in label_lower or '(thousands)' in label_lower:
                return Scale.THOUSANDS
            elif 'in billions' in label_lower or '(billions)' in label_lower:
                return Scale.BILLIONS

    return default_scale


def _extract_title(table_node) -> Optional[str]:
    """Extract title from table headers."""
    if not table_node.headers:
        return None

    for cell in table_node.headers[0]:
        content = cell.content.strip()
        if content and len(content) > 10:
            if not any(x in content.lower() for x in ['in millions', 'in thousands', 'unaudited']):
                return content[:80]

    return None


def _extract_date_headers_from_rows(table_node) -> List[str]:
    """
    Extract date column headers from early data rows.

    Some tables don't use <thead> - dates appear in regular rows.
    This scans the first several rows looking for date patterns without
    numeric data values. Extended range (8 rows) handles tables with
    title/subtitle rows before the actual headers.

    Also handles split date rows where month/day is on one row and
    year is on the next (e.g., Nvidia's "October 26," + "2025").
    """
    # Month pattern for detecting partial dates (month + day, no year)
    month_pattern = re.compile(
        r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+',
        re.IGNORECASE
    )

    rows = table_node.rows[:10]  # Scan first 10 rows

    for i, row in enumerate(rows):
        cells = row.cells
        non_empty = [c.content.strip() for c in cells if c.content.strip()]

        if not non_empty:
            continue

        # Check if this row contains dates but no numeric values
        dates_found = []
        partial_dates = []
        has_numeric = False

        for content in non_empty:
            # Skip scale descriptions
            if content.startswith("(In ") or content.startswith("(Dollars"):
                continue

            # Check for complete date pattern (contains year)
            if _YEAR_PATTERN.search(content):
                dates_found.append(content)
            # Check for partial date pattern (month + day, no year)
            elif month_pattern.match(content):
                partial_dates.append(content)
            # Check for numeric values (actual data, not headers)
            elif _is_numeric_or_currency(content) and content not in ('$', '—', '-', '–'):
                has_numeric = True
                break

        # If we found complete dates without numeric data, use them
        if dates_found and not has_numeric:
            return dates_found

        # If we found partial dates, check if next row has years to combine
        if partial_dates and not has_numeric and i + 1 < len(rows):
            next_row = rows[i + 1]
            next_non_empty = [c.content.strip() for c in next_row.cells if c.content.strip()]

            # Check if next row contains only years (4-digit numbers starting with 19 or 20)
            years = [c for c in next_non_empty if re.match(r'^(19|20)\d{2}$', c)]

            if years and len(years) == len(partial_dates):
                # Combine partial dates with years
                combined = [f"{date} {year}" for date, year in zip(partial_dates, years)]
                return combined

    return []


def _extract_clean_dataframe(table_node) -> pd.DataFrame:
    """
    Extract a clean DataFrame from a TableNode using Cell metadata.

    Handles:
    - Collapsing empty spacer cells (colspan=3 patterns)
    - Merging $ symbols with adjacent numbers
    - Building proper column headers from multi-row headers
    - Detecting date headers from early data rows (no <thead>)
    """
    header_cols = _extract_header_columns(table_node)

    # Fallback: try to extract date headers from early data rows
    date_headers_from_rows = []
    if not header_cols:
        date_headers_from_rows = _extract_date_headers_from_rows(table_node)

    row_labels = []
    row_data = []

    # Track if we should skip date-header rows from data
    skip_date_rows = bool(date_headers_from_rows)

    for row in table_node.rows:
        cells = row.cells
        non_empty = [c for c in cells if c.content.strip()]
        if not non_empty:
            continue

        # Skip rows that only contain dates (already used as headers)
        if skip_date_rows:
            non_empty_contents = [c.content.strip() for c in cells if c.content.strip()]

            # Pattern for partial dates (month + day)
            month_pattern = re.compile(
                r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+',
                re.IGNORECASE
            )
            # Pattern for year-only cells
            year_only_pattern = re.compile(r'^(19|20)\d{2}$')

            is_date_only_row = (
                all(
                    _YEAR_PATTERN.search(c) or
                    month_pattern.match(c) or
                    year_only_pattern.match(c) or
                    c.startswith("(In ") or
                    c.startswith("(Dollars")
                    for c in non_empty_contents
                )
                and any(
                    _YEAR_PATTERN.search(c) or month_pattern.match(c) or year_only_pattern.match(c)
                    for c in non_empty_contents
                )
            )
            if is_date_only_row:
                continue

        label_cell = None
        data_cells = []

        for cell in cells:
            content = cell.content.strip()
            if not content:
                continue

            if label_cell is None and not _is_numeric_or_currency(content):
                label_cell = content
            else:
                data_cells.append(content)

        if label_cell and data_cells:
            row_labels.append(label_cell)
            merged_data = _merge_currency_symbols(data_cells)
            row_data.append(merged_data)

    if not row_data:
        return pd.DataFrame()

    num_cols = len(header_cols) if header_cols else max(len(r) for r in row_data)

    padded_data = []
    for row in row_data:
        if len(row) < num_cols:
            row = row + [None] * (num_cols - len(row))
        elif len(row) > num_cols:
            row = row[:num_cols]
        padded_data.append(row)

    if header_cols:
        columns = [c.full_header for c in header_cols][:num_cols]
    elif date_headers_from_rows:
        # Use dates extracted from early data rows
        columns = date_headers_from_rows[:num_cols]
        # Pad with Col_N if we need more columns
        while len(columns) < num_cols:
            columns.append(f"Col_{len(columns)}")
    else:
        columns = [f"Col_{i}" for i in range(num_cols)]

    if padded_data and len(columns) < len(padded_data[0]):
        columns.extend([f"Col_{i}" for i in range(len(columns), len(padded_data[0]))])

    df = pd.DataFrame(padded_data, columns=columns[:len(padded_data[0])] if padded_data else columns)

    if row_labels and len(row_labels) >= len(df):
        df.index = row_labels[:len(df)]
        df.index.name = "Item"

    # Ensure object dtype so mixed types (str, float, None) can coexist after conversion.
    # Without this, pandas StringDtype columns reject non-string values on assignment.
    df = df.astype(object)

    # Convert numeric columns (using positional indexing to handle duplicate column names)
    for i, col in enumerate(df.columns):
        df.iloc[:, i] = df.iloc[:, i].apply(_parse_numeric)

    return df


def _extract_header_columns(table_node) -> List[_CleanColumn]:
    """Extract logical column structure from headers."""
    columns = []

    if not table_node.headers:
        return columns

    # For single header row, extract date columns directly
    if len(table_node.headers) == 1:
        for cell in table_node.headers[0]:
            content = cell.content.strip()
            # Skip scale/unit descriptions and empty cells
            if content and not content.startswith("(In ") and not content.startswith("(Dollars"):
                # Check if it looks like a date (contains year pattern)
                if _YEAR_PATTERN.search(content):
                    columns.append(_CleanColumn(header=content))
        return columns

    # For multi-row headers, use parent/child logic
    parent_headers = {}
    col_pos = 0
    for cell in table_node.headers[0]:
        content = cell.content.strip()
        if content:
            for i in range(cell.colspan):
                parent_headers[col_pos + i] = content
        col_pos += cell.colspan

    if len(table_node.headers) >= 2:
        col_pos = 0
        for cell in table_node.headers[1]:
            content = cell.content.strip()
            if content and not content.startswith("(In ") and not content.startswith("(Dollars"):
                parent = parent_headers.get(col_pos, None)
                columns.append(_CleanColumn(header=content, parent_header=parent))
            col_pos += cell.colspan

    return columns


def _is_numeric_or_currency(s: str) -> bool:
    """Check if string is a number or currency symbol."""
    s = s.strip()
    if s in ('$', '—', '-', '–', '%', '(', ')'):
        return True
    cleaned = s.replace(',', '').replace('$', '').replace('(', '').replace(')', '').replace('%', '').replace('*', '')
    if not cleaned:
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _merge_currency_symbols(cells: List[str]) -> List[str]:
    """
    Merge standalone currency symbols and parentheses with adjacent numbers.

    Handles:
    - ['$', '100'] -> ['$100']
    - ['$', '$', '100'] -> ['$', '$100'] (consecutive $ handled)
    - ['100', '$'] -> ['100', '$'] (trailing $ kept as-is)
    - ['(', '0.09', ')'] -> ['(0.09)']
    - ['$', '(', '0.09', ')'] -> ['$(0.09)']
    """
    if not cells:
        return []

    # Pass 1: merge currency symbols with following cell
    merged = []
    i = 0
    while i < len(cells):
        cell = cells[i].strip()
        # Check if this is a currency symbol that should be merged
        if cell in ('$', '€', '£', '¥') and i + 1 < len(cells):
            next_cell = cells[i + 1].strip()
            # Only merge if next cell is not also a currency symbol
            if next_cell and next_cell not in ('$', '€', '£', '¥'):
                merged.append(f"{cell}{next_cell}")
                i += 2
                continue
        merged.append(cell)
        i += 1

    # Pass 2: merge parentheses with adjacent numbers
    # e.g. ['(', '0.09', ')'] -> ['(0.09)']
    # e.g. ['$(', '0.09', ')'] -> ['$(0.09)']
    result = []
    i = 0
    while i < len(merged):
        cell = merged[i].strip()
        # Check for opening paren (standalone or trailing on currency like '$(')
        if cell.endswith('(') and i + 1 < len(merged):
            # Collect the number and optional closing paren
            prefix = cell  # e.g. '(' or '$('
            num = merged[i + 1].strip()
            if i + 2 < len(merged) and merged[i + 2].strip() == ')':
                result.append(f"{prefix}{num})")
                i += 3
            else:
                result.append(f"{prefix}{num}")
                i += 2
        else:
            result.append(cell)
            i += 1
    return result


def _parse_numeric(val) -> Union[float, str, None]:
    """
    Parse a string value to numeric.

    Returns:
        float if parseable, original string if not numeric, None if empty/null
    """
    # Handle Series/array values (shouldn't happen but be defensive)
    if isinstance(val, (pd.Series, pd.DataFrame)):
        return None

    # Use try/except for pd.isna to handle edge cases
    try:
        if val is None or (pd.api.types.is_scalar(val) and pd.isna(val)):
            return None
    except (ValueError, TypeError):
        pass

    s = str(val).strip()
    if s in ('—', '-', '–', '', '*'):
        return None

    s_for_sign_check = s.replace('$', '').replace('€', '').replace('£', '').replace('¥', '').strip()
    negative = s_for_sign_check.startswith('(') or s_for_sign_check.endswith(')')
    cleaned = s.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('(', '').replace(')', '').replace('%', '').replace('*', '').strip()

    try:
        num = float(cleaned)
        return -num if negative else num
    except ValueError:
        # Return original string for non-numeric values (e.g., "N/A", "n/m")
        return s
