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


def _currency(text):
    matches = [code for code, pattern in _CURRENCIES.items() if re.search(pattern, text, re.I)]
    return matches[0] if len(matches) == 1 else None


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

    def to_dataframe(self, **kwargs):
        """Actual currency amounts; EPS/ratios stay unscaled. Source labels remain."""
        frame = self.scaled_dataframe.reset_index(names='label')
        frame.attrs.update(source='HTML', currency=self.currency, reported_scale=self.scale.value,
                           source_url=self.source_url, notes=self.notes)
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
        if view is not None:
            raise ValidationError('HTML income statements do not support XBRL views',
                                  parameter='view', invalid_value=view)
        return self._income

    def _value(self, labels, period_offset):
        if not isinstance(period_offset, int) or period_offset < 0:
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
