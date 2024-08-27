import itertools
import pickle
import re
import webbrowser
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import Tuple, List, Dict, Union, Optional, Any, cast

import httpx
import numpy as np
import orjson as json
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq
import pytz
from bs4 import BeautifulSoup
from fastcore.parallel import parallel
from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from edgar._markdown import html_to_markdown, text_to_markdown
from edgar._party import Address
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.xmltools import child_text
from edgar.attachments import FilingHomepage, Attachment, Attachments, AttachmentServer
from edgar.core import (log, display_size, sec_edgar,
                        filter_by_date,
                        filter_by_form,
                        filter_by_cik,
                        filter_by_ticker,
                        listify,
                        InvalidDateException, IntString, DataPager)
from edgar.documents import HtmlDocument, get_clean_html
from edgar.filingheader import FilingHeader
from edgar.headers import FilingDirectory, IndexHeaders
from edgar.htmltools import html_sections
from edgar.httprequests import download_file, download_text, download_text_between_tags
from edgar.httprequests import get_with_retry

from edgar.xbrl import XBRLData, XBRLInstance, get_xbrl_object
from edgar.reference import describe_form
from edgar.search import BM25Search, RegexSearch

""" Contain functionality for working with SEC filing indexes and filings

The module contains the following functions

- `get_filings(year, quarter, index)`

"""

__all__ = [
    'Filing',
    'Filings',
    'get_filings',
    'FilingHeader',
    'FilingsState',
    'Attachment',
    'Attachments',
    'FilingHomepage',
    'CurrentFilings',
    'available_quarters',
    'get_current_filings',
    'get_by_accession_number',
    'filing_date_to_year_quarters'
]

full_index_url = "https://www.sec.gov/Archives/edgar/full-index/{}/QTR{}/{}.{}"
daily_index_url = "https://www.sec.gov/Archives/edgar/daily-index/{}/QTR{}/{}.{}.idx"

filing_homepage_url_re = re.compile(f"{sec_edgar}/data/[0-9]{1,}/[0-9]{10}-[0-9]{2}-[0-9]{4}-index.html")

full_or_daily = ['daily', 'full']
index_types = ['form', 'company', 'xbrl']
file_types = ['gz', 'idx']

form_index = "form"
xbrl_index = "xbrl"
company_index = "company"

max_concurrent_http_connections = 10
quarters_in_year: List[int] = list(range(1, 5))

YearAndQuarter = Tuple[int, int]
YearAndQuarters = List[YearAndQuarter]
Years = Union[int, List[int], range]
Quarters = Union[int, List[int], range]

accession_number_re = re.compile(r"\d{10}-\d{2}-\d{6}$")

xbrl_document_types = ['XBRL INSTANCE DOCUMENT', 'XBRL INSTANCE FILE', 'EXTRACTED XBRL INSTANCE DOCUMENT']


def current_year_and_quarter() -> Tuple[int, int]:
    # Define the Eastern timezone
    eastern = pytz.timezone('America/New_York')

    # Get the current time in Eastern timezone
    now_eastern = datetime.now(eastern)

    # Calculate the current year and quarter
    current_year, current_quarter = now_eastern.year, (now_eastern.month - 1) // 3 + 1

    return current_year, current_quarter


def is_valid_filing_date(filing_date: str) -> bool:
    if ":" in filing_date:
        # Check for only one colon
        if filing_date.count(":") > 1:
            return False
        start_date, end_date = filing_date.split(":")
        if start_date:
            if not is_valid_date(start_date):
                return False
        if end_date:
            if not is_valid_date(end_date):
                return False
    else:
        if not is_valid_date(filing_date):
            return False

    return True


def is_valid_date(date_str: str, date_format: str = "%Y-%m-%d") -> bool:
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, date_str):
        return False

    try:
        datetime.strptime(date_str, date_format)
        return True
    except ValueError:
        return False


def get_previous_quarter(year, quarter) -> Tuple[int, int]:
    # Given a year and quarter return the previous quarter
    if quarter == 1:
        return year - 1, 4
    else:
        return year, quarter - 1


@lru_cache(maxsize=1)
def available_quarters() -> YearAndQuarters:
    """
    Get a list of year and quarter tuples
    :return:
    """
    current_year, current_quarter = current_year_and_quarter()
    start_quarters = [(1994, 3), (1994, 4)]
    in_between_quarters = list(itertools.product(range(1995, current_year), range(1, 5)))
    end_quarters = list(itertools.product([current_year], range(1, current_quarter + 1)))
    return start_quarters + in_between_quarters + end_quarters


def expand_quarters(year: Years,
                    quarter: Optional[Quarters] = None) -> YearAndQuarters:
    """
    Expand the list of years and a list of quarters to a full list of tuples covering the full range
    :param year: The year or years
    :param quarter: The quarter or quarters
    :return:
    """
    years = listify(year)
    quarters = listify(quarter) if quarter else quarters_in_year
    return [yq
            for yq in itertools.product(years, quarters)
            if yq in available_quarters()
            ]


