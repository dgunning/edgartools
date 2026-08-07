import datetime
from typing import Optional, Sequence, Tuple, Union

__all__ = [
    "extract_dates",
    "InvalidDateException"
]

class InvalidDateException(Exception):

    def __init__(self, message: str):
        super().__init__(message)

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
        InvalidDateException: If the date string cannot be parsed
    """
    if not date_str:
        raise InvalidDateException("Empty date string provided")

    # Normalize tuple/list form into the colon-separated string form so the
    # rest of the parser stays a single code path. None in either slot is
    # treated as the "open" side of a range (same semantics as "start:" / ":end").
    if isinstance(date_str, (tuple, list)):
        if len(date_str) != 2:
            raise InvalidDateException(
                "Date range tuple must have exactly two elements (start, end); "
                f"got {len(date_str)}"
            )
        start_part, end_part = date_str
        if start_part is None and end_part is None:
            raise InvalidDateException(
                "Date range tuple must have at least one non-None bound"
            )
        date_str = f"{start_part or ''}:{end_part or ''}"

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
