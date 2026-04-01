"""
Formatting utilities for the edgar library.

This module contains various formatting functions for dates, numbers, and strings.
"""
import datetime
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Union

import humanize
from rich.text import Text


def moneyfmt(value, places=0, curr='$', sep=',', dp='.',
             pos='', neg='-'):
    """Convert Decimal to a money formatted string.

    Args:
        value: The decimal value to format
        places: Number of decimal places to show (default: 0)
        curr: Optional currency symbol (default: '$')
        sep: Thousands separator (default: ',')
        dp: Decimal point indicator (default: '.')
        pos: Sign for positive numbers (default: '')
        neg: Sign for negative numbers (default: '-')

    Examples:
        >>> moneyfmt(Decimal('-1234567.8901'), curr='$')
        '-$1,234,567.89'
        >>> moneyfmt(Decimal('123456789'), sep=' ')
        '123 456 789.00'
    """
    q = Decimal(10) ** -places  # 2 places --> '0.01'
    sign, digits, exp = value.quantize(q, rounding=ROUND_HALF_UP).as_tuple()
    result = []
    digits = list(map(str, digits))
    build, next = result.append, digits.pop

    # Add trailing zeros if needed
    for i in range(places):
        build(next() if digits else '0')

    # Add decimal point if needed
    if places:
        build(dp)

    # Add digits before decimal point
    if not digits:
        build('0')
    else:
        i = 0
        while digits:
            build(next())
            i += 1
            if i == 3 and digits:
                i = 0
                build(sep)

    # Add currency symbol and sign
    build(curr)
    if sign:
        build(neg)
    else:
        build(pos)

    return ''.join(reversed(result))


def format_currency_short(value: Union[int, float, Decimal, None], currency: str = '$') -> str:
    """Format currency with scale abbreviation for AI context output.

    Args:
        value: Numeric value to format
        currency: Currency symbol (default: '$'). Pass result of get_currency_symbol().

    Examples:
        >>> format_currency_short(394_328_000_000)
        '$394.3B'
        >>> format_currency_short(18_550_000)
        '$18.6M'
        >>> format_currency_short(42_500)
        '$42,500'
        >>> format_currency_short(-1_200_000)
        '-$1.2M'
        >>> format_currency_short(None)
        ''
        >>> format_currency_short(1_000_000, currency='NT$')
        'NT$1.0M'
    """
    if value is None:
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if value != value:  # NaN check
        return ""
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}{currency}{abs_val / 1_000_000_000:,.1f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}{currency}{abs_val / 1_000_000:,.1f}M"
    elif abs_val >= 1_000:
        return f"{sign}{currency}{abs_val:,.0f}"
    else:
        return f"{sign}{currency}{abs_val:,.2f}"


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


def display_size(size: Optional[Union[int, str]]) -> str:
    """
    :return the size in KB or MB as a string
    """
    if size:
        if isinstance(size, int) or size.isdigit():
            return humanize.naturalsize(int(size), binary=True).replace("i", "")
    return ""


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


def yes_no(value: bool) -> str:
    """Convert a boolean to 'Yes' or 'No'.

    Args:
        value: Boolean value

    Returns:
        'Yes' if True, 'No' if False
    """
    return "Yes" if value else "No"


# ── Surname prefixes that should stay attached to the last name ────────
_SURNAME_PREFIXES = frozenset({
    'VAN', 'VON', 'DE', 'DEL', 'DI', 'DU', 'DA', 'DAS', 'DOS', 'LA', 'LE',
    'LES', 'EL', 'AL', 'ST', 'SAN', 'DEN', 'DER', 'TEN', 'TER',
})

# Suffixes stripped from the main name and appended at the end
_SUFFIXES = frozenset({
    'JR', 'JR.', 'SR', 'SR.', 'II', 'III', 'IV',
    'MD', 'MD.', 'M.D.', 'PHD', 'PHD.', 'PH.D.', 'PH.D',
    'DDS', 'DDS,', 'DR', 'DR.', 'ESQ', 'ESQ.', 'CPA', 'CPA.',
    'ET', 'AL', 'AL.',
})

