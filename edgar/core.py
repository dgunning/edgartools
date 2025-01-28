import asyncio
import datetime
import logging.config
import os
import random
import re
import sys
import threading
import warnings
from _thread import interrupt_main
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from functools import wraps
from typing import Union, Optional, Tuple, List
from pathlib import Path
from datetime import date
import pytz
import httpx
import humanize
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from pandas.tseries.offsets import BDay
from rich.logging import RichHandler
from rich.prompt import Prompt

log = logging.getLogger(__name__)

# Pandas version
pandas_version = tuple(map(int, pd.__version__.split('.')))

# sys version
python_version = tuple(map(int, sys.version.split()[0].split('.')))

__all__ = [
    'log',
    'Result',
    'repr_df',
    'get_bool',
    'datefmt',
    'moneyfmt',
    'edgar_mode',
    'NORMAL',
    'CRAWL',
    'CAUTION',
    'sec_edgar',
    'IntString',
    'DataPager',
    'yes_no',
    'sec_dot_gov',
    'display_size',
    'reverse_name',
    'extract_dates',
    'get_resource',
    'get_identity',
    'pandas_version',
    'python_version',
    'set_identity',
    'strtobool',
    'listify',
    'decode_content',
    'filter_by_date',
    'filter_by_form',
    'filter_by_cik',
    'filter_by_ticker',
    'filter_by_accession_number',
    'split_camel_case',
    'cache_except_none',
    'text_extensions',
    'binary_extensions',
    'ask_for_identity',
    'is_start_of_quarter',
    'run_async_or_sync',
    'get_edgar_data_directory',
    'has_html_content',
    'default_page_size',
    'parse_acceptance_datetime',
    'InvalidDateException',
    'PagingState',
    'Years',
    'Quarters',
    'YearAndQuarter',
    'YearAndQuarters',
    'quarters_in_year',
]

IntString = Union[str, int]
quarters_in_year: List[int] = list(range(1, 5))

YearAndQuarter = Tuple[int, int]
YearAndQuarters = List[YearAndQuarter]
Years = Union[int, List[int], range]
Quarters = Union[int, List[int], range]

# Date patterns
YYYY_MM_DD = "\\d{4}-\\d{2}-\\d{2}"
DATE_PATTERN = re.compile(YYYY_MM_DD)
DATE_RANGE_PATTERN = re.compile(f"^({YYYY_MM_DD}(:({YYYY_MM_DD})?)?|:({YYYY_MM_DD}))$")

default_http_timeout: int = 12
default_page_size = 50
default_max_connections = 10
default_retries = 3

limits = httpx.Limits(max_connections=default_max_connections)


def strtobool (val:str):
    """Convert a string representation of truth to true (1) or false (0).

    True values are case insensitive 'y', 'yes', 't', 'true', 'on', and '1'.
    false values are case insensitive 'n', 'no', 'f', 'false', 'off', and '0'.
    Raises ValueError if 'val' is anything else.
    """
    if not val:
        return False
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        return 0
        #raise ValueError("invalid truth value %r" % (val,))


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
NORMAL = EdgarSettings(http_timeout=15, max_connections=10)

# A bit more cautious mode of accessing edgar
CAUTION = EdgarSettings(http_timeout=20, max_connections=5)

# Use this setting when you have long-running jobs and want to avoid breaching Edgar limits
CRAWL = EdgarSettings(http_timeout=25, max_connections=2, retries=2)

edgar_access_mode = os.getenv('EDGAR_ACCESS_MODE', 'NORMAL')
if edgar_access_mode == 'CAUTION':
    # A bit more cautious mode of accessing edgar
    edgar_mode = CAUTION
elif edgar_access_mode == 'CRAWL':
    # Use this setting when you have long-running jobs and want to avoid breaching Edgar limits
    edgar_mode = CRAWL
else:
    # The normal mode of accessing edgar
    edgar_mode = NORMAL

edgar_identity = 'EDGAR_IDENTITY'

# SEC urls
sec_dot_gov = "https://www.sec.gov"
sec_edgar = "https://www.sec.gov/Archives/edgar"

# Local storage directory.
edgar_data_dir = os.path.join(os.path.expanduser("~"), ".edgar")


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

    from edgar.httpclient import close_clients
    close_clients() # close any httpx clients, to reset the identity. 


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


@lru_cache(maxsize=None)
def get_edgar_data_directory() -> Path:
    """Get the edgar data directory"""
    default_local_data_dir = Path(os.path.join(os.path.expanduser("~"), ".edgar"))
    edgar_data_dir = Path(os.getenv('EDGAR_LOCAL_DATA_DIR', default_local_data_dir))
    os.makedirs(edgar_data_dir, exist_ok=True)
    return edgar_data_dir


