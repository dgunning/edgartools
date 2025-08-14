import re
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pyarrow as pa
import pyarrow.compute as pc
from bs4 import BeautifulSoup
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from edgar._filings import Filings
from edgar.core import IntString
from edgar.formatting import accession_number_text, accepted_time_text
from edgar.httprequests import get_with_retry
from edgar.reference.tickers import find_ticker
from edgar.xmltools import child_text

__all__ = [
    'CurrentFilings',
    'get_current_filings',
    'get_all_current_filings',
    'iter_current_filings_pages',
]

summary_regex = re.compile(r'<b>([^<]+):</b>\s+([^<\s]+)')
title_regex = re.compile(r"(.*) - (.*) \((\d+)\) \((.*)\)")

"""
Get the current filings from the SEC. Use this to get the filings filed after the 5:30 deadline
"""
GET_CURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom&owner=only&count=100"


def _empty_filing_index():
    schema = pa.schema([
        ('form', pa.string()),
        ('company', pa.string()),
        ('cik', pa.int32()),
        ('filing_date', pa.date32()),
        ('accession_number', pa.string()),
        ('accepted', pa.timestamp('s')),
    ])

    # Create an empty table with the defined schema
    return pa.Table.from_arrays([
        pa.array([], type=pa.string()),
        pa.array([], type=pa.string()),
        pa.array([], type=pa.int32()),
        pa.array([], type=pa.date32()),
        pa.array([], type=pa.string()),
        pa.array([], type=pa.timestamp('s')),
    ], schema=schema)

def parse_title(title: str):
    """
    Given the title in this example

    "144 - monday.com Ltd. (0001845338) (Subject)"
    which contains the form type, company name, CIK, and status
    parse into a tuple of form type, company name, CIK, and status using regex
    """
    match = title_regex.match(title)
    assert match, f"Could not parse title: {title} using regex: {title_regex}"
    return match.groups()

def parse_summary(summary: str):
    """
    Given the summary in this example

    "Filed: 2021-09-30 AccNo: 0001845338-21-000002 Size: 1 MB"

    parse into a tuple of filing date, accession number, and size
    """
    # Remove <b> and </b> tags from summary

    matches = re.findall(summary_regex, summary)

    # Convert matches into a dictionary
    fields = {k.strip(): (int(v) if v.isdigit() else v) for k, v in matches}

    return datetime.strptime(str(fields.get('Filed', '')), '%Y-%m-%d').date(), fields.get('AccNo')


def get_current_url(atom: bool = True,
                    count: int = 100,
                    start: int = 0,
                    form: str = '',
                    owner: str = 'include'):
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"

    count = count if count in [10, 20, 40, 80, 100] else 40
    owner = owner if owner in ['include', 'exclude', 'only'] else 'include'

    url = url + f"&count={count}&start={start}&type={form}&owner={owner}"
    if atom:
        url += "&output=atom"
    return url


@lru_cache(maxsize=32)
def get_current_entries_on_page(count: int, start: int, form: Optional[str] = None, owner: str = 'include'):
    url = get_current_url(count=count, start=start, form=form if form else '', owner=owner, atom=True)
    response = get_with_retry(url)

    soup = BeautifulSoup(response.text, features="xml")
    entries = []
    for entry in soup.find_all("entry"):
        # The title contains the form type, company name, CIK, and status e.g 4 - WILKS LEWIS (0001076463) (Reporting)
        title = child_text(entry, "title")
        form_type, company_name, cik, status = parse_title(title)
        # The summary contains the filing date and link to the filing
        summary = child_text(entry, "summary")
        filing_date, accession_number = parse_summary(summary)
        accepted = datetime.fromisoformat(child_text(entry, "updated"))

        entries.append({'form': form_type,
                        'company': company_name,
                        'cik': int(cik),
                        'filing_date': filing_date,
                        'accession_number': accession_number,
                        'accepted': accepted})
    return entries