# Titles that can appear as a prefix (first token) — removed, not appended
_TITLE_PREFIXES = frozenset({'DR', 'DR.', 'PROF', 'PROF.', 'REV', 'REV.'})

# Pre-computed normalized sets (avoid rebuilding per call)
_SUFFIXES_NORM = frozenset(s.rstrip('.,') for s in _SUFFIXES)
_TITLE_PREFIXES_NORM = frozenset(t.rstrip('.') for t in _TITLE_PREFIXES)


def _titlecase_part(part: str) -> str:
    """Title-case a name part, handling apostrophes (O'Brien) and hyphens."""
    if "'" in part:
        idx = part.index("'")
        return part[:idx + 1].title() + part[idx + 1:].title()
    if "-" in part:
        return "-".join(seg.title() for seg in part.split("-"))
    return part.title()


def reverse_name(name: str) -> str:
    """Reverse an SEC-style "LAST FIRST [MIDDLE] [SUFFIX]" name to "First [Middle] Last [Suffix]".

    Handles multi-word surnames (Van, De, Del …), professional suffixes (Jr, III, MD, PhD …),
    title prefixes (Dr, Judge …), and mixed-case input.
    """
    parts = name.split()

    if len(parts) <= 1:
        return parts[0].title() if parts else name

    # ── 1. Strip title prefix (DR SMITH JOHN → SMITH JOHN, remember DR) ──
    title_prefix = None
    if parts[0].upper().rstrip('.') in _TITLE_PREFIXES_NORM:
        title_prefix = parts[0]
        parts = parts[1:]
        if len(parts) <= 1:
            result = _titlecase_part(parts[0]) if parts else ""
            return f"{_titlecase_part(title_prefix)} {result}".strip() if title_prefix else result

    # ── 2. Strip trailing suffixes (JR, III, MD, ET AL …) ──
    suffixes: list[str] = []
    while len(parts) > 1 and parts[-1].upper().rstrip('.,') in _SUFFIXES_NORM:
        suffixes.insert(0, parts.pop())

    # Handle "ET AL" as a unit — if we popped "AL" check if previous is "ET"
    if suffixes and suffixes[0].upper().rstrip('.') == 'AL' and parts and parts[-1].upper().rstrip('.') == 'ET':
        suffixes.insert(0, parts.pop())

    if len(parts) <= 1:
        result = _titlecase_part(parts[0]) if parts else ""
        if suffixes:
            result += " " + " ".join(suffixes)
        return result

    # ── 3. Detect multi-word surname at the start ──
    # Consume leading tokens that are known surname prefixes
    surname_end = 0
    while surname_end < len(parts) - 1 and parts[surname_end].upper() in _SURNAME_PREFIXES:
        surname_end += 1
    # The token at surname_end is always part of the surname (it's the core last name)
    surname_end += 1

    # Guard: if we consumed everything as surname, fall back to first-token-only
    if surname_end >= len(parts):
        surname_end = 1

    surname_parts = parts[:surname_end]
    given_parts = parts[surname_end:]

    # ── 3b. Reorder displaced initials ──────────────────────────────
    # SEC sometimes stores "LAST INITIAL FIRST" (e.g. "Bennett C Frank",
    # "Borninkhof K. Michelle").  Detect when the first given-name token
    # is a single-char initial and the next token is a full name, then swap.
    if (len(given_parts) >= 2
            and (len(given_parts[0].rstrip('.')) == 1)
            and len(given_parts[1]) > 1):
        # Swap: move the full first name before the initial
        given_parts = [given_parts[1], given_parts[0]] + given_parts[2:]

    # ── 4. Title-case and assemble ──
    formatted_given = " ".join(_titlecase_part(p) for p in given_parts)
    formatted_surname = " ".join(_titlecase_part(p) for p in surname_parts)

    result = f"{formatted_given} {formatted_surname}"
    if suffixes:
        result += " " + " ".join(suffixes)
    if title_prefix:
        result = f"{_titlecase_part(title_prefix)} {result}"

    return result


