"""TXT format information table parsers with automatic format detection.

Supports two TXT formats from 2012 filings:
- Format 1 (Multiline): Company names can span multiple lines
- Format 2 (Columnar): All data on single line with <S> and <C> tags
"""

import re
import pandas as pd

from .format_multiline import parse_multiline_format
from .format_columnar import parse_columnar_format

__all__ = ['parse_infotable_txt']


def parse_infotable_txt(infotable_txt: str) -> pd.DataFrame:
    """
    Parse TXT format information table, auto-detecting format.

    Supports:
    - Format 1 (Multiline): Berkshire-style with multi-line company names
    - Format 2 (Columnar): JANA-style with all data on single line

    Args:
        infotable_txt: TXT content containing the information table

    Returns:
        pd.DataFrame: Holdings data with same structure as XML parser
    """
    if _is_columnar_format(infotable_txt):
        return parse_columnar_format(infotable_txt)
    else:
        return parse_multiline_format(infotable_txt)


def _is_columnar_format(infotable_txt: str) -> bool:
    """
    Detect if this is columnar format by looking for <S> tags in data rows.

    Columnar format has <S> at the start of each data row, followed by data.
    Multiline format only has <S> and <C> in the header row.

    Args:
        infotable_txt: TXT content to analyze

    Returns:
        bool: True if columnar format, False if multiline format
    """
    # Find the Form 13F Information Table section (case-insensitive)
    match = re.search(r'FORM\s+13F\s+INFORMATION\s+TABLE', infotable_txt, re.IGNORECASE)
    if not match:
        return False

    # Extract tables (case-insensitive)
    # Note: Search from beginning since <TABLE> tag may come before the header text
    table_pattern = r'<TABLE>(.*?)</TABLE>'
    tables = re.findall(table_pattern, infotable_txt, re.DOTALL | re.IGNORECASE)

    if len(tables) == 0:
        return False

    # Determine which table to check
    # If 2+ tables: check second table (first holdings table, after managers table)
    # If 1 table: check that single table
    if len(tables) >= 2:
        holdings_table = tables[1]
    else:
        holdings_table = tables[0]

    lines = holdings_table.split('\n')

    # Count data rows with <S> tags that also have CUSIPs
    # In columnar format, data rows start with <S> and have CUSIP on same line
    # In multiline format, only header has <S>, and CUSIP is on second line of company
    data_rows_with_s_and_cusip = 0
    data_rows_checked = 0

    for line in lines:
        line = line.strip()
        line_upper = line.upper()

        # Skip empty lines, CAPTION, and header rows (case-insensitive)
        if not line or '<CAPTION>' in line_upper:
            continue

        # Skip if this looks like a header (has <S> but no digits)
        if '<S>' in line_upper and not re.search(r'\d', line):
            continue

        # Check if this line has both <S> tag and a CUSIP (9 chars with digit, with or without spaces)
        cusip_match = re.search(r'\b([A-Za-z0-9]{9})\b', line)
        has_valid_cusip = cusip_match and any(c.isdigit() for c in cusip_match.group(1))

        # Also check for spaced CUSIPs
        if not has_valid_cusip:
            spaced_matches = re.finditer(r'\b([A-Za-z0-9 ]{9,15})\b', line)
            for match in spaced_matches:
                cleaned = match.group(1).replace(' ', '')
                if len(cleaned) == 9 and any(c.isdigit() for c in cleaned):
                    has_valid_cusip = True
                    break

        if '<S>' in line_upper and has_valid_cusip:
            data_rows_with_s_and_cusip += 1
            data_rows_checked += 1
        elif has_valid_cusip:
            # Has CUSIP but no <S> - multiline format
            data_rows_checked += 1

        # If we've checked 3 data rows, that's enough to decide
        if data_rows_checked >= 3:
            break

    # If most data rows with CUSIPs also have <S> tags, it's columnar format
    if data_rows_checked > 0 and data_rows_with_s_and_cusip >= data_rows_checked * 0.5:
        return True

    return False
