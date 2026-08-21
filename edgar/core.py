import asyncio
import datetime
import logging.config
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from functools import lru_cache, partial, wraps
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar, Union

import pandas as pd
import pyarrow as pa
from zoneinfo import ZoneInfo
from pandas.tseries.offsets import BDay
from rich.logging import RichHandler

from edgar.datatools import PagingState

log = logging.getLogger(__name__)

def parse_pandas_version():
    """Parse pandas version without external dependencies"""
    version_parts = pd.__version__.split('.')
    major = int(version_parts[0])
    minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    # Handle dev versions, rc versions, and build metadata
    patch_str = version_parts[2] if len(version_parts) > 2 else '0'
    patch = int(patch_str.split('+')[0].split('rc')[0].split('dev')[0])
    return (major, minor, patch)

pandas_version = parse_pandas_version()

# sys version
python_version = tuple(map(int, sys.version.split()[0].split('.')))

__all__ = [
    'log',
    'Result',
    'get_bool',
    'edgar_mode',
    'NORMAL',
    'CRAWL',
    'CAUTION',
    'IntString',
    'get_identity',
    'python_version',
    'set_identity',
    'strtobool',
    'listify',
    'decode_content',
    'cache_except_none',
    'text_extensions',
    'binary_extensions',
    'ask_for_identity',
    'is_start_of_quarter',
    'run_async_or_sync',
    'get_edgar_data_directory',
    'is_probably_html',
    'has_html_content',
    'default_page_size',
    'parse_acceptance_datetime',
    'PagingState',
    'Years',
    'Quarters',
    'YearAndQuarter',
    'YearAndQuarters',
    'quarters_in_year',
    'parallel_thread_map',
    'pandas_version'
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

# ---------------------------------------------------------------------------
# Settings and identity now live in edgar/settings.py (edgartools-07lk.12.1).
#
# These are RE-EXPORTS, not aliases: the implementation moved to the canonical
# name and this module imports it back, rather than the reverse. Aliasing onto
# the deprecated name is the trap 07lk.23 names — it leaves the real code at the
# path you intend to delete, so 6.0 cannot simply drop the shim.
#
# The whole block below goes away in 6.0. Every one of the 71 call sites is a
# `from edgar.core import <name>` (measured: zero `import edgar.core`, zero
# attribute access), so a re-export covers 100% of them.
# ---------------------------------------------------------------------------
from edgar.settings import (  # noqa: E402,F401  -- re-exports, intentionally unused here
    CAUTION,
    CRAWL,
    NORMAL,
    EdgarSettings,
    ask_for_identity,
    default_http_timeout,
    default_max_connections,
    default_page_size,
    default_retries,
    edgar_access_mode,
    edgar_data_dir,
    edgar_identity,
    edgar_mode,
    get_edgar_data_directory,
    get_identity,
    identity_prompt,
    limits,
    set_identity,
)


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
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    else:
        return False
        #raise ValueError("invalid truth value %r" % (val,))


def decode_content(content: bytes):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


# Extension tables. Entries MUST be lowercase and dot-prefixed: membership is tested against
# a normalized extension (see Attachment.is_text/is_binary), so a bare or uppercase entry here
# can never match. Two such entries ("png", "XML") silently classified nothing for years, which
# is how a .PDF primary document reached a UTF-8 decode and raised (edgartools-dzwm).
text_extensions = (".txt", ".htm", ".html", ".xsd", ".xml", ".json", ".idx", ".paper", ".css", ".js")
binary_extensions = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".ico", ".svg", ".webp",
                     ".avif", ".apng", ".xlsx", ".xls", ".zip", ".docx", ".pptx")


def get_bool(value: Optional[str] = None) -> Optional[bool]:
    """Convert the value to a boolean"""
    return value in [1, "1", "Y", "true", "True", "TRUE"]


