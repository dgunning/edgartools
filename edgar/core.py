import gzip
import logging.config
import os
import re
import threading
import warnings
from _thread import interrupt_main
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from typing import Union, Optional, Tuple

import httpx
import humanize
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from charset_normalizer import detect
from rich.logging import RichHandler
from rich.prompt import Prompt
from retry.api import retry_call

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

log = logging.getLogger("rich")

__all__ = [
    'log',
    'Result',
    'repr_df',
    'get_bool',
    'moneyfmt',
    'edgar_mode',
    'NORMAL',
    'CRAWL',
    'CAUTION',
    'sec_edgar',
    'IntString',
    'DataPager',
    'http_client',
    'sec_dot_gov',
    'display_size',
    'extract_dates',
    'get_resource',
    'get_identity',
    'set_identity',
    'download_text',
    'download_file',
    'decode_content',
    'filter_by_date',
    'ask_for_identity',
    'default_page_size',
    'InvalidDateException'
]

IntString = Union[str, int]

# Date patterns
YYYY_MM_DD = "\\d{4}-\\d{2}-\\d{2}"
DATE_PATTERN = re.compile(YYYY_MM_DD)
DATE_RANGE_PATTERN = re.compile(f"({YYYY_MM_DD})?:?(({YYYY_MM_DD})?)?")

default_http_timeout: int = 12
default_page_size = 50
default_max_connections = 10
default_retries = 3

limits = httpx.Limits(max_connections=default_max_connections)


@dataclass
class EdgarSettings:
    http_timeout: int
    max_connections: int
    retries: int = 3

    @property
    @lru_cache(maxsize=1)
    def limits(self):
        return httpx.Limits(max_connections=default_max_connections)

    def __eq__(self, othr):
        return (isinstance(othr, type(self))
                and (self.http_timeout, self.max_connections, self.retries) ==
                (othr.http_timeout, othr.max_connections, othr.retries))

    def __hash__(self):
        return hash((self.http_timeout, self.max_connections, self.retries))


# Modes of accessing edgar

# The normal mode of accessing edgar
NORMAL = EdgarSettings(http_timeout=12, max_connections=10)

# A bit more cautious mode of accessing edgar
CAUTION = EdgarSettings(http_timeout=15, max_connections=5)

# Use this setting when you have long-running jobs and want to avoid breaching Edgar limits
CRAWL = EdgarSettings(http_timeout=20, max_connections=2, retries=2)

# Use normal mode
edgar_mode = NORMAL

edgar_identity = 'EDGAR_IDENTITY'

# SEC urls
sec_dot_gov = "https://www.sec.gov"
sec_edgar = "https://www.sec.gov/Archives/edgar"


def set_identity(user_identity: str):
    """
    This function sets the environment variable EDGAR_IDENTITY to the identity you will use to call Edgar

    This user identity looks like

        "Sample Company Name AdminContact@<sample company domain>.com"

    See https://www.sec.gov/os/accessing-edgar-data

    :param user_identity:
    """
    os.environ[edgar_identity] = user_identity
    log.info(f"Identity of the Edgar REST client set to [{user_identity}]")


identity_prompt = """
[bold turquoise4]Identify your client to SEC Edgar[/bold turquoise4]
------------------------------------------------------------------------------

Before running [bold]edgartools[/bold] it needs to know the UserAgent string to send to Edgar.
See https://www.sec.gov/os/accessing-edgar-data

This can be set in the environment variable [bold green]EDGAR_IDENTITY[/bold green].

1. Set an OS environment variable 
    [bold]EDGAR_IDENTITY=[green]Name email@domain.com[/green][/bold] 
2. Or a Python environment variable
    import os
    [bold]os.environ['EDGAR_IDENTITY']=[green]"Name email@domain.com"[/green][/bold]
3. Or use [bold magenta]edgartools.set_identity[/bold magenta]
    from edgar import set_identity
    [bold]set_identity([green]'Name email@domain.com'[/green])[/bold]

But since you are already using [bold]edgartools[/bold] you can set it here

Enter your [bold green]EDGAR_IDENTITY[/bold green] e.g. [bold italic green]Name email@domain.com[/bold italic green]
"""


