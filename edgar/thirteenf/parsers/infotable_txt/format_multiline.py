"""Parser for multiline TXT format (Format 1) used in pre-2013 filings.

This format has company names that can span multiple lines, with the CUSIP
appearing on the same line as the continuation of the company name.
Column positions are determined from the <S>/<C> marker line.

Example raw data:
    <S>             <C>      <C>         <C>            <C>         <C>  <C>     <C>     <C>                  <C>         <C>    <C>
    American
       Express Co.    Com    025816 10 9       697,973   17,225,400         X            4, 2, 5, 17           17,225,400
                                               323,943    7,994,634         X            4, 13, 17              7,994,634
"""

import re

import pandas as pd

from edgar.reference import cusip_ticker_mapping

__all__ = ['parse_multiline_format']

# Minimum number of columns expected in a holdings table marker line
_MIN_HOLDINGS_COLUMNS = 6

# Regex for a valid cleaned CUSIP: exactly 9 alphanumeric chars with at least one digit
_CUSIP_RE = re.compile(r'^[A-Za-z0-9]{9}$')


def _extract_column_specs(table_text: str):
    """
    Find the <S>/<C> marker line in a table and return column specs.

    Returns:
        Tuple of (colspecs, marker_line_index, lines) where colspecs is a list
        of (start, end) tuples, or (None, None, None) if no marker found.
    """
    lines = table_text.split('\n')
    for i, line in enumerate(lines):
        line_upper = line.upper()
        # Accept lines with <S>+<C> or <C>-only (some filings omit <S>)
        if '<C>' in line_upper and (line_upper.count('<C>') >= 3 or '<S>' in line_upper):
            positions = [j for j, c in enumerate(line) if c == '<']
            if len(positions) < _MIN_HOLDINGS_COLUMNS:
                continue
            specs = []
            for k, start in enumerate(positions):
                end = positions[k + 1] if k + 1 < len(positions) else None
                specs.append((start, end))
            return specs, i, lines
    return None, None, None


def _slice_col(line, start, end):
    """Extract and strip a column value from a fixed-width line."""
    if start >= len(line):
        return ''
    segment = line[start:end] if end is not None else line[start:]
    return segment.strip()


def _clean_cusip(raw):
    """Strip spaces from a raw CUSIP field and validate."""
    cleaned = raw.replace(' ', '').replace('-', '')
    if len(cleaned) == 9 and _CUSIP_RE.match(cleaned) and any(c.isdigit() for c in cleaned):
        return cleaned
    return None



def _is_header_or_skip_line(line):
    """Check if a line should be skipped (headers, captions, separators)."""
    stripped = line.strip()
    if not stripped:
        return True
    upper = stripped.upper()
    # Skip SGML tags
    if '<CAPTION>' in upper or '<S>' in upper or '<C>' in upper or '<PAGE>' in upper:
        return True
    # Skip separator lines
    if all(c in '- =_' for c in stripped):
        return True
    # Skip known header keywords
    if any(kw in upper for kw in [
        'COLUMN 1', 'COLUMN 2', 'VOTING AUTHORITY', 'SHRS OR',
        'NAME OF ISSUER', 'FORM 13F', 'INFORMATION TABLE',
        'TITLE OF', 'MARKET VALUE', 'INVESTMENT', 'PRINCIPAL',
    ]):
        return True
    return False


def _parse_after_cusip(data_parts):
    """
    Parse the numeric fields after the CUSIP column.

    Expected order: VALUE SHARES [DISCRETION_FLAG] [MANAGERS...] [SOLE] [SHARED] [NONE]

    Returns dict with Value, SharesPrnAmount, InvestmentDiscretion, SoleVoting, SharedVoting, NonVoting
    or None if parsing fails.
    """
    if len(data_parts) < 2:
        return None

    try:
        value_str = data_parts[0].replace(',', '').replace('$', '')
        shares_str = data_parts[1].replace(',', '').replace('$', '')

        # Handle decimal values (some filings report exact dollar amounts)
        value = int(float(value_str)) if value_str and value_str != '-' else 0
        shares = int(float(shares_str)) if shares_str and shares_str != '-' else 0

        # Parse voting columns from the end (look for numeric values)
        voting_values = []
        for i in range(len(data_parts) - 1, 1, -1):
            part = data_parts[i].replace(',', '').replace('.', '')
            if part.replace('-', '').isdigit():
                val_str = data_parts[i].replace(',', '')
                try:
                    voting_values.insert(0, float(val_str) if val_str != '-' else 0)
                    if len(voting_values) == 3:
                        break
                except ValueError:
                    break
            else:
                break

        sole_voting = int(voting_values[0]) if len(voting_values) >= 1 else 0
        shared_voting = int(voting_values[1]) if len(voting_values) >= 2 else 0
        non_voting = int(voting_values[2]) if len(voting_values) >= 3 else 0

        # Find investment discretion
        investment_discretion = ''
        num_voting_at_end = len(voting_values)
        for i in range(2, len(data_parts) - num_voting_at_end):
            part = data_parts[i]
            if part and part not in ['-', 'SH', 'PRN'] and not part.replace(',', '').replace('.', '').isdigit():
                investment_discretion = part
                break

        return {
            'Value': value,
            'SharesPrnAmount': shares,
            'InvestmentDiscretion': investment_discretion,
            'SoleVoting': sole_voting,
            'SharedVoting': shared_voting,
            'NonVoting': non_voting,
        }
    except (ValueError, IndexError):
        return None


