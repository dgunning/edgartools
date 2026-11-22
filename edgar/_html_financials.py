"""Conservative, income-statement-only fallback for untagged 6-K exhibits.

Reuse the earnings parser; do not fabricate an XBRL object or infer missing
statements, currencies, or quarterly periods from the filing date.
"""
import json
import re
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from numbers import Real
from typing import TYPE_CHECKING, Optional

import pandas as pd

from edgar.earnings import (
    EarningsRelease,
    FinancialTable,
    RowType,
    _currency,
    _declared_table_units,
    _is_change_column,
    _names_currency,
    _parse_period_header,
    _table_context,
    find_earnings_exhibits,
)
from edgar.exceptions import ValidationError
from edgar.xbrl.presentation import ViewType, normalize_view

if TYPE_CHECKING:
    from edgar._filings import Filing


_REVENUE = ('total revenue', 'total revenues', 'net sales', 'net revenue', 'revenue', 'revenues')
_NET_INCOME = ('net income attributable to owners of the parent',
               'net income attributable to shareholders of the parent',
               'net income', 'net income (loss)', 'net loss', 'net earnings')
# These are existing standard concept identifiers, not invented source tags.
# Exact labels only: generic "Net income" does not establish parent attribution,
# and generic "EPS" does not establish basic versus diluted earnings per share.
_STANDARD_CONCEPTS = {
    **dict.fromkeys(_REVENUE, 'Revenue'),
    'gross profit': 'GrossProfit',
    'gross profit (loss)': 'GrossProfit',
    'income from operations': 'OperatingIncomeLoss',
    'operating income': 'OperatingIncomeLoss',
    'operating loss': 'OperatingIncomeLoss',
    'income before tax': 'PretaxIncomeLoss',
    'income before taxes': 'PretaxIncomeLoss',
    'net income attributable to owners of the parent': 'NetIncome',
    'net income attributable to shareholders of the parent': 'NetIncome',
    'profit (loss)': 'ProfitLoss',
}
_XBRL_METADATA = (
    'level', 'abstract', 'dimension', 'is_breakdown', 'dimension_axis',
    'dimension_member', 'dimension_member_label', 'dimension_label', 'balance',
    'weight', 'preferred_sign', 'parent_concept', 'parent_abstract_concept',
)


def _normalize_label(label):
    return ' '.join(str(label).lower().split())


def _standard_concept(label, row_type):
    label = _normalize_label(label)
    if row_type == RowType.PER_SHARE:
        # Do not use an unqualified EPS row or prose elsewhere to guess a type.
        match = re.fullmatch(r'(basic|diluted) (?:eps|(?:earnings|loss|earnings \(loss\)) per share)'
                             r'(?:\s*\((?:nt\$|us\$|hk\$|twd|usd|eur|cny|rmb|jpy|€|¥)\))?', label)
        if match:
            return {'basic': 'EarningsPerShareBasic', 'diluted': 'EarningsPerShareDiluted'}[match[1]]
        return None
    if row_type == RowType.AMOUNT:
        return _STANDARD_CONCEPTS.get(label)
    return None


def _unsupported_view(view):
    if view is not None:
        normalize_view(view)  # Preserve the public API's invalid-view diagnostics.
        raise NotImplementedError('view requires XBRL dimensions; HTML income tables have no dimensional views')


def _row_unit(label, row_type, reporting_currency):
    if row_type not in (RowType.AMOUNT, RowType.PER_SHARE):
        return {RowType.SHARES: 'shares', RowType.PERCENTAGE: 'percent'}.get(row_type)
    code = _currency(label)
    if code is None:
        if _names_currency(label) or re.search(r'\((?:[A-Z]{3}|\$)\)', label):
            return None
        code = reporting_currency
    currency = code.lower()
    return f'{currency}PerShare' if row_type == RowType.PER_SHARE else currency


