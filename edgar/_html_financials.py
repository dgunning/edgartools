"""Conservative, income-statement-only fallback for untagged 6-K exhibits.

Reuse the earnings parser; do not fabricate an XBRL object or infer missing
statements, currencies, or quarterly periods from the filing date.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from edgar.earnings import (
    EarningsRelease,
    FinancialTable,
    RowType,
    Scale,
    _is_change_column,
    _parse_period_header,
    find_earnings_exhibits,
)
from edgar.exceptions import ValidationError
from edgar.financials import Financials
from edgar.xbrl.presentation import ViewType, normalize_view

_REVENUE = ('total revenue', 'total revenues', 'net sales', 'net revenue', 'revenue', 'revenues')
_NET_INCOME = ('net income attributable to owners of the parent',
               'net income attributable to shareholders of the parent',
               'net income', 'net income (loss)', 'net loss', 'net earnings')
_CURRENCIES = {
    'TWD': r'NT\$|\bTWD\b|New Taiwan [Dd]ollars',
    'USD': r'US\$|\bUSD\b|U\.?S\.? [Dd]ollars',
    'EUR': r'€|\bEUR\b|\beuros?\b',
    'CNY': r'\bRMB\b|\bCNY\b|[Rr]enminbi',
    'HKD': r'HK\$|\bHKD\b|Hong Kong [Dd]ollars',
    'JPY': r'\bJPY\b|Japanese [Yy]en',
}
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


def _standard_concept(label, row_type):
    label = ' '.join(str(label).lower().split())
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


def _currency(text):
    matches = [code for code, pattern in _CURRENCIES.items() if re.search(pattern, text, re.I)]
    return matches[0] if len(matches) == 1 else None


def _row_unit(label, row_type, reporting_currency):
    if row_type not in (RowType.AMOUNT, RowType.PER_SHARE):
        return {RowType.SHARES: 'shares', RowType.PERCENTAGE: 'percent'}.get(row_type)
    currencies = [code for code, pattern in _CURRENCIES.items() if re.search(pattern, label, re.I)]
    if len(currencies) > 1 or (not currencies and re.search(r'\((?:[A-Z]{3}|\$)\)', label)):
        return None  # Ambiguous or unsupported explicit row currency.
    currency = (currencies[0] if currencies else reporting_currency).lower()
    return f'{currency}PerShare' if row_type == RowType.PER_SHARE else currency


def _quarter(header, filing_year):
    if _is_change_column(header) or re.search(r'\b(?:YTD|TTM|FY|annual|year.to.date)\b', header, re.I):
        return None
    info = _parse_period_header(header)
    if info['duration_months'] == 3:
        return info['period_end'].toordinal()
    if info['duration_months'] is not None:
        return None
    # Compact fiscal-quarter labels need not imply calendar-quarter dates.
    match = re.search(r'\b(?:([1-4])Q\s*(\d{4}|\d{2})|Q([1-4])\s*(\d{4}|\d{2}))\b', header, re.I)
    if match:
        quarter, year = int(match[1] or match[3]), match[2] or match[4]
        year = int(year) if len(year) == 4 else filing_year // 100 * 100 + int(year)
        if year > filing_year + 1:
            year -= 100
        # Same ordering domain as ordinal dates; only used to sort columns.
        from datetime import date
        return date(year, quarter * 3, 1).toordinal()
    return None


def _table_context(release, table):
    """Read nearby unit declarations and footnotes, not narrative USD amounts."""
    node = release.document.tables[table.raw_index]
    parent = node.parent
    while parent is not None and len(parent.children) == 1 and parent.parent is not None:
        node, parent = parent, parent.parent
    if parent is None:
        return [], []
    position = next(i for i, sibling in enumerate(parent.children) if sibling is node)

    def text(sibling):
        return (sibling.content or sibling.text() or '').strip()

    before = [text(s) for s in parent.children[max(0, position - 3):position]]
    after = [text(s) for s in parent.children[position + 1:position + 5]]
    return [table.title or '', *before], [s for s in after if s]


@dataclass
class _HTMLIncomeStatement(FinancialTable):
    currency: str = ''
    source_url: str = ''
    notes: tuple = field(default_factory=tuple)

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

    def to_context(self, detail='standard'):
        # FinancialTable's general formatter describes dollar amounts as USD.
        # This table has an explicit reporting currency and may instead be TWD.
        return (f'HTML income statement | {self.currency} {self.scale}\n'
                f'Source: {self.source_url}\n' + self.dataframe.to_string()
                + '\n' + '\n'.join(self.notes))

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


class _HTMLFinancials(Financials):
    def __init__(self, filing, statement):
        super().__init__(None)
        self.source_filing = filing
        self.source_url = statement.source_url
        self.currency = statement.currency
        self.notes = statement.notes
        self._income = statement

    def income_statement(self, *, view=None):
        """A FinancialTable with to_dataframe(); no XBRL dimensional views."""
        _unsupported_view(view)
        return self._income

    def _value(self, labels, period_offset):
        if isinstance(period_offset, bool) or not isinstance(period_offset, int) or period_offset < 0:
            raise ValidationError('period_offset must be a non-negative integer',
                                  parameter='period_offset', invalid_value=period_offset)
        if period_offset >= len(self._income.periods):
            return None
        frame = self._income.dataframe
        for label in labels:
            positions = [i for i, name in enumerate(frame.index) if str(name).strip().lower() == label]
            if len(positions) == 1:
                value = frame.iloc[positions[0], period_offset]
                if isinstance(value, (int, float)) and pd.notna(value):
                    return value * self._income.scale.value
        return None

    def get_revenue(self, period_offset=0):
        return self._value(_REVENUE, period_offset)

    def get_net_income(self, period_offset=0):
        return self._value(_NET_INCOME, period_offset)

    def get_operating_income(self, period_offset=0):
        return self._value(('income from operations', 'operating income', 'operating loss'), period_offset)

    def get_gross_profit(self, period_offset=0):
        return self._value(('gross profit', 'gross profit (loss)'), period_offset)

    def get_currency_symbol(self):
        return {'TWD': 'NT$', 'USD': '$', 'EUR': '€', 'CNY': '¥', 'HKD': 'HK$', 'JPY': '¥'}[self.currency]

    def to_context(self):
        return (f'Financials: HTML income statement ({self.currency}); xb=None\n'
                f'Source: {self.source_url}\n'
                'Only the reported income statement is available; other statements return None.\n'
                + '\n'.join(self.notes))

    def __str__(self):
        return f'Financials(HTML income statement, {self.currency}, {self.source_filing.accession_no})'

    def __rich__(self):
        return self._income.__rich__()


def _extract_6k_income_statement(filing) -> Optional[Financials]:
    """Return only an explicitly quarterly, currency-qualified income table.

    Absence is None; downloads and parser failures are not hidden. EX-99 exhibits
    are discovered from filing attachments, never guessed from document names.
    """
    if filing.form != '6-K':
        return None
    filing_year = int(str(filing.filing_date)[:4])
    for attachment in find_earnings_exhibits(filing.attachments):
        release = EarningsRelease(attachment)
        if release.document is None:
            continue
        table = release.income_statement
        if table is None:
            continue
        columns = [(key, i) for i, col in enumerate(table.dataframe.columns)
                   if (key := _quarter(str(col), filing_year)) is not None]
        if not columns or len({key for key, _ in columns}) != len(columns):
            continue
        labels = {str(label).strip().lower() for label in table.dataframe.index}
        if not labels.intersection(_REVENUE) or not labels.intersection(_NET_INCOME):
            continue
        # A grouped/NCI table needs explicit parent attribution; do not return
        # consolidated income as the owners' income via a loose label match.
        if any('noncontrolling' in label or 'non-controlling' in label for label in labels):
            if not labels.intersection(_NET_INCOME[:2]):
                continue
        context, notes = _table_context(release, table)
        declarations = [m[0] for text in reversed(context)
                        if (m := re.search(r'(?:\(?\s*units?\s*:\s*|\(\s*(?:amounts?\s+)?in\s+)[^)\n]+', text, re.I))]
        if not declarations or (currency := _currency(declarations[0])) is None:
            continue
        scale = Scale.detect(declarations[0])
        positions = [i for _, i in sorted(columns, reverse=True)]
        frame = table.dataframe.iloc[:, positions].copy()
        row_types = list(table.row_types)
        for row, label in enumerate(frame.index):
            if re.search(r'\beps\b|per share|per adr|per ads', str(label), re.I):
                row_types[row] = RowType.PER_SHARE
                # The existing parser preserves literal letter footnotes (29.43b).
                # Retain the footnote text below, remove only a numeric suffix.
                for col in range(len(frame.columns)):
                    raw = str(frame.iloc[row, col])
                    match = re.fullmatch(r'(-?\d+(?:\.\d+)?)[a-z]', raw, re.I)
                    if match:
                        frame.iloc[row, col] = float(match[1])
        source_url = attachment.url
        statement = _HTMLIncomeStatement(
            dataframe=frame, scale=scale, title=table.title,
            statement_type=table.statement_type, periods=list(frame.columns),
            raw_index=table.raw_index, row_types=row_types, currency=currency,
            source_url=source_url, notes=tuple([declarations[0], *notes]),
        )
        result = _HTMLFinancials(filing, statement)
        if result.get_revenue() is not None and result.get_net_income() is not None:
            return result
    return None