def filing_date_to_year_quarters(filing_date: str) -> List[Tuple[int, int]]:
    if ":" in filing_date:
        start_date, end_date = filing_date.split(":")

        if not start_date:
            start_date = "1994-06-01"

        if not end_date:
            end_date = date.today().strftime("%Y-%m-%d")

        start_year, start_month, _ = map(int, start_date.split("-"))
        end_year, end_month, _ = map(int, end_date.split("-"))

        start_quarter = (start_month - 1) // 3 + 1
        end_quarter = (end_month - 1) // 3 + 1

        result = []
        for year in range(start_year, end_year + 1):
            if year == start_year and year == end_year:
                quarters = range(start_quarter, end_quarter + 1)
            elif year == start_year:
                quarters = range(start_quarter, 5)
            elif year == end_year:
                quarters = range(1, end_quarter + 1)
            else:
                quarters = range(1, 5)

            for quarter in quarters:
                result.append((year, quarter))

        return result
    else:
        year, month, _ = map(int, filing_date.split("-"))
        quarter = (month - 1) // 3 + 1
        return [(year, quarter)]


class FileSpecs:
    """
    A specification for a fixed width file
    """

    def __init__(self, specs: List[Tuple[str, Tuple[int, int], pa.lib.DataType]]):
        self._spec_type = specs[0][0].title()
        self.splits = list(zip(*specs))[1]
        self.schema = pa.schema(
            [
                pa.field(name, datatype)
                for name, _, datatype in specs
            ]
        )

    def __str__(self):
        return f"{self._spec_type} File Specs"


form_specs = FileSpecs(
    [("form", (0, 12), pa.string()),
     ("company", (12, 74), pa.string()),
     ("cik", (74, 82), pa.int32()),
     ("filing_date", (85, 97), pa.string()),
     ("accession_number", (97, 141), pa.string())
     ]
)
company_specs = FileSpecs(
    [("company", (0, 62), pa.string()),
     ("form", (62, 74), pa.string()),
     ("cik", (74, 82), pa.int32()),
     ("filing_date", (85, 97), pa.string()),
     ("accession_number", (97, 141), pa.string())
     ]
)


def read_fixed_width_index(index_text: str,
                           file_specs: FileSpecs) -> pa.Table:
    """
    Read the index text as a fixed width file
    :param index_text: The index text as downloaded from SEC Edgar
    :param file_specs: The file specs containing the column definitions
    :return:
    """
    # Treat as a single array
    lines = index_text.rstrip('\n').split('\n')
    # Find where the data starts
    data_start = 0
    for index, line in enumerate(lines):
        if line.startswith("-----"):
            data_start = index + 1
            break
    data_lines = lines[data_start:]
    array = pa.array(data_lines)

    # Then split into separate arrays by file specs
    arrays = [
        pc.utf8_trim_whitespace(
            pc.utf8_slice_codeunits(array, start=start, stop=stop))
        for start, stop,
        in file_specs.splits
    ]

    # Change the CIK to int
    arrays[2] = pa.compute.cast(arrays[2], pa.int32())

    # Convert filingdate from string to date
    # Some files have %Y%m-%d other %Y%m%d
    date_format = '%Y-%m-%d' if len(arrays[3][0].as_py()) == 10 else '%Y%m%d'
    arrays[3] = pc.cast(pc.strptime(arrays[3], date_format, 'us'), pa.date32())

    # Get the accession number from the file directory_or_file
    arrays[4] = pa.compute.utf8_slice_codeunits(
        pa.compute.utf8_rtrim(arrays[4], characters=".txt"), start=-20)

    return pa.Table.from_arrays(
        arrays=arrays,
        names=list(file_specs.schema.names),
    )


def read_pipe_delimited_index(index_text: str) -> pa.Table:
    """
    Read the index file as a pipe delimited index
    :param index_text: The index text as read from SEC Edgar
    :return: The index data as a pyarrow table
    """
    index_table = pa_csv.read_csv(
        BytesIO(index_text.encode()),
        parse_options=pa_csv.ParseOptions(delimiter="|"),
        read_options=pa_csv.ReadOptions(skip_rows=10,
                                        column_names=['cik', 'company', 'form', 'filing_date', 'accession_number'])
    )
    index_table = index_table.set_column(
        0,
        "cik",
        pa.compute.cast(index_table[0], pa.int32())
    ).set_column(4,
                 "accession_number",
                 pc.utf8_slice_codeunits(index_table[4], start=-24, stop=-4))
    return index_table


def fetch_filing_index(year_and_quarter: YearAndQuarter,
                       index: str
                       ):
    year, quarter = year_and_quarter
    url = full_index_url.format(year, quarter, index, "gz")
    index_table = fetch_filing_index_at_url(url, index)
    return (year, quarter), index_table


def fetch_daily_filing_index(date: str,
                             index: str = 'form'):
    year, month, day = date.split("-")
    quarter = (int(month) - 1) // 3 + 1
    url = daily_index_url.format(year, quarter, index, date.replace("-", ""))
    index_table = fetch_filing_index_at_url(url, index)
    return index_table