def ask_for_identity(user_prompt: str = identity_prompt,
                     timeout: int = 60):
    timer = threading.Timer(timeout, interrupt_main)
    timer.start()

    try:
        # Prompt the user for input
        input_str = Prompt.ask(user_prompt)

        # Strip the newline character from the end of the input string
        input_str = input_str.strip()
    except KeyboardInterrupt:
        # If the timeout is reached, raise a TimeoutError exception
        message = "You did not enter your Edgar user identity. Try again .. or set environment variable EDGAR_IDENTITY"
        log.warning(message)
        raise TimeoutError(message)
    finally:
        # Cancel the timer to prevent it from interrupting the main thread
        timer.cancel()

    return input_str


def get_identity() -> str:
    """
    Get the sec identity used to set the UserAgent string
    :return:
    """
    identity = os.environ.get(edgar_identity)
    if not identity:
        identity = ask_for_identity()
        os.environ[edgar_identity] = identity
    return identity


class InvalidDateException(Exception):

    def __init__(self, message: str):
        super().__init__(message)


def extract_dates(date: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Split a date or a date range into start_date and end_date
    >>> split_date("2022-03-04")
          2022-03-04, None, False
    >>> split_date("2022-03-04:2022-04-05")
        2022-03-04, 2022-04-05, True
    >>> split_date("2022-03-04:")
        2022-03-04, None, True
    >>> split_date(":2022-03-04")
        None, 2022-03-04, True
    :param date: The date to split
    :return:
    """
    match = re.match(DATE_RANGE_PATTERN, date)
    if match:
        start_date, _, end_date = match.groups()
        try:
            start_date_tm = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_date_tm = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
            if start_date_tm or end_date_tm:
                return start_date_tm, end_date_tm, ":" in date
        except ValueError:
            log.error(f"The date {date} cannot be extracted using date pattern YYYY-MM-DD")
    raise InvalidDateException(f"""
    Cannot extract a date or date range from string {date}
    Provide either 
        1. A date in the format "YYYY-MM-DD" e.g. "2022-10-27"
        2. A date range in the format "YYYY-MM-DD:YYYY-MM-DD" e.g. "2022-10-01:2022-10-27"
        3. A partial date range "YYYY-MM-DD:" to specify dates after the value e.g.  "2022-10-01:"
        4. A partial date range ":YYYY-MM-DD" to specify dates before the value  e.g. ":2022-10-27"
    """)


def filter_by_date(data: pa.Table,
                   date: str,
                   date_col: str):
    # Extract the date parts ... this should raise an exception if we cannot
    date_parts = extract_dates(date)
    start_date, end_date, is_range = date_parts
    if is_range:
        filtered_data = data
        if start_date:
            filtered_data = filtered_data.filter(pc.field(date_col) >= pc.scalar(start_date))
        if end_date:
            filtered_data = filtered_data.filter(pc.field(date_col) <= pc.scalar(end_date))
    else:
        # filter by filings on date
        filtered_data = data.filter(pc.field(date_col) == pc.scalar(start_date))
    return filtered_data


def autodetect(content):
    return detect(content).get("encoding")


@lru_cache(maxsize=1)
def client_headers():
    return {'User-Agent': get_identity()}


def http_client():
    return httpx.Client(headers=client_headers(),
                        timeout=edgar_mode.http_timeout,
                        limits=edgar_mode.limits,
                        default_encoding=autodetect)


def decode_content(content: bytes):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


def download_file(url: str,
                  client: Union[httpx.Client, httpx.AsyncClient] = None,
                  as_text: bool = None):
    # reason_phrase = 'Too Many Requests' status_code = 429
    if not client:
        client = http_client()
        
    r = retry_call(client.get, fargs=[url], tries=5, delay=3)
    if r.status_code == 200:
        if url.endswith("gz"):
            binary_file = BytesIO(r.content)
            with gzip.open(binary_file, 'rb') as f:
                file_content = f.read()
                if as_text:
                    return decode_content(file_content)
                return file_content
        else:
            # If we explicitely asked for text or there is an encoding, try to return text
            if as_text or r.encoding:
                return r.text
            # Should get here for jpg and PDFs
            return r.content
    else:
        r.raise_for_status()


def download_text(url: str, client: Union[httpx.Client, httpx.AsyncClient] = None):
    return download_file(url, client, as_text=True)


def repr_df(df, hide_index: bool = True):
    disp = df.style
    if hide_index:
        # TODO
        # Note this is deprecated in pandas 1.4.0 but needed to support python 3.7/pandas 1.3.5
        # Should be instead
        # disp = disp.hide(axis="index")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            disp = disp.hide_index()
    return disp._repr_html_()


def get_bool(value: str = None) -> bool:
    """Convert the value to a boolean"""
    if value is None:
        return None
    if value == '1' or value == 1:
        return True
    return False


class Result:
    """
    This class represents the result of an operation which can succeed or fail.
    It allows for handling the failures more gracefully that using error handling
    """

    def __init__(self,
                 success: bool,
                 error: str,
                 value: object):
        self.success = success
        self.error = error
        self.value = value

    @property
    def failure(self) -> bool:
        """:return True if the operation failed"""
        return not self.success

    def __str__(self):
        if self.success:
            return '[Success]'
        else:
            return f'[Failure] "{self.error}"'

    def __repr__(self):
        if self.success:
            return f"Result (success={self.success})"
        else:
            return f'Result (success={self.success}, message="{self.error}")'

    @classmethod
    def Fail(cls,
             error: str):
        """Create a Result for a failed operation"""
        return cls(False, error=error, value=None)

    @classmethod
    def Ok(cls,
           value: object):
        """Create a Result for a successful operation"""
        return cls(success=True, value=value, error=None)


def get_resource(file: str):
    import importlib
    import edgar
    return importlib.resources.path(edgar, file)


def display_size(size: Optional[int]) -> str:
    """
    :return the size in KB or MB as a string
    """
    if size:
        if isinstance(size, int) or size.isdigit():
            return humanize.naturalsize(int(size), binary=True).replace("i", "")
    return ""


class DataPager:
    def __init__(self,
                 data: Union[pa.Table, pd.DataFrame],
                 page_size=default_page_size):
        self.data: Union[pa.Table, pd.DataFrame] = data
        self.page_size = page_size
        self.total_pages = (len(self.data) // page_size) + 1
        self.current_page = 1

    def next(self):
        """Get the next page of data"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            return self.current()
        else:
            return None

    def previous(self):
        """Get the previous page of data"""
        if self.current_page > 1:
            self.current_page -= 1
            return self.current()
        else:
            return None

    @property
    def _current_range(self) -> Tuple[int, int]:
        """Get the current start and end index for the data"""
        start_index = (self.current_page - 1) * self.page_size
        end_index = min(len(self.data), start_index + self.page_size)
        return start_index, end_index

    def current(self) -> pa.Table:
        """
        Get the current data page as a pyarrow Table
        :return:
        """
        start_index = (self.current_page - 1) * self.page_size
        end_index = start_index + self.page_size
        if isinstance(self.data, pa.Table):
            return self.data.slice(offset=start_index, length=self.page_size)
        else:
            return self.data.iloc[start_index:end_index]


def moneyfmt(value, places=0, curr='$', sep=',', dp='.',
             pos='', neg='-', trailneg=''):
    """Convert Decimal to a money formatted string.

    places:  required number of places after the decimal point
    curr:    optional currency symbol before the sign (may be blank)
    sep:     optional grouping separator (comma, period, space, or blank)
    dp:      decimal point indicator (comma or period)
             only specify as blank when places is zero
    pos:     optional sign for positive numbers: '+', space or blank
    neg:     optional sign for negative numbers: '-', '(', space or blank
    trailneg:optional trailing minus indicator:  '-', ')', space or blank

    >>> d = Decimal('-1234567.8901')
    >>> moneyfmt(d, curr='$')
    '-$1,234,567.89'
    >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
    '1.234.568-'
    >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
    '($1,234,567.89)'
    >>> moneyfmt(Decimal(123456789), sep=' ')
    '123 456 789.00'
    >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
    '<0.02>'

    """
    q = Decimal(10) ** -places  # 2 places --> '0.01'
    sign, digits, exp = value.quantize(q).as_tuple()
    result = []
    digits = list(map(str, digits))
    build, next = result.append, digits.pop
    if sign:
        build(trailneg)
    for i in range(places):
        build(next() if digits else '0')
    if places:
        build(dp)
    if not digits:
        build('0')
    i = 0
    while digits:
        build(next())
        i += 1
        if i == 3 and digits:
            i = 0
            build(sep)
    build(curr)
    build(neg if sign else pos)
    return ''.join(reversed(result))
