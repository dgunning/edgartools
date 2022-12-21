import itertools
import os.path
import re
import webbrowser
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from typing import Tuple, List, Dict

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq
from bs4 import BeautifulSoup
from fastcore.basics import listify
from fastcore.parallel import parallel
from pydantic import BaseModel

from edgar.core import http_client, download_text, download_file
from edgar.xbrl import FilingXbrl

__all__ = [
    'get_filings',
    'Filing',
    'Filings',
    'FilingHomepage',
    'available_quarters'
]
sec_dot_gov = "https://www.sec.gov"
sec_edgar = "https://www.sec.gov/Archives/edgar"
full_index_url = "https://www.sec.gov/Archives/edgar/full-index/{}/QTR{}/{}.{}"

filing_homepage_url_re = re.compile(f"{sec_edgar}/data/[0-9]{1,}/[0-9]{10}-[0-9]{2}-[0-9]{4}-index.html")

headers = {'User-Agent': 'Dwight Gunning dgunning@gmail.com'}

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
Years = int | List[int] | range
Quarters = int | List[int] | range


@lru_cache(maxsize=1)
def available_quarters() -> YearAndQuarters:
    now = datetime.now()
    current_year, current_quarter = now.year, (now.month - 1) // 3 + 1
    start_quarters = [(1994, 3), (1994, 4)]
    in_between_quarters = list(itertools.product(range(1995, current_year), range(1, 5)))
    end_quarters = list(itertools.product([current_year], range(1, current_quarter + 1)))
    return start_quarters + in_between_quarters + end_quarters


def expand_quarters(year: Years,
                    quarter: int = None) -> YearAndQuarters:
    years = listify(year)
    quarters = listify(quarter) if quarter else quarters_in_year
    return [yq
            for yq in itertools.product(years, quarters)
            if yq in available_quarters()
            ]


class FileSpecs:

    def __init__(self, specs: List[Tuple[str, Tuple[int, int], pa.lib.DataType]]):
        self.splits = list(zip(*specs))[1]
        self.schema = pa.schema(
            [
                pa.field(name, datatype)
                for name, _, datatype in specs
            ]
        )


form_specs = FileSpecs(
    [("form", (0, 12), pa.string()),
     ("company", (12, 74), pa.string()),
     ("cik", (74, 82), pa.int32()),
     ("filingDate", (85, 97), pa.string()),
     ("accessionNumber", (-33, -13), pa.string())
     ]
)
company_specs = FileSpecs(
    [("company", (0, 62), pa.string()),
     ("form", (62, 74), pa.string()),
     ("cik", (74, 82), pa.int32()),
     ("filingDate", (85, 97), pa.string()),
     ("accessionNumber", (-33, -13), pa.string())
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
    array = pa.array(index_text.rstrip('\n').split('\n')[10:])

    # Then split into separate arrays by file specs
    arrays = [
        pc.utf8_trim_whitespace(
            pc.utf8_slice_codeunits(array, start=start, stop=stop))
        for start, stop,
        in file_specs.splits
    ]

    # Change the CIK to int
    arrays[2] = pa.compute.cast(arrays[2], pa.int32())

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
                                        column_names=['cik', 'company', 'form', 'filingDate', 'accessionNumber'])
    )
    index_table = index_table.set_column(
        0,
        "cik",
        pa.compute.cast(index_table[0], pa.int32())
    ).set_column(4,
                 "accessionNumber",
                 pc.utf8_slice_codeunits(index_table[4], start=-24, stop=-4))
    return index_table


def fetch_filing_index(year_and_quarter: YearAndQuarter,
                       client: httpx.Client | httpx.AsyncClient,
                       index: str
                       ):
    year, quarter = year_and_quarter
    url = full_index_url.format(year, quarter, index, "idx")
    index_text = download_text(url=url, client=client)
    if index == "xbrl":
        index_table = read_pipe_delimited_index(index_text)
    else:
        # Read as a fixed width index file
        file_specs = form_specs if index == "form" else company_specs
        index_table = read_fixed_width_index(index_text,
                                             file_specs=file_specs)
    return (year, quarter), index_table