def _quarter(header, filing_year, fiscal_year_end='1231'):
    if _is_change_column(header) or re.search(r'\b(?:YTD|TTM|FY|annual|year.to.date)\b', header, re.I):
        return None
    info = _parse_period_header(header)
    if info['duration_months'] == 3:
        end = info['period_end']
        # The same fiscal quarter must have one key regardless of header style.
        # This is an identity/sort key, never a fabricated source date.
        fiscal_month = int(fiscal_year_end[:2])
        quarter = ((end.month - fiscal_month - 1) % 12) // 3 + 1
        year = end.year + (end.month > fiscal_month)
        return year, quarter
    if info['duration_months'] is not None:
        return None
    # Compact fiscal-quarter labels need not imply calendar-quarter dates.
    match = re.search(r'\b(?:([1-4])Q\s*(\d{4}|\d{2})|Q([1-4])\s*(\d{4}|\d{2}))\b', header, re.I)
    if match:
        quarter, year = int(match[1] or match[3]), match[2] or match[4]
        year = int(year) if len(year) == 4 else filing_year // 100 * 100 + int(year)
        if year > filing_year + 1:
            year -= 100
        return year, quarter
    return None


@dataclass
class QuarterlyIncome(FinancialTable):
    """Reported quarterly income table from a 6-K exhibit, with its source and units.

    to_dataframe() returns actual currency amounts. period_offset in the income
    getters selects a reported comparison column, starting with the most recent.
    """

    source_filing: Optional['Filing'] = None
    source_url: str = ''
    notes: tuple = field(default_factory=tuple)

    def __post_init__(self):
        self.dataframe = self.dataframe.copy()
        # An explicit loss label carries the sign when a release prints a
        # positive magnitude. Already-negative values must not flip twice.
        for i, label in enumerate(self.dataframe.index):
            if _normalize_label(label) not in ('net loss', 'operating loss'):
                continue
            for j in range(len(self.dataframe.columns)):
                value = self.dataframe.iloc[i, j]
                if isinstance(value, Real) and pd.notna(value) and value > 0:
                    self.dataframe.iloc[i, j] = -value

    def to_dataframe(self,
                     period_filter: Optional[str] = None,
                     period_view: Optional[str] = None,
                     standard: bool = True,
                     view: ViewType = None,
                     *,
                     include_unit: bool = False,
                     include_point_in_time: bool = False,
                     include_standardization: bool = False,
                     presentation: bool = True,
                     matrix: bool = False) -> pd.DataFrame:
        """Statement-compatible columns with honest HTML provenance.

        Amounts use actual currency units and EPS stays unscaled. Source XBRL
        concepts and linkbase metadata are null. ``standard`` adds conservative
        exact-label mappings without changing labels; the deprecated
        ``include_standardization`` flag does not override it, as in Statement.
        ``period_filter`` selects an exact source column from ``periods``.
        XBRL period/dimensional views, raw-instance signs and equity matrices
        are unavailable and raise rather than being silently ignored.
        """
        for name, value in (('standard', standard), ('include_unit', include_unit),
                            ('include_point_in_time', include_point_in_time),
                            ('include_standardization', include_standardization),
                            ('presentation', presentation), ('matrix', matrix)):
            if not isinstance(value, bool):
                raise ValidationError(f'{name} must be a boolean', parameter=name, invalid_value=value)
        _unsupported_view(view)
        if period_view is not None:
            if not isinstance(period_view, str):
                raise ValidationError('period_view must be a string', parameter='period_view', invalid_value=period_view)
            raise NotImplementedError('period_view requires XBRL periods; use period_filter with a source column')
        if not presentation:
            raise NotImplementedError('presentation=False requires raw XBRL signs; HTML preserves reported signs')
        if matrix:
            raise NotImplementedError('matrix=True is unavailable for HTML income tables')

        columns = list(self.periods)
        if period_filter is not None:
            if not isinstance(period_filter, str) or period_filter not in columns:
                raise ValidationError(f'period_filter must be one of the reported columns: {columns}',
                                      parameter='period_filter', invalid_value=period_filter)
            columns = [period_filter]
        frame = self.scaled_dataframe.loc[:, columns].reset_index(names='label')
        row_types = [self.get_row_type(str(label), pos) for pos, label in enumerate(frame['label'])]
        frame.insert(0, 'concept', None)
        frame.insert(2, 'standard_concept', [
            _standard_concept(label, row_type) if standard else None
            for label, row_type in zip(frame['label'], row_types, strict=True)
        ])
        if include_unit:
            frame['unit'] = [_row_unit(str(label), row_type, self.currency)
                             for label, row_type in zip(frame['label'], row_types, strict=True)]
        if include_point_in_time:
            frame['point_in_time'] = False  # Explicit quarterly durations, never instants.
        for name in _XBRL_METADATA:
            frame[name] = None
        frame.attrs.update(source='HTML', currency=self.currency, reported_scale=self.scale.value,
                           source_url=self.source_url, notes=self.notes, period_columns=columns,
                           standardization_source='HTML exact labels' if standard else None)
        return frame

    def to_json(self, include_metadata=True):
        result = json.loads(super().to_json(include_metadata=include_metadata))
        if include_metadata:
            result['metadata'].update(source='HTML', currency=self.currency,
                                      source_url=self.source_url, notes=self.notes)
        return json.dumps(result, indent=2, default=str)

    def to_facts_dataframe(self):
        raise NotImplementedError('HTML financials do not synthesize XBRL facts; use to_dataframe()')

    def __rich__(self):
        from rich.console import Group
        from rich.text import Text
        return Group(Text(f'HTML income statement | {self.currency} {self.scale} | {self.source_url}'),
                     super().__rich__(), *(Text(note) for note in self.notes))

    def _value(self, labels, period_offset):
        if isinstance(period_offset, bool) or not isinstance(period_offset, int) or period_offset < 0:
            raise ValidationError('period_offset must be a non-negative integer',
                                  parameter='period_offset', invalid_value=period_offset)
        if period_offset >= len(self.periods):
            return None
        frame = self.dataframe
        for label in labels:
            positions = [i for i, name in enumerate(frame.index) if _normalize_label(name) == label]
            if len(positions) == 1:
                value = frame.iloc[positions[0], period_offset]
                if isinstance(value, Real) and pd.notna(value):
                    return value * self.scale.value
        return None

    def get_revenue(self, period_offset=0):
        return self._value(_REVENUE, period_offset)

    def get_net_income(self, period_offset=0):
        return self._value(_NET_INCOME, period_offset)

    def get_operating_income(self, period_offset=0):
        return self._value(('income from operations', 'operating income', 'operating loss'), period_offset)

    def get_gross_profit(self, period_offset=0):
        return self._value(('gross profit', 'gross profit (loss)'), period_offset)


