import itertools
import json
import pickle
import re
import webbrowser
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property, lru_cache
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import httpx
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq
from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from edgar._markdown import text_to_markdown
from edgar._party import Address
from edgar.attachments import Attachment, Attachments, AttachmentServer, FilingHomepage
from edgar.core import (
    DataPager,
    IntString,
    PagingState,
    Quarters,
    YearAndQuarter,
    YearAndQuarters,
    Years,
    cache_except_none,
    current_year_and_quarter,
    filing_date_to_year_quarters,
    is_probably_html,
    is_start_of_quarter,
    listify,
    log,
    parallel_thread_map,
    quarters_in_year,
)
from edgar.config import SEC_ARCHIVE_URL
from edgar.dates import InvalidDateException
from edgar.files.html import Document
from edgar.files.html_documents import get_clean_html
from edgar.files.htmltools import html_sections
from edgar.files.markdown import to_markdown
from edgar.filtering import filter_by_accession_number, filter_by_cik, filter_by_date, filter_by_exchange, filter_by_form, filter_by_ticker
from edgar.formatting import accession_number_text, display_size
from edgar.headers import FilingDirectory, IndexHeaders
from edgar.httprequests import download_file, download_text, download_text_between_tags
from edgar.reference import describe_form
from edgar.reference.tickers import Exchange, find_ticker, find_ticker_safe
from edgar.richtools import Docs, print_rich, repr_rich, rich_to_text
from edgar.search import BM25Search, RegexSearch
from edgar.sgml import FilingHeader, FilingSGML, Reports, Statements
from edgar.storage import is_using_local_storage, local_filing_path
from edgar.xbrl import XBRL, XBRLFilingWithNoXbrlData

""" Contain functionality for working with SEC filing indexes and filings

The module contains the following functions

- `get_filings(year, quarter, index)`

"""

__all__ = [
    'Filing',
    'Filings',
    'get_filings',
    'FilingHeader',
    'PagingState',
    'Attachment',
    'Attachments',
    'FilingHomepage',
    'available_quarters',
    'get_by_accession_number',
    'filing_date_to_year_quarters'
]

from edgar.urls import build_full_index_url, build_daily_index_url

filing_homepage_url_re = re.compile(f"{SEC_ARCHIVE_URL}/data/[0-9]{{1,}}/[0-9]{{10}}-[0-9]{{2}}-[0-9]{{4}}-index.html")

full_or_daily = ['daily', 'full']
index_types = ['form', 'company', 'xbrl']
file_types = ['gz', 'idx']

form_index = "form"
xbrl_index = "xbrl"
company_index = "company"

index_field_delimiter_re = re.compile(r" {2,}")

max_concurrent_http_connections = 10

accession_number_re = re.compile(r"\d{10}-\d{2}-\d{6}$")

xbrl_document_types = ['XBRL INSTANCE DOCUMENT', 'XBRL INSTANCE FILE', 'EXTRACTED XBRL INSTANCE DOCUMENT']


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
    if not quarter:
        _, quarter = current_year_and_quarter()
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


def expand_quarters(year: Union[int, List[int]],
                    quarter: Optional[Union[int, List[int]]] = None) -> YearAndQuarters:
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


class FileSpecs:
    """
    A specification for a fixed width file
    """

    def __init__(self, specs: List[Tuple[str, Tuple[int, int], pa.lib.DataType]]):
        self._spec_type = specs[0][0].title()
        self.splits = list(zip(*specs, strict=False))[1]
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

FORM_INDEX_FORM_COLUMN = 0
COMPANY_INDEX_FORM_COLUMN = -4
INDEX_COLUMN_NAMES = ['form', 'company', 'cik', 'filing_date', 'accession_number']


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


def read_index_file(index_text: str,
                    form_column: int = FORM_INDEX_FORM_COLUMN,
                    filing_date_format:str="%Y-%m-%d") -> pa.Table:
    """
    Read the index text using multiple spaces as delimiter
    """
    # Split into lines and find the data start
    lines = index_text.rstrip('\n').split('\n')
    data_start = 0
    for index, line in enumerate(lines):
        if line.startswith("-----"):
            data_start = index + 1
            break

    # Process data lines
    data_lines = lines[data_start:]

    # Handle empty lines
    if not data_lines:
        return _empty_filing_index()

    # The form and company name can both contain spaces the remaining fields cannot.
    # It is assumed that the form will only contain runs of a single space (e.g. "1-A POS")
    # so splitting on runs of 2 spaces or more will keep form names intact.
    rows = [re.split(index_field_delimiter_re, line.strip()) for line in data_lines if line.strip()]

    # Form names are in a different column depending on the index type.
    forms = pa.array([row[form_column] for row in rows]) 

    # CIKs are always the third-to-last field
    ciks = pa.array([int(row[-3]) for row in rows], type=pa.int32())

    # Dates are always second-to-last field
    dates = pc.strptime(pa.array([row[-2] for row in rows]), filing_date_format, 'us')
    dates = pc.cast(dates, pa.date32())

    # Accession numbers are in the file path
    accession_numbers = pa.array([row[-1][-24:-4] for row in rows])

    # Company names may have runs of more than one space so anything which hasn't already
    # been extracted is concatenated to form the company name.
    if form_column == 0:
        companies = pa.array([" ".join(row[1:-3]) for row in rows])
    else:
        companies = pa.array([" ".join(row[0:form_column]) for row in rows])

    return pa.Table.from_arrays(
        [forms, companies, ciks, dates, accession_numbers],
        names=INDEX_COLUMN_NAMES
    )


def read_form_index_file(index_text: str) -> pa.Table:
    """Read the form index file"""
    return read_index_file(index_text, form_column=FORM_INDEX_FORM_COLUMN)


def read_company_index_file(index_text: str) -> pa.Table:
    """Read the company index file"""
    return read_index_file(index_text, form_column=COMPANY_INDEX_FORM_COLUMN)


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
    url = build_full_index_url(year, quarter, index, "gz")
    try:
        index_table = fetch_filing_index_at_url(url, index)
        return (year, quarter), index_table
    except httpx.HTTPStatusError as e:
        if is_start_of_quarter() and e.response.status_code == 403:
            # Return an empty filing index
            return (year, quarter), _empty_filing_index()
        else:
            raise