def get_filings_for_quarters(year_and_quarters: YearAndQuarters,
                             index="form"):
    with http_client() as client:
        if len(year_and_quarters) == 1:
            _, final_index_table = fetch_filing_index(year_and_quarter=year_and_quarters[0],
                                                      client=client,
                                                      index=index)
        else:
            quarters_and_indexes = parallel(fetch_filing_index,
                                            items=year_and_quarters,
                                            client=client,
                                            index=index,
                                            threadpool=True,
                                            progress=True
                                            )
            quarter_and_indexes_sorted = sorted(quarters_and_indexes, key=lambda d: d[0])
            index_tables = [fd[1] for fd in quarter_and_indexes_sorted]
            final_index_table = pa.concat_tables(index_tables, promote=False)
    return final_index_table


def get_filings(year: Years,
                quarter: Quarters = None,
                index="form"):
    year_and_quarters: YearAndQuarters = expand_quarters(year, quarter)
    filing_index = get_filings_for_quarters(year_and_quarters, index=index)

    return Filings(filing_index)


class Filings:
    """
    A container for filings
    """

    def __init__(self,
                 filing_index: pa.Table):
        self.filing_index: pa.Table = filing_index

    def to_pandas(self, *columns) -> pd.DataFrame:
        """Return the filing index as a python dataframe"""
        df = self.filing_index.to_pandas()
        return df.filter(columns) if len(columns) > 0 else df

    def to_duckdb(self):
        """return an in memory duck db instance over the filings"""
        import duckdb
        con = duckdb.connect(database=':memory:')
        con.register('filings', self.filing_index)
        return con

    def save_parquet(self, location: str):
        """Save the filing index as parquet"""
        pq.write_table(self.filing_index, location)

    def save(self, location: str):
        """Save the filing index as parquet"""
        self.save_parquet(location)

    def get_filing_at(self, item: int):
        """Get the filing at the specified index"""
        return Filing(
            cik=self.filing_index['cik'][item].as_py(),
            company=self.filing_index['company'][item].as_py(),
            form=self.filing_index['form'][item].as_py(),
            date=self.filing_index['filingDate'][item].as_py(),
            accession_no=self.filing_index['accessionNumber'][item].as_py(),
        )

    @property
    def date_range(self) -> Tuple[datetime]:
        """Return a tuple of the start and end dates in the filing index"""
        min_max_dates = pc.min_max(self.filing_index['filingDate']).as_py()
        return min_max_dates['min'], min_max_dates['max']

    def latest(self, n: int = 1) -> int:
        """Get the latest n filings"""
        sort_indices = pc.sort_indices(self.filing_index, sort_keys=[("filingDate", "descending")])
        sort_indices_top = sort_indices[:min(n, len(sort_indices))]
        latest_filing_index = pc.take(data=self.filing_index, indices=sort_indices_top)
        filings = Filings(latest_filing_index)
        if len(filings) == 1:
            return filings[0]
        return filings

    def __head(self, n):
        assert n > 0, "The number of filings to select - `n`, should be greater than 0"
        return self.filing_index.slice(0, min(n, len(self.filing_index)))

    def head(self, n: int):
        """Get the first n filings"""
        selection = self.__head(n)
        return Filings(selection)

    def __tail(self, n):
        assert n > 0, "The number of filings to select - `n`, should be greater than 0"
        return self.filing_index.slice(max(0, len(self.filing_index) - n), len(self.filing_index))

    def tail(self, n: int):
        """Get the last n filings"""
        selection = self.__tail(n)
        return Filings(selection)

    def __getitem__(self, item):
        return self.get_filing_at(item)

    def __len__(self):
        return len(self.filing_index)

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n <= len(self.filing_index):
            filing: Filing = self[self.n]
            self.n += 1
            return filing
        else:
            raise StopIteration

    def __repr__(self):
        start_date, end_date = self.date_range
        return f"Filings - {len(self.filing_index):,} in total from {start_date} to {end_date}"


