import re
from decimal import Decimal
from typing import Union, Any, Optional, Tuple

import numpy as np
import pandas as pd
from lxml import etree

__all__ = ['is_numeric', 'compute_average_price', 'compute_total_value', 
           'format_currency', 'format_amount', 'safe_numeric', 'format_numeric']


def is_numeric(series: pd.Series) -> bool:
    if np.issubdtype(series.dtype, np.number):
        return True
    try:
        series.astype(float)
        return True
    except ValueError:
        return False

def compute_average_price(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the average price of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum() / shares.sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))


def compute_total_value(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the total value of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))

def format_currency(amount: Union[int, float]) -> str:
    if amount is None or np.isnan(amount):
        return ""
    if isinstance(amount, (int, float)):
        return f"${amount:,.2f}"
    return str(amount)


def format_amount(amount: Union[int, float]) -> str:
    if amount is None:
        return ""
    if isinstance(amount, (int, float)):
        # Can it be formatted as an integer?
        if amount == int(amount):
            return f"{amount:,.0f}"
        return f"{amount:,.2f}"
    return str(amount)


def safe_numeric(value: Any) -> Optional[Union[int, float]]:
    """
    Safely convert a value to a number, handling footnote references and other special cases.

    Args:
        value: The value to convert (could be string, int, float, or None)

    Returns:
        Numeric value if conversion is possible, None otherwise
    """
    if value is None or pd.isna(value):
        return None

    # If already a number, return as is
    if isinstance(value, (int, float)) and not np.isnan(value):
        return value

    # Handle string cases
    if isinstance(value, str):
        # Remove commas, dollar signs, and whitespace
        cleaned = value.replace(',', '').replace('$', '').strip()

        # Remove footnote references like [F1], [1], etc.
        cleaned = re.sub(r'\[\w+]', '', cleaned)

        # Try numeric conversion
        try:
            # Check if it's an integer
            if '.' not in cleaned:
                return int(cleaned)
            else:
                return float(cleaned)
        except (ValueError, TypeError):
            return None

    return None


def format_numeric(value: Any, currency: bool = False, default: str = "N/A") -> str:
    """
    Format a potentially non-numeric value for display, handling special cases.

    Args:
        value: The value to format
        currency: Whether to format as currency with $ symbol
        default: Default string to return if value can't be converted to number

    Returns:
        Formatted string representation
    """
    number = safe_numeric(value)

    if number is None:
        # If the original value was a string with content, return it instead of default
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    if currency:
        return f"${number:,.2f}"
    else:
        # Format integers without decimal places
        if isinstance(number, int) or (isinstance(number, float) and number.is_integer()):
            return f"{int(number):,}"
        return f"{number:,.2f}"

  # Add a dedicated currency formatter
def format_price(value: Any, default: str = "N/A") -> str:
    """Format a price value with currency symbol"""
    return format_numeric(value, currency=True, default=default)


def _get_xml_value(elem: etree._Element, xpath: str, with_footnote: bool = True) -> str:
    """Helper to safely get text from XML element with value tag and optional footnote
    
    Args:
        elem: XML element to search within
        xpath: XPath expression to find target element
        with_footnote: Whether to include footnote references in output
        
    Returns:
        Text value with optional footnote reference
    """
    # Handle both direct text elements and those with <value> wrapper
    nodes = elem.xpath(xpath)
    if not nodes:
        return ''
        
    node = nodes[0]
    
    # Try to get text from <value> child first
    value = node.find('value')
    if value is not None:
        text = value.text if value.text else ''
    else:
        # If no <value> tag, get direct text content
        text = node.text if node.text else ''
    
    # Add footnote reference if present and requested
    if with_footnote:
        footnote = node.find('footnoteId')
        if footnote is not None:
            footnote_id = footnote.get('id', '')
            if footnote_id:
                text = f"{text}<sup>({footnote_id})</sup>"
                
    return text.strip()


def _parse_name(name: str) -> Tuple[str, str, str]:
    """Parse a full name into (last, first, middle) components"""
    # Remove any extra whitespace
    name = ' '.join(name.split())
    parts = name.split(' ')
    
    if len(parts) == 1:
        return (parts[0], '', '')
    elif len(parts) == 2:
        return (parts[1], parts[0], '')
    else:
        return (parts[-1], parts[0], ' '.join(parts[1:-1]))

def _format_xml_date(date_str: str) -> str:
    """Format YYYY-MM-DD to MM/DD/YYYY"""
    if not date_str:
        return ''
    try:
        year, month, day = date_str.split('-')
        return f"{month}/{day}/{year}"
    except ValueError:
        return date_str
