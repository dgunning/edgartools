"""
HTML table extraction for 497K (Summary Prospectus) filings.

497K filings have ZERO XBRL — all structured data comes from HTML tables
mandated by Form N-1A rules. This module handles the two main layout patterns:

1. Multi-column (e.g., Vanguard): one table per category with multiple share class columns
2. Repeated-section (e.g., Fidelity): separate table sets per share class
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)

__all__ = [
    'extract_fee_tables',
    'extract_performance_table',
    'extract_fund_metadata',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip nbsp and special chars."""
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text


def _parse_percentage(text: str) -> Optional[Decimal]:
    """Parse '0.14%', '- 22.03 %', 'None', '—', '' into Optional[Decimal]."""
    text = text.strip().replace('\xa0', ' ').replace(',', '')
    if not text or text.lower().strip() in ('none', '—', '–', '-', 'n/a', ''):
        return None
    # Remove % sign and everything after it
    text = re.sub(r'%.*', '', text)
    # Remove trailing footnote markers (letters, spaces)
    text = re.sub(r'[A-Za-z,]+$', '', text).strip()
    if not text:
        return None
    # Collapse internal spaces (handles "- 22.03" → "-22.03")
    text = re.sub(r'\s+', '', text)
    # Handle negative: "(0.05)" -> "-0.05"
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _parse_dollar(text: str) -> Optional[int]:
    """Parse '$14', '$1,234', '14' into Optional[int]."""
    text = text.strip().replace('\xa0', '').replace(',', '').replace('$', '')
    text = re.sub(r'[A-Za-z\s]+$', '', text).strip()
    if not text:
        return None
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _get_cell_text(cell: Tag) -> str:
    """Get clean text from a table cell."""
    return cell.get_text(separator=' ', strip=True)


def _table_texts(table: Tag) -> List[List[str]]:
    """Extract all cell texts from a table as a 2D list."""
    rows = []
    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        rows.append([_get_cell_text(c) for c in cells])
    return rows


def _label_matches(text: str, *patterns: str) -> bool:
    """Check if normalized text matches any of the given patterns."""
    norm = _normalize(text)
    for pat in patterns:
        if pat in norm:
            return True
    return False


# ---------------------------------------------------------------------------
# Table classification
# ---------------------------------------------------------------------------

_FEE_TABLE_LABELS = (
    'management fee',
    'management fees',
)

_EXPENSE_EXAMPLE_LABELS = (
    '1 year',
    '1year',
)

_PERFORMANCE_LABELS = (
    'return before taxes',
)

_QUARTER_LABELS = (
    'highest',
    'lowest',
    'highest quarter',
    'lowest quarter',
)

_SHAREHOLDER_FEE_LABELS = (
    'sales charge',
    'sales load',
    'redemption fee',
    'purchase fee',
    'fees paid directly',
)

_BAR_CHART_LABELS = (
    '2024', '2023', '2022', '2021', '2020',
)


def _classify_table(rows: List[List[str]]) -> Optional[str]:
    """Classify a table by its content. Returns a type string or None."""
    all_text = ' '.join(' '.join(row) for row in rows)
    norm = _normalize(all_text)

    # Check for performance table (has "return before taxes")
    if 'return before taxes' in norm:
        return 'performance'

    # Check for best/worst quarter table
    if ('highest' in norm and 'lowest' in norm and
            ('quarter' in norm or 'return' in norm)):
        return 'quarter'

    # Check for operating expenses table (has "management fee")
    if any(p in norm for p in _FEE_TABLE_LABELS):
        return 'operating_expenses'

    # Tables with year-period columns (1 year, 3 years, etc.)
    # Distinguish expense example ($) from performance (%)
    # Use regex word boundary to avoid 'past 1' matching 'past 10'
    if '1 year' in norm or '1year' in norm or re.search(r'past 1\b', norm):
        has_dollar = '$' in all_text
        has_pct = '%' in all_text
        # If only percentages and no dollar signs → performance
        if has_pct and not has_dollar:
            return 'performance'
        # If dollar amounts present → expense example
        if has_dollar:
            return 'expense_example'

    # Check for shareholder fees
    if any(p in norm for p in _SHAREHOLDER_FEE_LABELS):
        return 'shareholder_fees'

    # Check for bar chart data (has year columns 2020-2024)
    year_count = sum(1 for y in _BAR_CHART_LABELS if y in norm)
    if year_count >= 3:
        return 'bar_chart'

    return None