class Filing:
    """
    An SEC filing
    """

    def __init__(self,
                 cik: int,
                 company: str,
                 form: str,
                 date: str,
                 accession_no: str):
        self.cik = cik
        self.company = company
        self.form = form
        self.date = date
        self.accession_no = accession_no
        self._filing_homepage = None

    def html(self):
        return self.get_homepage().filing_document.download()

    def xbrl(self) -> FilingXbrl:
        xbrl_document = self.get_homepage().xbrl_document
        if xbrl_document:
            xbrl_text = xbrl_document.download()
            return FilingXbrl.parse(xbrl_text)

    def open_homepage(self):
        """Open the homepage in the browser"""
        webbrowser.open(self.homepage_url)

    def open_filing(self):
        """Open the main filing document"""
        webbrowser.open(self.get_homepage().filing_document.url)

    @property
    def homepage_url(self):
        return f"{sec_edgar}/data/{self.cik}/{self.accession_no}-index.html"

    @lru_cache(maxsize=1)
    def get_homepage(self):
        if not self._filing_homepage:
            homepage_html = download_text(self.homepage_url)
            self._filing_homepage = FilingHomepage.from_html(homepage_html, form=self.form)
        return self._filing_homepage

    def __hash__(self):
        return hash(self.accession_no)

    def __eq__(self, other):
        return isinstance(other, Filing) and self.accession_no == other.accession_no

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return (f"Filing(form='{self.form}', company='{self.company}', cik={self.cik}, "
                f"date='{self.date}', accession_no='{self.accession_no}')")


class FilingDocument(BaseModel):
    seq: int
    description: str
    form: str
    size: int
    path: str

    @property
    def url(self) -> str:
        """
        :return: The full sec url
        """
        return f"{sec_dot_gov}{self.path}"

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @classmethod
    def from_dataframe_row(cls, dataframe_row: pd.Series):
        assert dataframe_row.shape == (5,), ("Cannot create a FilingDocument from the dataframe .. "
                                             "should only be one row from which to create the FilingDocument "
                                             )
        return cls(seq=dataframe_row.Seq,
                   description=dataframe_row.Description,
                   form=dataframe_row.Type,
                   size=int(dataframe_row.Size),
                   path=dataframe_row.Url)

    def download(self):
        return download_file(self.url)


class FilingHomepage:

    def __init__(self,
                 filing_files: Dict[str, pd.DataFrame],
                 form: str):
        self.filing_files: Dict[str, pd.DataFrame] = filing_files
        self.form = form

    def get_by_seq(self, seq: int | str):
        query = f"Seq=='{seq}'"
        return self.get_matching_document(query) or self.get_matching_datafile(query)

    def get_matching_document(self,
                              query: str):
        res = self.documents.query(query)
        if not res.empty:
            rec = res.iloc[0]
            return FilingDocument.from_dataframe_row(rec)

    def get_matching_datafile(self,
                              query: str):
        res = self.datafiles.query(query)
        if not res.empty:
            rec = res.iloc[0]
            return FilingDocument.from_dataframe_row(rec)

    @property
    def filing_document(self):
        document: FilingDocument = self.get_matching_document(f"Description=='{self.form}'")
        return document

    @property
    def xbrl_document(self):
        xbrl_document_query = \
            "Description.isin(['XBRL INSTANCE DOCUMENT', 'XBRL INSTANCE FILE', 'EXTRACTED XBRL INSTANCE DOCUMENT'])"
        document: FilingDocument = self.get_matching_datafile(xbrl_document_query)
        if document:
            return document

    @property
    def documents(self):
        return self.filing_files.get("Document Format Files")

    @property
    def datafiles(self):
        return self.filing_files.get("Data Files")

    @classmethod
    def from_html(cls, homepage_html: str, form: str):
        soup = BeautifulSoup(homepage_html, features="html.parser")
        filing_files = dict()
        tables = soup.find_all("table", class_="tableFile")
        for table in tables:
            summary = table.attrs.get("summary")
            rows = table.find_all("tr")
            column_names = [th.text for th in rows[0].find_all("th")] + ["Url"]
            records = []
            for row in rows[1:]:
                cells = row.find_all("td")
                link = cells[2].a
                cell_values = [cell.text for cell in cells] + [link["href"] if link else None]
                records.append(cell_values)
            filing_files[summary] = (pd.DataFrame(records, columns=column_names)
                                     .filter(['Seq', 'Description', 'Type', 'Size', 'Url'])
                                     )
        return cls(filing_files, form=form)