def _quarter_column_positions(table, filing_year, fiscal_year_end=None):
    """Keep unique quarterly amount columns, newest comparison first."""
    headers = [str(col) for col in table.dataframe.columns]
    compact = any(re.search(r'\b(?:[1-4]Q|Q[1-4])\s*\d{2,4}\b', h, re.I) for h in headers)
    dated = any(_parse_period_header(h)['duration_months'] == 3 for h in headers)
    if compact and dated and fiscal_year_end is None:
        return []  # Compact fiscal labels cannot establish calendar identity alone.
    if fiscal_year_end is not None and (
        not isinstance(fiscal_year_end, str)
        or not re.fullmatch(r'(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])', fiscal_year_end)
    ):
        return []
    if fiscal_year_end is not None:
        month, day = int(fiscal_year_end[:2]), int(fiscal_year_end[2:])
        if day > monthrange(filing_year, month)[1]:
            return []
    columns = {}
    for i, header in enumerate(headers):
        key = _quarter(header, filing_year, fiscal_year_end or '1231')
        if key is None:
            continue
        if key in columns:
            if not table.dataframe.iloc[:, columns[key]].equals(table.dataframe.iloc[:, i]):
                return []  # Conflicting amounts/currencies/segments, never pick arbitrarily.
        else:
            columns[key] = i
    return [columns[key] for key in sorted(columns, reverse=True)]


