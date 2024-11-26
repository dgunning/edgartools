import re


def _get_period_header_pattern() -> re.Pattern:
    """Create regex pattern for common financial period headers"""
    periods = r'(?:three|six|nine|twelve|[1-4]|first|second|third|fourth)'
    timeframes = r'(?:month|quarter|year|week)'
    ended_variants = r'(?:ended|ending|end|period)'
    date_patterns = r'(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}'
    years = r'(?:19|20)\d{2}'

    # Combine into flexible patterns that match common variations
    patterns = [
        # "Three Months Ended December 31,"
        fr'{periods}\s+{timeframes}\s+{ended_variants}(?:\s+{date_patterns})?',
        # "Fiscal Year Ended"
        fr'(?:fiscal\s+)?{timeframes}\s+{ended_variants}',
        # "Quarters Ended June 30, 2023"
        fr'{timeframes}\s+{ended_variants}(?:\s+{date_patterns})?(?:\s*,?\s*{years})?'
    ]

    # Combine all patterns with non-capturing group
    combined_pattern = '|'.join(f'(?:{p})' for p in patterns)
    return re.compile(combined_pattern, re.IGNORECASE)


def _analyze_table_structure(rows: list) -> tuple[list, int]:
    """
    Analyze table structure to determine headers and data rows.
    Returns (header_rows, data_start_index)
    """
    if not rows:
        return [], 0

    row_analyses = [_analyze_row(row) for row in rows[:4]]
    period_pattern = _get_period_header_pattern()

    # Pattern 1: Look for period headers
    for i, row in enumerate(rows[:3]):  # Check first 3 rows
        header_text = ' '.join(cell.strip() for cell in row).lower()
        if period_pattern.search(header_text):
            # Found a period header, check if next row has years or is part of header
            if i + 1 < len(rows):
                next_row = rows[i + 1]
                next_text = ' '.join(cell.strip() for cell in next_row)
                # Check if next row has years or quarter references
                if (any(str(year) in next_text for year in range(2010, 2030)) or
                        any(q in next_text.lower() for q in ['q1', 'q2', 'q3', 'q4'])):
                    return rows[:i + 2], i + 2
            return rows[:i + 1], i + 1