# ---------------------------------------------------------------------------
# Fee extraction
# ---------------------------------------------------------------------------

def _is_fee_label(text: str) -> bool:
    """Check if a cell contains a fee-related label (not a class name)."""
    norm = _normalize(text)
    fee_keywords = ('management fee', 'distribution', '12b-1', 'other expense',
                    'total annual', 'fee waiver', 'acquired fund', 'net expense',
                    'reimbursement')
    return any(kw in norm for kw in fee_keywords)


def _extract_operating_expenses(rows: List[List[str]]) -> List[Dict]:
    """
    Extract operating expenses from a table.
    Returns list of dicts, one per share class.

    Handles both multi-column (Vanguard: one row per fee type, columns per class)
    and single-column (Fidelity: one data column) layouts.
    """
    if not rows:
        return []

    # Detect if first row is a header (class names) or data (fee labels)
    first_row = rows[0]
    has_header = not _is_fee_label(first_row[0]) if first_row else False

    if has_header:
        header = first_row
        data_rows = rows[1:]
    else:
        header = None
        data_rows = rows

    n_cols = len(first_row) if first_row else 0

    # Find class names from header (skip first column which is labels)
    class_names = []
    if has_header and n_cols > 1:
        for i in range(1, n_cols):
            name = header[i].strip()
            if name:
                class_names.append((i, name))

    # If no header or no class names, single-column format
    if not class_names:
        class_names = [(1, '')]

    results = []
    for col_idx, class_name in class_names:
        data = {'class_name': class_name}

        for row in data_rows:
            if len(row) <= col_idx:
                continue
            label = _normalize(row[0]) if row[0] else ''
            value = row[col_idx] if col_idx < len(row) else ''

            if 'management fee' in label:
                data['management_fee'] = _parse_percentage(value)
            elif '12b-1' in label or ('distribution' in label and 'service' in label):
                data['twelve_b1_fee'] = _parse_percentage(value)
            elif 'other expense' in label:
                data['other_expenses'] = _parse_percentage(value)
            elif 'acquired fund' in label:
                data['acquired_fund_fees'] = _parse_percentage(value)
            elif 'total annual' in label and 'after' not in label:
                data['total_annual_expenses'] = _parse_percentage(value)
            elif 'fee waiver' in label or 'reimbursement' in label:
                data['fee_waiver'] = _parse_percentage(value)
            elif ('net expense' in label or
                  ('total' in label and 'after' in label)):
                data['net_expenses'] = _parse_percentage(value)

        results.append(data)

    return results


def _is_shareholder_fee_label(text: str) -> bool:
    """Check if a cell contains a shareholder fee-related label."""
    norm = _normalize(text)
    keywords = ('sales charge', 'sales load', 'redemption fee', 'purchase fee',
                'exchange fee', 'account service', 'fees paid directly')
    return any(kw in norm for kw in keywords)


def _extract_shareholder_fees(rows: List[List[str]]) -> List[Dict]:
    """Extract shareholder fees (sales loads, redemption fees)."""
    if not rows:
        return []

    # Detect if first row is a header or data
    first_row = rows[0]
    has_header = first_row and not _is_shareholder_fee_label(first_row[0])

    if has_header:
        header = first_row
        data_rows = rows[1:]
    else:
        header = None
        data_rows = rows

    n_cols = len(first_row) if first_row else 0

    class_names = []
    if has_header and n_cols > 1:
        for i in range(1, n_cols):
            name = header[i].strip()
            if name:
                class_names.append((i, name))

    if not class_names:
        class_names = [(1, '')]

    results = []
    for col_idx, class_name in class_names:
        data = {'class_name': class_name}

        for row in data_rows:
            if len(row) <= col_idx:
                continue
            label = _normalize(row[0]) if row[0] else ''
            value = row[col_idx] if col_idx < len(row) else ''

            if ('sales charge' in label or 'sales load' in label) and 'deferred' not in label and 'reinvest' not in label:
                data['max_sales_load'] = _parse_percentage(value)
            elif 'deferred' in label:
                data['max_deferred_sales_load'] = _parse_percentage(value)
            elif 'redemption fee' in label:
                data['redemption_fee'] = _parse_percentage(value)

        results.append(data)

    return results