def fetch_daily_filing_index(date: str,
                             index: str = 'form'):
    year, month, day = date.split("-")
    quarter = (int(month) - 1) // 3 + 1
    url = build_daily_index_url(int(year), quarter, date.replace("-", ""), "idx")
    index_table = fetch_filing_index_at_url(url, index, filing_date_format='%Y%m%d')
    return index_table


def fetch_filing_index_at_url(url: str,
                              index: str,
                              filing_date_format:str='%Y-%m-%d') -> Optional[pa.Table]:
    index_text = download_text(url=url)
    assert index_text is not None
    if index == "xbrl":
        index_table: pa.Table = read_pipe_delimited_index(str(index_text))
    else:
        # Read as a fixed width index file
        form_column = FORM_INDEX_FORM_COLUMN if index == "form" else COMPANY_INDEX_FORM_COLUMN
        index_table: pa.Table = read_index_file(index_text, form_column=form_column, filing_date_format=filing_date_format)
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
    :return: The filings as a pyarrow table
    """

    if len(year_and_quarters) == 1:
        _, final_index_table = fetch_filing_index(year_and_quarter=year_and_quarters[0],
                                                  index=index)
    else:
        quarters_and_indexes = parallel_thread_map(
            lambda yq: fetch_filing_index(year_and_quarter=yq, index=index),
            year_and_quarters
        )
        quarter_and_indexes_sorted = sorted(quarters_and_indexes, key=lambda d: d[0])
        index_tables = [fd[1] for fd in quarter_and_indexes_sorted]
        final_index_table: pa.Table = pa.concat_tables(index_tables, mode="default")
    return final_index_table


class Filings:
    """
    A container for filings
    """

    def __init__(self,
                 filing_index: pa.Table,
                 original_state: Optional[PagingState] = None):
        self.data: pa.Table = filing_index
        self.data_pager = DataPager(self.data)
        # This keeps track of where the index should start in case this is just a page in the Filings
        self._original_state = original_state or PagingState(0, len(self.data))
        self._hash = None

    @property
    def docs(self):
        return Docs(self)

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

    def download(self, data_directory: Optional[str] = None):
        """
        Download the filings based on the accession numbers in this Filings object.

        This is a convenience method that calls `download_filings` with this object
        as the `filings` parameter.

        Args:
            data_directory: Directory to save the downloaded files. Defaults to the Edgar data directory.
        """
        from edgar.storage import download_filings
        download_filings(data_directory=data_directory, 
                         overwrite_existing=True,
                         filings=self)

    def get_filing_at(self, item: int, enrich: bool = True):
        """Get filing at index, optionally enriching with related entities"""
        # Get the primary filing data
        accession_no = self.data['accession_number'][item].as_py()

        related_entities = []
        if enrich:
            # Use PyArrow to find all entities with same accession number
            # Limit search to nearby entries for performance (+/- 10 positions)
            start = max(0, item - 10)
            end = min(len(self.data), item + 11)

            # Slice the data and search efficiently
            slice_data = self.data.slice(start, end - start)
            mask = pc.equal(slice_data['accession_number'], accession_no)

            for idx in range(len(mask)):
                if mask[idx].as_py():
                    actual_idx = start + idx
                    if actual_idx != item:  # Skip the primary filing
                        related_entities.append({
                            'cik': slice_data['cik'][idx].as_py(),
                            'company': slice_data['company'][idx].as_py()
                        })

        # Create Filing with related entities
        return Filing(
            cik=self.data['cik'][item].as_py(),
            company=self.data['company'][item].as_py(),
            form=self.data['form'][item].as_py(),
            filing_date=self.data['filing_date'][item].as_py(),
            accession_no=accession_no,
            related_entities=related_entities
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

    def filter(self, *,
               form: Optional[Union[str, List[IntString]]] = None,
               amendments: bool = None,
               filing_date: Optional[str] = None,
               date: Optional[str] = None,
               cik: Union[IntString, List[IntString]] = None,
               exchange: Union[str, List[str], Exchange, List[Exchange]] = None,
               ticker: Union[str, List[str]] = None,
               accession_number: Union[str, List[str]] = None) -> 'Filings':
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
        :param exchange: The exchange or list of exchanges to filter by
        :param ticker: The ticker or list of tickers to filter by
        :param accession_number: The accession number or list of accession numbers to filter by
        :return: The filtered filings
        """
        filing_index = self.data
        forms = form

        if isinstance(forms, list):
            forms = [str(f) for f in forms]

        # Filter by form
        if forms:
            filing_index = filter_by_form(filing_index, form=forms, amendments=amendments)
        elif amendments is not None:
            # Get the unique values of the form as a pylist
            forms = list(set([form.replace("/A", "") for form in pc.unique(filing_index['form']).to_pylist()]))
            filing_index = filter_by_form(filing_index, form=forms, amendments=amendments)

        # filing_date and date are aliases
        filing_date = filing_date or date
        if filing_date:
            try:
                filing_index = filter_by_date(filing_index, filing_date, 'filing_date')
            except InvalidDateException as e:
                log.error(e)
                return Filings(_empty_filing_index())

        # Filter by cik
        if cik:
            filing_index = filter_by_cik(filing_index, cik)

        # Filter by exchange
        if exchange:
            filing_index = filter_by_exchange(filing_index, exchange)

        if ticker:
            filing_index = filter_by_ticker(filing_index, ticker)

        # Filter by accession number
        if accession_number:
            filing_index = filter_by_accession_number(filing_index, accession_number=accession_number)

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
            log.warning("End of data .. use previous() \u2190 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = PagingState(page_start=start_index, num_records=len(self))
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
        filings_state = PagingState(page_start=start_index, num_records=len(self))
        return Filings(data_page, original_state=filings_state)

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
        from edgar.entity import find_company

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
                f"{self._original_state.num_records:,} filings")

    def _page_index(self) -> range:
        """Create the range index to set on the page dataframe depending on where in the data we are
        """
        if self._original_state:
            return range(self._original_state.page_start,
                         self._original_state.page_start
                         + min(self.data_pager.page_size, len(self.data)))  # set the index to the size of the page
        else:
            return range(*self.data_pager._current_range)

    def __eq__(self, other):
        # Check if other is Filings or subclass of Filings
        if not isinstance(other, self.__class__) and not issubclass(other.__class__, self.__class__):
            return False

        if len(self) != len(other):
            return False

        if self.start_date != other.start_date or self.end_date != other.end_date:
            return False

        # Handle empty tables
        if len(self) == 0:
            return True  # Two empty tables with same dates are equal

        # Compare just accession_number columns
        return self.data['accession_number'].equals(other.data['accession_number'])


    def __hash__(self):
        if self._hash is None:
            # Base hash components
            hash_components = [self.__class__.__name__, len(self), self.start_date, self.end_date]

            # Only add accession numbers if table is not empty
            if len(self) > 0:
                # Handle different table sizes appropriately
                if len(self) == 1:
                    hash_components.append(self.data['accession_number'][0].as_py())
                elif len(self) == 2:
                    hash_components.append(self.data['accession_number'][0].as_py())
                    hash_components.append(self.data['accession_number'][1].as_py())
                else:
                    hash_components.append(self.data['accession_number'][0].as_py())
                    hash_components.append(self.data['accession_number'][len(self) // 2].as_py())
                    hash_components.append(self.data['accession_number'][len(self) - 1].as_py())

            self._hash = hash(tuple(hash_components))
        return self._hash

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns AI-optimized collection summary for language models.

        This method provides structured information about the filings collection in a markdown-KV format
        that is optimized for AI agent navigation and discovery.

        Args:
            detail: Level of detail to include:
                - 'minimal': Basic collection info (~100 tokens)
                - 'standard': Adds sample entries (~250 tokens)
                - 'full': Adds form breakdown (~400 tokens)

        Returns:
            Markdown-KV formatted context string optimized for LLMs

        Example:
            >>> filings = get_filings(2024, 1, form='C')
            >>> print(filings.to_context('standard'))
            FILINGS COLLECTION

            Total: 150 filings
            Forms: C, C-U, C-AR
            Date Range: 2024-01-01 to 2024-03-31

            AVAILABLE ACTIONS:
              - Use .latest() to get most recent filing
              - Use [index] to access specific filing (e.g., filings[0])
              - Use .filter(form='C') to narrow by form type
              - Use .docs for detailed API documentation

            SAMPLE FILINGS:
              0. Form C - 2024-03-29 - ViiT Health Inc
              1. Form C - 2024-03-28 - Artisan Creative Inc
              2. Form C-U - 2024-03-28 - TechStart LLC
              ... (147 more)
        """
        lines = []

        # Header
        lines.append("FILINGS COLLECTION")
        lines.append("")

        # Always include count
        count = len(self)
        lines.append(f"Total: {count} filings" if count != 1 else "Total: 1 filing")

        # Get unique form types using PyArrow
        if count > 0:
            forms_column = self.data['form']
            unique_forms = sorted(set(forms_column.to_pylist()))

            # Truncate form list if too many to avoid token bloat
            MAX_FORMS_TO_SHOW = 5
            if len(unique_forms) > MAX_FORMS_TO_SHOW:
                shown = ', '.join(unique_forms[:MAX_FORMS_TO_SHOW])
                remaining = len(unique_forms) - MAX_FORMS_TO_SHOW
                lines.append(f"Forms: {shown} (+{remaining} more)")
            else:
                lines.append(f"Forms: {', '.join(unique_forms)}")

            # Get date range
            try:
                start_date, end_date = self.date_range
                lines.append(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            except:
                pass  # Date range not available

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  - Use .latest() to get most recent filing")
        lines.append("  - Use [index] to access specific filing (e.g., filings[0])")
        lines.append("  - Use .filter(form='C') to narrow by form type")
        lines.append("  - Use .docs for detailed API documentation")

        if detail in ['standard', 'full'] and count > 0:
            # Show sample entries
            lines.append("")
            lines.append("SAMPLE FILINGS:")
            sample_size = min(3, count)
            for i in range(sample_size):
                try:
                    form = self.data['form'][i].as_py()
                    filing_date = self.data['filing_date'][i].as_py()
                    company = self.data['company'][i].as_py()
                    lines.append(f"  {i}. Form {form} - {filing_date} - {company}")
                except:
                    pass  # Skip if there's an issue with this entry

            if count > sample_size:
                lines.append(f"  ... ({count - sample_size} more)")

        if detail == 'full' and count > 0:
            # Form breakdown using PyArrow compute
            from collections import Counter
            forms_list = self.data['form'].to_pylist()
            form_counts = Counter(forms_list)

            lines.append("")
            lines.append("FORM BREAKDOWN:")
            for form, cnt in sorted(form_counts.items()):
                lines.append(f"  {form}: {cnt} {'filing' if cnt == 1 else 'filings'}")

        return "\n".join(lines)

    def __rich__(self) -> Panel:
        # Create table with appropriate columns and styling
        table = Table(
            show_header=True,
            header_style="bold",
            show_edge=True,
            expand=False,
            padding=(0, 1),
            box=box.SIMPLE,
            row_styles=["", "bold"]
        )

        # Add columns with specific styling and alignment
        table.add_column("#", style="dim", justify="right")
        table.add_column("Form", width=10)
        table.add_column("CIK", style="dim", width=10, justify="right")
        table.add_column("Ticker", width=6, style="yellow")
        table.add_column("Company", style="bold green", width=38, no_wrap=True)
        table.add_column("Filing Date", width=11)
        table.add_column("Accession Number", width=20)
        table.add_column(" ", width=1, style="cyan dim")  # Group indicator column

        # Get current page from data pager
        current_page = self.data_pager.current()

        # Calculate start index for proper indexing
        start_idx = self._original_state.page_start if self._original_state else self.data_pager.start_index

        # Identify groups of consecutive filings with same accession number
        groups = {}
        accession_numbers = [current_page['accession_number'][i].as_py() for i in range(len(current_page))]

        for i in range(len(accession_numbers)):
            acc_no = accession_numbers[i]

            # Check previous and next accession numbers
            prev_acc = accession_numbers[i-1] if i > 0 else None
            next_acc = accession_numbers[i+1] if i < len(accession_numbers)-1 else None

            if acc_no != prev_acc and acc_no == next_acc:
                groups[i] = '┐'  # Start of group
            elif acc_no == prev_acc and acc_no == next_acc:
                groups[i] = '│'  # Middle of group
            elif acc_no == prev_acc and acc_no != next_acc:
                groups[i] = '┘'  # End of group
            else:
                groups[i] = ' '   # Standalone filing

        # Iterate through rows in current page
        for i in range(len(current_page)):
            cik = current_page['cik'][i].as_py()
            ticker = find_ticker(cik)

            row = [
                str(start_idx + i),
                current_page['form'][i].as_py(),
                str(cik),
                ticker,
                current_page['company'][i].as_py(),
                str(current_page['filing_date'][i].as_py()),
                accession_number_text(current_page['accession_number'][i].as_py()),
                groups.get(i, ' ')  # Add group indicator
            ]
            table.add_row(*row)

        # Show paging information only if there are multiple pages
        elements = [table]

        if self.data_pager.total_pages > 1:
            total_filings = self._original_state.num_records
            current_count = len(current_page)
            start_num = start_idx + 1
            end_num = start_idx + current_count

            page_info = Text.assemble(
                ("Showing ", "dim"),
                (f"{start_num:,}", "bold red"),
                (" to ", "dim"),
                (f"{end_num:,}", "bold red"),
                (" of ", "dim"),
                (f"{total_filings:,}", "bold"),
                (" filings.", "dim"),
                (" Page using ", "dim"),
                ("← prev()", "bold gray54"),
                (" and ", "dim"),
                ("next() →", "bold gray54")
            )

            elements.extend([Text("\n"), page_info])

        # Get the subtitle
        start_date, end_date = self.date_range
        subtitle = f"SEC Filings between {start_date:%Y-%m-%d} and {end_date:%Y-%m-%d}" if start_date else ""
        return Panel(
            Group(*elements),
            title="SEC Filings",
            subtitle=subtitle,
            border_style="bold grey54",
            expand=False
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


def sort_filings_by_priority(filing_table: pa.Table,
                             priority_forms: Optional[List[str]] = None) -> pa.Table:
    """
    Sort a filings table by date (descending) and form priority.

    Args:
        filing_table: PyArrow table containing filings data
        priority_forms: List of forms in priority order. Forms not in list will be sorted
                       alphabetically after priority forms. Defaults to common forms if None.

    Returns:
        PyArrow table sorted by date and form priority
    """
    if priority_forms is None:
        priority_forms = ['10-Q', '10-Q/A', '10-K', '10-K/A', '8-K', '8-K/A',
                          '6-K', '6-K/A', '13F-HR', '144', '4', 'D', 'SC 13D', 'SC 13G']

    # Create form priority values
    forms_array = filing_table['form']
    priorities = []
    for form_type in forms_array.to_pylist():
        try:
            priority = priority_forms.index(form_type)
        except ValueError:
            priority = len(priority_forms)
        priorities.append(priority)

    # Add priority column
    with_priority = filing_table.append_column(
        'form_priority',
        pa.array(priorities, type=pa.int32())
    )

    # Sort by date (descending), priority (ascending), form name (ascending)
    sorted_table = with_priority.sort_by([
        ("filing_date", "descending"),
        ("form_priority", "ascending"),
        ("form", "ascending")
    ])

    # Remove temporary priority column
    return sorted_table.drop(['form_priority'])


def get_filings(year: Optional[Years] = None,
                quarter: Optional[Quarters] = None,
                form: Optional[Union[str, List[IntString]]] = None,
                amendments: bool = True,
                filing_date: Optional[str] = None,
                index="form",
                priority_sorted_forms: Optional[List[str]] = None) -> Optional[Filings]:
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
    :param priority_sorted_forms: A list of forms to sort by priority. This presents these forms first for each day.
    :return:
    """
    # Check if defaults were used
    defaults_used = (year is None and
                     quarter is None and
                     form is None and
                     amendments is True and
                     filing_date is None and
                     index == "form" and
                     priority_sorted_forms is None)
    if filing_date:
        if not is_valid_filing_date(filing_date):
            log.warning("""Provide a valid filing date in the format YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD""")
            return None
        year_and_quarters = filing_date_to_year_quarters(filing_date)
    elif not year:
        # If no year specified, take the current year and quarter. (We need the quarter later)
        year, quarter = current_year_and_quarter()
        # Expand quarters for the year to date so use expand_quarters(year, quarter=None)
        year_and_quarters: YearAndQuarters = expand_quarters(year, quarter=None)
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
    filing_index = get_filings_for_quarters(year_and_quarters, index=index)

    filings = Filings(filing_index)

    if form or filing_date:
        filings = filings.filter(form=form, amendments=amendments, filing_date=filing_date)

    if not filings:
        if defaults_used:
            # Ensure at least some data is returned
            previous_quarter = [get_previous_quarter(year, quarter)]
            filing_index = get_filings_for_quarters(previous_quarter, index=index)
            filings = Filings(filing_index)
            sorted_filing_index = sort_filings_by_priority(filings.data, priority_sorted_forms)
            return Filings(sorted_filing_index)
        # Return an empty filings object
        return Filings(_empty_filing_index())

    # Sort the filings using the separate sort function
    sorted_filing_index = sort_filings_by_priority(filings.data, priority_sorted_forms)

    return Filings(sorted_filing_index)














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
                 accession_no: str,
                 related_entities: List[Dict] = None):
        self.cik = cik
        self.company = company
        self.form = form
        self.filing_date = filing_date
        self.accession_no = accession_no
        self._filing_homepage = None
        self._sgml = None

        # New: Store related entities from index
        self._related_entities = related_entities or []

    @property
    def docs(self):
        return Docs(self)

    @property
    def accession_number(self):
        return self.accession_no

    @property
    def all_ciks(self) -> List[int]:
        """Get all CIKs including related entities"""
        # If we have related entities from the index, use those
        if self._related_entities:
            ciks = [self.cik]
            ciks.extend(e['cik'] for e in self._related_entities)
            return sorted(list(set(ciks)))

        # Otherwise, check the header for all filers
        try:
            header = self.header
            if header and header.filers and len(header.filers) > 1:
                # Multiple filers in header
                ciks = []
                for filer in header.filers:
                    if filer.company_information and filer.company_information.cik:
                        # Convert CIK string to int, removing leading zeros
                        cik_int = int(filer.company_information.cik.lstrip('0'))
                        ciks.append(cik_int)
                if ciks:
                    return sorted(list(set(ciks)))
        except Exception as e:
            # Log warning when header access fails
            log.warning(
                f"Could not access header for multi-entity detection in Filing "
                f"(accession_no={self.accession_no}, cik={self.cik}): {str(e)}. "
                f"This may occur if the accession number is invalid or the filing doesn't exist on EDGAR."
            )

        return [self.cik]

    @property
    def all_entities(self) -> List[Dict[str, Any]]:
        """Get all entity information"""
        # If we have related entities from the index, use those
        if self._related_entities:
            entities = [{'cik': self.cik, 'company': self.company}]
            entities.extend(self._related_entities)
            return entities

        # Otherwise, check the header for all filers
        try:
            header = self.header
            if header and header.filers and len(header.filers) > 1:
                # Multiple filers in header
                entities = []
                for filer in header.filers:
                    if filer.company_information and filer.company_information.cik:
                        # Convert CIK string to int, removing leading zeros
                        cik_int = int(filer.company_information.cik.lstrip('0'))
                        entities.append({
                            'cik': cik_int,
                            'company': filer.company_information.name or f'CIK {cik_int}'
                        })
                if entities:
                    return entities
        except Exception as e:
            # Log warning when header access fails
            log.warning(
                f"Could not access header for entity information in Filing "
                f"(accession_no={self.accession_no}, cik={self.cik}): {str(e)}. "
                f"This may occur if the accession number is invalid or the filing doesn't exist on EDGAR."
            )

        return [{'cik': self.cik, 'company': self.company}]

    @property
    def is_multi_entity(self) -> bool:
        """Check if this filing has multiple entities"""
        # First check if we have related entities from the index
        if len(self._related_entities) > 0:
            return True

        # Otherwise, check the header for multiple filers
        try:
            header = self.header
            if header and header.filers and len(header.filers) > 1:
                return True
        except Exception as e:
            # Log warning when header access fails
            log.warning(
                f"Could not access header for multi-entity check in Filing "
                f"(accession_no={self.accession_no}, cik={self.cik}): {str(e)}. "
                f"This may occur if the accession number is invalid or the filing doesn't exist on EDGAR."
            )

        return False

    @property
    def document(self):
        """
        :return: The primary display document on the filing, generally HTML but can be XHTML
        """
        document = self.sgml().attachments.primary_html_document
        # If the document is not in the SGML then we have to go to the homepage
        if document:
            if document.extension == '.paper':
                # If the document is a paper filing, we return the scanned document if it exists
                attachments = self.homepage.attachments
                scanned_documents = attachments.query("document == 'scanned.pdf'")
                if len(scanned_documents) > 0:
                    return scanned_documents.get_by_index(0)
                return self.homepage.primary_html_document
            return document
        return self.homepage.primary_html_document

    @property
    def primary_documents(self):
        """
        :return: a list of the primary documents on the filing, generally HTML or XHTML and optionally XML
        """
        documents = self.sgml().attachments.primary_documents
        if len(documents) == 0:
            documents = self.homepage.primary_documents
        return documents

    @property
    def period_of_report(self):
        """
        Get the period of report for the filing
        """
        return self.sgml().period_of_report

    @property
    def attachments(self):
        # Return all the attachments on the filing
        sgml_filing: FilingSGML = self.sgml()
        return sgml_filing.attachments

    @property
    def exhibits(self):
        # Return all the exhibits on the filing
        return self.attachments.exhibits

    @lru_cache(maxsize=4)
    def html(self) -> Optional[str]:
        """Returns the html contents of the primary document if it is html"""
        sgml = self.sgml()
        html = sgml.html()
        if not html:
            document:Attachment = self.homepage.primary_html_document
            if document.empty or document.is_binary():
                return None
            return self.homepage.primary_html_document.download()
        if html.endswith("</PDF>"):
            return None
        if html.startswith("<?xml"):
            if self.form in ['3','3/A', '4', '4/A', '5', '5/A']:
                from edgar.ownership import Ownership
                ownership:Ownership = self.obj()
                html = ownership.to_html()
            else:
                html = self.homepage.primary_html_document.download()
        if isinstance(html, bytes):
            try:
                return html.decode("utf-8")
            except UnicodeDecodeError:
                return None
        if is_probably_html(html):
            return html
        else:
            html = html.replace("<PAGE>", "")
            return f"<html><body><div>{html}</div></body></html>"

    @lru_cache(maxsize=4)
    def xml(self) -> Optional[str]:
        """Returns the xml contents of the primary document if it is xml"""
        sgml = self.sgml()
        return sgml.xml()

    @lru_cache(maxsize=4)
    def text(self) -> str:
        """Convert the html of the main filing document to text"""
        html_content = self.html()
        if html_content and is_probably_html(html_content):
            document = Document.parse(html_content)
            return rich_to_text(document)
        else:
            text_extract_attachments = self.attachments.query("document_type == 'TEXT-EXTRACT'")
            if len(text_extract_attachments) > 0 and text_extract_attachments.get_by_index(0) is not None:
                text_extract_attachment = text_extract_attachments.get_by_index(0)
                return text_extract_attachment.content
            else:
                return self._download_filing_text()

    def _download_filing_text(self):
        """
        Download the text of the filing directly from the primary text sources.
        Either from the text url or the text extract attachment
        """
        text_extract_attachments = self.attachments.query("document_type == 'TEXT-EXTRACT'")
        if len(text_extract_attachments) > 0 and text_extract_attachments[0] is not None:
            text_extract_attachment = text_extract_attachments[0]
            assert text_extract_attachment is not None
            return download_text_between_tags(text_extract_attachment.url, "TEXT")
        else:
            return download_text_between_tags(self.text_url, "TEXT")

    def full_text_submission(self) -> str:
        """Return the complete text submission file"""
        downloaded = download_file(self.text_url, as_text=True)
        assert downloaded is not None
        return str(downloaded)

    def markdown(self, include_page_breaks: bool = False, start_page_number: int = 0) -> str:
        """
        Return the markdown version of this filing html

        Args:
            include_page_breaks: If True, include page break delimiters in the markdown
            start_page_number: Starting page number for page break markers (default: 0)
        """
        html = self.html()
        if html:
            clean_html = get_clean_html(html)
            if clean_html:
                return to_markdown(clean_html, include_page_breaks=include_page_breaks, start_page_number=start_page_number)
        text_content = self.text()
        return text_to_markdown(text_content)

    def view(self):
        """Preview this filing's primary document as markdown. This should display in the console"""
        html_content = self.html()
        if html_content and is_probably_html(html_content):
            document = Document.parse(html_content)
            print_rich(document)
        else:
            # Fallback to text content for forms without HTML (like UPLOAD forms)
            text_content = self.text()
            if text_content:
                print(text_content)

    def xbrl(self) -> Optional[XBRL]:
        """
        Get the XBRL document for the filing, parsed and as a FilingXbrl object
        :return: Get the XBRL document for the filing, parsed and as a FilingXbrl object, or None
        """
        try:
            return XBRL.from_filing(self)
        except XBRLFilingWithNoXbrlData:
            return None

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

    @cached_property
    def filing_directory(self) -> FilingDirectory:
        return FilingDirectory.load(self.base_dir)

    def _local_path(self) -> Path:
        """
        Get the local path for the filing
        """
        return local_filing_path(str(self.filing_date), self.accession_no)

    @classmethod
    def from_sgml(cls, source: Union[str, Path]):
        """
        Read the filing from the SGML string
        """
        filing_sgml = FilingSGML.from_source(source)
        filers = filing_sgml.header.filers
        if filers and len(filers) > 0:
             company = filers[0].company_information.name if filers[0].company_information else ""
        else:
            company = ""

        filing = cls(cik=filing_sgml.cik,
                   accession_no=filing_sgml.accession_number,
                   form=filing_sgml.form,
                   company=company,
                   filing_date=filing_sgml.filing_date)
        filing._sgml = filing_sgml
        return filing

    @classmethod
    def from_sgml_text(cls, full_text_submission: str):
        """
        Read the filing from the full text submission
        """
        filing_sgml = FilingSGML.from_text(full_text_submission)
        filers = filing_sgml.header.filers
        if filers and len(filers) > 0:
             company = filers[0].company_information.name if filers[0].company_information else ""
        else:
            company = ""

        filing = cls(cik=filing_sgml.cik,
                   accession_no=filing_sgml.accession_number,
                   form=filing_sgml.form,
                   company=company,
                   filing_date=filing_sgml.filing_date)
        filing._sgml = filing_sgml
        return filing

    def sgml(self) -> FilingSGML:
        """
        Read the filing from the local storage path if it exists
        """
        if self._sgml:
            return self._sgml
        if is_using_local_storage():
            local_path = local_filing_path(str(self.filing_date), self.accession_no)
            if local_path.exists():
                self._sgml = FilingSGML.from_source(local_path)

        if self._sgml is None:
            self._sgml = FilingSGML.from_filing(self)
        return self._sgml

    @cached_property
    def reports(self)  -> Optional[Reports]:
        """
        If the filing has report attachments then return the reports
        """
        filing_summary = self.sgml().filing_summary
        if filing_summary:
            return filing_summary.reports

    @cached_property
    def statements(self) -> Optional[Statements]:
        """
        Get the statements for a report
        """
        if self.reports:
            return self.reports.statements

    @cached_property
    def index_headers(self) -> IndexHeaders:
        """
        Get the index headers for the filing. This is a listing of all the files in the filing directory
        """
        index_headers_url = f"{self.base_dir}/{self.accession_no}-index-headers.html"
        index_header_text = download_text(index_headers_url)
        return IndexHeaders.load(index_header_text)

    def to_dict(self) -> Dict[str, Union[str, int]]:
        """Return the filing as a Dict string"""
        return {'accession_number': self.accession_number,
                'cik': self.cik,
                'company': self.company,
                'form': self.form,
                'filing_date': self.filing_date}

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int]]):
        """Create a Filing from a dictionary.
        Thw dict must have the keys cik, company, form, filing_date, accession_no
        """
        assert all(key in data for key in ['cik', 'company', 'form', 'filing_date', 'accession_number']), \
            "The dict must have the keys cik, company, form, filing_date, accession_number"
        return cls(cik=int(data['cik']),
                   company=str(data['company']),
                   form=str(data['form']),
                   filing_date=str(data['filing_date']),
                   accession_no=str(data['accession_number']))

    @classmethod
    def from_json(cls, path: str):
        """Create a Filing from a JSON file"""
        with open(path, 'r') as file:
            data = json.load(file)
            return cls.from_dict(data)

    @cached_property
    def header(self):
        """Get the header for the filing"""
        _sgml = self.sgml()
        return _sgml.header


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
        # Use the homepage to determine the url since SGML sometimes miss the primary HTML file
        webbrowser.open(self.homepage.primary_html_document.url)

    @lru_cache(maxsize=1)
    def sections(self) -> List[str]:
        html = self.html()
        assert html is not None
        return html_sections(html)

    @cached_property
    def __get_bm25_search_index(self):
        return BM25Search(self.sections())

    @cached_property
    def __get_regex_search_index(self):
        return RegexSearch(self.sections())

    def search(self,
               query: str,
               regex=False):
        """Search for the query string in the filing HTML"""
        if regex:
            return self.__get_regex_search_index.search(query)
        return self.__get_bm25_search_index.search(query)

    @property
    def filing_url(self) -> str:
        return f"{self.base_dir}/{self.document.document}"

    @property
    def homepage_url(self) -> str:
        return f"{SEC_ARCHIVE_URL}/data/{self.cik}/{self.accession_no}-index.html"

    @property
    def text_url(self) -> str:
        return f"{self.base_dir}/{self.accession_no}.txt"

    @property
    def index_header_url(self) -> str:
        return f"{self.base_dir}/index-headers.html"

    @property
    def base_dir(self) -> str:
        return f"{SEC_ARCHIVE_URL}/data/{self.cik}/{self.accession_no.replace('-', '')}"

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
        from edgar.entity import Company
        return Company(self.cik)

    @lru_cache(maxsize=1)
    def as_company_filing(self):
        """Get this filing as a company filing. Company Filings have more information"""
        company = self.get_entity()
        if not company:
            return None

        filings = company.get_filings(accession_number=self.accession_no)
        if filings and not filings.empty:
            return filings[0]
        return None

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
        if not filings or filings.empty:
            if is_using_local_storage():
                # In this case the local storage is missing the filing so we have to download it
                log.warning(f"Filing {self.accession_no} not found in local storage. Downloading from SEC ...")
                from edgar.entity import download_entity_submissions_from_sec, parse_entity_submissions
                submissions_json = download_entity_submissions_from_sec(self.cik)
                c_from_sec = parse_entity_submissions(submissions_json)
                filings = c_from_sec.get_filings(accession_number=self.accession_no)

                if not filings or filings.empty:
                    # Shouldn't get here
                    return company._empty_company_filings()
            else:
                return company._empty_company_filings()
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

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns AI-optimized filing metadata for language models.

        This method provides structured information about the filing in a markdown-KV format
        that is optimized for AI agent navigation and discovery.

        Args:
            detail: Level of detail to include:
                - 'minimal': Basic filing info (~100 tokens)
                - 'standard': Adds available actions and methods (~250 tokens)
                - 'full': Adds document details and XBRL status (~500 tokens)

        Returns:
            Markdown-KV formatted context string optimized for LLMs

        Example:
            >>> filing = filings[0]
            >>> print(filing.to_context('standard'))
            FILING: Form C

            Company: ViiT Health Inc
            CIK: 1881570
            Filed: 2025-06-11
            Accession: 0001670254-25-000647

            AVAILABLE ACTIONS:
              - Use .obj() to parse as structured data
                Returns: FormC (crowdfunding offering details)
              - Use .docs for detailed API documentation
              - Use .xbrl() for financial statements (if available)
              - Use .document() for structured text extraction
              - Use .attachments for exhibits (5 documents)
        """
        from edgar import get_obj_info

        lines = []

        # Header
        lines.append(f"FILING: Form {self.form}")
        lines.append("")

        # Always include basic info
        lines.append(f"Company: {self.company}")
        lines.append(f"CIK: {self.cik}")
        lines.append(f"Filed: {self.filing_date}")
        lines.append(f"Accession: {self.accession_no}")

        # Add period of report if available and not minimal
        if detail in ['standard', 'full']:
            try:
                period = self.period_of_report
                if period:
                    lines.append(f"Period: {period}")
            except:
                pass  # Period not available for all filing types

        # Add multi-entity info if present
        if self.is_multi_entity and detail != 'minimal':
            num_entities = len(self.all_ciks)
            lines.append(f"Multi-Entity Filing: {num_entities} entities")

        if detail in ['standard', 'full']:
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")

            # Check if this form has a structured data object
            has_obj, obj_type, obj_desc = get_obj_info(self.form)
            if has_obj:
                lines.append(f"  - Use .obj() to parse as structured data")
                lines.append(f"    Returns: {obj_type} ({obj_desc})")

            # Mention .docs for API documentation
            lines.append(f"  - Use .docs for detailed API documentation")

            # Check for XBRL availability (non-blocking check)
            has_xbrl = False
            if detail == 'full':
                try:
                    # Only do full check in 'full' mode
                    xbrl_data = self.xbrl()
                    has_xbrl = xbrl_data is not None
                except:
                    pass

            xbrl_hint = "for financial statements" if has_xbrl or self.form in ['10-K', '10-Q', '20-F', '8-K', '6-K'] else "(if available)"
            lines.append(f"  - Use .xbrl() {xbrl_hint}")

            lines.append(f"  - Use .document() for structured text extraction")

            # Add attachments info if available
            try:
                num_attachments = len(self.attachments)
                lines.append(f"  - Use .attachments for exhibits ({num_attachments} documents)")
            except:
                lines.append(f"  - Use .attachments for exhibits")

        if detail == 'full':
            lines.append("")
            lines.append("DOCUMENTS:")
            try:
                primary_docs = self.primary_documents
                if primary_docs and len(primary_docs) > 0:
                    lines.append(f"  Primary: {primary_docs[0].document}")
                else:
                    lines.append(f"  Primary: N/A")
            except:
                lines.append(f"  Primary: N/A")

            # Add XBRL status
            if has_xbrl:
                lines.append(f"  XBRL: Available")
            elif self.form in ['10-K', '10-Q', '20-F', '8-K', '6-K']:
                lines.append(f"  XBRL: Check with .xbrl()")

        return "\n".join(lines)

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
        ticker = find_ticker_safe(self.cik)
        ticker = f"{ticker}" if ticker else ""

        # Check for multi-entity (without triggering header lookup)
        has_related = hasattr(self, '_related_entities') and self._related_entities

        # Build the title components
        title_parts = [
            (f"Form {self.form} ", "bold"),
            (self.company, "bold green"),
            " ",
            (f"[{self.cik}] ", "dim"),
        ]

        if ticker:
            title_parts.append((ticker, "bold yellow"))

        # Add multi-entity indicator if present
        if has_related:
            num_related = len(self._related_entities)
            title_parts.extend([
                " ",
                (f"(+{num_related} {'entity' if num_related == 1 else 'entities'})", "cyan dim")
            ])

        # The title of the panel
        title = Text.assemble(*title_parts)

        # The subtitle of the panel
        form_description = describe_form(self.form, False)
        subtitle = Text.assemble(
            (form_description, "dim"),
            " • ",
            ("filing.docs", "cyan dim"),
            (" for usage guide", "dim")
        )

        attachments = self.attachments

        # The filing information table
        filing_info_table = Table("Accession Number", "Filing Date", "Period of Report", "Documents",
                                  header_style="dim",
                                  box=box.SIMPLE_HEAD)
        filing_info_table.add_row(accession_number_text(self.accession_no),
                                  Text(str(self.filing_date), "bold"),
                                  Text(self.period_of_report or "-", "bold"),
                                  f"{len(attachments)}")

        # Build content elements
        elements = [filing_info_table]

        # Add entities table if multi-entity filing
        if has_related:
            # Add spacing and header
            elements.append(Text())  # Empty line for spacing
            elements.append(Text("All Entities:", style="bold dim"))

            # Create entities table
            entities_table = Table(
                "CIK", "Company",
                header_style="dim",
                box=box.SIMPLE,
                show_edge=False,
                padding=(0, 1)
            )

            # Add primary entity
            entities_table.add_row(
                Text(str(self.cik), style="dim"),
                Text(self.company, style="bold green")
            )

            # Add related entities
            for entity in self._related_entities:
                entities_table.add_row(
                    Text(str(entity.get('cik', '')), style="dim"),
                    Text(entity.get('company', ''), style="green")
                )

            elements.append(entities_table)

        return Panel(
            Group(*elements),
            title=title,
            subtitle=subtitle,
            box=box.ROUNDED,
            expand=False
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


@cache_except_none(maxsize=16)
def get_filing_by_accession(accession_number: str, year: int):
    """Cache-friendly version that takes year as parameter instead of using datetime.now()"""
    assert re.match(r"\d{10}-\d{2}-\d{6}", accession_number)

    # Static logic that doesn't depend on current time
    for quarter in range(1, 5):
        filings = _get_cached_filings(year=year, quarter=quarter)
        if filings and (filing := filings.get(accession_number)):
            return filing

    return None


def get_by_accession_number_enriched(accession_number: str):
    """Get filing with all related entities populated using PyArrow"""
    year = int("19" + accession_number[11:13]) if accession_number[11] == '9' else int("20" + accession_number[11:13])

    # Find all entities with this accession number
    all_entities = []
    for quarter in range(1, 5):
        filings = _get_cached_filings(year=year, quarter=quarter)
        if filings:
            # Use PyArrow filtering (same pattern as Filings.get())
            mask = pc.equal(filings.data['accession_number'], accession_number)
            # Convert mask to indices
            indices = []
            for i in range(len(mask)):
                if mask[i].as_py():
                    indices.append(i)

            if len(indices) > 0:
                # Extract all matching entities efficiently
                for idx in indices:
                    all_entities.append({
                        'cik': filings.data['cik'][idx].as_py(),
                        'company': filings.data['company'][idx].as_py(),
                        'form': filings.data['form'][idx].as_py(),
                        'filing_date': filings.data['filing_date'][idx].as_py()
                    })
                break  # Found matches, no need to check other quarters

    if all_entities:
        # Return first entity as primary, with others as related
        primary = all_entities[0]
        related = all_entities[1:] if len(all_entities) > 1 else []

        # Create enriched Filing
        filing = Filing(
            cik=primary['cik'],
            company=primary['company'],
            form=primary['form'],
            filing_date=primary['filing_date'],
            accession_no=accession_number,
            related_entities=related
        )
        return filing

    # Fall back to current behavior if not found
    return get_by_accession_number(accession_number)


def get_by_accession_number(accession_number: str, show_progress: bool = False):
    """Wrapper that handles progress display and current time logic"""
    year = int("19" + accession_number[11:13]) if accession_number[11] == '9' else int("20" + accession_number[11:13])

    with Status("[bold deep_sky_blue1]Searching...", spinner="dots2") if show_progress else nullcontext():
        filing = get_filing_by_accession(accession_number, year)

        if not filing and year == datetime.now().year:
            from edgar.current_filings import get_current_filings
            filings = get_current_filings()
            filing = filings.get(accession_number)

    return filing


def form_with_amendments(*forms: str):
    return list(forms) + [f"{f}/A" for f in forms]


barchart = '\U0001F4CA'
ticket = '\U0001F3AB'
page_facing_up = '\U0001F4C4'
classical_building = '\U0001F3DB'


def unicode_for_form(form: str) -> str:
    """
    Returns a meaningful Unicode symbol based on SEC form type.

    Args:
        form (str): SEC form type identifier

    Returns:
        str: Unicode symbol representing the form type

    Form type categories:
    - Periodic Reports (10-K, 10-Q): 📊 (financial statements/data)
    - Current Reports (8-K, 6-K): ⚡ (immediate/material events)
    - Registration & Offerings:
        - S-1, F-1: 🎯 (initial public offerings)
        - S-3, F-3: 🔄 (follow-on offerings)
        - Prospectuses (424B*): 📖 (offering documents)
    - Insider Forms (3, 4, 5): 👥 (insider activity)
    - Beneficial Ownership:
        - SC 13D/G: 🏰 (significant ownership stakes)
        - 13F-HR: 📈 (institutional holdings)
    - Investment Company:
        - N-CSR, N-Q: 💼 (investment portfolio reports)
        - N-PX: 🗳️ (proxy voting record)
    - Foreign Company Forms (20-F, 40-F): 🌐 (international)
    - Municipal Advisor Forms (MA): ⚖️ (regulation/compliance)
    - Communications (CORRESP/UPLOAD): 💬 (dialogue with SEC)
    - Proxy Materials (DEF 14A): 📩 (shareholder voting)
    - Default: 📄 (generic document)
    """

    # Periodic financial reports
    if form in ['10-K', '10-Q', '10-K/A', '10-Q/A']:
        return '📊'  # Chart for financial statements

    # Current reports (material events)
    elif form in ['8-K', '8-K/A', '6-K', '6-K/A']:
        return '⚡'  # Lightning bolt for immediate/current events

    # Initial registration statements
    elif form.startswith(('S-1', 'F-1')) or form in ['S-1/A', 'F-1/A']:
        return '🎯'  # Target for initial offerings

    # Shelf registration statements
    elif form.startswith(('S-3', 'F-3')) or form in ['S-3/A', 'F-3/A']:
        return '🔄'  # Circular arrows for repeat/follow-on offerings

    # Prospectuses
    elif form.startswith('424B'):
        return '📖'  # Open book for offering documents

    # Foreign issuer annual reports
    elif form in ['20-F', '20-F/A', '40-F', '40-F/A']:
        return '🌐'  # Globe for international filings

    # Insider trading forms
    elif form in ['3', '4', '5', '3/A', '4/A', '5/A']:
        return '👥'  # People for insider/beneficial owner reports

    # Significant beneficial ownership reports
    elif form.startswith(('SC 13D', 'SC 13G')) or form in ['SC 13D/A', 'SC 13G/A']:
        return '🏰'  # Castle for large ownership stakes

    # Institutional investment holdings
    elif form in ['13F-HR', '13F-HR/A', '13F-NT', '13F-NT/A']:
        return '📈'  # Chart up for investment positions

    # Investment company reports
    elif form in ['N-CSR', 'N-CSR/A', 'N-Q', 'N-Q/A']:
        return '💼'  # Briefcase for investment portfolio

    # Proxy voting records
    elif form in ['N-PX', 'N-PX/A']:
        return '🗳️'  # Ballot box for voting records

    # Municipal advisor forms
    elif form in ['MA', 'MA/A', 'MA-I', 'MA-I/A']:
        return '⚖️'  # Scales for regulatory/compliance

    # SEC correspondence
    elif form in ['CORRESP', 'UPLOAD']:
        return '💬'  # Speech bubble for communications

    # Proxy statements
    elif form in ['DEF 14A', 'PRE 14A', 'DEFA14A', 'DEFC14A']:
        return '📩'  # Envelope for shareholder communications

    # Default case - generic document
    return '📄'
