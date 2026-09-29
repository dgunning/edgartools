"""Date and quarter reasoning.

`extract_dates` parses the date-range strings the filing APIs accept. The quarter
helpers below answer which SEC full-index partitions a date or range falls in --
the index is published per year-quarter, so almost every fetch has to translate a
user's dates into (year, quarter) pairs first.

They moved here from `edgar.core` under edgartools-07lk.12.1 item (6), which is
the same bounded extraction `edgar/settings.py` was (PR #1075): a coherent third of
core.py goes to the module that already owns the concern, and the grab-bag that is
left keeps its name rather than being relabelled around whatever is left in it.
`edgar.core` re-exports these, so existing imports keep working until 6.0 drops the
shim. The implementation lives HERE, not there -- aliasing the other way would
leave the real code at the path 6.0 deletes (the edgartools-07lk.23 rename trap).
"""
import datetime
from datetime import date
from typing import List, Optional, Sequence, Tuple, Union
from zoneinfo import ZoneInfo

from pandas.tseries.offsets import BDay

from edgar._compat import deprecated_alias
from edgar.exceptions import InvalidDateError

__all__ = [
    "extract_dates",
    "filing_date_to_year_quarters",
    "current_year_and_quarter",
    "is_start_of_quarter",
    "parse_acceptance_datetime",
    "InvalidDateError",
    "InvalidDateException",  # deprecated alias, removed in 6.0
]

# InvalidDateException is now InvalidDateError in edgar.exceptions, under the
# ValidationError branch (bead edgartools-07lk.10) — so it is now also a
# ValueError, which is what a bad date string always was.
__getattr__ = deprecated_alias(InvalidDateException=InvalidDateError)

def extract_dates(
    date_str: Union[str, Sequence[Optional[str]]]
) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime], bool]:
    """
    Split a date or a date range into start_date and end_date
    Examples:
        extract_dates("2022-03-04") -> 2022-03-04, None, False
        extract_dates("2022-03-04:2022-04-05") -> 2022-03-04, 2022-04-05, True
        extract_dates("2022-03-04:") -> 2022-03-04, <current_date>, True
        extract_dates(":2022-03-04") -> 1994-07-01, 2022-03-04, True
        extract_dates(("2022-03-04", "2022-04-05")) -> 2022-03-04, 2022-04-05, True
        extract_dates(("2022-03-04", None)) -> 2022-03-04, <current_date>, True
        extract_dates((None, "2022-03-04")) -> 1994-07-01, 2022-03-04, True

    Args:
        date_str: Date string in YYYY-MM-DD format, optionally with a range
            separator ':'. Accepts a 2-tuple or 2-list of YYYY-MM-DD strings as
            equivalent to the colon-separated form (with ``None`` in either
            slot meaning "open" and treated the same as a missing side of
            "start:" or ":end"). The tuple form matches the public type hint
            on ``Entity.get_filings(filing_date=...)`` which had silently
            crashed before edgartools 5.30.2 (GH #794).

    Returns:
        Tuple of (start_date, end_date, is_range) where dates are datetime objects
        and is_range indicates if this was a date range query

    Raises:
        InvalidDateError: If the date string cannot be parsed
    """
    if not date_str:
        raise InvalidDateError("Empty date string provided")

    # Normalize tuple/list form into the colon-separated string form so the
    # rest of the parser stays a single code path. None in either slot is
    # treated as the "open" side of a range (same semantics as "start:" / ":end").
    if isinstance(date_str, (tuple, list)):
        if len(date_str) != 2:
            raise InvalidDateError(
                "Date range tuple must have exactly two elements (start, end); "
                f"got {len(date_str)}"
            )
        start_part, end_part = date_str
        if start_part is None and end_part is None:
            raise InvalidDateError(
                "Date range tuple must have at least one non-None bound"
            )
        date_str = f"{start_part or ''}:{end_part or ''}"

    try:
        # Split on colon, handling the single date case
        has_colon = ':' in date_str
        parts = date_str.split(':') if has_colon else [date_str]

        # Handle invalid formats
        if len(parts) != (2 if has_colon else 1):
            raise InvalidDateError("Invalid date range format")

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
            raise InvalidDateError(
                f"Invalid date range: start date ({start_date.date()}) "
                f"cannot be after end date ({end_date.date()})"
            )

        return start_date, end_date, has_colon

    except ValueError as e:
        raise InvalidDateError(f"""
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


def parse_acceptance_datetime(acceptance_datetime: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(acceptance_datetime.replace('Z', '+00:00'))