def accession_number_text(accession: str) -> Text:
    """Format an SEC accession number with color highlighting.

    Args:
        accession: SEC accession number (e.g., '0001234567-25-000123')

    Returns:
        Rich Text object with colored parts:
        - Leading zeros in dim
        - Year in dodger_blue1
        - Trailing zeros in dim
    """
    if not accession:
        return Text()

    # Split the accession number into its components
    parts = accession.split('-')
    if len(parts) != 3:
        return Text(accession)  # Return unformatted if not in expected format

    cik_part, year_part, seq_part = parts

    # Find leading zeros in CIK
    cik_zeros = len(cik_part) - len(cik_part.lstrip('0'))
    cik_value = cik_part[cik_zeros:]

    # Find leading zeros in sequence
    seq_zeros = len(seq_part) - len(seq_part.lstrip('0'))
    seq_value = seq_part[seq_zeros:]

    # Assemble the colored text
    return Text.assemble(
        ("0" * cik_zeros, "dim"),
        (cik_value, "bold white"),
        ("-", None),
        (year_part, "dodger_blue1"),
        ("-", None),
        ("0" * seq_zeros, "dim"),
        (seq_value, "bold white")
    )


def cik_text(cik: Union[str, int]) -> Text:
    """Format a CIK number with color highlighting for leading zeros.

    Args:
        cik: CIK number as string or int (e.g., '320193' or 320193)

    Returns:
        Rich Text object with colored parts:
        - Leading zeros in dim grey
        - CIK value in bold white

    Examples:
        >>> cik_text(320193)
        Text('0000320193') with leading zeros dimmed
        >>> cik_text('0000320193')
        Text('0000320193') with leading zeros dimmed
    """
    if cik is None or cik == '':
        return Text()

    # Convert to string and pad to 10 digits
    cik_str = str(cik).zfill(10)

    # Find leading zeros
    leading_zeros = len(cik_str) - len(cik_str.lstrip('0'))
    cik_value = cik_str[leading_zeros:]

    # Assemble the colored text
    if leading_zeros > 0 and cik_value:
        # Normal case: some leading zeros and a value
        return Text.assemble(
            ("0" * leading_zeros, "dim"),
            (cik_value, "bold")
        )
    elif leading_zeros == len(cik_str):
        # All zeros - show them all dimmed
        return Text(cik_str, "dim")
    else:
        # No leading zeros
        return Text(cik_str, "bold white")


def accepted_time_text(accepted_datetime) -> Text:
    """Format accepted datetime for current filings with visual emphasis.

    Args:
        accepted_datetime: datetime object from filing acceptance

    Returns:
        Rich Text object with color-coded time components:
        - Date in dim (often the same for recent filings)
        - Hour in bright color (key differentiator)
        - Minutes and seconds with emphasis
    """

    if not accepted_datetime:
        return Text("N/A", style="dim")

    # Convert to datetime if needed
    if not isinstance(accepted_datetime, datetime.datetime):
        try:
            accepted_datetime = datetime.datetime.fromisoformat(str(accepted_datetime))
        except Exception:
            return Text(str(accepted_datetime))

    # Format components
    date_str = accepted_datetime.strftime("%Y-%m-%d")
    hour_str = accepted_datetime.strftime("%H")
    minute_str = accepted_datetime.strftime("%M")
    second_str = accepted_datetime.strftime("%S")

    # Determine colors based on time of day
    hour_int = int(hour_str)
    if 16 <= hour_int <= 17:  # 4-5 PM (common filing time)
        hour_color = "yellow"
    elif hour_int >= 18:  # After hours
        hour_color = "bright_red"
    elif hour_int < 9:  # Pre-market
        hour_color = "bright_cyan"
    else:  # Regular hours
        hour_color = "bright_green"

    # Assemble with visual hierarchy
    return Text.assemble(
        (date_str, "dim"),
        (" ", None),
        (hour_str, f"bold {hour_color}"),
        (":", "dim"),
        (minute_str, "bold white"),
        (":", "dim"),
        (second_str, "white")
    )