def _extract_class_and_issuer(before_parts):
    """
    Split name+class parts into (issuer_name, title_class).

    Common patterns:
    - ["COMPANY", "NAME", "COM"] -> ("COMPANY NAME", "COM")
    - ["COMPANY", "SPONSORED", "ADR"] -> ("COMPANY", "SPONSORED ADR")
    - ["COMPANY", "CL", "A"] -> ("COMPANY", "CL A")
    - ["COMPANY", "CLA", "SPL"] -> ("COMPANY", "CLA SPL")
    """
    if len(before_parts) < 2:
        return None, None

    if len(before_parts) >= 3 and before_parts[-2].upper() == 'SPONSORED' and before_parts[-1].upper() == 'ADR':
        title_class = 'SPONSORED ADR'
        issuer_parts = before_parts[:-2]
    elif len(before_parts) >= 3 and before_parts[-2].upper() in ('CL', 'CLA'):
        title_class = before_parts[-2] + ' ' + before_parts[-1]
        issuer_parts = before_parts[:-2]
    elif len(before_parts) >= 5 and ' '.join(before_parts[-4:]).upper().startswith('LIB CAP COM'):
        title_class = ' '.join(before_parts[-4:])
        issuer_parts = before_parts[:-4]
    else:
        title_class = before_parts[-1]
        issuer_parts = before_parts[:-1]

    issuer_name = ' '.join(issuer_parts)
    return issuer_name if issuer_name else None, title_class


