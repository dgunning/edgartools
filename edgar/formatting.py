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


def accession_number_text(accession: str) -> Text:
    """Format an SEC accession number with color highlighting.

    Args:
        accession: SEC accession number (e.g., '0001234567-25-000123')

    Returns:
        Rich Text object with colored parts:
        - Leading zeros in grey54
        - Year in bright_blue
        - Trailing zeros in grey54
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
        (year_part, "bright_blue"),
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
        except:
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