class CurrentFilings(Filings):
    """
    This version of the Filings class is used to get the current filings from the SEC
    page by page
    """

    def __init__(self,
                 filing_index: pa.Table,
                 form: str = '',
                 start: int = 1,
                 page_size: int = 40,
                 owner: str = 'include'):
        super().__init__(filing_index, original_state=None)
        self._start = start
        self._page_size = page_size
        self.owner = owner
        self.form = form

    def next(self):
        # If the number of entries is less than the page size then we are at the end of the data
        if len(self.data) < self._page_size:
            return None
        start = self._start + len(self.data)
        next_entries = get_current_entries_on_page(start=start-1, count=self._page_size, form=self.form)
        if next_entries:
            # Copy the values to this Filings object and return it
            self.data = pa.Table.from_pylist(next_entries)
            self._start = start
            return self

    def previous(self):
        # If start = 1 then there are no previous entries
        if self._start == 1:
            return None
        start = max(1, self._start - self._page_size)
        previous_entries = get_current_entries_on_page(start=start, count=self._page_size, form=self.form)
        if previous_entries:
            # Copy the values to this Filings object and return it
            self.data = pa.Table.from_pylist(previous_entries)
            self._start = start
            return self

    def __getitem__(self, item):  # type: ignore
        item = self.get(item)
        assert item is not None
        return item

    def get(self, index_or_accession_number: IntString):
        if isinstance(index_or_accession_number, int) or index_or_accession_number.isdigit():
            idx = int(index_or_accession_number)
            if self._start - 1 <= idx < self._start - 1 + len(self.data):
                # Where on this page is the index
                idx_on_page = idx - (self._start - 1)
                return super().get_filing_at(idx_on_page)
        else:
            accession_number = index_or_accession_number.strip()
            # See if the filing is in this page
            filing = super().get(accession_number)
            if filing:
                return filing

            current_filings = get_current_filings(self.form, self.owner, page_size=100)
            filing = CurrentFilings._get_current_filing_by_accession_number(current_filings.data, accession_number)
            if filing:
                return filing
            with Status(f"[bold deep_sky_blue1]Searching through the most recent filings for {accession_number}...",
                        spinner="dots2"):
                while True:
                    current_filings = current_filings.next()
                    if current_filings is None:
                        return None
                    filing = CurrentFilings._get_current_filing_by_accession_number(current_filings.data,
                                                                                    accession_number)
                    if filing:
                        return filing

    @staticmethod
    def _get_current_filing_by_accession_number(data: pa.Table, accession_number: str):
        from edgar import Filing
        mask = pc.equal(data['accession_number'], accession_number)
        idx = mask.index(True).as_py()
        if idx > -1:
            return Filing(
                cik=data['cik'][idx].as_py(),
                company=data['company'][idx].as_py(),
                form=data['form'][idx].as_py(),
                filing_date=data['filing_date'][idx].as_py(),
                accession_no=data['accession_number'][idx].as_py(),
            )
        return None

    def __rich__(self):

        # Create table with appropriate columns and styling
        table = Table(
            show_header=True,
            header_style="bold",
            show_edge=True,
            expand=False,
            padding=(0, 1),
            box=box.SIMPLE,
        )

        # Add columns with specific styling and alignment
        table.add_column("#", style="dim", justify="right")
        table.add_column("Form", width=12)
        table.add_column("CIK", style="dim", width=10, justify="right")
        table.add_column("Ticker", width=6, style="yellow")
        table.add_column("Company", style="bold green", width=38, no_wrap=True)
        table.add_column("Accepted", width=20)
        table.add_column("Accession Number", width=20)


        # Get current page from data pager
        current_page = self.data.to_pandas()

        # compute the index from the start and page_size and set it as the index of the page
        current_page.index = range(self._start - 1, self._start - 1 + len(current_page))

        # Iterate through rows in current page
        for t in current_page.itertuples():
            cik = t.cik
            ticker = find_ticker(cik)

            row = [
                str(t.Index),
                t.form,
                str(cik),
                ticker,
                t.company,
                accepted_time_text(t.accepted),
                accession_number_text(t.accession_number)
            ]
            table.add_row(*row)

        # Show paging information only if there are multiple pages
        elements = [table]

        page_info = Text.assemble(
            ("Showing ", "dim"),
            (f"{current_page.index.min():,}", "bold red"),
            (" to ", "dim"),
            (f"{current_page.index.max():,}", "bold red"),
            (" most recent filings.", "dim"),
            (" Page using ", "dim"),
            ("← prev()", "bold gray54"),
            (" and ", "dim"),
            ("next() →", "bold gray54")
        )

        elements.extend([Text("\n"), page_info])

        # Get the subtitle
        start_date, end_date = self.date_range
        subtitle = "Most recent filings from the SEC"
        return Panel(
            Group(*elements),
            title="SEC Filings",
            subtitle=subtitle,
            border_style="bold grey54",
            expand=False
        )


def get_all_current_filings(form: str = '',
                            owner: str = 'include',
                            page_size: int = 100) -> 'Filings':
    """
    Get ALL current filings by iterating through all pages.

    Args:
        form: Form type to filter by (e.g., "10-K", "8-K")
        owner: Owner filter ('include', 'exclude', 'only')
        page_size: Number of filings per page (10, 20, 40, 80, 100)

    Returns:
        Filings: A regular Filings object containing all current filings

    Example:
        >>> all_filings = get_all_current_filings(form="10-K")
        >>> print(f"Found {len(all_filings)} total current 10-K filings")
    """
    from edgar._filings import Filings
    all_entries = []

    for page in iter_current_filings_pages(form=form, owner=owner, page_size=page_size):
        # Convert PyArrow table to list and extend
        page_entries = page.data.to_pylist()
        all_entries.extend(page_entries)

    if not all_entries:
        return Filings(_empty_filing_index())

    # Return as regular Filings object (not CurrentFilings)
    return Filings(pa.Table.from_pylist(all_entries))


def get_current_filings(form: str = '',
                        owner: str = 'include',
                        page_size: int = 40):
    """
    Get the current filings from the SEC
    :return: The current filings from the SEC
    """
    owner = owner if owner in ['include', 'exclude', 'only'] else 'include'
    page_size = page_size if page_size in [10, 20, 40, 80, 100] else 100
    start = 0

    entries = get_current_entries_on_page(count=page_size, start=start, form=form, owner=owner)
    if not entries:
        return CurrentFilings(filing_index=_empty_filing_index(), owner=owner, form=form, page_size=page_size)
    return CurrentFilings(filing_index=pa.Table.from_pylist(entries), owner=owner, form=form, page_size=page_size)


def iter_current_filings_pages(form: str = '',
                               owner: str = 'include',
                               page_size: int = 100):
    """
    Iterator that yields CurrentFilings pages until exhausted.

    Args:
        form: Form type to filter by (e.g., "10-K", "8-K")
        owner: Owner filter ('include', 'exclude', 'only')
        page_size: Number of filings per page (10, 20, 40, 80, 100)

    Yields:
        CurrentFilings: Each page of current filings until no more pages

    Example:
        >>> for page in iter_current_filings_pages(form="10-K"):
        ...     print(f"Processing {len(page)} filings")
        ...     # Process each page
    """
    current_page = get_current_filings(form=form, owner=owner, page_size=page_size)

    while current_page is not None:
        yield current_page
        current_page = current_page.next()