def _parse_table_with_columns(table_text: str):
    """
    Parse a single <TABLE> block using column positions from the marker line.

    Returns list of row dicts.
    """
    colspecs, marker_idx, lines = _extract_column_specs(table_text)
    if colspecs is None:
        return []

    # Column indices assume the standard 13F layout mandated by the SEC.
    # All observed TXT-era filings (2005-2013) follow this order.
    # 0: Name of Issuer, 1: Title of Class, 2: CUSIP Number
    # 3: Market Value, 4: Shares/Principal Amount
    # 5+: Discretion fields, Other Managers, Voting Authority
    NAME_COL = 0
    CLASS_COL = 1
    CUSIP_COL = 2
    VALUE_COL = 3
    SHARES_COL = 4

    parsed_rows = []
    pending_name_parts = []
    current_issuer = ''
    current_class = ''
    current_cusip = ''

    # Process data lines after the marker
    for line_idx in range(marker_idx + 1, len(lines)):
        raw_line = lines[line_idx]

        if _is_header_or_skip_line(raw_line):
            continue

        # Check for end-of-table markers
        stripped = raw_line.strip().upper()
        if stripped.startswith('GRAND TOTAL'):
            break

        # Extract columns using fixed positions
        name_raw = _slice_col(raw_line, colspecs[NAME_COL][0], colspecs[NAME_COL][1])
        class_raw = _slice_col(raw_line, colspecs[CLASS_COL][0], colspecs[CLASS_COL][1]) if CLASS_COL < len(colspecs) else ''
        cusip_raw = _slice_col(raw_line, colspecs[CUSIP_COL][0], colspecs[CUSIP_COL][1]) if CUSIP_COL < len(colspecs) else ''
        value_raw = _slice_col(raw_line, colspecs[VALUE_COL][0], colspecs[VALUE_COL][1]) if VALUE_COL < len(colspecs) else ''
        shares_raw = _slice_col(raw_line, colspecs[SHARES_COL][0], colspecs[SHARES_COL][1]) if SHARES_COL < len(colspecs) else ''

        # Check for subtotal separator lines (dashes in value column)
        if value_raw and all(c in '-=' for c in value_raw.replace(' ', '')):
            break

        cusip = _clean_cusip(cusip_raw)
        has_cusip = cusip is not None
        has_value = bool(value_raw and value_raw.replace(',', '').replace('$', '').replace('-', '').replace('.', '').strip().isdigit())

        if has_cusip:
            # This line has a CUSIP — it's a primary data row
            # Combine pending name parts with name on this line
            name_parts = pending_name_parts[:]
            if name_raw:
                name_parts.append(name_raw)
            pending_name_parts = []

            # Extract class from this line
            class_parts = []
            if class_raw:
                class_parts = class_raw.split()

            # Build issuer name and class
            if class_parts:
                current_class = ' '.join(class_parts)
                current_issuer = ' '.join(name_parts)
            else:
                # Class might be at end of name parts
                all_parts = []
                for part in name_parts:
                    all_parts.extend(part.split())
                if all_parts:
                    issuer_name, title_class = _extract_class_and_issuer(all_parts)
                    if issuer_name:
                        current_issuer = issuer_name
                        current_class = title_class or ''
                    else:
                        continue
                else:
                    continue

            current_cusip = cusip

            if not current_issuer:
                continue

            # Parse the numeric data after CUSIP
            # Gather everything from the value column onward as text, then split
            value_start = colspecs[VALUE_COL][0]
            after_cusip_text = raw_line[value_start:].strip() if value_start < len(raw_line) else ''
            data_parts = after_cusip_text.split()

            parsed = _parse_after_cusip(data_parts)
            if parsed is None:
                continue

            row_dict = {
                'Issuer': current_issuer,
                'Class': current_class,
                'Cusip': current_cusip,
                'Type': 'Shares',
                'PutCall': '',
                **parsed,
            }
            parsed_rows.append(row_dict)

        elif has_value and not name_raw and not cusip_raw:
            # Continuation row: same company/CUSIP, different manager assignment
            if not current_cusip or not current_issuer:
                continue

            value_start = colspecs[VALUE_COL][0]
            after_cusip_text = raw_line[value_start:].strip() if value_start < len(raw_line) else ''
            data_parts = after_cusip_text.split()

            parsed = _parse_after_cusip(data_parts)
            if parsed is None:
                continue

            row_dict = {
                'Issuer': current_issuer,
                'Class': current_class,
                'Cusip': current_cusip,
                'Type': 'Shares',
                'PutCall': '',
                **parsed,
            }
            parsed_rows.append(row_dict)

        elif name_raw and not has_cusip and not has_value:
            # Name-only line: accumulate for multi-line company name
            pending_name_parts.append(name_raw)

        # else: skip unrecognizable lines

    return parsed_rows