class Result:
    """Deprecated, removed in 6.0. Nothing imports this.

    It was scaffolding for a flagged-result pattern that never got adopted —
    zero importers anywhere in the codebase. The pattern that *did* get adopted
    is NonAccrualResult (edgar/bdc/nonaccrual.py): a frozen dataclass carrying
    the value plus its provenance and warnings, so a caller can tell "genuinely
    zero" from "we may have failed to parse". Use that shape instead.
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
    return importlib.resources.as_file(importlib.resources.files(edgar).joinpath(file))


# TooManyRequestsException was a dead duplicate of
# edgar.exceptions.TooManyRequestsError: never raised anywhere, different
# suffix, same meaning. Kept as a deprecated alias (see the module __getattr__
# at the end of this file); removed in 6.0.


def filing_date_to_year_quarters(filing_date: str) -> List[Tuple[int, int]]:
    if ":" in filing_date:
        start_date, end_date = filing_date.split(":")

        if not start_date:
            # SEC's full-index goes back to 1993 Q1 - see available_quarters() in _filings.py
            start_date = "1993-01-01"

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
    eastern = ZoneInfo('America/New_York')

    # Get the current time in Eastern timezone
    now_eastern = datetime.datetime.now(eastern)

    # Calculate the current year and quarter
    current_year, current_quarter = now_eastern.year, (now_eastern.month - 1) // 3 + 1

    return current_year, current_quarter


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

def is_probably_html(content: str) -> bool:
    """Does it have html tags"""
    if isinstance(content, bytes):
        content = content.decode('utf-8', errors='ignore')

    # Check for common HTML tags. Lowercase once: `content` can be hundreds of MB and
    # doing it inside the generator allocated a fresh copy for every tag tried.
    html_tags = ['<html>', '<body>', '<head>', '<title>', '<div', '<span', '<p>']
    lowered = content.lower()
    return any(tag in lowered for tag in html_tags)

def has_html_content(content: str) -> bool:
    """
    Check if the content is HTML or inline XBRL HTML
    """
    if content is None:
        return False

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

        # If we have an <html> tag, it's likely HTML content
        # This catches cases like <html style="..."> that don't have XBRL namespaces
        return True

    # Just check for straightforward HTML
    if first_200_lower.startswith('<html>') and content[-7:].lower().startswith('</html>'):
        return True

    return False


T = TypeVar('T')
R = TypeVar('R')

def parallel_thread_map(func: Callable[[T], R],
                        items: Iterable[T],
                        **kwargs) -> List[R]:
    """
    Run a function in parallel across multiple items using ThreadPoolExecutor.

    This is a replacement for fastcore's parallel function, supporting only the threadpool
    execution mode. It does not include progress bars.

    Args:
        func: The function to apply to each item
        items: The items to process
        **kwargs: Additional keyword arguments to pass to func

    Returns:
        List of results from applying func to each item
    """
    # Default to min(32, cores+4) which is a good balance for I/O-bound tasks
    max_workers = kwargs.pop('n_workers', None) or min(32, (os.cpu_count() or 1) + 4)

    # Convert items to a list for easier handling
    items_list = list(items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if kwargs:
            # If there are kwargs, create a partial function
            partial_func = partial(func, **kwargs)
            results = list(executor.map(partial_func, items_list))
        else:
            results = list(executor.map(func, items_list))

    return results


def initialize_rich_logging():
    # Rich logging
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )

    # Third-party loggers already suppressed at module level


# Suppress noisy third-party loggers by default.
# Users can override after import: logging.getLogger("httpx").setLevel(logging.DEBUG)
_NOISY_LOGGERS = {
    "httpx": logging.WARNING,
    "httpxthrottlecache": logging.WARNING,
    "pyrate_limiter": logging.CRITICAL,  # Emits spurious "async" messages at WARNING
}
for _logger_name, _level in _NOISY_LOGGERS.items():
    _lg = logging.getLogger(_logger_name)
    if _lg.level == logging.NOTSET:  # Only set if user hasn't already configured
        _lg.setLevel(_level)

# Turn on rich logging if the environment variable is set
if os.getenv('EDGAR_USE_RICH_LOGGING', '0') == '1':
    initialize_rich_logging()


# ---------------------------------------------------------------------------
# Deprecated names (bead edgartools-07lk.10), removed in 6.0.
# ---------------------------------------------------------------------------
from edgar._compat import deprecated_alias  # noqa: E402
from edgar.exceptions import TooManyRequestsError  # noqa: E402

__getattr__ = deprecated_alias(TooManyRequestsException=TooManyRequestsError)
