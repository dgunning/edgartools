"""
497K Summary Prospectus data object.

Form 497K is the SEC-mandated summary prospectus for mutual funds and ETFs,
filed under Rule 498 of the Securities Act of 1933. It has ZERO XBRL — all
structured data comes from HTML table parsing. The section order is mandated
by Form N-1A rules, making extraction reliable.

~20,000 filings per year with extremely consistent HTML structure.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import df_to_rich_table, repr_rich

log = logging.getLogger(__name__)

__all__ = ['Prospectus497K', 'PROSPECTUS497K_FORMS']

PROSPECTUS497K_FORMS = ["497K"]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ShareClassFees(BaseModel):
    """Fee data for a single share class extracted from 497K HTML tables."""
    class_name: str = ""
    ticker: Optional[str] = None
    class_id: Optional[str] = None  # C000xxxxx

    # Shareholder fees (paid directly)
    max_sales_load: Optional[Decimal] = None
    max_deferred_sales_load: Optional[Decimal] = None
    redemption_fee: Optional[Decimal] = None

    # Annual operating expenses (% of assets)
    management_fee: Optional[Decimal] = None
    twelve_b1_fee: Optional[Decimal] = None
    other_expenses: Optional[Decimal] = None
    acquired_fund_fees: Optional[Decimal] = None
    total_annual_expenses: Optional[Decimal] = None
    fee_waiver: Optional[Decimal] = None
    net_expenses: Optional[Decimal] = None

    # Expense example ($10K hypothetical)
    expense_1yr: Optional[int] = None
    expense_3yr: Optional[int] = None
    expense_5yr: Optional[int] = None
    expense_10yr: Optional[int] = None

    def __str__(self):
        ticker = f" ({self.ticker})" if self.ticker else ""
        total = f" {self.total_annual_expenses}%" if self.total_annual_expenses else ""
        return f"{self.class_name}{ticker}{total}"


class PerformanceReturn(BaseModel):
    """A row from the average annual returns table."""
    label: str
    section: str = ""  # Share class section header
    return_1yr: Optional[Decimal] = None
    return_5yr: Optional[Decimal] = None
    return_10yr: Optional[Decimal] = None
    return_since_inception: Optional[Decimal] = None
    inception_date: Optional[str] = None


# ---------------------------------------------------------------------------
# SGML header extraction
# ---------------------------------------------------------------------------

def _extract_header_data(filing) -> Dict:
    """Extract series ID, class IDs, and tickers from SGML header."""
    result = {
        'series_id': None,
        'series_name': None,
        'class_info': [],  # list of {'class_id': ..., 'name': ..., 'ticker': ...}
        'cik': None,
    }

    header = getattr(filing, 'header', None)
    if not header or not hasattr(header, 'text'):
        return result

    result['cik'] = str(header.cik) if header.cik else str(getattr(filing, 'cik', ''))

    text = header.text
    match = re.search(
        r'<SERIES-AND-CLASSES-CONTRACTS-DATA>(.*?)</SERIES-AND-CLASSES-CONTRACTS-DATA>',
        text, re.DOTALL
    )
    if not match:
        return result

    sgml = match.group(1)

    # Extract series info
    series_match = re.search(r'<SERIES-ID>\s*(\S+)', sgml)
    if series_match:
        result['series_id'] = series_match.group(1).strip()

    series_name_match = re.search(r'<SERIES-NAME>\s*(.+)', sgml)
    if series_name_match:
        result['series_name'] = series_name_match.group(1).strip()

    # Extract class/contract blocks
    class_pattern = re.compile(
        r'<CLASS-CONTRACT>(.*?)</CLASS-CONTRACT>', re.DOTALL
    )
    for block in class_pattern.finditer(sgml):
        block_text = block.group(1)
        class_id_match = re.search(r'<CLASS-CONTRACT-ID>\s*(\S+)', block_text)
        name_match = re.search(r'<CLASS-CONTRACT-NAME>\s*(.+)', block_text)
        ticker_match = re.search(r'<CLASS-CONTRACT-TICKER-SYMBOL>\s*(\S+)', block_text)

        info = {
            'class_id': class_id_match.group(1).strip() if class_id_match else None,
            'name': name_match.group(1).strip() if name_match else None,
            'ticker': ticker_match.group(1).strip() if ticker_match else None,
        }
        result['class_info'].append(info)

    return result


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class Prospectus497K:
    """
    Summary Prospectus for registered open-end investment companies (497K).

    Extracts structured data from the standardized summary prospectus HTML.
    No XBRL is available in 497K filings — all data comes from HTML tables.

    Usage::

        filing = find("0001683863-25-002784")
        p = filing.obj()              # Prospectus497K

        p.fund_name                   # "Vanguard California Long-Term Tax-Exempt Fund"
        p.tickers                     # ["VCITX", "VCLAX"]
        p.fees                        # DataFrame: class, fees per share class
        p.performance                 # DataFrame: label, 1yr, 5yr, 10yr returns
        p.best_quarter                # (Decimal('8.80'), 'December 31, 2023')
    """

    def __init__(self,
                 filing=None,
                 share_classes: Optional[List[ShareClassFees]] = None,
                 performance_returns: Optional[List[PerformanceReturn]] = None,
                 best_quarter: Optional[Tuple[Decimal, str]] = None,
                 worst_quarter: Optional[Tuple[Decimal, str]] = None,
                 fund_name: Optional[str] = None,
                 prospectus_date: Optional[str] = None,
                 investment_objective: Optional[str] = None,
                 portfolio_turnover: Optional[Decimal] = None,
                 portfolio_managers: Optional[List[str]] = None,
                 min_investments: Optional[Dict] = None,
                 series_id: Optional[str] = None,
                 series_name: Optional[str] = None,
                 class_info: Optional[List[Dict]] = None,
                 cik: Optional[str] = None):
        self._filing = filing
        self._share_classes = share_classes or []
        self._performance_returns = performance_returns or []
        self._best_quarter = best_quarter
        self._worst_quarter = worst_quarter
        self._fund_name = fund_name or ''
        self._prospectus_date = prospectus_date
        self._investment_objective = investment_objective
        self._portfolio_turnover = portfolio_turnover
        self._portfolio_managers = portfolio_managers or []
        self._min_investments = min_investments or {}
        self._series_id = series_id
        self._series_name = series_name
        self._class_info = class_info or []
        self._cik = cik

        # Cached DataFrames
        self._fees_df = None
        self._expense_example_df = None
        self._performance_df = None

    # -------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------

    @property
    def filing(self):
        """The source Filing object."""
        return self._filing

    @property
    def fund_name(self) -> str:
        return self._fund_name or self._series_name or ''

    @property
    def prospectus_date(self) -> Optional[str]:
        return self._prospectus_date

    @property
    def investment_objective(self) -> Optional[str]:
        return self._investment_objective

    @property
    def portfolio_turnover(self) -> Optional[Decimal]:
        return self._portfolio_turnover

    @property
    def portfolio_managers(self) -> List[str]:
        return self._portfolio_managers

    @property
    def tickers(self) -> List[str]:
        """All share class tickers."""
        return [sc.ticker for sc in self._share_classes if sc.ticker]

    @property
    def series_id(self) -> Optional[str]:
        """Series ID (S000xxxxx) from SGML header."""
        return self._series_id

    @property
    def class_ids(self) -> List[str]:
        """Class/Contract IDs (C000xxxxx) from SGML header."""
        return [sc.class_id for sc in self._share_classes if sc.class_id]

    @property
    def cik(self) -> Optional[str]:
        return self._cik

    @property
    def share_classes(self) -> List[ShareClassFees]:
        return self._share_classes

    @property
    def num_share_classes(self) -> int:
        return len(self._share_classes)

    @property
    def best_quarter(self) -> Optional[Tuple[Decimal, str]]:
        """(return_pct, date_str) for the best quarter, or None."""
        return self._best_quarter

    @property
    def worst_quarter(self) -> Optional[Tuple[Decimal, str]]:
        """(return_pct, date_str) for the worst quarter, or None."""
        return self._worst_quarter

    # -------------------------------------------------------------------
    # DataFrame methods
    # -------------------------------------------------------------------

    @property
    def fees(self) -> pd.DataFrame:
        """Fee data per share class as a DataFrame."""
        if self._fees_df is not None:
            return self._fees_df
        rows = []
        for sc in self._share_classes:
            rows.append({
                'class_name': sc.class_name,
                'ticker': sc.ticker,
                'management_fee': sc.management_fee,
                'twelve_b1_fee': sc.twelve_b1_fee,
                'other_expenses': sc.other_expenses,
                'total_annual_expenses': sc.total_annual_expenses,
                'fee_waiver': sc.fee_waiver,
                'net_expenses': sc.net_expenses,
            })
        self._fees_df = pd.DataFrame(rows)
        return self._fees_df

    @property
    def expense_example(self) -> pd.DataFrame:
        """Expense example per share class ($10K hypothetical investment)."""
        if self._expense_example_df is not None:
            return self._expense_example_df
        rows = []
        for sc in self._share_classes:
            rows.append({
                'class_name': sc.class_name,
                'ticker': sc.ticker,
                '1yr': sc.expense_1yr,
                '3yr': sc.expense_3yr,
                '5yr': sc.expense_5yr,
                '10yr': sc.expense_10yr,
            })
        self._expense_example_df = pd.DataFrame(rows)
        return self._expense_example_df

    @property
    def performance(self) -> pd.DataFrame:
        """Average annual returns as a DataFrame."""
        if self._performance_df is not None:
            return self._performance_df
        rows = []
        for pr in self._performance_returns:
            rows.append({
                'label': pr.label,
                'section': pr.section,
                '1yr': pr.return_1yr,
                '5yr': pr.return_5yr,
                '10yr': pr.return_10yr,
                'since_inception': pr.return_since_inception,
            })
        self._performance_df = pd.DataFrame(rows)
        return self._performance_df

    # -------------------------------------------------------------------
    # Rich display
    # -------------------------------------------------------------------

    @property
    def _summary_table(self) -> Table:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Fund", self.fund_name)
        if self.series_id:
            table.add_row("Series", self.series_id)
        if self.tickers:
            table.add_row("Tickers", ", ".join(self.tickers))
        if self._portfolio_turnover is not None:
            table.add_row("Portfolio Turnover", f"{self._portfolio_turnover}%")
        table.add_row("Share Classes", str(self.num_share_classes))
        return table

    @property
    def _fee_table(self) -> Optional[Table]:
        df = self.fees
        if df.empty:
            return None
        display = df.copy()
        display = display.rename(columns={
            'class_name': 'Class',
            'ticker': 'Ticker',
            'management_fee': 'Mgmt Fee %',
            'twelve_b1_fee': '12b-1 %',
            'other_expenses': 'Other %',
            'total_annual_expenses': 'Total %',
            'fee_waiver': 'Waiver %',
            'net_expenses': 'Net %',
        })
        # Format percentage columns
        for col in ['Mgmt Fee %', '12b-1 %', 'Other %', 'Total %', 'Waiver %', 'Net %']:
            if col in display.columns:
                display[col] = display[col].apply(
                    lambda x: f"{x}%" if pd.notna(x) and x is not None else "—"
                )
        return df_to_rich_table(
            display,
            title="Annual Operating Expenses",
            title_style="bold deep_sky_blue1",
            max_rows=20,
        )

    @property
    def _expense_example_table(self) -> Optional[Table]:
        df = self.expense_example
        if df.empty:
            return None
        display = df.copy()
        display = display.rename(columns={
            'class_name': 'Class',
            'ticker': 'Ticker',
            '1yr': '1 Year',
            '3yr': '3 Years',
            '5yr': '5 Years',
            '10yr': '10 Years',
        })
        for col in ['1 Year', '3 Years', '5 Years', '10 Years']:
            if col in display.columns:
                display[col] = display[col].apply(
                    lambda x: f"${x}" if pd.notna(x) and x is not None else "—"
                )
        return df_to_rich_table(
            display,
            title="Expense Example ($10K Investment)",
            title_style="bold deep_sky_blue1",
            max_rows=20,
        )

    @property
    def _performance_table(self) -> Optional[Table]:
        df = self.performance
        if df.empty:
            return None
        display = df.drop(columns=['section'], errors='ignore').copy()
        display = display.rename(columns={
            'label': 'Return Type',
            '1yr': '1 Year',
            '5yr': '5 Years',
            '10yr': '10 Years',
            'since_inception': 'Since Inception',
        })
        for col in ['1 Year', '5 Years', '10 Years', 'Since Inception']:
            if col in display.columns:
                display[col] = display[col].apply(
                    lambda x: f"{x}%" if pd.notna(x) and x is not None else "—"
                )
        return df_to_rich_table(
            display,
            title="Average Annual Returns",
            title_style="bold deep_sky_blue1",
            max_rows=30,
        )

    @property
    def _quarter_text(self) -> Optional[Text]:
        parts = []
        if self._best_quarter:
            pct, date = self._best_quarter
            parts.append(f"Best Quarter: {pct}% ({date})")
        if self._worst_quarter:
            pct, date = self._worst_quarter
            parts.append(f"Worst Quarter: {pct}% ({date})")
        if parts:
            return Text("  |  ".join(parts))
        return None

    def __rich__(self):
        renderables = [self._summary_table]

        fee = self._fee_table
        if fee:
            renderables.append(fee)

        expense = self._expense_example_table
        if expense:
            renderables.append(expense)

        perf = self._performance_table
        if perf:
            renderables.append(perf)

        qtext = self._quarter_text
        if qtext:
            renderables.append(qtext)

        return Panel(
            Group(*renderables),
            title=self.fund_name,
            subtitle="497K Summary Prospectus",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        n = self.num_share_classes
        tickers = ", ".join(self.tickers) if self.tickers else "no tickers"
        return f"Prospectus497K({self.fund_name}, {n} classes, {tickers})"

    # -------------------------------------------------------------------
    # AI context
    # -------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        lines = []
        lines.append(f"PROSPECTUS497K: {self.fund_name}")
        lines.append("")
        lines.append(f"Tickers: {', '.join(self.tickers) if self.tickers else 'N/A'}")
        lines.append(f"Share Classes: {self.num_share_classes}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Standard
        if self.series_id:
            lines.append(f"Series ID: {self.series_id}")
        if self._portfolio_turnover:
            lines.append(f"Portfolio Turnover: {self._portfolio_turnover}%")

        lines.append("")
        for sc in self._share_classes:
            sc_line = f"  {sc.class_name}"
            if sc.ticker:
                sc_line += f" ({sc.ticker})"
            if sc.total_annual_expenses:
                sc_line += f" Total Expenses: {sc.total_annual_expenses}%"
            lines.append(sc_line)

        if self._best_quarter:
            pct, date = self._best_quarter
            lines.append(f"Best Quarter: {pct}% ({date})")
        if self._worst_quarter:
            pct, date = self._worst_quarter
            lines.append(f"Worst Quarter: {pct}% ({date})")

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .fees                    Fee data per share class")
        lines.append("  .expense_example         Hypothetical $10K expense")
        lines.append("  .performance             Average annual returns")
        lines.append("  .share_classes           Share class details list")

        if detail == 'standard':
            return "\n".join(lines)

        # Full
        if self._investment_objective:
            lines.append("")
            lines.append(f"Investment Objective: {self._investment_objective[:300]}")

        if not self.performance.empty:
            lines.append("")
            lines.append("PERFORMANCE:")
            for _, row in self.performance.iterrows():
                parts = [f"  {row['label']}:"]
                for col in ['1yr', '5yr', '10yr']:
                    val = row.get(col)
                    if pd.notna(val) and val is not None:
                        parts.append(f" {col}={val}%")
                lines.append("".join(parts))

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing) -> Optional['Prospectus497K']:
        """Create a Prospectus497K from a Filing object."""
        from edgar.funds._497k_tables import (
            extract_fee_tables,
            extract_fund_metadata,
            extract_performance_table,
        )

        html = filing.html()
        if not html:
            return None

        # Extract SGML header data (series/class/ticker)
        header_data = _extract_header_data(filing)

        # Extract HTML tables
        fee_data = extract_fee_tables(html, class_info=header_data.get('class_info'))
        perf_data, best_quarter, worst_quarter = extract_performance_table(html)
        metadata = extract_fund_metadata(html)

        # Build ShareClassFees models
        share_classes = []
        for fd in fee_data:
            share_classes.append(ShareClassFees(
                class_name=fd.get('class_name', ''),
                ticker=fd.get('ticker'),
                class_id=fd.get('class_id'),
                max_sales_load=fd.get('max_sales_load'),
                max_deferred_sales_load=fd.get('max_deferred_sales_load'),
                redemption_fee=fd.get('redemption_fee'),
                management_fee=fd.get('management_fee'),
                twelve_b1_fee=fd.get('twelve_b1_fee'),
                other_expenses=fd.get('other_expenses'),
                acquired_fund_fees=fd.get('acquired_fund_fees'),
                total_annual_expenses=fd.get('total_annual_expenses'),
                fee_waiver=fd.get('fee_waiver'),
                net_expenses=fd.get('net_expenses'),
                expense_1yr=fd.get('expense_1yr'),
                expense_3yr=fd.get('expense_3yr'),
                expense_5yr=fd.get('expense_5yr'),
                expense_10yr=fd.get('expense_10yr'),
            ))

        # Build PerformanceReturn models
        performance_returns = []
        for pd_row in perf_data:
            performance_returns.append(PerformanceReturn(
                label=pd_row.get('label', ''),
                section=pd_row.get('section', ''),
                return_1yr=pd_row.get('return_1yr'),
                return_5yr=pd_row.get('return_5yr'),
                return_10yr=pd_row.get('return_10yr'),
                return_since_inception=pd_row.get('return_since_inception'),
            ))

        # Use series_name from SGML as fund_name if metadata didn't find one
        fund_name = metadata.get('fund_name') or header_data.get('series_name', '')

        return cls(
            filing=filing,
            share_classes=share_classes,
            performance_returns=performance_returns,
            best_quarter=best_quarter,
            worst_quarter=worst_quarter,
            fund_name=fund_name,
            prospectus_date=metadata.get('prospectus_date'),
            investment_objective=metadata.get('investment_objective'),
            portfolio_turnover=metadata.get('portfolio_turnover'),
            portfolio_managers=metadata.get('portfolio_managers', []),
            min_investments=metadata.get('min_investments', {}),
            series_id=header_data.get('series_id'),
            series_name=header_data.get('series_name'),
            class_info=header_data.get('class_info', []),
            cik=header_data.get('cik'),
        )
