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
import re
from datetime import date
from typing import List, Optional, Sequence, Tuple, Union
from zoneinfo import ZoneInfo

from pandas.tseries.offsets import BDay

from edgar.exceptions import InvalidDateError

# SEC's own clock: EDGAR acceptance times and market sessions are Eastern time.
SEC_TIMEZONE = ZoneInfo("America/New_York")

__all__ = [
    "calculate_fiscal_year_for_label",
    "fiscal_year_end_month",
    "extract_dates",
    "filing_date_to_year_quarters",
    "current_year_and_quarter",
    "is_start_of_quarter",
    "parse_acceptance_datetime",
    "normalize_period_boundary",
    "SEC_TIMEZONE",
    "InvalidDateError",
]


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
    eastern = SEC_TIMEZONE

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


_WHOLE_DAY_DATETIME_RE = re.compile(r'(\d{4}-\d{2}-\d{2})T(00|24):00:00(?:\.0+)?')


def normalize_period_boundary(text: Optional[str], is_end: bool) -> Optional[str]:
    """An XBRL context period boundary (``xbrli:dateUnion``) in its date-only form.

    The type collapses whitespace, so `` 2024-06-30 `` is 2024-06-30. A
    date-only instant or ``endDate`` means the end of that day (XBRL 2.1
    §4.7.2), so for an end boundary ``2025-01-01T00:00:00`` is the same point
    as ``2024-12-31``. A ``startDate`` means the start of its day, so
    ``2024-01-01T00:00:00`` is ``2024-01-01``. ``T24:00:00`` is the end of the
    day it names. Both are folded onto the date-only spelling, so equal periods
    share one key (GH #1762).

    A dateTime that is not a whole-day boundary, or that carries a timezone,
    has no date-only equivalent and comes back with only its whitespace
    collapsed. The XBRL instance parser and the inline (edgar.documents) context
    reader both use this, so the two readings cannot drift apart.
    """
    if text is None:
        return None
    value = ' '.join(text.split())
    match = _WHOLE_DAY_DATETIME_RE.fullmatch(value)
    if match is None:
        return value
    try:
        day = date.fromisoformat(match.group(1))
    except ValueError:
        return value
    midnight = match.group(2) == '00'
    if is_end and midnight:
        day -= datetime.timedelta(days=1)
    elif not is_end and not midnight:
        day += datetime.timedelta(days=1)
    return day.isoformat()


def parse_acceptance_datetime(acceptance_datetime: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(acceptance_datetime.replace('Z', '+00:00'))


def fiscal_year_end_month(month: int, day: int) -> int:
    """The month a fiscal year that ends on ``month``/``day`` belongs to.

    A 52/53-week year closes on the weekday nearest a month end, which can land
    in the first week of the next month: Sprouts' and Krispy Kreme's December
    years close on 2023-01-01, Costco's August year on 2023-09-03. Those dates
    belong to the previous month, so a year end on day 1-7 counts as that month.
    """
    if day <= 7:
        return 12 if month == 1 else month - 1
    return month


def calculate_fiscal_year_for_label(period_end: date, fiscal_year_end_month: int) -> int:
    """
    Calculate the fiscal year label for a period based on the dominant convention:
    fiscal years are named by the calendar year in which they end.

    This matches how companies, the SEC, Bloomberg, S&P Capital IQ, and other
    financial data providers label fiscal years. For example, Autodesk's fiscal
    year ending Jan 31, 2026 is "FY2026", and Q1 (Feb-Apr 2025) is "Q1 2026".

    Args:
        period_end: The period end date
        fiscal_year_end_month: Company's fiscal year end month (1-12)

    Returns:
        The fiscal year number (the calendar year in which the fiscal year ends)

    Examples:
        >>> # NVIDIA (fiscal year ends in January)
        >>> # Q3 ending October 26, 2025 → FY2026 (ends Jan 2026)
        >>> calculate_fiscal_year_for_label(date(2025, 10, 26), 1)
        2026

        >>> # NVIDIA Q4 ending January 26, 2026 → FY2026
        >>> calculate_fiscal_year_for_label(date(2026, 1, 26), 1)
        2026

        >>> # Apple (fiscal year ends in September)
        >>> # Q1 ending December 30, 2023 → FY2024 (ends Sept 2024)
        >>> calculate_fiscal_year_for_label(date(2023, 12, 30), 9)
        2024

        >>> # Apple Q3 ending June 28, 2024 → FY2024
        >>> calculate_fiscal_year_for_label(date(2024, 6, 28), 9)
        2024

        >>> # Early January period (52/53-week calendar edge case)
        >>> # Period ending Jan 1, 2023 for a Dec FYE company → FY2022
        >>> calculate_fiscal_year_for_label(date(2023, 1, 1), 12)
        2022

        >>> # Costco (August FYE) year ending September 3, 2023 → FY2023
        >>> calculate_fiscal_year_for_label(date(2023, 9, 3), 8)
        2023
    """
    # Early January (Jan 1-7): Use prior year (52/53-week calendar convention)
    # Companies with 52/53-week calendars can have fiscal year end dates
    # fall in the first week of January (e.g., Jan 1 belongs to prior FY)
    if period_end.month == 1 and period_end.day <= 7:
        return period_end.year - 1

    # The same drift for any fiscal year-end month: a 52/53-week year closes on
    # the weekday nearest the month end, which can be a few days into the next
    # month (Costco, August FYE: 2023-09-03; Home Depot, January FYE:
    # 2026-02-01). That period closes the fiscal year, it does not open the next.
    if period_end.month == fiscal_year_end_month % 12 + 1 and period_end.day <= 7:
        return period_end.year

    # Fiscal year convention: if the period ends after the FYE month,
    # it belongs to the next fiscal year (which ends in FYE month of the following year)
    # Example: Apple (Sept FYE) Q1 ends in Dec 2023 → FY2024 (ends Sept 2024)
    # Example: NVIDIA (Jan FYE) Q1 ends in Apr 2025 → FY2026 (ends Jan 2026)
    if period_end.month > fiscal_year_end_month:
        return period_end.year + 1

    # Period ends at or before FYE month — belongs to fiscal year ending this calendar year
    return period_end.year
