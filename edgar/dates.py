import datetime
from typing import Optional, Tuple

__all__ = [
    "extract_dates",
    "InvalidDateException"
]

class InvalidDateException(Exception):

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
