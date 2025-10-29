"""Parser for columnar TXT format (Format 2) used in some 2012 filings.

This format has <S> and <C> tags for each field, with all data on a single line.

Example:
    <S>                     <C>           <C>       <C>      <C>
    AETNA INC               NEW COM       00817Y108 92,760   2,342,435 SH SOLE 2,238,895 103,540 0
"""

import re
import pandas as pd

from edgar.reference import cusip_ticker_mapping

__all__ = ['parse_columnar_format']


def parse_columnar_format(infotable_txt: str) -> pd.DataFrame:
    """
    Parse columnar TXT format (Format 2) information table.

    This parser handles the format where all data is on a single line with
    <S> and <C> tags marking column boundaries.

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
    # - If 1 table: Check if it has holdings data (CUSIPs with <S> tags), if so process it
    if len(tables) >= 2:
        holdings_tables = tables[1:]  # Skip first table (managers)
    elif len(tables) == 1:
        # Check if the single table has holdings data (contains CUSIPs with <S> tags)
        # Look for lines that have both <S> tag and valid CUSIP (with or without spaces)
        potential_lines = [line for line in tables[0].split('\n') if '<S>' in line.upper()]
        has_data = False
        for line in potential_lines[:10]:  # Check first 10 <S> lines
            # Try non-spaced CUSIPs first
            cusip_match = re.search(r'\b([A-Za-z0-9]{9})\b', line)
            if cusip_match and any(c.isdigit() for c in cusip_match.group(1)):
                has_data = True
                break
            # Try spaced CUSIPs
            spaced_matches = re.finditer(r'\b([A-Za-z0-9 ]{9,15})\b', line)
            for match in spaced_matches:
                cleaned = match.group(1).replace(' ', '')
                if len(cleaned) == 9 and any(c.isdigit() for c in cleaned):
                    has_data = True
                    break
            if has_data:
                break
        if has_data:
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

        lines = holdings_table.split('\n')

        for line in lines:
            line = line.strip()

            # Skip empty lines, CAPTION lines, header rows (case-insensitive)
            line_upper = line.upper()
            if not line or '<CAPTION>' in line_upper:
                continue

            # Skip header rows with just tags (case-insensitive)
            # Header rows have <S> but no valid CUSIPs (9 chars with at least one digit, with or without spaces)
            if line_upper.startswith('<S>'):
                # Check for normal 9-char CUSIP
                has_cusip = False
                cusip_check = re.search(r'\b([A-Za-z0-9]{9})\b', line)
                if cusip_check and any(c.isdigit() for c in cusip_check.group(1)):
                    has_cusip = True

                # If not found, check for spaced CUSIP
                if not has_cusip:
                    spaced_check = re.finditer(r'\b([A-Za-z0-9 ]{9,15})\b', line)
                    for match in spaced_check:
                        cleaned = match.group(1).replace(' ', '')
                        if len(cleaned) == 9 and any(c.isdigit() for c in cleaned):
                            has_cusip = True
                            break

                if not has_cusip:
                    continue

            if line.startswith(('Total', 'Title', 'NAME OF ISSUER', 'of', 'Market Value')):
                continue

            # Look for data rows with <S> tag and a CUSIP (case-insensitive)
            if '<S>' not in line_upper:
                continue

            # CUSIP is a reliable anchor - it's always 9 alphanumeric characters (case-insensitive)
            # Must contain at least one digit to avoid matching company names or words like "SPONSORED"
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

            if not cusip_match:
                continue

            # Remove SGML tags and split by whitespace
            # Replace <S> and <C> with spaces to help with splitting
            cleaned_line = line.replace('<S>', ' ').replace('<C>', ' ')
            parts = cleaned_line.split()

            # Filter out empty parts
            parts = [p for p in parts if p.strip()]

            if len(parts) < 10:  # Need at least issuer, class, cusip, value, shares, type, discretion, sole, shared, none
                continue

            try:
                # Find CUSIP position in parts
                # cusip already set above (either from direct match or cleaned from spaced match)
                # Try to find it in parts - it might be spaced or not spaced
                cusip_idx = None
                cusip_span = 1  # How many elements the CUSIP occupies in parts

                # First try to find cleaned CUSIP as a single element
                if cusip in parts:
                    cusip_idx = parts.index(cusip)
                else:
                    # Try to find the original spaced version as a single element
                    original_cusip = cusip_match.group(1)
                    if original_cusip in parts:
                        cusip_idx = parts.index(original_cusip)
                    else:
                        # For spaced CUSIPs split across multiple parts (e.g., "00724F 10 1" -> ["00724F", "10", "1"])
                        # Look for a sequence of parts that, when joined, matches the cleaned CUSIP
                        for i in range(len(parts) - 2):  # Need at least 3 parts for a split CUSIP
                            # Try joining 2-4 consecutive parts
                            for span in range(2, 5):
                                if i + span > len(parts):
                                    break
                                joined = ''.join(parts[i:i+span])
                                if joined == cusip:
                                    cusip_idx = i
                                    cusip_span = span
                                    break
                            if cusip_idx is not None:
                                break

                if cusip_idx is None:
                    continue

                # Before CUSIP: Issuer name and class
                # Everything before CUSIP minus the last word (which is the class)
                before_cusip = parts[:cusip_idx]
                if len(before_cusip) < 2:
                    continue

                # Last part before CUSIP is the class, rest is issuer name
                title_class = before_cusip[-1]
                issuer_name = ' '.join(before_cusip[:-1])

                # After CUSIP: value, shares, type (SH/PRN), discretion, sole, shared, none
                # Skip cusip_span elements for spaced CUSIPs (e.g., ["00724F", "10", "1"])
                after_cusip = parts[cusip_idx + cusip_span:]

                if len(after_cusip) < 7:
                    continue

                # Parse fields after CUSIP
                # Expected order: VALUE SHARES TYPE DISCRETION ... SOLE SHARED NONE
                value_str = after_cusip[0].replace(',', '').replace('$', '')
                shares_str = after_cusip[1].replace(',', '')

                value = int(value_str) if value_str and value_str != '-' else 0
                shares = int(shares_str) if shares_str and shares_str != '-' else 0

                # Type (SH/PRN) is typically at index 2
                share_type = after_cusip[2] if len(after_cusip) > 2 else 'SH'
                if share_type == 'SH':
                    share_type_full = 'Shares'
                elif share_type == 'PRN':
                    share_type_full = 'Principal'
                else:
                    share_type_full = 'Shares'

                # Find investment discretion (typically "SOLE", "SHARED", "DEFINED", or compound like "SHARED-DEFINED")
                # It's the first non-numeric field after type
                discretion_idx = 3
                investment_discretion = ''
                for i in range(3, len(after_cusip) - 3):  # Last 3 are voting columns
                    part = after_cusip[i]
                    if part and part not in ['-'] and not part.replace(',', '').isdigit():
                        investment_discretion = part
                        discretion_idx = i
                        break

                # Voting columns are the last 3 fields
                if len(after_cusip) >= 3:
                    none_voting_str = after_cusip[-1].replace(',', '')
                    shared_voting_str = after_cusip[-2].replace(',', '')
                    sole_voting_str = after_cusip[-3].replace(',', '')

                    non_voting = int(none_voting_str) if none_voting_str and none_voting_str != '-' else 0
                    shared_voting = int(shared_voting_str) if shared_voting_str and shared_voting_str != '-' else 0
                    sole_voting = int(sole_voting_str) if sole_voting_str and sole_voting_str != '-' else 0
                else:
                    sole_voting = 0
                    shared_voting = 0
                    non_voting = 0

                # Create row dict
                row_dict = {
                    'Issuer': issuer_name,
                    'Class': title_class,
                    'Cusip': cusip,
                    'Value': value,
                    'SharesPrnAmount': shares,
                    'Type': share_type_full,
                    'PutCall': '',
                    'InvestmentDiscretion': investment_discretion,
                    'SoleVoting': sole_voting,
                    'SharedVoting': shared_voting,
                    'NonVoting': non_voting
                }

                parsed_rows.append(row_dict)

            except (ValueError, IndexError) as e:
                # Skip rows that don't parse correctly
                continue

    # Create DataFrame
    if not parsed_rows:
        return pd.DataFrame()

    table = pd.DataFrame(parsed_rows)

    # Add ticker symbols using CUSIP mapping
    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

    return table