def _extract_expense_example_multicolumn(rows: List[List[str]]) -> List[Dict]:
    """
    Extract expense example from a multi-row table where each row is a share class.

    Vanguard format:
        ['', '1 Year', '3 Years', '5 Years', '10 Years']
        ['Investor Shares', '$14', '$45', '$79', '$179']
    """
    if not rows:
        return []

    # Find the header row with year columns
    header_idx = 0
    year_cols = {}
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            norm = _normalize(cell)
            if '1 year' in norm or '1year' in norm:
                header_idx = i
                # Map year columns — check longest matches first
                for k, hcell in enumerate(row):
                    hn = _normalize(hcell)
                    if '10 year' in hn or '10year' in hn:
                        year_cols[10] = k
                    elif '5 year' in hn or '5year' in hn:
                        year_cols[5] = k
                    elif '3 year' in hn or '3year' in hn:
                        year_cols[3] = k
                    elif '1 year' in hn or '1year' in hn:
                        year_cols[1] = k
                break
        if year_cols:
            break

    if not year_cols:
        return []

    results = []
    for row in rows[header_idx + 1:]:
        if not row or not row[0].strip():
            continue
        class_name = row[0].strip()
        data = {'class_name': class_name}
        if 1 in year_cols and year_cols[1] < len(row):
            data['expense_1yr'] = _parse_dollar(row[year_cols[1]])
        if 3 in year_cols and year_cols[3] < len(row):
            data['expense_3yr'] = _parse_dollar(row[year_cols[3]])
        if 5 in year_cols and year_cols[5] < len(row):
            data['expense_5yr'] = _parse_dollar(row[year_cols[5]])
        if 10 in year_cols and year_cols[10] < len(row):
            data['expense_10yr'] = _parse_dollar(row[year_cols[10]])
        results.append(data)

    return results


def _extract_expense_example_singlecolumn(rows: List[List[str]]) -> Dict:
    """
    Extract expense example from a single-column table (Fidelity format).

    Fidelity format:
        ['1 year', '$', '47']
        ['3 years', '$', '148']
    """
    data = {}
    for row in rows:
        if not row:
            continue
        label = _normalize(row[0]) if row[0] else ''
        # Combine all cells after label for the value
        value_text = ' '.join(row[1:]) if len(row) > 1 else ''

        # Check longest matches first to avoid '1 year' matching '10 year'
        if '10 year' in label or '10year' in label:
            data['expense_10yr'] = _parse_dollar(value_text)
        elif '5 year' in label or '5year' in label:
            data['expense_5yr'] = _parse_dollar(value_text)
        elif '3 year' in label or '3year' in label:
            data['expense_3yr'] = _parse_dollar(value_text)
        elif '1 year' in label or '1year' in label:
            data['expense_1yr'] = _parse_dollar(value_text)

    return data


# ---------------------------------------------------------------------------
# Performance extraction
# ---------------------------------------------------------------------------