class InvalidDateException(Exception):

    def __init__(self, message: str):
        super().__init__(message)


class TooManyRequestsException(Exception):

    def __init__(self, message: str):
        super().__init__(message)


def extract_dates(date_str: str) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime], bool]:
    """
    Split a date or a date range into start_date and end_date
    Examples:
        extract_dates("2022-03-04") -> 2022-03-04, None, False
        extract_dates("2022-03-04:2022-04-05") -> 2022-03-04, 2022-04-05, True
        extract_dates("2022-03-04:") -> 2022-03-04, <current_date>, True
        extract_dates(":2022-03-04") -> 1994-07-01, 2022-03-04, True

    Args:
        date_str: Date string in YYYY-MM-DD format, optionally with a range separator ':'

    Returns:
        Tuple of (start_date, end_date, is_range) where dates are datetime objects
        and is_range indicates if this was a date range query

    Raises:
        InvalidDateException: If the date string cannot be parsed
    """
    if not date_str:
        raise InvalidDateException("Empty date string provided")

    try:
        # Split on colon, handling the single date case
        has_colon = ':' in date_str
        parts = date_str.split(':') if has_colon else [date_str]

        # Handle invalid formats
        if len(parts) != (2 if has_colon else 1):
            raise InvalidDateException("Invalid date range format")

        # Parse start date
        if not has_colon or parts[0]:
            start_date = datetime.datetime.strptime(parts[0], "%Y-%m-%d")
        else:
            start_date = datetime.datetime.strptime('1994-07-01', '%Y-%m-%d')

        # Parse end date
        if has_colon and parts[1]:
            end_date = datetime.datetime.strptime(parts[1], "%Y-%m-%d")
        elif has_colon:
            end_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            end_date = None

        # Validate date order if both dates are present
        if has_colon and end_date and start_date > end_date:
            raise InvalidDateException(
                f"Invalid date range: start date ({start_date.date()}) "
                f"cannot be after end date ({end_date.date()})"
            )

        return start_date, end_date, has_colon

    except ValueError as e:
        raise InvalidDateException(f"""
        Cannot extract a date or date range from string {date_str}
        Provide either 
            1. A date in the format "YYYY-MM-DD" e.g. "2022-10-27"
            2. A date range in the format "YYYY-MM-DD:YYYY-MM-DD" e.g. "2022-10-01:2022-10-27"
            3. A partial date range "YYYY-MM-DD:" to specify dates after the value e.g.  "2022-10-01:"
            4. A partial date range ":YYYY-MM-DD" to specify dates before the value  e.g. ":2022-10-27"
        """) from e


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


def current_year_and_quarter() -> Tuple[int, int]:
    # Define the Eastern timezone
    eastern = pytz.timezone('America/New_York')

    # Get the current time in Eastern timezone
    now_eastern = datetime.datetime.now(eastern)

    # Calculate the current year and quarter
    current_year, current_quarter = now_eastern.year, (now_eastern.month - 1) // 3 + 1

    return current_year, current_quarter


def filter_by_date(data: pa.Table,
                   date: Union[str, datetime.datetime],
                   date_col: str) -> pa.Table:
    # If datetime convert to string
    if isinstance(date, datetime.date) or isinstance(date, datetime.datetime):
        date = date.strftime('%Y-%m-%d')

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


