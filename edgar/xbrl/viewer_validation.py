"""
Cross-validation between the SEC Viewer (R*.htm) and XBRL parser output.

Compares values from the SEC's pre-rendered viewer reports against the
edgartools XBRL parser to detect discrepancies. The viewer is treated as
ground truth since it reflects the SEC's authoritative rendering.

Usage:
    from edgar.xbrl.viewer_validation import compare_viewer_to_xbrl

    viewer = filing.viewer
    xbrl = filing.xbrl()
    results = compare_viewer_to_xbrl(viewer, xbrl)
    results.match_rate          # 0.97
    results.mismatches          # [ComparisonResult(...), ...]
    results.to_dataframe()      # Full results as DataFrame
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

from edgar.sgml.concept_extractor import parse_numeric

if TYPE_CHECKING:
    from edgar.xbrl.viewer import FilingViewer
    from edgar.xbrl.xbrl import XBRL

__all__ = ['compare_viewer_to_xbrl', 'ComparisonResult', 'ComparisonResults']

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

_DATE_RE = re.compile(
    r'(?:(\d+)\s+(?:Months?|Years?)\s+Ended\s+)?'
    r'([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})'
)


def _parse_viewer_period(header: str) -> Optional[dict]:
    """
    Parse a structured period header into components.

    Examples:
        "Mar. 29, 2025"                 -> {end: '2025-03-29', duration_hint: None}
        "3 Months Ended Mar. 29, 2025"  -> {end: '2025-03-29', duration_hint: 90}
        "6 Months Ended Mar. 29, 2025"  -> {end: '2025-03-29', duration_hint: 180}
    """
    match = _DATE_RE.match(header)
    if not match:
        return None
    duration_num, month_str, day_str, year_str = match.groups()
    month_key = month_str[:3].lower()
    month = _MONTH_MAP.get(month_key)
    if not month:
        return None
    try:
        end_date = datetime(int(year_str), month, int(day_str)).strftime('%Y-%m-%d')
    except ValueError:
        return None

    duration_hint = None
    if duration_num:
        n = int(duration_num)
        if 'year' in header.lower():
            duration_hint = n * 365
        else:
            duration_hint = n * 30  # approximate

    return {'end': end_date, 'duration_hint': duration_hint}


def _normalize_concept_id(viewer_id: str) -> str:
    """
    Normalize viewer concept ID for XBRL fact lookup.

    Viewer uses underscore: us-gaap_Assets
    XBRL facts use colon:   us-gaap:Assets
    """
    parts = viewer_id.split('_', 1)
    if len(parts) == 2:
        return f"{parts[0]}:{parts[1]}"
    return viewer_id


def _match_xbrl_period(end_date: str, duration_hint: Optional[int],
                       xbrl_columns: List[str]) -> Optional[str]:
    """
    Find the XBRL DataFrame column matching a viewer period.

    XBRL DataFrame columns may be:
        - Just end dates: "2025-12-27" (most common — used for both instant and duration)
        - Full duration keys: "2024-09-28_2025-12-27" (less common)

    Since the XBRL parser typically uses just end dates as column names,
    we first try a direct end-date match, then fall back to duration keys.
    """
    # Direct end-date match (most common case)
    if end_date in xbrl_columns:
        return end_date

    # Try full duration columns (start_end format)
    candidates = []
    for col in xbrl_columns:
        if '_' in col and col.count('-') >= 4:
            parts = col.split('_')
            if len(parts) == 2:
                col_start, col_end = parts
                if col_end == end_date:
                    try:
                        start_dt = datetime.strptime(col_start, '%Y-%m-%d')
                        end_dt = datetime.strptime(col_end, '%Y-%m-%d')
                        days = (end_dt - start_dt).days
                        candidates.append((col, days))
                    except ValueError:
                        continue

    if candidates and duration_hint is not None:
        candidates.sort(key=lambda x: abs(x[1] - duration_hint))
        return candidates[0][0]
    elif candidates:
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    return None


def _lookup_xbrl_value(concept: str, period_info: dict,
                       period_end_dates: Dict[str, List[str]],
                       xbrl_lookup: Dict[tuple, float]) -> Optional[float]:
    """
    Find the XBRL fact value matching a viewer concept+period.

    Uses full period keys (duration_start_end or instant_date) for precise matching,
    selecting the period whose duration best matches the viewer's duration hint.
    """
    end_date = period_info['end']
    duration_hint = period_info['duration_hint']

    period_keys = period_end_dates.get(end_date, [])
    if not period_keys:
        return None

    if duration_hint is None:
        # Instant period — try instant key first
        instant_key = f'instant_{end_date}'
        val = xbrl_lookup.get((concept, instant_key))
        if val is not None:
            return val
        # Fall back to shortest duration
        candidates = []
        for pk in period_keys:
            val = xbrl_lookup.get((concept, pk))
            if val is not None:
                if pk.startswith('duration_'):
                    parts = pk.replace('duration_', '').split('_')
                    if len(parts) == 2:
                        try:
                            days = (datetime.strptime(parts[1], '%Y-%m-%d') -
                                    datetime.strptime(parts[0], '%Y-%m-%d')).days
                            candidates.append((pk, days, val))
                        except ValueError:
                            continue
                else:
                    return val
        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][2]
        return None

    # Duration period — find the period key closest to the hint
    candidates = []
    for pk in period_keys:
        val = xbrl_lookup.get((concept, pk))
        if val is None:
            continue
        if pk.startswith('duration_'):
            parts = pk.replace('duration_', '').split('_')
            if len(parts) == 2:
                try:
                    days = (datetime.strptime(parts[1], '%Y-%m-%d') -
                            datetime.strptime(parts[0], '%Y-%m-%d')).days
                    candidates.append((pk, days, val))
                except ValueError:
                    continue

    if not candidates:
        return None

    # Pick the candidate closest to the duration hint
    candidates.sort(key=lambda x: abs(x[1] - duration_hint))
    return candidates[0][2]


@dataclass
class ComparisonResult:
    """Result of comparing one concept+period between viewer and XBRL."""
    concept_id: str
    label: str
    period: str
    viewer_value: float
    xbrl_value: Optional[float]
    difference: Optional[float]
    match: bool
    report: str


@dataclass
class ComparisonResults:
    """Aggregate comparison results between viewer and XBRL."""
    results: List[ComparisonResult] = field(default_factory=list)
    scaling_factor: int = 1

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def matched(self) -> int:
        return sum(1 for r in self.results if r.match)

    @property
    def mismatched(self) -> int:
        return sum(1 for r in self.results if not r.match and r.xbrl_value is not None)

    @property
    def missing(self) -> int:
        """Concepts in viewer not found in XBRL."""
        return sum(1 for r in self.results if r.xbrl_value is None)

    @property
    def match_rate(self) -> float:
        compared = self.total - self.missing
        if compared == 0:
            return 0.0
        return self.matched / compared

    @property
    def mismatches(self) -> List[ComparisonResult]:
        return [r for r in self.results if not r.match and r.xbrl_value is not None]

    def to_dataframe(self):
        """Export results as a pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame([
            {
                'concept_id': r.concept_id,
                'label': r.label,
                'period': r.period,
                'viewer_value': r.viewer_value,
                'xbrl_value': r.xbrl_value,
                'difference': r.difference,
                'match': r.match,
                'report': r.report,
            }
            for r in self.results
        ])

    def __rich__(self):
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        summary = Text()
        summary.append(f"Compared: {self.total}  ", style="dim")
        summary.append(f"Matched: {self.matched}  ", style="green")
        if self.mismatched:
            summary.append(f"Mismatched: {self.mismatched}  ", style="red")
        if self.missing:
            summary.append(f"Missing: {self.missing}  ", style="yellow")
        summary.append(f"Match rate: {self.match_rate:.1%}", style="bold")

        parts = [summary]

        if self.mismatches:
            table = Table(show_header=True, header_style="dim", padding=(0, 1))
            table.add_column("Concept", width=35)
            table.add_column("Period", width=28)
            table.add_column("Viewer", justify="right", width=12)
            table.add_column("XBRL", justify="right", width=12)
            table.add_column("Diff", justify="right", width=10)
            for r in self.mismatches[:15]:
                table.add_row(
                    r.label[:35],
                    r.period[:28],
                    f"{r.viewer_value:,.0f}",
                    f"{r.xbrl_value:,.0f}" if r.xbrl_value is not None else "—",
                    f"{r.difference:,.0f}" if r.difference is not None else "—",
                )
            parts.append(table)

        return Panel(Group(*parts), title="[bold]Viewer vs XBRL[/bold]", expand=False, width=105)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"ComparisonResults(total={self.total}, matched={self.matched}, mismatched={self.mismatched}, rate={self.match_rate:.1%})"