def _extract_performance(rows: List[List[str]]) -> Tuple[List[Dict], List[str]]:
    """
    Extract average annual returns from a performance table.

    Returns (list of return dicts, list of period column names).

    Both formats have header row with period columns and data rows with labels.
    Handles section headers (e.g. fund name row with empty data cells).
    """
    if not rows:
        return [], []

    # Find header row with period columns
    header_idx = 0
    period_cols = {}
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            norm = _normalize(cell)
            if '1 year' in norm or '1year' in norm or 'past 1' in norm:
                header_idx = i
                # Map year columns — check longest matches first to avoid
                # 'past 1' matching 'past 10 years'
                for k, hcell in enumerate(row):
                    hn = _normalize(hcell)
                    if '10 year' in hn or '10year' in hn or 'past 10' in hn:
                        period_cols['10yr'] = k
                    elif '5 year' in hn or '5year' in hn or 'past 5' in hn:
                        period_cols['5yr'] = k
                    elif '1 year' in hn or '1year' in hn or 'past 1' in hn:
                        period_cols['1yr'] = k
                    elif 'since inception' in hn or 'since fund' in hn:
                        period_cols['since_inception'] = k
                break
        if period_cols:
            break

    if not period_cols:
        return [], []

    results = []
    current_section = ''
    for row in rows[header_idx + 1:]:
        if not row or not row[0].strip():
            continue

        label = row[0].strip()
        norm_label = _normalize(label)

        # Check if this is a section header (fund/class name with empty data)
        data_cells = [row[c] if c < len(row) else '' for c in period_cols.values()]
        has_data = any(cell.strip() for cell in data_cells)

        if not has_data:
            current_section = label
            continue

        data = {'label': label, 'section': current_section}
        if '1yr' in period_cols and period_cols['1yr'] < len(row):
            data['return_1yr'] = _parse_percentage(row[period_cols['1yr']])
        if '5yr' in period_cols and period_cols['5yr'] < len(row):
            data['return_5yr'] = _parse_percentage(row[period_cols['5yr']])
        if '10yr' in period_cols and period_cols['10yr'] < len(row):
            data['return_10yr'] = _parse_percentage(row[period_cols['10yr']])
        if 'since_inception' in period_cols and period_cols['since_inception'] < len(row):
            data['return_since_inception'] = _parse_percentage(row[period_cols['since_inception']])

        results.append(data)

    return results, list(period_cols.keys())