def filter_by_accession_number(data: pa.Table,
                               accession_number: Union[IntString, List[IntString]]) -> pa.Table:
    """Return the data filtered by accession number"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    accession_numbers = [str(el) for el in listify(accession_number)]
    data = data.filter(pc.is_in(data['accession_number'], pa.array(accession_numbers)))
    return data


def filter_by_form(data: pa.Table,
                   form: Union[str, List[str]],
                   amendments: bool = True) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    forms = [str(el) for el in listify(form)]
    if amendments:
        forms = list(set(forms + [f"{val}/A" for val in forms]))
    else:
        forms = list(set([val.replace("/A", "") for val in forms]))
    data = data.filter(pc.is_in(data['form'], pa.array(forms)))
    return data


def filter_by_cik(data: pa.Table,
                  cik: Union[IntString, List[IntString]]) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    ciks = [int(el) for el in listify(cik)]
    data = data.filter(pc.is_in(data['cik'], pa.array(ciks)))
    return data


def filter_by_ticker(data: pa.Table,
                     ticker: Union[str, List[str]]) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    from edgar.reference.tickers import get_cik_tickers
    company_tickers = get_cik_tickers()
    tickers = listify(ticker)
    filtered_tickers = company_tickers[company_tickers.ticker.isin(tickers)]
    ciks = filtered_tickers.cik.tolist()
    return filter_by_cik(data, cik=ciks)

    # return data


@lru_cache(maxsize=1)
def client_headers():
    return {'User-Agent': get_identity()}

def decode_content(content: bytes):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


text_extensions = (".txt", ".htm", ".html", ".xsd", ".xml", "XML", ".json", ".idx", ".paper")
binary_extensions = (".pdf", ".jpg", ".jpeg", "png", ".gif", ".tif", ".tiff", ".bmp", ".ico", ".svg", ".webp", ".avif",
                     ".apng")




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


def get_bool(value: str = None) -> Optional[bool]:
    """Convert the value to a boolean"""
    return value in [1, "1", "Y", "true", "True", "TRUE"]


class Result:
    """
    This class represents the result of an operation which can succeed or fail.
    It allows for handling the failures more gracefully that using error handling
    """

    def __init__(self,
                 success: bool,
                 error: Optional[str] = None,
                 value: Optional[object] = None):
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


def display_size(size: Optional[Union[int, str]]) -> str:
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

    def has_next(self):
        return self.current_page < self.total_pages

    def has_previous(self):
        return self.current_page > 1

    def next(self):
        """Get the next page of data"""
        if self.has_next():
            self.current_page += 1
            return self.current()
        else:
            return None

    def previous(self):
        """Get the previous page of data"""
        if self.has_previous():
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

    @property
    def start_index(self):
        return (self.current_page - 1) * self.page_size

    @property
    def end_index(self):
        return self.start_index + self.page_size


@dataclass
class PagingState:
    page_start: int
    num_records: int



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


def datefmt(value: Union[datetime.datetime, str], fmt: str = "%Y-%m-%d") -> str:
    """Format a date as a string"""
    if isinstance(value, str):
        # if value matches %Y%m%d, then parse it
        if re.match(r"^\d{8}$", value):
            value = datetime.datetime.strptime(value, "%Y%m%d")
        # If value matches %Y%m%d%H%M%s, then parse it
        elif re.match(r"^\d{14}$", value):
            value = datetime.datetime.strptime(value, "%Y%m%d%H%M%S")
        elif re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            value = datetime.datetime.strptime(value, "%Y-%m-%d")
        return value.strftime(fmt)
    else:
        return value.strftime(fmt)

def parse_acceptance_datetime(acceptance_datetime: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(acceptance_datetime.replace('Z', '+00:00'))


def sample_table(table, n=None, frac=None, replace=False, random_state=None):
    """Take a sample from a pyarrow Table"""
    if random_state:
        random.seed(random_state)

    if frac is not None:
        n = int(len(table) * frac)

    if n is not None:
        if replace:
            indices = [random.randint(0, len(table) - 1) for _ in range(n)]
        else:
            indices = random.sample(range(len(table)), min(n, len(table)))
    else:
        indices = random.sample(range(len(table)), len(table))

    return table.take(indices)


def reverse_name(name):
    # Split the name into parts
    parts = name.split()

    # Return immediately if there's only one name part
    if len(parts) == 1:
        return parts[0].title()

    # Handle the cases where there's a 'Jr', 'Sr', 'II', 'III', 'MD', etc., or 'ET AL'
    special_parts = ['Jr', 'JR', 'Sr', 'SR', 'II', 'III', 'MD', 'ET', 'AL', 'et', 'al']
    special_parts_with_period = [part + '.' for part in special_parts if part not in ['II', 'III']] + special_parts
    special_part_indices = [i for i, part in enumerate(parts) if part in special_parts_with_period or (
            i > 0 and parts[i - 1].rstrip('.') + ' ' + part.rstrip('.') == 'ET AL')]

    # Extract the special parts and the main name parts
    special_parts_list = [parts[i] for i in special_part_indices]
    main_name_parts = [part for i, part in enumerate(parts) if i not in special_part_indices]

    # Handle initials in the name
    if len(main_name_parts) > 2 and (('.' in main_name_parts[-2] or len(main_name_parts[-2]) == 1)):
        main_name_parts = [' '.join(main_name_parts[:-2]).title()] + [
            f"{main_name_parts[-1].title()} {main_name_parts[-2]}"]
    else:
        main_name_parts = [part.title() if len(part) > 2 else part for part in main_name_parts]

    # Reverse the main name parts
    reversed_main_parts = [part for part in main_name_parts[1:]] + [main_name_parts[0]]
    reversed_name = " ".join(reversed_main_parts)

    # Append the special parts to the reversed name, maintaining their original case
    if special_parts_list:
        reversed_name += " " + " ".join(special_parts_list)

    return reversed_name


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def split_camel_case(item):
    # Check if the string is all uppercase or all lowercase
    if item.isupper() or item.islower():
        return item
    else:
        # Split at the boundary between uppercase and lowercase, and between lowercase and uppercase
        words = re.findall(r'[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+|[A-Z]?[a-z]+|\W+', item)
        # Join the words, preserving consecutive uppercase words
        result = []
        for i, word in enumerate(words):
            if i > 0 and word.isupper() and words[i - 1].isupper():
                result[-1] += word
            else:
                result.append(word)
        return ' '.join(result)


def run_async_or_sync(coroutine):
    try:
        # Check if we're in an IPython environment
        ipython = sys.modules['IPython']
        if 'asyncio' in sys.modules:
            # try is needed for ipython console
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                import nest_asyncio
                nest_asyncio.apply()
                loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in a notebook with an active event loop
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coroutine)
            else:
                # We're in IPython but without an active event loop
                return loop.run_until_complete(coroutine)
        else:
            # We're in IPython but asyncio is not available
            return ipython.get_ipython().run_cell_magic('time', '', f'import asyncio; asyncio.run({coroutine!r})')
    except (KeyError, AttributeError):
        # We're not in an IPython environment, use asyncio.run()
        return asyncio.run(coroutine)


def listify(value):
    """
    Convert the input to a list if it's not already a list.

    Args:
    value: Any type of input

    Returns:
    list: The input as a list
    """
    if isinstance(value, list):
        return value
    elif isinstance(value, range):
        return list(value)
    else:
        return [value]


def is_start_of_quarter():
    today = datetime.datetime.now().date()

    # Check if it's the start of a quarter
    if today.month in [1, 4, 7, 10] and today.day <= 5:
        # Get the first day of the current quarter
        first_day_of_quarter = datetime.datetime(today.year, today.month, 1).date()

        # Calculate one business day after the start of the quarter
        one_business_day_after = (first_day_of_quarter + BDay(1)).date()

        # Check if we haven't passed one full business day yet
        if today <= one_business_day_after:
            return True

    return False


def format_date(date: Union[str, datetime.datetime], fmt: str = "%Y-%m-%d") -> str:
    """
    Format a date as a string
    :param date: The date to format
    :param fmt: The format to use
    :return: The formatted date
    """
    if isinstance(date, str):
        return date
    else:
        return date.strftime(fmt)


def cache_except_none(maxsize=128):
    """
    A decorator that caches the result of a function, but only if the result is not None.
    """
    def decorator(func):
        cache = lru_cache(maxsize=maxsize)

        @cache
        def cached_func(*args, **kwargs):
            result = func(*args, **kwargs)
            if result is None:
                # Clear this result from the cache
                cached_func.cache_clear()
            return result

        @wraps(func)
        def wrapper(*args, **kwargs):
            return cached_func(*args, **kwargs)

        # Preserve cache methods
        wrapper.cache_info = cached_func.cache_info
        wrapper.cache_clear = cached_func.cache_clear
        return wrapper

    return decorator


def has_html_content(content: str) -> bool:
    """
    Check if the content is HTML or inline XBRL HTML
    """
    if isinstance(content, bytes):
        content = content.decode('utf-8', errors='ignore')

    # Strip only leading whitespace and get first 200 chars for doctype check
    content = content.lstrip()
    first_200_lower = content[:200].lower()

    # Check for XHTML doctype declarations
    if '<!doctype html public "-//w3c//dtd xhtml' in first_200_lower or \
            '<!doctype html system "http://www.w3.org/tr/xhtml1/dtd/' in first_200_lower or \
            '<!doctype html public "-//w3c//dtd html 4.01 transitional//en"' in first_200_lower:
        return True

    # Look for common XML/HTML indicators in first 1000 chars
    first_1000 = content[:1000]

    # Check for standard XHTML namespace
    if 'xmlns="http://www.w3.org/1999/xhtml"' in first_1000:
        return True

    # Check for HTML root element
    if '<html' in first_1000:
        # Check for common inline XBRL namespaces
        if ('xmlns:xbrli' in first_1000 or
                'xmlns:ix' in first_1000 or
                'xmlns:html' in first_1000):
            return True

    # Just check for straightforward HTML
    if first_200_lower.startswith('<html>') and content[-7:].lower().startswith('</html>'):
        return True

    return False


def initialize_rich_logging():
    # Rich logging
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )

    # Turn down 3rd party logging
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Turn on rich logging if the environment variable is set
if os.getenv('EDGAR_USE_RICH_LOGGING', '0') == '1':
    initialize_rich_logging()