def compare_viewer_to_xbrl(viewer: 'FilingViewer', xbrl: 'XBRL',
                           tolerance: float = 1.0) -> ComparisonResults:
    """
    Compare viewer (R*.htm) values against XBRL parser output.

    For each concept in the viewer's financial statements, looks up the
    same concept and period in the XBRL data and checks if values match.

    The viewer value is scaled by the report's currency_scaling before
    comparison (e.g., viewer shows 95,359 in millions -> compared against
    XBRL raw value of 95,359,000,000).

    Args:
        viewer: FilingViewer with parsed R*.htm data
        xbrl: XBRL object from filing.xbrl()
        tolerance: Maximum allowed difference in display units (default 1.0,
                   meaning ±$1M for filings reported in millions)

    Returns:
        ComparisonResults with per-concept match/mismatch details
    """
    results = ComparisonResults()

    # Build XBRL lookup from raw facts — this gives us full period keys
    # (duration_start_end) rather than the DataFrame's collapsed end-date columns.
    # Only include non-dimensional facts for comparison against viewer totals.
    xbrl_lookup: Dict[tuple, float] = {}
    all_period_end_dates: Dict[str, List[str]] = {}  # end_date -> [period_keys]

    facts_df = xbrl.facts.to_dataframe()
    if facts_df is not None and not facts_df.empty:
        for _, row in facts_df.iterrows():
            concept = row.get('concept', '')
            period_key = row.get('period_key', '')
            val = row.get('value')
            # Skip dimensional facts — only compare totals
            if row.get('is_dimensioned', False):
                continue
            if not concept or not period_key or val is None:
                continue
            try:
                fval = float(val)
                if fval != fval:  # NaN check
                    continue
            except (ValueError, TypeError):
                continue
            # Store fact — last occurrence wins (non-dimensional total)
            xbrl_lookup[(concept, period_key)] = fval
            # Index by end date for period matching
            if period_key.startswith('duration_'):
                parts = period_key.replace('duration_', '').split('_')
                if len(parts) == 2:
                    end_date = parts[1]
                    if end_date not in all_period_end_dates:
                        all_period_end_dates[end_date] = []
                    if period_key not in all_period_end_dates[end_date]:
                        all_period_end_dates[end_date].append(period_key)
            elif period_key.startswith('instant_'):
                end_date = period_key.replace('instant_', '')
                if end_date not in all_period_end_dates:
                    all_period_end_dates[end_date] = []
                if period_key not in all_period_end_dates[end_date]:
                    all_period_end_dates[end_date].append(period_key)

    # Build tag type lookup from MetaLinks for unit-aware scaling
    metalinks = viewer._metalinks

    # Compare viewer financial statements against XBRL.
    # Only compare the FIRST occurrence of each concept per report — subsequent
    # occurrences are dimensional breakdowns (Products, Services, etc.) that
    # appear under rh headers but have the same concept ID as the total.
    for vr in viewer.financial_statements:
        cr = vr.concept_report
        if not cr:
            continue

        currency_scaling = cr.currency_scaling
        shares_scaling = cr.shares_scaling
        results.scaling_factor = currency_scaling
        seen_concepts_in_report = set()

        for crow in cr.rows:
            if crow.is_abstract or crow.is_dimensional or crow.is_header:
                continue
            if not crow.values:
                continue
            # Skip dimensional repeats — only compare the first (total) occurrence
            if crow.concept_id in seen_concepts_in_report:
                continue
            seen_concepts_in_report.add(crow.concept_id)

            xbrl_concept = _normalize_concept_id(crow.concept_id)

            # Determine scaling based on concept type
            tag = metalinks.get_tag(crow.concept_id)
            xbrltype = tag.xbrltype if tag else ''
            if 'perShareItemType' in xbrltype or 'pureItemType' in xbrltype:
                scaling = 1  # EPS, ratios — not scaled
            elif 'sharesItemType' in xbrltype:
                scaling = shares_scaling  # Share counts
            elif 'percentItemType' in xbrltype:
                scaling = 1  # Percentages — display value is the value
            else:
                scaling = currency_scaling  # Monetary values

            for period_header, display_val in crow.values.items():
                viewer_num = parse_numeric(display_val)
                if viewer_num is None:
                    continue

                period_info = _parse_viewer_period(period_header)
                if not period_info:
                    continue

                # Match viewer period to XBRL period key
                xbrl_val = _lookup_xbrl_value(
                    xbrl_concept, period_info, all_period_end_dates, xbrl_lookup
                )

                if xbrl_val is not None:
                    # Compare in display units (divide XBRL by scaling)
                    xbrl_display = xbrl_val / scaling if scaling else xbrl_val
                    diff = viewer_num - xbrl_display
                    # Match if values agree, OR if magnitudes match but signs differ
                    # (sign differences are presentation-layer, not data errors)
                    is_match = (abs(diff) <= tolerance or
                                abs(abs(viewer_num) - abs(xbrl_display)) <= tolerance)
                else:
                    xbrl_display = None
                    diff = None
                    is_match = False

                results.results.append(ComparisonResult(
                    concept_id=xbrl_concept,
                    label=crow.label,
                    period=period_header,
                    viewer_value=viewer_num,
                    xbrl_value=xbrl_display,
                    difference=diff,
                    match=is_match,
                    report=vr.short_name,
                ))

    return results