def _extract_quarter_data(rows: List[List[str]]) -> Tuple[Optional[Tuple[Decimal, str]],
                                                            Optional[Tuple[Decimal, str]]]:
    """
    Extract best/worst quarter from a table.
    Returns (best_quarter, worst_quarter) as (return, date) tuples.
    """
    best = None
    worst = None

    for row in rows:
        if not row:
            continue
        label = _normalize(row[0]) if row[0] else ''

        if 'highest' in label or 'best' in label:
            # Look for return value and date in remaining cells
            return_val = None
            date_str = None
            for cell in row[1:]:
                cell_text = cell.strip()
                if '%' in cell_text or re.match(r'-?\d+\.?\d*', cell_text):
                    pct = _parse_percentage(cell_text)
                    if pct is not None:
                        return_val = pct
                elif re.search(r'(january|february|march|april|may|june|july|august|'
                               r'september|october|november|december)', cell_text.lower()):
                    date_str = cell_text
            if return_val is not None:
                best = (return_val, date_str or '')

        elif 'lowest' in label or 'worst' in label:
            return_val = None
            date_str = None
            for cell in row[1:]:
                cell_text = cell.strip()
                if '%' in cell_text or re.match(r'-?\d+\.?\d*', cell_text):
                    pct = _parse_percentage(cell_text)
                    if pct is not None:
                        return_val = pct
                elif re.search(r'(january|february|march|april|may|june|july|august|'
                               r'september|october|november|december)', cell_text.lower()):
                    date_str = cell_text
            if return_val is not None:
                worst = (return_val, date_str or '')

    return best, worst


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_fee_tables(html: str, class_info: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Extract fee data from 497K HTML. Returns a list of dicts, one per share class.

    Each dict has keys: class_name, management_fee, twelve_b1_fee, other_expenses,
    total_annual_expenses, fee_waiver, net_expenses, max_sales_load,
    max_deferred_sales_load, redemption_fee, expense_1yr, expense_3yr,
    expense_5yr, expense_10yr.

    Args:
        html: The HTML content of the 497K filing
        class_info: Optional list of class dicts from SGML header with 'name' and 'ticker' keys
    """
    soup = BeautifulSoup(html, 'lxml')
    tables = soup.find_all('table')

    # Classify all tables
    classified = []
    for table in tables:
        rows = _table_texts(table)
        if not rows:
            continue
        ttype = _classify_table(rows)
        if ttype:
            classified.append((ttype, rows))

    # Group tables into sections by type sequence
    # Strategy: find operating_expenses tables and build share class data around them
    op_expense_tables = [(i, rows) for i, (ttype, rows) in enumerate(classified)
                         if ttype == 'operating_expenses']
    sh_fee_tables = [(i, rows) for i, (ttype, rows) in enumerate(classified)
                     if ttype == 'shareholder_fees']
    expense_ex_tables = [(i, rows) for i, (ttype, rows) in enumerate(classified)
                         if ttype == 'expense_example']

    # Determine layout: multi-column vs repeated-section
    share_classes = []

    if len(op_expense_tables) == 1:
        # Single fee table — likely multi-column (Vanguard style)
        _, rows = op_expense_tables[0]
        op_data = _extract_operating_expenses(rows)

        # Shareholder fees
        sh_data = []
        if sh_fee_tables:
            _, sh_rows = sh_fee_tables[0]
            sh_data = _extract_shareholder_fees(sh_rows)

        # Expense example
        ex_data = []
        if expense_ex_tables:
            _, ex_rows = expense_ex_tables[0]
            # Check if multi-row (Vanguard) or single-column (Fidelity)
            ex_extracted = _extract_expense_example_multicolumn(ex_rows)
            if ex_extracted:
                ex_data = ex_extracted

        # Merge data per class
        for i, od in enumerate(op_data):
            merged = dict(od)
            if i < len(sh_data):
                merged.update({k: v for k, v in sh_data[i].items() if k != 'class_name'})
            if i < len(ex_data):
                merged.update({k: v for k, v in ex_data[i].items() if k != 'class_name'})
            share_classes.append(merged)

    elif len(op_expense_tables) > 1:
        # Multiple fee tables — likely repeated sections (Fidelity style)
        for section_idx, (table_idx, rows) in enumerate(op_expense_tables):
            op_data = _extract_operating_expenses(rows)
            data = op_data[0] if op_data else {}

            # Find the nearest shareholder fee table before this one
            for sh_idx, sh_rows in reversed(sh_fee_tables):
                if sh_idx < table_idx:
                    sh_data = _extract_shareholder_fees(sh_rows)
                    if sh_data:
                        data.update({k: v for k, v in sh_data[0].items() if k != 'class_name'})
                    break

            # Find the nearest expense example table after this one
            for ex_idx, ex_rows in expense_ex_tables:
                if ex_idx > table_idx:
                    # Try single-column first (Fidelity)
                    ex_data = _extract_expense_example_singlecolumn(ex_rows)
                    if ex_data:
                        data.update(ex_data)
                    else:
                        ex_multi = _extract_expense_example_multicolumn(ex_rows)
                        if ex_multi:
                            data.update({k: v for k, v in ex_multi[0].items() if k != 'class_name'})
                    break

            share_classes.append(data)

    # Enrich with class info from SGML header
    if class_info and share_classes:
        _merge_class_info(share_classes, class_info, html=html)

    return share_classes


def extract_performance_table(html: str) -> Tuple[List[Dict],
                                                    Optional[Tuple[Decimal, str]],
                                                    Optional[Tuple[Decimal, str]]]:
    """
    Extract performance returns and best/worst quarter data from 497K HTML.

    Returns:
        (performance_rows, best_quarter, worst_quarter)
        - performance_rows: list of dicts with label, return_1yr, return_5yr, return_10yr, etc.
        - best_quarter: (return_pct, date_str) or None
        - worst_quarter: (return_pct, date_str) or None
    """
    soup = BeautifulSoup(html, 'lxml')
    tables = soup.find_all('table')

    all_performance = []
    best_quarter = None
    worst_quarter = None

    for table in tables:
        rows = _table_texts(table)
        if not rows:
            continue
        ttype = _classify_table(rows)

        if ttype == 'performance':
            perf_data, _ = _extract_performance(rows)
            all_performance.extend(perf_data)

        elif ttype == 'quarter':
            best, worst = _extract_quarter_data(rows)
            # Use the first best/worst we find (for multi-section, the first is primary class)
            if best and best_quarter is None:
                best_quarter = best
            if worst and worst_quarter is None:
                worst_quarter = worst

    return all_performance, best_quarter, worst_quarter


def extract_fund_metadata(html: str) -> Dict:
    """
    Extract fund-level metadata from 497K HTML.

    Returns dict with keys: fund_name, prospectus_date, portfolio_turnover,
    investment_objective, portfolio_managers, min_investments.
    """
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator='\n', strip=True)
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    result = {
        'fund_name': None,
        'prospectus_date': None,
        'portfolio_turnover': None,
        'investment_objective': None,
        'portfolio_managers': [],
        'min_investments': {},
    }

    # Portfolio turnover — look for "XX%" near "portfolio turnover"
    turnover_pattern = re.compile(
        r'portfolio\s+turnover.*?(\d+(?:\.\d+)?)\s*%',
        re.IGNORECASE | re.DOTALL
    )
    match = turnover_pattern.search(text)
    if match:
        try:
            result['portfolio_turnover'] = Decimal(match.group(1))
        except (InvalidOperation, ValueError):
            pass

    # Investment objective — usually first substantive paragraph after "Investment Objective"
    obj_pattern = re.compile(
        r'investment\s+objective\s*[:\.]?\s*(.*?)(?:fees?\s+and\s+expenses?|principal|$)',
        re.IGNORECASE | re.DOTALL
    )
    match = obj_pattern.search(text)
    if match:
        obj_text = match.group(1).strip()
        # Take first sentence or two
        sentences = re.split(r'(?<=[.!?])\s+', obj_text)
        if sentences:
            result['investment_objective'] = ' '.join(sentences[:3]).strip()

    # Minimum investments — look for "$X,XXX" near "minimum"
    min_pattern = re.compile(
        r'(?:minimum|initial)\s+(?:investment|purchase)[^$]*\$\s*([\d,]+)',
        re.IGNORECASE
    )
    for match in min_pattern.finditer(text):
        amount = match.group(1).replace(',', '')
        try:
            result['min_investments'][int(amount)] = match.group(0).strip()
        except ValueError:
            pass

    return result


# ---------------------------------------------------------------------------
# Merging helpers
# ---------------------------------------------------------------------------

def _reorder_class_info_by_html(class_info: List[Dict], html: str) -> List[Dict]:
    """Reorder class_info to match the order tickers/names appear in the HTML."""
    if len(class_info) <= 1:
        return class_info

    # Find the first position of each class's ticker or name in the HTML
    positions = []
    for ci in class_info:
        pos = len(html)  # default to end
        ticker = ci.get('ticker', '')
        name = ci.get('name', '')
        if ticker:
            idx = html.find(ticker)
            if idx >= 0:
                pos = min(pos, idx)
        if name:
            idx = html.find(name)
            if idx >= 0:
                pos = min(pos, idx)
        positions.append((pos, ci))

    # Sort by position in HTML
    positions.sort(key=lambda x: x[0])
    return [ci for _, ci in positions]


def _merge_class_info(share_classes: List[Dict], class_info: List[Dict],
                      html: Optional[str] = None):
    """
    Merge SGML header class info (ticker, class_id) into extracted share classes.

    Matching strategy:
    1. Exact match on class name
    2. Substring match (SGML name in extracted name or vice versa)
    3. Positional fallback with HTML-order alignment
    """
    if not class_info or not share_classes:
        return

    # Try name matching first
    matched_ci = set()
    matched_sc = set()
    for sc_idx, sc in enumerate(share_classes):
        sc_name = _normalize(sc.get('class_name', ''))
        for ci_idx, ci in enumerate(class_info):
            if ci_idx in matched_ci:
                continue
            ci_name = _normalize(ci.get('name', ''))
            if ci_name and sc_name and (ci_name in sc_name or sc_name in ci_name):
                sc['ticker'] = ci.get('ticker')
                sc['class_id'] = ci.get('class_id')
                if not sc.get('class_name') or sc['class_name'] == '':
                    sc['class_name'] = ci.get('name', '')
                matched_ci.add(ci_idx)
                matched_sc.add(sc_idx)
                break

    # Positional fallback for unmatched — reorder class_info by HTML position
    unmatched_sc = [i for i in range(len(share_classes)) if i not in matched_sc]
    unmatched_ci = [class_info[i] for i in range(len(class_info)) if i not in matched_ci]

    if unmatched_sc and unmatched_ci:
        if html:
            unmatched_ci = _reorder_class_info_by_html(unmatched_ci, html)
        for sc_idx, ci in zip(unmatched_sc, unmatched_ci):
            sc = share_classes[sc_idx]
            sc['ticker'] = ci.get('ticker')
            sc['class_id'] = ci.get('class_id')
            if not sc.get('class_name') or sc['class_name'] == '':
                sc['class_name'] = ci.get('name', '')
