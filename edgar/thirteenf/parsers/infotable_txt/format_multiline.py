"""Parser for multiline TXT format (Format 1) used in some 2012 filings.

This format has company names that can span multiple lines, with the CUSIP
appearing on the same line as the continuation of the company name.

Example:
    AMERICAN
      EXPRESS CO    COM    025816109  110999  1952142 Shared-Defined...
"""

import re
import pandas as pd

from edgar.reference import cusip_ticker_mapping

__all__ = ['parse_multiline_format']


def parse_multiline_format(infotable_txt: str) -> pd.DataFrame:
    """
    Parse multiline TXT format (Format 1) information table.

    This parser handles the format where company names can span multiple lines,
    with the CUSIP appearing on the line that contains the continuation.

    Args:
        infotable_txt: TXT content containing the information table

    Returns:
        pd.DataFrame: Holdings data with same structure as XML parser
    """
    # Find the Form 13F Information Table section (case-insensitive)
    match = re.search(r'FORM\s+13F\s+INFORMATION\s+TABLE', infotable_txt, re.IGNORECASE)
    if not match:
        return pd.DataFrame()

    # Extract all table content between <TABLE> and </TABLE> tags (case-insensitive)
    # Note: Search from beginning since <TABLE> tag may come before the header text
    table_pattern = r'<TABLE>(.*?)</TABLE>'
    tables = re.findall(table_pattern, infotable_txt, re.DOTALL | re.IGNORECASE)

    if len(tables) == 0:
        return pd.DataFrame()

    # Determine which tables to process:
    # - If 2+ tables: Skip first table (usually managers list), process rest
    # - If 1 table: Check if it has holdings data (CUSIPs), if so process it
    if len(tables) >= 2:
        holdings_tables = tables[1:]  # Skip first table (managers)
    elif len(tables) == 1:
        # Check if the single table has holdings data (contains CUSIPs with digits)
        # Look for 9-char alphanumeric sequences (with or without spaces) that contain at least one digit
        potential_cusips = re.findall(r'\b([A-Za-z0-9]{9})\b', tables[0])
        # Also check for spaced CUSIPs
        spaced_cusips = re.findall(r'\b([A-Za-z0-9 ]{9,15})\b', tables[0])
        spaced_cusips_cleaned = [c.replace(' ', '') for c in spaced_cusips if len(c.replace(' ', '')) == 9]

        has_valid_cusips = (
            any(any(c.isdigit() for c in cusip) for cusip in potential_cusips) or
            any(any(c.isdigit() for c in cusip) for cusip in spaced_cusips_cleaned)
        )
        if has_valid_cusips:
            holdings_tables = tables  # Process the single table
        else:
            return pd.DataFrame()  # No holdings data
    else:
        return pd.DataFrame()

    parsed_rows = []

    for holdings_table in holdings_tables:
        # Skip if this is the totals table (very short, < 200 chars)
        if len(holdings_table.strip()) < 200:
            continue

        # Reset pending issuer parts for each table
        pending_issuer_parts = []

        lines = holdings_table.split('\n')

        for line in lines:
            orig_line = line
            line = line.strip()

            # Skip empty lines, CAPTION lines, header rows (case-insensitive)
            line_upper = line.upper()
            if not line or '<CAPTION>' in line_upper or '<S>' in line_upper or '<C>' in line_upper:
                continue

            # Skip separator lines (made of dashes and spaces)
            if all(c in '- ' for c in line):
                continue

            # Skip header/title rows
            line_upper = line.upper()
            if line.startswith(('Total', 'Title', 'Name of Issuer', 'of', 'Market Value')):
                continue

            # Skip column header rows (contain keywords like COLUMN, VOTING AUTHORITY, SHRS OR PRN, etc.)
            if any(keyword in line_upper for keyword in ['COLUMN 1', 'COLUMN 2', 'VOTING AUTHORITY', 'SHRS OR', 'NAME OF ISSUER', 'FORM 13F', 'INFORMATION TABLE']):
                continue

            # Try to parse as a data row
            # CUSIP is a reliable anchor - it's always 9 alphanumeric characters (case-insensitive)
            # Must contain at least one digit to avoid matching company names like "Berkshire" or "SPONSORED"
            # Some filings have spaces in CUSIPs: "00724F 10 1" should be "00724F101"
            # Find ALL potential CUSIP sequences (with or without spaces), then pick the first valid one

            # First try without spaces (faster path)
            cusip_match = None
            cusip = None
            all_cusip_matches = re.finditer(r'\b([A-Za-z0-9]{9})\b', line)
            for match in all_cusip_matches:
                if any(c.isdigit() for c in match.group(1)):
                    cusip_match = match
                    cusip = match.group(1)
                    break

            # If not found, try matching with spaces and cleaning
            if not cusip_match:
                # Match sequences of 9-15 chars that might contain spaces
                spaced_matches = re.finditer(r'\b([A-Za-z0-9 ]{9,15})\b', line)
                for match in spaced_matches:
                    cleaned = match.group(1).replace(' ', '')
                    # Check if cleaned version is exactly 9 chars and has a digit
                    if len(cleaned) == 9 and any(c.isdigit() for c in cleaned):
                        cusip_match = match
                        cusip = cleaned  # Use cleaned version
                        break

            if cusip_match:
                # This line contains a CUSIP, so it has the main data
                # cusip already set above (either from direct match or cleaned from spaced match)
                cusip_pos = cusip_match.start()

                # Everything before CUSIP is issuer name + class
                before_cusip = line[:cusip_pos].strip()
                # Everything after CUSIP is the numeric data
                # Use match.end() to handle spaced CUSIPs correctly (e.g., "00724F 10 1")
                after_cusip = line[cusip_match.end():].strip()

                # Split before_cusip into issuer parts
                # Combine with any pending issuer parts from previous line
                before_parts = before_cusip.split()

                # If we have pending parts, this completes a multi-line company name
                if pending_issuer_parts:
                    before_parts = pending_issuer_parts + before_parts
                    pending_issuer_parts = []

                if len(before_parts) < 2:
                    # Not enough data, skip
                    continue

                # Extract class and issuer name
                # Common patterns:
                # - "COMPANY NAME COM" → class="COM", issuer="COMPANY NAME"
                # - "COMPANY NAME SPONSORED ADR" → class="SPONSORED ADR", issuer="COMPANY NAME"
                # - "COMPANY NAME CL A" → class="CL A", issuer="COMPANY NAME"

                if len(before_parts) >= 3 and before_parts[-2] == 'SPONSORED' and before_parts[-1] == 'ADR':
                    title_class = 'SPONSORED ADR'
                    issuer_parts = before_parts[:-2]
                elif len(before_parts) >= 3 and before_parts[-2] == 'CL':
                    title_class = 'CL ' + before_parts[-1]
                    issuer_parts = before_parts[:-2]
                elif len(before_parts) >= 5 and ' '.join(before_parts[-4:]).startswith('LIB CAP COM'):
                    # "LIBERTY MEDIA CORPORATION LIB CAP COM A"
                    title_class = ' '.join(before_parts[-4:])
                    issuer_parts = before_parts[:-4]
                elif len(before_parts) >= 2:
                    # Default: last word/token is the class
                    title_class = before_parts[-1]
                    issuer_parts = before_parts[:-1]
                else:
                    # Only one part - skip this row
                    continue

                issuer_name = ' '.join(issuer_parts)

                # Skip if issuer name is empty
                if not issuer_name:
                    continue

                # Parse the numeric data after CUSIP
                # Flexible format handling since empty columns may not appear
                # Expected order: VALUE SHARES [TYPE] [DISCRETION] [MANAGERS] [SOLE] [SHARED] [NONE]
                data_parts = after_cusip.split()

                if len(data_parts) < 2:  # At minimum need value and shares
                    continue

                try:
                    # Value and Shares are always the first two fields
                    value_str = data_parts[0].replace(',', '').replace('$', '')
                    shares_str = data_parts[1].replace(',', '')

                    value = int(value_str) if value_str and value_str != '-' else 0
                    shares = float(shares_str) if shares_str and shares_str != '-' else 0

                    # Parse voting columns from the end (look for numeric values)
                    # Work backwards from end to find up to 3 numeric voting columns
                    voting_values = []
                    for i in range(len(data_parts) - 1, 1, -1):  # Start from end, skip first 2 (value/shares)
                        part = data_parts[i].replace(',', '').replace('.', '')
                        if part.replace('-', '').isdigit():
                            # This is a numeric value (could be voting)
                            val_str = data_parts[i].replace(',', '')
                            try:
                                voting_values.insert(0, float(val_str) if val_str != '-' else 0)
                                if len(voting_values) == 3:
                                    break
                            except ValueError:
                                break
                        else:
                            # Non-numeric, stop looking for voting columns
                            break

                    # Assign voting values (may have 0-3 values)
                    sole_voting = int(voting_values[0]) if len(voting_values) >= 1 else 0
                    shared_voting = int(voting_values[1]) if len(voting_values) >= 2 else 0
                    non_voting = int(voting_values[2]) if len(voting_values) >= 3 else 0

                    # Find investment discretion by looking for non-numeric field after position 2
                    # It's typically "Shared-Defined", "SOLE", "Defined", etc.
                    # Skip position 2 which might be TYPE (SH/PRN)
                    investment_discretion = ''
                    num_voting_at_end = len(voting_values)
                    for i in range(2, len(data_parts) - num_voting_at_end):
                        part = data_parts[i]
                        # Investment discretion contains letters and is not a known type marker
                        if part and part not in ['-', 'SH', 'PRN'] and not part.replace(',', '').replace('.', '').isdigit():
                            investment_discretion = part
                            break

                    # Create row dict
                    row_dict = {
                        'Issuer': issuer_name,
                        'Class': title_class,
                        'Cusip': cusip,
                        'Value': value,
                        'SharesPrnAmount': shares,
                        'Type': 'Shares',
                        'PutCall': '',
                        'InvestmentDiscretion': investment_discretion,
                        'SoleVoting': sole_voting,
                        'SharedVoting': shared_voting,
                        'NonVoting': non_voting
                    }

                    parsed_rows.append(row_dict)

                except (ValueError, IndexError):
                    # Skip rows that don't parse correctly
                    continue

            else:
                # No CUSIP on this line - might be first part of a multi-line company name
                # Store it for the next line
                if line and not line.startswith(('Total', 'Title')):
                    pending_issuer_parts = line.split()

    # Create DataFrame
    if not parsed_rows:
        return pd.DataFrame()

    table = pd.DataFrame(parsed_rows)

    # Add ticker symbols using CUSIP mapping
    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

    return table