def fetch_filing_index_at_url(url: str,
                              index: str):
    index_text = download_text(url=url)
    assert index_text is not None
    if index == "xbrl":
        index_table: pa.Table = read_pipe_delimited_index(str(index_text))
    else:
        # Read as a fixed width index file
        file_specs: FileSpecs = form_specs if index == "form" else company_specs
        index_table: pa.Table = read_fixed_width_index(index_text,
                                                       file_specs=file_specs)
    return index_table


def _empty_filing_index():
    schema = pa.schema([
        ('form', pa.string()),
        ('company', pa.string()),
        ('cik', pa.int32()),
        ('filing_date', pa.date32()),
        ('accession_number', pa.string()),
    ])

    # Create an empty table with the defined schema
    return pa.Table.from_arrays([
        pa.array([], type=pa.string()),
        pa.array([], type=pa.string()),
        pa.array([], type=pa.int32()),
        pa.array([], type=pa.date32()),
        pa.array([], type=pa.string()),
    ], schema=schema)


def get_filings_for_quarters(year_and_quarters: YearAndQuarters,
                             index="form") -> pa.Table:
    """
    Get the filings for the quarters
    :param year_and_quarters:
    :param index: The index to use - "form", "company", or "xbrl"
    :return:
    """

    if len(year_and_quarters) == 1:
        _, final_index_table = fetch_filing_index(year_and_quarter=year_and_quarters[0],
                                                  index=index)
    else:
        quarters_and_indexes = parallel(fetch_filing_index,
                                        items=year_and_quarters,
                                        index=index,
                                        threadpool=True,
                                        progress=True
                                        )
        quarter_and_indexes_sorted = sorted(quarters_and_indexes, key=lambda d: d[0])
        index_tables = [fd[1] for fd in quarter_and_indexes_sorted]
        final_index_table: pa.Table = pa.concat_tables(index_tables, mode="default")
    return final_index_table


@dataclass
class FilingsState:
    page_start: int
    num_filings: int