def _has_income_totals(table):
    labels = {_normalize_label(label) for label in table.dataframe.index}
    if not labels.intersection(_REVENUE) or not labels.intersection(_NET_INCOME):
        return False
    # A grouped/NCI table needs explicit parent attribution; do not return
    # consolidated income as the owners' income via a loose label match.
    has_nci = any('noncontrolling' in label or 'non-controlling' in label for label in labels)
    return not has_nci or bool(labels.intersection(_NET_INCOME[:2]))


def _extract_6k_income_statement(filing, *, exhibits=None, fiscal_year_end=None) -> Optional[QuarterlyIncome]:
    """Return only an explicitly quarterly, currency-qualified income table.

    Absence is None; downloads and parser failures are not hidden. EX-99 exhibits
    are discovered from filing attachments, never guessed from document names.
    """
    if filing.form != '6-K':
        return None
    filing_year = int(str(filing.filing_date)[:4])
    for attachment in (find_earnings_exhibits(filing.attachments) if exhibits is None else exhibits):
        release = EarningsRelease(attachment)
        if release.document is None:
            continue
        table = release.income_statement
        if table is None:
            continue
        positions = _quarter_column_positions(table, filing_year, fiscal_year_end)
        if not positions or not _has_income_totals(table):
            continue
        nodes = release.document.tables
        if not 0 <= table.raw_index < len(nodes):
            continue
        context, notes = _table_context(nodes[table.raw_index], table.title)
        units = _declared_table_units(context)
        if units is None:
            continue
        declaration, currency, scale = units
        # FinancialTable supports a default USD display. A filing-level income
        # result requires explicit units and consistent table-local currency.
        if scale is None or _currency(declaration) is None or table.currency != currency:
            continue
        frame = table.dataframe.iloc[:, positions].copy()
        row_types = list(table.row_types)
        source_url = attachment.url
        result = QuarterlyIncome(
            dataframe=frame, scale=scale, title=table.title,
            statement_type=table.statement_type, periods=list(frame.columns),
            raw_index=table.raw_index, row_types=row_types, currency=currency,
            source_filing=filing, source_url=source_url, notes=tuple([declaration, *notes]),
        )
        if result.get_revenue() is not None and result.get_net_income() is not None:
            return result
    return None


def _latest_candidates(filings, limit):
    """Try the newest filing first. Sort a larger window only on a miss."""
    newest = filings.latest()
    if newest is None:
        return
    yield newest
    if limit > 1:
        recent = filings.latest(limit)
        # EntityFilings.latest returns a single filing for a one-element result.
        if recent is not None and not hasattr(recent, 'accession_no'):
            yield from (filing for filing in recent if filing.accession_no != newest.accession_no)


def _recent_quarterly_income(filings, limit, fiscal_year_end):
    from edgar.financials import Financials

    today = date.today()
    cutoff = today - timedelta(days=183)
    for filing in _latest_candidates(filings, limit):
        filed = getattr(filing, 'filing_date', None)
        if filed is None:
            # Without a date we can still read the newest filing's XBRL, but
            # cannot establish the recency of an HTML fallback search.
            return Financials.extract(filing)
        filed = date.fromisoformat(str(filed))
        if filed < cutoff:
            break
        if filed > today:
            continue
        exhibits = None
        if getattr(filing, 'is_xbrl', None) in (False, 0, '0'):
            homepage = getattr(filing, 'homepage', None)
            attachments = homepage.attachments if homepage is not None else filing.attachments
            exhibits = find_earnings_exhibits(attachments)
            if not exhibits and not getattr(attachments, 'data_files', None):
                continue

        financials = Financials.extract(filing)
        if financials is not None:
            return financials
        income = _extract_6k_income_statement(filing, exhibits=exhibits, fiscal_year_end=fiscal_year_end)
        if income is not None:
            return income
    return None
