import datetime
import logging.config
import os
import random
import re
import sys
import threading
import asyncio
import warnings
from _thread import interrupt_main
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Union, Optional, Tuple, List

import httpx
import humanize
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from rich.logging import RichHandler
from rich.prompt import Prompt

# Rich logging
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

log = logging.getLogger("rich")

# Pandas version
pandas_version = tuple(map(int, pd.__version__.split('.')))

# sys version
python_version = tuple(map(int, sys.version.split()[0].split('.')))

# Turn down 3rd party logging
logging.getLogger("httpx").setLevel(logging.WARNING)

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
    'http_client',
    'sec_dot_gov',
    'display_size',
    'reverse_name',
    'extract_dates',
    'get_resource',
    'get_identity',
    'pandas_version',
    'python_version',
    'set_identity',
    'listify',
    'decode_content',
    'filter_by_date',
    'filter_by_form',
    'filter_by_cik',
    'filter_by_ticker',
    'split_camel_case',
    'text_extensions',
    'binary_extensions',
    'ask_for_identity',
    'use_local_storage',
    'run_async_or_sync',
    'download_edgar_data',
    'default_page_size',
    'InvalidDateException',
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
NORMAL = EdgarSettings(http_timeout=15, max_connections=10)

# A bit more cautious mode of accessing edgar
CAUTION = EdgarSettings(http_timeout=20, max_connections=5)

# Use this setting when you have long-running jobs and want to avoid breaching Edgar limits
CRAWL = EdgarSettings(http_timeout=25, max_connections=2, retries=2)

# Use normal mode
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


def get_edgar_data_directory() -> Path:
    """Get the edgar data directory"""
    default_local_data_dir = Path(os.path.join(os.path.expanduser("~"), ".edgar"))
    edgar_data_dir = Path(os.getenv('EDGAR_LOCAL_DATA_DIR', default_local_data_dir))
    if not edgar_data_dir.exists():
        os.makedirs(edgar_data_dir)
    return edgar_data_dir


def use_local_storage(use_local: bool = True):
    """
    Will use local data if set to True
    """
    os.environ['EDGAR_USE_LOCAL_DATA'] = "1" if use_local else "0"


def download_edgar_data(submissions: bool = True, facts: bool = True):
    """
    Download Edgar data to the local storage directory
    :param submissions: Download submissions
    :param facts: Download facts
    """
    if submissions:
        from edgar.entities import download_submissions
        download_submissions()
    if facts:
        from edgar.entities import download_facts
        download_facts()


class InvalidDateException(Exception):

    def __init__(self, message: str):
        super().__init__(message)


class TooManyRequestsException(Exception):

    def __init__(self, message: str):
        super().__init__(message)


def extract_dates(date: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Split a date or a date range into start_date and end_date
        split_date("2022-03-04")
          2022-03-04, None, False
       split_date("2022-03-04:2022-04-05")
        2022-03-04, 2022-04-05, True
       split_date("2022-03-04:")
        2022-03-04, None, True
       split_date(":2022-03-04")
        None, 2022-03-04, True
    :param date: The date to split
    :return:
    """
    match = re.match(DATE_RANGE_PATTERN, date)
    if match:
        start_date, _, end_date = match.groups()
        try:
            start_date_tm = datetime.datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_date_tm = datetime.datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
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


def filter_by_form(data: pa.Table,
                   form: Union[str, List[str]],
                   amendments: bool = True) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    forms = [str(el) for el in listify(form)]
    # If amendments then add amendments
    if amendments:
        forms = list(set(forms + [f"{val}/A" for val in forms]))
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
    from edgar.entities import get_company_tickers
    company_tickers = get_company_tickers()
    tickers = [str(el) for el in listify(ticker)]
    filtered_tickers = company_tickers[company_tickers.ticker.isin(tickers)]
    ciks = filtered_tickers.cik.tolist()
    return filter_by_cik(data, cik=ciks)

    # return data


@lru_cache(maxsize=1)
def client_headers():
    return {'User-Agent': get_identity()}


def http_client():
    return httpx.Client(headers=client_headers(),
                        timeout=edgar_mode.http_timeout,
                        limits=edgar_mode.limits,
                        default_encoding="utf-8")


def async_http_client():
    return httpx.AsyncClient(headers=client_headers(),
                             timeout=edgar_mode.http_timeout,
                             limits=edgar_mode.limits,
                             default_encoding='utf-8')


def get_json(data_url: str):
    with http_client() as client:
        r = client.get(data_url)
        if r.status_code == 200:
            return r.json()
        r.raise_for_status()


def decode_content(content: bytes):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


text_extensions = (".txt", ".htm", ".html", ".xsd", ".xml", "XML", ".json", ".idx", ".paper")
binary_extensions = (".pdf", ".jpg", ".jpeg", "png", ".gif", ".tif", ".tiff", ".bmp", ".ico", ".svg", ".webp", ".avif",
                     ".apng")


def extract_text_between_tags(content: str, tag: str) -> str:
    """
    Extracts text from provided content between the specified HTML/XML tags.

    :param content: The text content to search through
    :param tag: The tag to extract the content from
    :return: The extracted text between the tags
    """
    tag_start = f'<{tag}>'
    tag_end = f'</{tag}>'
    is_tag = False
    extracted_content = ""

    for line in content.splitlines():
        if line.startswith(tag_start):
            is_tag = True
            continue  # Skip the start tag line
        elif line.startswith(tag_end):
            break  # Stop reading if end tag is found
        elif is_tag:
            extracted_content += line + '\n'  # Add line to result

    return extracted_content.strip()


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

    @property
    def start_index(self):
        return (self.current_page - 1) * self.page_size

    @property
    def end_index(self):
        return self.start_index + self.page_size


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
        return value.strftime(fmt)
    else:
        return value.strftime(fmt)


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
            if i > 0 and word.isupper() and words[i-1].isupper():
                result[-1] += word
            else:
                result.append(word)
        return ' '.join(result)


def run_async_or_sync(coroutine):
    try:
        # Check if we're in an IPython environment
        ipython = sys.modules['IPython']
        if 'asyncio' in sys.modules:
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
    else:
        return [value]