class Filings:
    """
    A container for filings
    """

    def __init__(self,
                 filing_index: pa.Table,
                 original_state: Optional[FilingsState] = None):
        self.data: pa.Table = filing_index
        self.data_pager = DataPager(self.data)
        # This keeps track of where the index should start in case this is just a page in the Filings
        self._original_state = original_state or FilingsState(0, len(self.data))

    def to_pandas(self, *columns) -> pd.DataFrame:
        """Return the filing index as a python dataframe"""
        df = self.data.to_pandas()
        return df.filter(columns) if len(columns) > 0 else df

    def save_parquet(self, location: str):
        """Save the filing index as parquet"""
        pq.write_table(self.data, location)

    def save(self, location: str):
        """Save the filing index as parquet"""
        self.save_parquet(location)

    def get_filing_at(self, item: int):
        """Get the filing at the specified index"""
        return Filing(
            cik=self.data['cik'][item].as_py(),
            company=self.data['company'][item].as_py(),
            form=self.data['form'][item].as_py(),
            filing_date=self.data['filing_date'][item].as_py(),
            accession_no=self.data['accession_number'][item].as_py(),
        )

    @property
    def date_range(self) -> Tuple[datetime, datetime]:
        """Return a tuple of the start and end dates in the filing index"""
        min_max_dates: dict[str, datetime] = pc.min_max(self.data['filing_date']).as_py()
        return min_max_dates['min'], min_max_dates['max']

    @property
    def start_date(self) -> Optional[str]:
        """Return the start date for the filings"""
        return str(self.date_range[0]) if self.date_range[0] else self.date_range[0]

    @property
    def end_date(self) -> str:
        """Return the end date for the filings"""
        return str(self.date_range[1]) if self.date_range[1] else self.date_range[1]

    def latest(self, n: int = 1):
        """Get the latest n filings"""
        sort_indices = pc.sort_indices(self.data, sort_keys=[("filing_date", "descending")])
        sort_indices_top = sort_indices[:min(n, len(sort_indices))]
        latest_filing_index = pc.take(data=self.data, indices=sort_indices_top)
        filings = Filings(latest_filing_index)
        if len(filings) == 1:
            return filings[0]
        return filings

    def filter(self,
               form: Optional[Union[str, List[IntString]]] = None,
               amendments: bool = False,
               filing_date: Optional[str] = None,
               date: Optional[str] = None,
               cik: Union[IntString, List[IntString]] = None,
               ticker: Union[str, List[str]] = None):
        """
        Get some filings

        >>> filings = get_filings()

        Filter the filings

        On a date
        >>> filings.filter(date="2020-01-01")

        Up to a date
        >>> filings.filter(date=":2020-03-01")

        From a date
        >>> filings.filter(date="2020-01-01:")

        # Between dates
        >>> filings.filter(date="2020-01-01:2020-03-01")

        :param form: The form or list of forms to filter by
        :param amendments: Whether to include amendments to the forms e.g. include "10-K/A" if filtering for "10-K"
        :param filing_date: The filing date
        :param date: An alias for the filing date
        :param cik: The CIK or list of CIKs to filter by
        :param ticker: The ticker or list of tickers to filter by
        :return: The filtered filings
        """
        filing_index = self.data
        forms = form

        if isinstance(forms, list):
            forms = [str(f) for f in forms]

        # Filter by form
        if forms:
            filing_index = filter_by_form(filing_index, form=forms, amendments=amendments)

        # filing_date and date are aliases
        filing_date = filing_date or date
        if filing_date:
            try:
                filing_index = filter_by_date(filing_index, filing_date, 'filing_date')
            except InvalidDateException as e:
                log.error(e)
                return None

        # Filter by cik
        if cik:
            filing_index = filter_by_cik(filing_index, cik)

        if ticker:
            filing_index = filter_by_ticker(filing_index, ticker)

        return Filings(filing_index)

    def _head(self, n):
        assert n > 0, "The number of filings to select - `n`, should be greater than 0"
        return self.data.slice(0, min(n, len(self.data)))

    def head(self, n: int):
        """Get the first n filings"""
        selection = self._head(n)
        return Filings(selection)

    def _tail(self, n):
        assert n > 0, "The number of filings to select - `n`, should be greater than 0"
        return self.data.slice(max(0, len(self.data) - n), len(self.data))

    def tail(self, n: int):
        """Get the last n filings"""
        selection = self._tail(n)
        return Filings(selection)

    def _sample(self, n: int):
        assert len(self) >= n > 0, \
            "The number of filings to select - `n`, should be greater than 0 and less than the number of filings"
        return self.data.take(np.random.choice(len(self), n, replace=False)).sort_by([("filing_date", "descending")])

    def sample(self, n: int):
        """Get a random sample of n filings"""
        selection = self._sample(n)
        return Filings(selection)

    @property
    def empty(self) -> bool:
        return len(self.data) == 0

    def current(self):
        """Display the current page ... which is the default for this filings object"""
        return self

    def next(self):
        """Show the next page"""
        data_page = self.data_pager.next()
        if data_page is None:
            log.warning("End of data .. use prev() \u2190 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = FilingsState(page_start=start_index, num_filings=len(self))
        return Filings(data_page, original_state=filings_state)

    def previous(self):
        """
        Show the previous page of the data
        :return:
        """
        data_page = self.data_pager.previous()
        if data_page is None:
            log.warning(" No previous data .. use next() \u2192 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = FilingsState(page_start=start_index, num_filings=len(self))
        return Filings(data_page, original_state=filings_state)

    def prev(self):
        """Alias for self.previous()"""
        return self.previous()

    def _get_by_accession_number(self, accession_number: str):
        mask = pc.equal(self.data['accession_number'], accession_number)
        idx = mask.index(True).as_py()
        if idx > -1:
            return self.get_filing_at(idx)

    def get(self, index_or_accession_number: IntString):
        """
        First, get some filings
        >>> filings = get_filings()

        Get the Filing at that index location or that has the accession number
        >>> filings.get(100)

        >>> filings.get("0001721868-22-000010")

        :param index_or_accession_number:
        :return:
        """
        if isinstance(index_or_accession_number, int) or index_or_accession_number.isdigit():
            return self.get_filing_at(int(index_or_accession_number))
        else:
            accession_number = index_or_accession_number.strip()
            mask = pc.equal(self.data['accession_number'], accession_number)
            idx = mask.index(True).as_py()
            if idx > -1:
                return self.get_filing_at(idx)
            if not accession_number_re.match(accession_number):
                log.warning(
                    f"Invalid accession number [{accession_number}]"
                    "\n  valid accession number [0000000000-00-000000]"
                )

    def find(self,
             company_search_str: str):
        from edgar.entities import find_company

        # Search for the company
        search_results = find_company(company_search_str)

        return self.filter(cik=search_results.ciks)

    def to_dict(self, max_rows: int = 1000) -> Dict[str, Any]:
        """Return the filings as a json string but only the first max_rows records"""
        return cast(Dict[str, Any], self.to_pandas().head(max_rows).to_dict(orient="records"))

    def __getitem__(self, item):
        return self.get_filing_at(item)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n < len(self.data):
            filing: Filing = self[self.n]
            self.n += 1
            return filing
        else:
            raise StopIteration

    @property
    def summary(self):
        return (f"Showing {self.data_pager.page_size} of "
                f"{self._original_state.num_filings:,} filings")

    def _page_index(self) -> range:
        """Create the range index to set on the page dataframe depending on where in the data we are
        """
        if self._original_state:
            return range(self._original_state.page_start,
                         self._original_state.page_start
                         + min(self.data_pager.page_size, len(self.data)))  # set the index to the size of the page
        else:
            return range(*self.data_pager._current_range)

    def __rich__(self) -> Panel:
        page = self.data_pager.current().to_pandas()
        page.index = self._page_index()

        # Show paging information
        page_info = f"Showing {len(page)} of {self._original_state.num_filings:,} filings"

        return Panel(
            Group(
                df_to_rich_table(page, max_rows=len(page)),
                Text(page_info)
            ), title="Filings"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


def get_filings(year: Optional[Years] = None,
                quarter: Optional[Quarters] = None,
                form: Optional[Union[str, List[IntString]]] = None,
                amendments: bool = True,
                filing_date: Optional[str] = None,
                index="form") -> Optional[Filings]:
    """
    Downloads the filing index for a given year or list of years, and a quarter or list of quarters.

    So you can download for 2020, [2020,2021,2022] or range(2020, 2023)

    Examples

    >>> from edgar import get_filings

    >>> filings_ = get_filings(2021) # Get filings for 2021

    >>> filings_ = get_filings(2021, 4) # Get filings for 2021 Q4

    >>> filings_ = get_filings(2021, [3,4]) # Get filings for 2021 Q3 and Q4

    >>> filings_ = get_filings([2020, 2021]) # Get filings for 2020 and 2021

    >>> filings_ = get_filings([2020, 2021], 4) # Get filings for Q4 of 2020 and 2021

    >>> filings_ = get_filings(range(2010, 2021)) # Get filings between 2010 and 2021 - does not include 2021

    >>> filings_ = get_filings(2021, 4, form="D") # Get filings for 2021 Q4 for form D

    >>> filings_ = get_filings(2021, 4, filing_date="2021-10-01") # Get filings for 2021 Q4 on "2021-10-01"

    >>> filings_ = get_filings(2021, 4, filing_date="2021-10-01:2021-10-10") # Get filings for 2021 Q4 between
                                                                            # "2021-10-01" and "2021-10-10"


    :param year The year of the filing
    :param quarter The quarter of the filing
    :param form The form or forms as a string e.g. "10-K" or a List ["10-K", "8-K"]
    :param amendments If True will expand the list of forms to include amendments e.g. "10-K/A"
    :param filing_date The filing date to filter by in YYYY-MM-DD format
                e.g. filing_date="2022-01-17" or filing_date="2022-01-17:2022-02-28"
    :param index The index type - "form" or "company" or "xbrl"
    :return:
    """
    # Get the year or default to the current year
    using_default_year = False
    if filing_date:
        if not is_valid_filing_date(filing_date):
            log.warning("""Provide a valid filing date in the format YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD""")
            return None
        year_and_quarters = filing_date_to_year_quarters(filing_date)
    elif not year:
        year, quarter = current_year_and_quarter()
        year_and_quarters: YearAndQuarters = expand_quarters(year, quarter)
        using_default_year = True
    else:
        year_and_quarters: YearAndQuarters = expand_quarters(year, quarter)

    if len(year_and_quarters) == 0:
        log.warning(f"""
    Provide a year between 1994 and {datetime.now().year} and optionally a quarter (1-4) for which the SEC has filings. 
    
        e.g. filings = get_filings(2023) OR
             filings = get_filings(2023, 1)
    
    (You specified the year {year} and quarter {quarter})   
        """)
        return None
    try:
        filing_index = get_filings_for_quarters(year_and_quarters, index=index)
    except httpx.HTTPStatusError as e:
        if using_default_year and 'AccessDenied' in e.response.text:
            previous_quarter = [get_previous_quarter(year, quarter)]
            filing_index = get_filings_for_quarters(previous_quarter, index=index)
        else:
            raise

    filings = Filings(filing_index)

    if form or filing_date:
        filings = filings.filter(form=form, amendments=amendments, filing_date=filing_date)

    if not filings:
        return None

    # Finally sort by filing date
    filings = Filings(filings.data.sort_by([("filing_date", "descending")]))
    return filings


"""
Get the current filings from the SEC. Use this to get the filings filed after the 5:30 deadline
"""
GET_CURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom&owner=only&count=100"
title_regex = re.compile(r"(.*) - (.*) \((\d+)\) \((.*)\)")
summary_regex = re.compile(r'<b>([^<]+):</b>\s+([^<\s]+)')


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

        entries.append({'form': form_type,
                        'company': company_name,
                        'cik': cik,
                        'filing_date': filing_date,
                        'accession_number': accession_number})
    return entries


def get_current_filings(form: str = '',
                        owner: str = 'include',
                        page_size: int = 40):
    """
    Get the current filings from the SEC
    :return: The current filings from the SEC
    """
    owner = owner if owner in ['include', 'exclude', 'only'] else 'include'
    page_size = page_size if page_size in [10, 20, 40, 80, 100] else 40
    start = 0

    entries = get_current_entries_on_page(count=page_size, start=start, form=form, owner=owner)
    if not entries:
        return CurrentFilings(filing_index=_empty_filing_index(), owner=owner, form=form, page_size=page_size)
    return CurrentFilings(filing_index=pa.Table.from_pylist(entries), owner=owner, form=form, page_size=page_size)


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
        next_entries = get_current_entries_on_page(start=start, count=self._page_size, form=self.form)
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
        page: pd.DataFrame = self.to_pandas()

        # compute the index from the start and page_size and set it as the index of the page
        page.index = range(self._start - 1, self._start - 1 + len(page))

        return Panel(
            Group(
                df_to_rich_table(page),
                Text(f"Filings {page.index.min()} to {page.index.max()}")
            ), title=f"Current Filings on {self.start_date}"
        )


@lru_cache(maxsize=8)
def _get_cached_filings(year: Optional[Years] = None,
                        quarter: Optional[Quarters] = None,
                        form: Optional[Union[str, List[IntString]]] = None,
                        amendments: bool = True,
                        filing_date: Optional[str] = None,
                        index="form") -> Union[Filings, None]:
    # Get the filings but cache the result
    return get_filings(year=year, quarter=quarter, form=form, amendments=amendments, filing_date=filing_date,
                       index=index)


def parse_filing_header(content):
    data = {}
    current_key = None

    lines = content.split('\n')
    for line in lines:
        if line.endswith(':'):
            current_key = line[:-1]  # Remove the trailing colon
            data[current_key] = {}
        elif current_key and ':' in line:
            key, value = map(str.strip, line.split(':', 1))
            data[current_key][key] = value

    return data


def _create_address_table(business_address: Address, mailing_address: Address):
    address_table = Table("Type", "Street1", "Street2", "City", "State", "Zipcode",
                          title="\U0001F4EC Addresses", box=box.SIMPLE)
    if business_address:
        address_table.add_row("\U0001F3E2 Business Address",
                              business_address.street1,
                              business_address.street2,
                              business_address.city,
                              business_address.state_or_country,
                              business_address.zipcode)

    if mailing_address:
        address_table.add_row("\U0001F4ED Mailing Address",
                              mailing_address.street1,
                              mailing_address.street2,
                              mailing_address.city,
                              mailing_address.state_or_country,
                              mailing_address.zipcode)
    return address_table


class Filing:
    """
    A single SEC filing. Allow you to access the documents and data for that filing
    """

    def __init__(self,
                 cik: int,
                 company: str,
                 form: str,
                 filing_date: str,
                 accession_no: str):
        self.cik = cik
        self.company = company
        self.form = form
        self.filing_date = filing_date
        self.accession_no = accession_no
        self._filing_homepage = None

    @property
    def accession_number(self):
        return self.accession_no

    @property
    def document(self):
        """
        :return: The primary display document on the filing, generally HTML but can be XHTML
        """
        return self.homepage.primary_html_document

    @property
    def primary_documents(self):
        """
        :return: a list of the primary documents on the filing, generally HTML or XHTML and optionally XML
        """
        return self.homepage.primary_documents

    @property
    def attachments(self):
        # Return all the attachments on the filing
        return self.homepage.attachments

    @property
    def exhibits(self):
        # Return all the exhibits on the filing
        return self.homepage.attachments.exhibits

    def html(self) -> Optional[str]:
        """Returns the html contents of the primary document if it is html"""
        if self.document and not self.document.is_binary() and not self.document.empty:
            return str(self.document.download())

    @lru_cache(maxsize=4)
    def xml(self) -> Optional[str]:
        """Returns the xml contents of the primary document if it is xml"""
        xml_document = self.homepage.primary_xml_document
        if xml_document:
            return str(xml_document.download())

    @lru_cache(maxsize=4)
    def text(self) -> str:
        """Convert the html of the main filing document to text"""
        html_content = self.html()
        if html_content:
            html_document = HtmlDocument.from_html(html_content, extract_data=False)
            if html_document:
                return html_document.text
            else:
                return download_text_between_tags(self.text_url, "TEXT")
        else:
            # Some Form types like UPLOAD don't have a primary document. Look for a TEXT EXTRACT attachment
            # Look for an attachment that is TEXT EXTRACT
            text_extract_attachments = self.attachments.query("document_type == 'TEXT-EXTRACT'")
            if len(text_extract_attachments) > 0 and text_extract_attachments[0] is not None:
                text_extract_attachment = text_extract_attachments[0]
                assert text_extract_attachment is not None
                return download_text_between_tags(text_extract_attachment.url, "TEXT")
            else:
                # Use the full text submission
                return download_text_between_tags(self.text_url, "TEXT")

    def full_text_submission(self) -> str:
        """Return the complete text submission file"""
        downloaded = download_file(self.text_url, as_text=True)
        assert downloaded is not None
        return str(downloaded)

    def markdown(self) -> str:
        """return the markdown version of this filing html"""
        html = self.html()
        if html:
            clean_html = get_clean_html(html)
            if clean_html:
                return html_to_markdown(clean_html)
        text_content = self.text()
        return text_to_markdown(text_content)

    def view(self):
        """Preview this filing's primary document as markdown. This should display in the console"""
        print(self.text())

    def xbrl(self) -> Optional[Union[XBRLData, XBRLInstance]]:
        """
        Get the XBRL document for the filing, parsed and as a FilingXbrl object
        :return: Get the XBRL document for the filing, parsed and as a FilingXbrl object, or None
        """
        return get_xbrl_object(self)

    def serve(self, port: int = 8000) -> AttachmentServer:
        """Serve the filings on a local server
        port: The port to serve the filings on
        """
        return self.attachments.serve(port=port)

    def save(self, directory_or_file: PathLike):
        """Save the filing to a directory path or a file using pickle.dump

            If directory_or_file is a directory then the final file will be

            '<directory>/<accession_number>.pkl'

            Otherwise, save to the file passed in
        """
        filing_path = Path(directory_or_file)
        if filing_path.is_dir():
            filing_path = filing_path / f"{self.accession_no}.pkl"
        with filing_path.open("wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: PathLike):
        """Load a filing from a json file"""
        path = Path(path)
        with path.open("rb") as file:
            return pickle.load(file)

    @property
    @lru_cache(maxsize=1)
    def filing_directory(self) -> FilingDirectory:
        return FilingDirectory.load(self.base_dir)

    @property
    @lru_cache(maxsize=1)
    def index_headers(self) -> IndexHeaders:
        index_headers_url = f"{self.base_dir}/{self.accession_no}-index-headers.html"
        index_header_text = download_text(index_headers_url)
        return IndexHeaders.load(index_header_text)

    def to_dict(self) -> Dict[str, Union[str, int]]:
        """Return the filing as a Dict string"""
        return {'accession_no': self.accession_no,
                'cik': self.cik,
                'company': self.company,
                'form': self.form,
                'filing_date': self.filing_date}

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int]]):
        """Create a Filing from a dictionary.
        Thw dict must have the keys cik, company, form, filing_date, accession_no
        """
        assert all(key in data for key in ['cik', 'company', 'form', 'filing_date', 'accession_no']), \
            "The dict must have the keys cik, company, form, filing_date, accession_no"
        return cls(cik=int(data['cik']),
                   company=str(data['company']),
                   form=str(data['form']),
                   filing_date=str(data['filing_date']),
                   accession_no=str(data['accession_no']))

    @classmethod
    def from_json(cls, path: str):
        """Create a Filing from a JSON file"""
        with open(path, 'r') as file:
            data = json.load(file)
            return cls.from_dict(data)

    @property
    @lru_cache(maxsize=1)
    def header(self):
        sec_header_content = download_text_between_tags(self.text_url, "SEC-HEADER")
        try:
            return FilingHeader.parse_from_sgml_text(sec_header_content)
        except Exception:
            # Try again with preprocessing - likely with a filing from the 1990's
            return FilingHeader.parse_from_sgml_text(sec_header_content, preprocess=True)

    def data_object(self):
        """ Get this filing as the data object that it might be"""
        from edgar import obj
        return obj(self)

    def obj(self):
        """Alias for data_object()"""
        return self.data_object()

    def open_homepage(self):
        """Open the homepage in the browser"""
        webbrowser.open(self.homepage_url)

    def open(self):
        """Open the main filing document"""
        assert self.document is not None
        webbrowser.open(self.document.url)

    @lru_cache(maxsize=1)
    def sections(self) -> List[str]:
        html = self.html()
        assert html is not None
        return html_sections(html)

    @lru_cache(maxsize=1)
    def __get_bm25_search_index(self):
        return BM25Search(self.sections())

    @lru_cache(maxsize=1)
    def __get_regex_search_index(self):
        return RegexSearch(self.sections())

    def search(self,
               query: str,
               regex=False):
        """Search for the query string in the filing HTML"""
        if regex:
            return self.__get_regex_search_index().search(query)
        return self.__get_bm25_search_index().search(query)

    @property
    def homepage_url(self) -> str:
        return f"{sec_edgar}/data/{self.cik}/{self.accession_no}-index.html"

    @property
    def text_url(self) -> str:
        return f"{self.base_dir}/{self.accession_no}.txt"

    @property
    def index_header_url(self) -> str:
        return f"{self.base_dir}/index-headers.html"

    @property
    def base_dir(self) -> str:
        return f"{sec_edgar}/data/{self.cik}/{self.accession_no.replace('-', '')}"

    @property
    def url(self) -> str:
        return self.homepage_url

    @property
    def homepage(self):
        """
        Get the homepage for the filing
        :return: the FilingHomepage
        """
        if not self._filing_homepage:
            self._filing_homepage = FilingHomepage.load(self.homepage_url)
        return self._filing_homepage

    @property
    def home(self):
        """Alias for homepage"""
        return self.homepage

    @lru_cache(maxsize=1)
    def get_entity(self):
        """Get the company to which this filing belongs"""
        "Get the company for cik. Cache for performance"
        from edgar.entities import CompanyData
        return CompanyData.for_cik(self.cik)

    @lru_cache(maxsize=1)
    def as_company_filing(self):
        """Get this filing as a company filing. Company Filings have more information"""
        company = self.get_entity()
        if not company:
            return None

        filings = company.get_filings(accession_number=self.accession_no)
        if filings and not filings.empty:
            return filings[0]

    @lru_cache(maxsize=1)
    def related_filings(self):
        """Get all the filings related to this one
        There is no file number on this base Filing class so first get the company,

        then this filing then get the related filings
        """
        company = self.get_entity()
        if not company:
            return

        filings = company.get_filings(accession_number=self.accession_no)
        if filings and not filings.empty:
            file_number = filings[0].file_number
            return company.get_filings(file_number=file_number,
                                       sort_by=[("filing_date", "ascending"), ("accession_number", "ascending")])

    def __hash__(self):
        return hash(self.accession_no)

    def __eq__(self, other):
        return isinstance(other, Filing) and self.accession_no == other.accession_no

    def __ne__(self, other):
        return not self == other

    def summary(self) -> pd.DataFrame:
        """Return a summary of this filing as a dataframe"""
        return pd.DataFrame([{"Accession Number": self.accession_no,
                              "Filing Date": self.filing_date,
                              "Company": self.company,
                              "CIK": self.cik}]).set_index("Accession Number")

    def __str__(self):
        """
        Return a string version of this filing e.g.

        Filing(form='10-K', filing_date='2018-03-08', company='CARBO CERAMICS INC',
              cik=1009672, accession_no='0001564590-18-004771')
        :return:
        """
        return (f"Filing(form='{self.form}', filing_date='{self.filing_date}', company='{self.company}', "
                f"cik={self.cik}, accession_no='{self.accession_no}')")

    def __rich__(self):
        """
        Produce a table version of this filing e.g.
        ┌──────────────────────┬──────┬────────────┬────────────────────┬─────────┐
        │                      │ form │ filing_date│ company            │ cik     │
        ├──────────────────────┼──────┼────────────┼────────────────────┼─────────┤
        │ 0001564590-18-004771 │ 10-K │ 2018-03-08 │ CARBO CERAMICS INC │ 1009672 │
        └──────────────────────┴──────┴────────────┴────────────────────┴─────────┘
        :return: a rich table version of this filing
        """
        summary_table = Table(box=box.ROUNDED, show_header=False)
        summary_table.add_column("Accession#", style="bold deep_sky_blue1", header_style="bold")
        summary_table.add_column("Filed")
        summary_table.add_row(self.accession_no, str(self.filing_date))

        homepage_url = Text(f"\U0001F3E0 {self.homepage_url.replace('//www.', '//')}")
        primary_doc_url = Text(f"\U0001F4C4 {self.document.url.replace('//www.', '//') if self.document else ''}")
        submission_text_url = Text(f"\U0001F4DC {self.text_url.replace('//www.', '//')}")

        links_table = Table(
            "[b]Links[/b]: \U0001F3E0 Homepage \U0001F4C4 Primary Document \U0001F4DC Full Submission Text",
            box=box.ROUNDED)
        links_table.add_row(homepage_url)
        links_table.add_row(primary_doc_url)
        links_table.add_row(submission_text_url)

        return Panel(
            Group(summary_table, links_table),
            title=Text(f"{self.company} [{self.cik}] {self.form} {unicode_for_form(self.form)}", style="bold"),
            subtitle=describe_form(self.form),
            box=box.ROUNDED
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


# These are the columns on the table on the filing homepage
filing_file_cols = ['Seq', 'Description', 'Document', 'Type', 'Size', 'Url']


@dataclass(frozen=True)
class ClassContractSeries:
    cik: str
    url: str


@dataclass(frozen=True)
class ClassContract:
    cik: str
    name: str
    ticker: str
    status: str


@dataclass(frozen=True)
class FilerInfo:
    company_name: str
    identification: str
    addresses: List[str]

    def __rich__(self):
        return Panel(
            Columns([self.identification, Text("   "), self.addresses[0], self.addresses[1]]),
            title=self.company_name
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


def summarize_files(data: pd.DataFrame) -> pd.DataFrame:
    return (data
            .filter(["Seq", "Document", "Description", "Size"])
            .assign(Size=data.Size.apply(display_size))
            .set_index("Seq")
            )


@lru_cache(maxsize=16)
def get_by_accession_number(accession_number: str):
    """Find the filing using the accession number"""
    assert re.match(r"\d{10}-\d{2}-\d{6}", accession_number), \
        f"{accession_number} is not a valid accession number .. should be 10digits-2digits-6digits"
    year = int("19" + accession_number[11:13]) if accession_number[11] == '9' else int("20" + accession_number[11:13])

    if year == datetime.now().year:
        # For the current year create a range of quarters to search from 1 up to the current quarter of the year
        current_quarter = (datetime.now().month - 1) // 3 + 1
        quarters = range(1, current_quarter + 1)
    else:
        # Search all quarters
        quarters = range(1, 5)

    with Status(f"[bold deep_sky_blue1]Searching for filing {accession_number}...", spinner="dots2"):
        for quarter in quarters:
            filings = _get_cached_filings(year=year, quarter=quarter)
            if filings:
                filing = filings.get(accession_number)
                if filing:
                    return filing
    # We haven't found the filing normally so check the most recent SEC filings
    # Check if the year is the current year
    if year == datetime.now().year:
        # Get the most recent filings
        filings = get_current_filings()
        return filings.get(accession_number)


def form_with_amendments(*forms: str):
    return list(forms) + [f"{f}/A" for f in forms]


barchart = '\U0001F4CA'
ticket = '\U0001F3AB'
page_facing_up = '\U0001F4C4'
classical_building = '\U0001F3DB'


def unicode_for_form(form: str):
    if form in ['10-K', '10-Q', '10-K/A', '10-Q/A', '6-K', '6-K/A']:
        return barchart
    elif form in ['3', '4', '5', '3/A', '4/A', '5/A']:
        return ticket
    elif form in ['MA-I', 'MA-I/A', 'MA', 'MA/A']:
        return classical_building
    return page_facing_up