def _parse_text_regex_fallback(text: str):
    """
    Regex-based fallback parser for filings without <S>/<C> marker lines.

    Scans each line for a valid 9-char CUSIP, uses it as an anchor to split
    the line into name+class (before) and numeric data (after).
    Handles two-line formats where shares/voting appear on the next line.

    Returns list of row dicts.
    """
    parsed_rows = []
    pending_issuer_parts = []
    pending_row = None  # Row awaiting continuation data from next line

    lines = text.split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()

        # Skip headers and separators
        if any(kw in upper for kw in [
            'NAME OF ISSUER', 'FORM 13F', 'INFORMATION TABLE',
            'TITLE OF', 'MARKET VALUE', 'COLUMN 1', 'COLUMN 2',
            'VOTING AUTHORITY', 'SHRS OR', 'PRN AMT', 'DSCRETN',
            'PRN CALL', 'ASSET NAME', '13F HOLDINGS',
            '<CAPTION>', '<S>', '<C>', '<PAGE>', '<TABLE>', '</TABLE>',
        ]):
            continue
        # Skip single-word header keywords
        if upper in ('VALUE', 'SHARES', 'CUSIP', 'NONE', 'SOLE', 'SHARED'):
            continue
        if all(c in '- =_' for c in stripped):
            continue
        if upper.startswith('GRAND TOTAL'):
            break

        # Look for a 9-char CUSIP (no spaces) on this line
        cusip_match = None
        cusip = None
        for m in re.finditer(r'\b([A-Za-z0-9]{9})\b', stripped):
            candidate = m.group(1)
            if any(c.isdigit() for c in candidate):
                cusip_match = m
                cusip = candidate
                break

        if cusip_match:
            # Flush any pending row from a previous CUSIP line
            if pending_row:
                parsed_rows.append(pending_row)
                pending_row = None

            before_cusip = stripped[:cusip_match.start()].strip()
            after_cusip = stripped[cusip_match.end():].strip()

            before_parts = before_cusip.split()

            if pending_issuer_parts:
                before_parts = pending_issuer_parts + before_parts
                pending_issuer_parts = []

            if len(before_parts) < 2:
                continue

            issuer_name, title_class = _extract_class_and_issuer(before_parts)
            if not issuer_name:
                continue

            data_parts = after_cusip.split()
            parsed = _parse_after_cusip(data_parts)
            if parsed is not None:
                row_dict = {
                    'Issuer': issuer_name,
                    'Class': title_class,
                    'Cusip': cusip,
                    'Type': 'Shares',
                    'PutCall': '',
                    **parsed,
                }
                parsed_rows.append(row_dict)
            elif data_parts:
                # Partial data (e.g., just value) — shares may be on next line
                try:
                    value_str = data_parts[0].replace(',', '').replace('$', '')
                    value = int(float(value_str)) if value_str and value_str != '-' else 0
                    pending_row = {
                        'Issuer': issuer_name,
                        'Class': title_class,
                        'Cusip': cusip,
                        'Value': value,
                        'SharesPrnAmount': 0,
                        'Type': 'Shares',
                        'PutCall': '',
                        'InvestmentDiscretion': '',
                        'SoleVoting': 0,
                        'SharedVoting': 0,
                        'NonVoting': 0,
                    }
                except (ValueError, IndexError):
                    pass
        else:
            # No CUSIP on this line
            # Check if this is a continuation line for a pending row
            # (starts with digits — shares count)
            if pending_row and stripped and stripped[0].isdigit():
                # Reuse _parse_after_cusip by prepending the pending value
                # so the shares become position 1 (expected by the parser)
                parts = [str(pending_row['Value'])] + stripped.split()
                parsed = _parse_after_cusip(parts)
                if parsed:
                    pending_row.update(parsed)
                parsed_rows.append(pending_row)
                pending_row = None
            elif stripped and not stripped[0].isdigit():
                # Might be a multi-line company name
                if pending_row:
                    parsed_rows.append(pending_row)
                    pending_row = None
                pending_issuer_parts = stripped.split()

    # Flush final pending row
    if pending_row:
        parsed_rows.append(pending_row)

    return parsed_rows


def parse_multiline_format(infotable_txt: str) -> pd.DataFrame:
    """
    Parse multiline TXT format (Format 1) information table.

    Primary strategy: use column positions from <S>/<C> marker lines.
    Fallback: regex-based CUSIP scanning for filings without markers.

    Args:
        infotable_txt: TXT content containing the information table

    Returns:
        pd.DataFrame: Holdings data with same structure as XML parser
    """
    # Find the Form 13F Information Table section (case-insensitive)
    match = re.search(r'FORM\s+13F\s+INFORMATION\s+TABLE', infotable_txt, re.IGNORECASE)
    if not match:
        return pd.DataFrame()

    # Extract all table content between <TABLE> and </TABLE> tags
    table_pattern = r'<TABLE>(.*?)</TABLE>'
    tables = re.findall(table_pattern, infotable_txt, re.DOTALL | re.IGNORECASE)

    parsed_rows = []

    if tables:
        # Filter tables: keep those with 6+ column markers (holdings tables)
        holdings_tables = []
        remaining_tables = []
        for table_text in tables:
            specs, _, _ = _extract_column_specs(table_text)
            if specs and len(specs) >= _MIN_HOLDINGS_COLUMNS:
                holdings_tables.append(table_text)
            else:
                remaining_tables.append(table_text)

        # Primary: column-position parsing on tables with markers
        for holdings_table in holdings_tables:
            if len(holdings_table.strip()) < 200:
                continue
            rows = _parse_table_with_columns(holdings_table)
            parsed_rows.extend(rows)

        # Fallback: regex parsing on tables without sufficient markers
        if not parsed_rows:
            for table_text in remaining_tables:
                if len(table_text.strip()) < 200:
                    continue
                rows = _parse_text_regex_fallback(table_text)
                parsed_rows.extend(rows)

    # Final fallback: no <TABLE> tags at all — parse raw text after header
    if not parsed_rows:
        text_after_header = infotable_txt[match.start():]
        rows = _parse_text_regex_fallback(text_after_header)
        parsed_rows.extend(rows)

    if not parsed_rows:
        return pd.DataFrame()

    table = pd.DataFrame(parsed_rows)

    # Add ticker symbols using CUSIP mapping
    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

    return table
