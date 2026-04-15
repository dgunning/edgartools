"""
Market-wide proxy contest discovery.

Scans EDGAR filings for contest-indicator forms across all companies,
groups them by company, and returns a browsable collection of ProxyContest objects.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)

__all__ = ['ProxyContests', 'proxy_contests']


@dataclass
class _ContestEntry:
    """Internal: a ProxyContest annotated with discovery metadata."""
    contest: 'ProxyContest'
    ticker: str
    is_company: bool  # True = target company, False = activist fund


class ProxyContests:
    """
    A collection of proxy contests discovered across the market.

    Works like Filings — supports len(), indexing, slicing, .head(),
    and renders as a Rich table.

    Contains both target companies and activist funds. Use .companies
    to see only target companies, or .activists to see only activist funds.

    Usage:
        >>> from edgar import proxy_contests
        >>> contests = proxy_contests(year=2024)
        >>> contests.head(10)              # Top 10 by filing count
        >>> contests.companies.head(10)    # Just the target companies
        >>> contests.activists             # Just the activist funds
    """

    def __init__(self, entries: List[_ContestEntry], year: Optional[int] = None, quarter: Optional[int] = None):
        self._entries = entries
        self._year = year
        self._quarter = quarter

    def __len__(self):
        return len(self._entries)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return ProxyContests(self._entries[item], self._year, self._quarter)
        return self._entries[item].contest

    def __iter__(self):
        return iter([e.contest for e in self._entries])

    def head(self, n: int = 10) -> 'ProxyContests':
        """Return a new ProxyContests with the first n entries."""
        return ProxyContests(self._entries[:n], self._year, self._quarter)

    @property
    def empty(self) -> bool:
        return len(self._entries) == 0

    @property
    def companies(self) -> 'ProxyContests':
        """Only target companies (those with tickers, filing management-side forms)."""
        return ProxyContests([e for e in self._entries if e.is_company], self._year, self._quarter)

    @property
    def activists(self) -> 'ProxyContests':
        """Only activist funds (those filing dissident-side contest forms)."""
        return ProxyContests([e for e in self._entries if not e.is_company], self._year, self._quarter)

    def __rich__(self):
        if not self._entries:
            return Panel(
                Text("No proxy contests found.", style="dim italic"),
                title="Proxy Contests",
                border_style="bold grey54",
                expand=False,
            )

        table = Table(
            show_header=True,
            header_style="bold",
            show_edge=True,
            expand=False,
            padding=(0, 1),
            box=box.SIMPLE,
            row_styles=["", "bold"],
        )

        table.add_column("#", style="dim", justify="right", width=4)
        table.add_column("Ticker", style="yellow", width=6)
        table.add_column("Company", style="bold green", width=30, no_wrap=True)
        table.add_column("Dissidents", width=34, no_wrap=True)
        table.add_column("Filings", justify="right", width=8)
        table.add_column("Status", width=10)

        for i, entry in enumerate(self._entries):
            contest = entry.contest
            dissidents = ', '.join(contest.dissidents) if contest.dissidents else 'Unknown'

            if contest.is_settled:
                status = Text("Settled", style="yellow")
            else:
                status = Text("Active", style="red")

            table.add_row(
                str(i),
                entry.ticker,
                contest.company_name,
                dissidents,
                str(contest.num_filings),
                status,
            )

        elements = [table]

        # Summary line
        n_companies = sum(1 for e in self._entries if e.is_company)
        n_activists = sum(1 for e in self._entries if not e.is_company)
        parts = []
        if n_companies:
            parts.append((f"{n_companies}", "bold"))
            parts.append((" companies", "dim"))
        if n_companies and n_activists:
            parts.append((", ", "dim"))
        if n_activists:
            parts.append((f"{n_activists}", "bold"))
            parts.append((" activists", "dim"))

        elements.append(Text())
        elements.append(Text.assemble(*parts))

        subtitle = ""
        if self._year:
            subtitle = f"Q{self._quarter} {self._year}" if self._quarter else str(self._year)

        return Panel(
            Group(*elements),
            title="Proxy Contests",
            subtitle=subtitle,
            border_style="bold grey54",
            expand=False,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"ProxyContests({len(self._entries)} contests)"


def proxy_contests(year: Optional[int] = None, quarter: Optional[int] = None) -> ProxyContests:
    """
    Discover proxy contests across the entire market.

    Scans EDGAR for contest-indicator filings (DEFC14A, DFAN14A, PREC14A, etc.),
    groups them by filer, and builds a ProxyContest for each.

    Results contain both target companies and activist funds. Use .companies
    or .activists to filter.

    Args:
        year: Filing year to scan. Defaults to the current year.
        quarter: Quarter (1-4) to scan. If None, scans all available quarters.

    Returns:
        ProxyContests collection sorted by filing count (most active first).

    Usage:
        >>> contests = proxy_contests(year=2024)
        >>> contests.companies.head(10)     # Target companies only
        >>> contests.activists              # Activist funds only
    """
    from edgar._filings import get_filings
    from edgar.proxy.contest import ProxyContest
    from edgar.proxy.models import CONTEST_INDICATOR_FORMS, DISSIDENT_ONLY_FORMS
    from edgar.reference.tickers import find_ticker

    contest_forms = sorted(CONTEST_INDICATOR_FORMS)

    if year is None:
        from datetime import date
        year = date.today().year

    # Fetch all contest-indicator filings across the market
    if quarter:
        filings = get_filings(year=year, quarter=quarter, form=contest_forms)
    else:
        filings = get_filings(year=year, form=contest_forms)

    if filings is None or len(filings) == 0:
        return ProxyContests([])

    # Group filings by filer CIK
    filings_by_cik = defaultdict(list)
    company_names = {}

    for filing in filings:
        cik = filing.cik
        filings_by_cik[cik].append(filing)
        if cik not in company_names:
            company_names[cik] = filing.company

    # Classify each CIK as company or activist
    dissident_base_forms = {f.replace('/A', '').strip() for f in DISSIDENT_ONLY_FORMS}

    entries = []
    for cik, cik_filings in filings_by_cik.items():
        forms_filed = {f.form.replace('/A', '').strip() for f in cik_filings}
        ticker = find_ticker(cik)

        # Classify: is this CIK a target company or an activist fund?
        # A CIK is likely a target company if it has a ticker.
        # A CIK filing only dissident forms (DFAN14A, etc.) is always an activist.
        # A CIK with no ticker filing DEFC14A/PREC14A is likely an activist fund
        # filing contested proxies under its own CIK.
        if forms_filed <= dissident_base_forms:
            is_company = False
        elif ticker:
            is_company = True
        else:
            is_company = False

        contest = ProxyContest(
            company_name=company_names[cik],
            company_cik=str(cik),
            contest_filings=cik_filings,
        )
        entries.append(_ContestEntry(contest=contest, ticker=ticker, is_company=is_company))

    # Sort by number of filings descending (most active first)
    entries.sort(key=lambda e: e.contest.num_filings, reverse=True)

    return ProxyContests(entries, year=year, quarter=quarter)
