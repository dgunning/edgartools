"""
424B* table classification and extraction.

Classifies tables from filing.parse().tables into semantic types,
then extracts structured data from identified tables.

See docs/internal/research/424b-research-results/table-classification.md
for validation results and edge cases.
"""

from __future__ import annotations

import re
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.documents.table_nodes import TableNode

__all__ = [
    'classify_table',
    'classify_tables_in_document',
    'extract_pricing_data',
    'extract_offering_terms',
    'extract_dilution_data',
    'extract_capitalization_data',
    'extract_selling_stockholders_data',
    'extract_structured_note_terms',
    'extract_underwriting_from_tables',
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_table_cells(table: 'TableNode') -> List[str]:
    """Flatten all non-empty cell texts from table rows."""
    cells = []
    for r in table.rows:
        for c in r.cells:
            t = c.text().strip()
            if t:
                cells.append(t)
    return cells


def _get_all_cells_including_headers(table: 'TableNode') -> List[str]:
    """All non-empty cells including header rows."""
    cells = []
    for r in table.rows:
        for c in r.cells:
            t = c.text().strip()
            if t:
                cells.append(t)
    for h in table.headers:
        for c in h:
            t = c.text().strip()
            if t:
                cells.append(t)
    return cells


def _get_full_text(table: 'TableNode') -> str:
    """Lowercase text from all cells including headers."""
    return ' '.join(_get_all_cells_including_headers(table)).lower()


def _get_row_texts(table: 'TableNode') -> List[List[str]]:
    """List of rows, each as list of non-empty cell texts."""
    result = []
    for r in table.rows:
        row = [c.text().strip() for c in r.cells if c.text().strip()]
        result.append(row)
    return result


def _fraction_long_cells(table: 'TableNode', min_len: int = 60) -> float:
    """Fraction of non-empty cells exceeding min_len characters."""
    cells = _get_table_cells(table)
    if not cells:
        return 0.0
    return sum(1 for c in cells if len(c) >= min_len) / len(cells)


def _has_numeric_cells(table: 'TableNode') -> bool:
    """True if any row cell is numeric."""
    return any(c.is_numeric for r in table.rows for c in r.cells)


def _extract_row_label_and_values(row) -> tuple:
    """
    Extract (label, numeric_values) from a row with sparse cells.

    SEC HTML tables often have empty spacer cells and separate '$' cells.
    Returns the first non-empty non-$ text as label, and all numeric cell
    texts as the values list.
    """
    label = ''
    values = []
    for c in row.cells:
        t = c.text().strip()
        if not t or t == '$':
            continue
        if c.is_numeric:
            values.append(t)
        elif not label:
            label = t
    return label, values


# ---------------------------------------------------------------------------
# Table type predicates
# ---------------------------------------------------------------------------

def _is_layout_table(table: 'TableNode') -> bool:
    """Layout container: single cell, empty, bullet list, or all long paragraphs."""
    nrows = len(table.rows)

    if nrows == 0:
        header_cells = [c.text().strip() for h in table.headers for c in h if c.text().strip()]
        if not header_cells:
            return True
        if header_cells[0] in ('·', '•', '●', '-', '—', 'Q:', 'A:'):
            return True
        if len(header_cells) == 1 and len(header_cells[0]) > 80:
            return True
        if all(len(c) > 40 for c in header_cells):
            return True
        return False

    cells = _get_table_cells(table)
    if not cells:
        return True

    # Single value = page number or long text
    if len(cells) == 1:
        v = cells[0].strip()
        if re.match(r'^(S-?\d+|[ivxlIVXL]+|\d{1,3})$', v, re.IGNORECASE):
            return True
        if len(v) > 100:
            return True

    # Bullet-list pattern
    if cells[0] in ('·', '•', '●', '-', '—'):
        return True

    # Q&A pattern
    if nrows == 1:
        first = cells[0]
        if re.match(r'^[QA][:.]$', first) or re.match(r'^\(\d\)$', first):
            return True

    # All cells are long paragraphs
    if _fraction_long_cells(table, 60) >= 0.75:
        return True

    return False


def _is_toc_table(table: 'TableNode') -> bool:
    """Table of contents: rightmost column has page numbers."""
    rows = _get_row_texts(table)
    if len(rows) < 3:
        return False
    page_pattern = re.compile(r'^(S-?\d+|[ivxlIVXL]+|\d{1,3})$', re.IGNORECASE)
    page_matches = 0
    valid_rows = 0
    for row in rows:
        if len(row) >= 2:
            valid_rows += 1
            if page_pattern.match(row[-1].strip()):
                page_matches += 1
    return valid_rows >= 3 and page_matches / valid_rows >= 0.6


def _is_pricing_table(table: 'TableNode') -> bool:
    """Pricing: offering price + fee + proceeds with numeric data."""
    if len(table.rows) < 2:
        return False
    if _fraction_long_cells(table, 60) > 0.4:
        return False
    cells = _get_table_cells(table)
    if cells and cells[0] in ('·', '•', '●', '-', '—'):
        return False
    text = _get_full_text(table)
    has_offering = ('offering price' in text or 'public offering price' in text or
                    'subscription price' in text)
    has_proceeds = 'proceeds' in text
    has_fee = ('discount' in text or 'commission' in text or
               'placement agent' in text or 'placement agents' in text or
               "agent's fee" in text or "agent fees" in text or
               'underwriting' in text)
    has_numeric = _has_numeric_cells(table)
    is_rights = 'subscription price' in text and has_proceeds and has_numeric
    return has_offering and has_proceeds and (has_fee or is_rights) and has_numeric


def _is_offering_summary(table: 'TableNode') -> bool:
    """Offering terms key-value table."""
    if len(table.rows) < 3:
        return False
    cells = _get_table_cells(table)
    if not cells:
        return False
    if _fraction_long_cells(table, 200) >= 0.5:
        return False
    ncols = max((len(r.cells) for r in table.rows), default=0)
    if ncols > 4:
        return False
    text = _get_full_text(table)
    keywords = [
        'shares offered', 'common stock offered', 'notes offered',
        'use of proceeds', 'trading symbol', 'stock symbol', 'listing',
        'risk factors', 'issuer:', 'common stock offered:',
        'record date', 'subscription rights', 'aggregate offering',
        'subscription price', 'basic subscription', 'over-subscription',
    ]
    return sum(1 for kw in keywords if kw in text) >= 2


def _is_selling_stockholders(table: 'TableNode') -> bool:
    """Selling stockholders name + before/after shares table."""
    text = _get_full_text(table)
    has_selling_kw = ('selling stockholder' in text or 'selling security' in text or
                      'selling shareholder' in text)
    has_before_after = ('before offering' in text or 'before the offering' in text) and \
                       ('after offering' in text or 'after the offering' in text)
    has_name = 'name and address' in text or 'name of selling' in text
    has_beneficial = 'beneficial' in text and 'offered' in text
    has_numeric = _has_numeric_cells(table)
    if has_selling_kw and has_numeric:
        return True
    if has_before_after and has_name and has_numeric:
        return True
    if has_name and has_beneficial and has_numeric and len(table.rows) >= 5:
        return True
    return False


def _is_key_terms(table: 'TableNode') -> bool:
    """Structured note key terms: Issuer, CUSIP, Maturity, etc."""
    if len(table.rows) < 5:
        return False
    if _fraction_long_cells(table, 200) > 0.5:
        return False
    text = _get_full_text(table)
    core_keywords = ['cusip', 'maturity date', 'underlying', 'pricing date',
                     'issue date', 'valuation date', 'denominations',
                     'upside participation', 'max return', 'threshold value']
    supporting_keywords = ['issuer', 'guarantor', 'notes offered', 'term:',
                           'redemption amount', 'indenture', 'calculation agent',
                           'selling agent']
    core_matches = sum(1 for kw in core_keywords if kw in text)
    supp_matches = sum(1 for kw in supporting_keywords if kw in text)
    ncols = max((len(r.cells) for r in table.rows), default=0)
    if ncols <= 3 and (core_matches >= 2 or (core_matches >= 1 and supp_matches >= 3)):
        return True
    return False


def _is_dilution(table: 'TableNode') -> bool:
    """Dilution per share table with NTBV."""
    text = _get_full_text(table)
    has_dilution = 'dilution' in text
    has_ntbv = 'net tangible book value' in text or 'tangible book value' in text
    has_per_share = 'per share' in text
    has_numeric = _has_numeric_cells(table)
    return has_dilution and (has_ntbv or has_per_share) and has_numeric


def _is_capitalization(table: 'TableNode') -> bool:
    """Capitalization: actual/as-adjusted columns with capital structure."""
    if len(table.rows) < 4:
        return False
    if _fraction_long_cells(table, 80) > 0.5:
        return False
    text = _get_full_text(table)
    has_adj = 'as adjusted' in text or ('actual' in text and 'adjusted' in text)
    has_capital = ('stockholders' in text or 'shareholders' in text or
                   'total capitalization' in text)
    has_numeric = _has_numeric_cells(table)
    return has_adj and has_capital and has_numeric


def _is_underwriting_syndicate(table: 'TableNode') -> bool:
    """Underwriting syndicate: bank names as header cells."""
    short_header_cells = []
    for h in table.headers:
        for c in h:
            ct = c.text().strip()
            if ct and len(ct) < 50:
                short_header_cells.append(ct.lower())
    specific_bank_patterns = [
        r'\bj\.?p\.?\s*morgan\b', r'\bmorgan stanley\b', r'\bgoldman\b',
        r'\bmerrill lynch\b', r'\bbarclays\b', r'\bcitigroup\b', r'\bciti\b',
        r'\bwells fargo\b', r'\bbofa securities\b',
        r'\bcredit suisse\b', r'\bdeutsche bank\b', r'\bubs\s+\b',
        r'\brbc\s+capital\b', r'\bjefferies\b', r'\bpiper sandler\b',
        r'\bmizuho\b', r'\bbny\s+capital\b', r'\bbnp paribas\b',
        r'\bstifel\b', r'\bcanaccord\b', r'\bleerink\b',
        r'\bwilliam blair\b', r'\bneedham\b',
    ]
    short_header_text = ' '.join(short_header_cells)
    bank_count = sum(1 for p in specific_bank_patterns
                     if re.search(p, short_header_text, re.IGNORECASE))
    if bank_count >= 2 and len(table.headers) >= 1:
        return True
    text = _get_full_text(table)
    has_underwriter_kw = 'underwriter' in text and 'number of shares' in text
    has_numbers = any(
        re.search(r'\b\d{1,3}(?:,\d{3})+\b', c.text())
        for r in table.rows for c in r.cells
    )
    return has_underwriter_kw and has_numbers and len(table.rows) > 3


def _is_expenses(table: 'TableNode') -> bool:
    """Itemized offering expenses table."""
    if len(table.rows) < 2:
        return False
    text = _get_full_text(table)
    expense_keywords = [
        'sec registration', 'sec filing fee', 'finra filing fee', 'finra',
        'legal fees', 'legal expenses', 'accounting fees', 'accounting expenses',
        'printing', 'transfer agent', 'estimated expenses', 'total expenses',
        'miscellaneous expenses',
    ]
    return sum(1 for kw in expense_keywords if kw in text) >= 2


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_table(table: 'TableNode') -> str:
    """
    Classify a TableNode into a semantic table type.

    Returns one of: 'layout', 'toc', 'pricing_table', 'offering_summary',
    'selling_stockholders', 'key_terms', 'dilution', 'capitalization',
    'underwriting_syndicate', 'expenses', 'other'.
    """
    if _is_layout_table(table):
        return 'layout'
    if _is_toc_table(table):
        return 'toc'
    if _is_pricing_table(table):
        return 'pricing_table'
    if _is_selling_stockholders(table):
        return 'selling_stockholders'
    if _is_key_terms(table):
        return 'key_terms'
    if _is_dilution(table):
        return 'dilution'
    if _is_capitalization(table):
        return 'capitalization'
    if _is_underwriting_syndicate(table):
        return 'underwriting_syndicate'
    if _is_expenses(table):
        return 'expenses'
    if _is_offering_summary(table):
        return 'offering_summary'
    return 'other'


def classify_tables_in_document(document) -> dict:
    """
    Classify all tables in a parsed Document.

    Args:
        document: Document from filing.parse()

    Returns:
        Dict mapping table type -> list of TableNode objects.
        Only types with at least one match are included.
    """
    tables = document.tables
    if not tables:
        return {}

    result: dict[str, list] = {}
    for table in tables:
        label = classify_table(table)
        if label not in ('layout', 'other', 'toc'):
            result.setdefault(label, []).append(table)
    return result


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def extract_pricing_data(table: 'TableNode'):
    """
    Extract structured pricing data from a pricing_table.

    Handles both equity (per-share columns) and debt (per-note) layouts.
    SEC tables have sparse cells with separate '$' cells.
    """
    from edgar.offerings.prospectus import PricingData, PricingColumnData

    # Determine column structure from header row (row 0)
    # Row 0 typically has column labels like "Per Share", "Total"
    header_labels = []
    if table.rows:
        for c in table.rows[0].cells:
            t = c.text().strip()
            if t and not c.is_numeric and t != '$':
                header_labels.append(t)

    # Extract row data
    offering_price_vals: list[str] = []
    fee_vals: list[str] = []
    proceeds_vals: list[str] = []
    raw_rows: list[list[str]] = []

    for row in table.rows:
        label, values = _extract_row_label_and_values(row)
        label_lower = label.lower()
        raw_rows.append([label] + values)

        if not values:
            continue

        if 'offering price' in label_lower or 'subscription price' in label_lower:
            offering_price_vals = values
        elif 'proceeds' in label_lower:
            proceeds_vals = values
        elif any(kw in label_lower for kw in ('discount', 'commission', 'placement agent',
                                                'agent fee', "agent's fee")):
            fee_vals = values

    # Build columns from the extracted values
    # Typically: col 0 = per unit, col -1 = total
    num_cols = max(len(offering_price_vals), len(fee_vals), len(proceeds_vals))
    if num_cols == 0:
        return PricingData(raw_rows=raw_rows)

    columns = []
    for i in range(num_cols):
        col_label = header_labels[i] if i < len(header_labels) else None
        columns.append(PricingColumnData(
            column_label=col_label,
            offering_price='$' + offering_price_vals[i] if i < len(offering_price_vals) else None,
            fee_or_discount='$' + fee_vals[i] if i < len(fee_vals) else None,
            proceeds='$' + proceeds_vals[i] if i < len(proceeds_vals) else None,
        ))

    # Detect percentage pricing (debt offerings)
    is_pct = any(
        '%' in (v or '')
        for col in columns
        for v in [col.offering_price]
    )

    # Detect fee type
    fee_type = None
    for row in table.rows:
        label, _ = _extract_row_label_and_values(row)
        ll = label.lower()
        if 'placement agent' in ll:
            fee_type = 'placement_agent_fees'
            break
        if 'underwriting' in ll or 'discount' in ll:
            fee_type = 'underwriting_discount'
            break

    return PricingData(
        columns=columns,
        fee_type=fee_type,
        is_percentage_price=is_pct,
        raw_rows=raw_rows,
    )


def extract_offering_terms(table: 'TableNode'):
    """
    Extract key-value offering terms from an offering_summary table.

    These tables have 2 columns: term label | description.
    """
    from edgar.offerings.prospectus import OfferingTerms

    terms: dict = {}
    additional: dict = {}

    for row in table.rows:
        # Get non-empty cells
        cells = [c.text().strip() for c in row.cells if c.text().strip()]
        if len(cells) < 2:
            continue

        key = cells[0].lower().rstrip(':')
        value = cells[-1]  # Last non-empty cell is the value

        if 'shares offered' in key or 'common stock offered' in key:
            terms['shares_offered'] = value
        elif 'pre-funded warrant' in key:
            terms['pre_funded_warrants_offered'] = value
        elif 'warrant' in key and 'offered' in key:
            terms['warrants_offered'] = value
        elif 'use of proceeds' in key:
            terms['use_of_proceeds_summary'] = value
        elif 'trading symbol' in key or 'stock symbol' in key:
            terms['trading_symbol'] = value
        elif 'listing' in key or 'exchange' in key:
            terms['listing_exchange'] = value
        elif 'subscription price' in key:
            terms['subscription_price'] = value
        elif 'subscription rights' in key:
            terms['subscription_rights'] = value
        elif 'record date' in key:
            terms['record_date'] = value
        elif 'over-subscription' in key or 'over subscription' in key:
            terms['over_subscription_privilege'] = value
        else:
            # Store as additional term
            additional[cells[0].rstrip(':')] = value

    return OfferingTerms(**terms, additional_terms=additional)


def extract_dilution_data(table: 'TableNode'):
    """
    Extract per-share dilution data from a dilution table.

    Rows have labels like "Public offering price per share" followed
    by sparse cells with '$' separators and numeric values.
    """
    from edgar.offerings.prospectus import DilutionData

    fields: dict = {}

    for row in table.rows:
        label, values = _extract_row_label_and_values(row)
        label_lower = label.lower()
        val = values[-1] if values else None  # Rightmost numeric value

        if not val:
            continue

        # Format with $ if positive or negative
        formatted = f"${val}" if not val.startswith('(') else val

        if 'offering price' in label_lower:
            fields['public_offering_price'] = formatted
        elif 'historical' in label_lower or ('book value' in label_lower and 'before' in label_lower):
            fields['ntbv_before_offering'] = formatted
        elif 'increase' in label_lower or 'attributable' in label_lower:
            fields['ntbv_increase'] = formatted
        elif ('as adjusted' in label_lower or 'after' in label_lower) and 'book value' in label_lower:
            fields['ntbv_after_offering'] = formatted
        elif 'dilution' in label_lower and 'per share' in label_lower:
            fields['dilution_per_share'] = formatted

    return DilutionData(**fields)


def extract_capitalization_data(table: 'TableNode'):
    """
    Extract actual vs. as-adjusted capitalization data.

    The table has 2+ data columns (Actual, As Adjusted) with many rows.
    """
    from edgar.offerings.prospectus import CapitalizationData

    rows_data: list[dict] = []
    fields: dict = {}

    for row in table.rows:
        label, values = _extract_row_label_and_values(row)
        if not label:
            continue

        label_lower = label.lower()

        # Skip pure header rows
        if label_lower in ('actual', 'as adjusted'):
            continue

        row_dict = {'label': label}
        if len(values) >= 2:
            row_dict['actual'] = values[0]
            row_dict['as_adjusted'] = values[1]
        elif len(values) == 1:
            row_dict['actual'] = values[0]

        rows_data.append(row_dict)

        # Map known fields
        if 'cash' in label_lower and 'equivalents' in label_lower:
            if len(values) >= 2:
                fields['cash_actual'] = values[0]
                fields['cash_as_adjusted'] = values[1]
        elif 'total stockholders' in label_lower or 'total shareholders' in label_lower:
            if len(values) >= 2:
                fields['total_stockholders_equity_actual'] = values[0]
                fields['total_stockholders_equity_as_adjusted'] = values[1]
        elif 'total capitalization' in label_lower:
            if len(values) >= 2:
                fields['total_capitalization_actual'] = values[0]
                fields['total_capitalization_as_adjusted'] = values[1]

    return CapitalizationData(rows=rows_data, **fields)


def extract_selling_stockholders_data(table: 'TableNode'):
    """
    Extract selling stockholder entries from a selling_stockholders table.

    These tables list stockholders with shares before/after the offering.
    Column layouts vary but typically include:
    name | shares_before | pct_before | shares_offered | shares_after | pct_after
    """
    from edgar.offerings.prospectus import SellingStockholdersData, SellingStockholderEntry

    entries: list = []
    total_offered: Optional[str] = None

    # Determine column mapping from headers or first row
    header_cells = []
    for h in table.headers:
        for c in h:
            t = c.text().strip()
            if t:
                header_cells.append(t.lower())

    if not header_cells:
        # Try first non-empty row as header
        for r in table.rows:
            cells = [c.text().strip() for c in r.cells if c.text().strip()]
            if cells and any(kw in ' '.join(cells).lower() for kw in
                            ('name', 'selling', 'beneficial', 'shares')):
                header_cells = [c.lower() for c in cells]
                break

    # Parse data rows
    for row in table.rows:
        cells = [c.text().strip() for c in row.cells]
        non_empty = [c for c in cells if c and c != '$']
        if not non_empty:
            continue

        # Skip header-like rows
        first_lower = non_empty[0].lower()
        if any(kw in first_lower for kw in ('name', 'selling stockholder', 'selling shareholder',
                                             'beneficial owner')):
            if len(non_empty) > 1 and any(kw in non_empty[1].lower() for kw in
                                          ('shares', 'before', 'number')):
                continue

        # Skip footnote rows
        if first_lower.startswith('(') and len(first_lower) < 5:
            continue

        # Extract name (first non-numeric, non-$ cell)
        name = ''
        numeric_vals = []
        pct_vals = []
        for c in row.cells:
            t = c.text().strip()
            if not t or t == '$':
                continue
            if c.is_numeric:
                numeric_vals.append(t)
            elif '%' in t or re.match(r'^[\d.]+\s*%$', t):
                pct_vals.append(t)
            elif not name:
                name = t

        if not name or name.lower() in ('total', 'subtotal', ''):
            if name.lower() == 'total' and numeric_vals:
                total_offered = numeric_vals[0]
            continue

        # Skip long text (footnotes/disclaimers)
        if len(name) > 120:
            continue

        entry = SellingStockholderEntry(name=name)
        # Map numeric values positionally: before, offered, after
        if len(numeric_vals) >= 3:
            entry.shares_before_offering = numeric_vals[0]
            entry.shares_offered = numeric_vals[1]
            entry.shares_after_offering = numeric_vals[2]
        elif len(numeric_vals) == 2:
            entry.shares_before_offering = numeric_vals[0]
            entry.shares_offered = numeric_vals[1]
        elif len(numeric_vals) == 1:
            entry.shares_offered = numeric_vals[0]

        if len(pct_vals) >= 2:
            entry.pct_before_offering = pct_vals[0]
            entry.pct_after_offering = pct_vals[1]
        elif len(pct_vals) == 1:
            entry.pct_before_offering = pct_vals[0]

        entries.append(entry)

    return SellingStockholdersData(
        stockholders=entries,
        total_shares_offered=total_offered,
    )


def extract_structured_note_terms(table: 'TableNode'):
    """
    Extract key terms from a structured note key_terms table.

    These are 2-column key-value tables with terms like:
    Issuer | Bank of America Corporation
    CUSIP | 06055HBV7
    Maturity Date | January 20, 2028
    """
    from edgar.offerings.prospectus import StructuredNoteTerms

    fields: dict = {}
    additional: dict = {}

    for row in table.rows:
        cells = [c.text().strip() for c in row.cells if c.text().strip()]
        if len(cells) < 2:
            continue

        key = cells[0].rstrip(':').strip()
        value = cells[-1].strip()
        key_lower = key.lower()

        if not value or value == key:
            continue

        if 'issuer' in key_lower and 'co-issuer' not in key_lower:
            fields['issuer'] = value
        elif 'guarantor' in key_lower:
            fields['guarantor'] = value
        elif 'cusip' in key_lower:
            fields['cusip'] = value
        elif 'pricing date' in key_lower:
            fields['pricing_date'] = value
        elif 'issue date' in key_lower or 'settlement date' in key_lower:
            fields['issue_date'] = value
        elif 'maturity date' in key_lower or 'final valuation' in key_lower:
            fields['maturity_date'] = value
        elif 'underlying' in key_lower or 'reference asset' in key_lower:
            fields['underlying'] = value
        elif 'denomination' in key_lower:
            fields['denominations'] = value
        elif key_lower in ('term', 'term:'):
            fields['term'] = value
        elif 'principal amount' in key_lower or 'aggregate' in key_lower:
            fields['principal_amount'] = value
        elif 'upside participation' in key_lower:
            fields['upside_participation_rate'] = value
        elif 'max' in key_lower and 'return' in key_lower:
            fields['max_return'] = value
        elif 'threshold' in key_lower:
            fields['threshold_value'] = value
        elif 'buffer' in key_lower:
            fields['buffer_amount'] = value
        elif 'coupon' in key_lower and 'rate' in key_lower:
            fields['coupon_rate'] = value
        elif 'coupon' in key_lower and 'frequency' in key_lower:
            fields['coupon_frequency'] = value
        else:
            additional[key] = value

    return StructuredNoteTerms(**fields, additional_terms=additional)


# ---------------------------------------------------------------------------
# Underwriter table extraction
# ---------------------------------------------------------------------------

# Bank name patterns for recognizing underwriter/agent names in tables
_BANK_PATTERNS = [
    r'\bj\.?\s*p\.?\s*morgan\b', r'\bjpmorgan\b',
    r'\bmorgan stanley\b', r'\bgoldman sachs\b',
    r'\bbofa securities\b', r'\bmerrill lynch\b', r'\bbank of america\b',
    r'\bcitigroup\b', r'\bcitibank\b', r'\bciti(?:group)?\s*global\b',
    r'\bbarclays\b', r'\bwells fargo\b', r'\bdeutsche bank\b',
    r'\bubs\s+(?:securities|investment)\b', r'\brbc\s+capital\b',
    r'\bbnp\s+paribas\b',
    r'\bpiper\s+sandler\b', r'\bjefferies\b', r'\bstifel\b',
    r'\bwilliam\s+blair\b', r'\bneedham\b', r'\bcanaccord\b',
    r'\bleerink\b', r'\bevercore\b', r'\bmizuho\b',
    r'\btd\s+(?:securities|cowen|global)\b', r'\btruist\b', r'\bsmbc\b',
    r'\bbmo\s+capital\b', r'\bmufg\b', r'\bguggenheim\b',
    r'\braymond\s+james\b', r'\boppenheimer\b', r'\bnomura\b',
    r'\bscotiabank\b', r'\bscotia\s+capital\b', r'\bloop\s+capital\b',
    r'\bladenburg\b', r'\bwainwright\b', r'\bh\.c\.\s+wainwright\b',
    r'\ba\.g\.p\.\b', r'\baegis\b', r'\both\s+capital\b',
    r'\bboustead\b', r'\bef\s+hutton\b', r'\btungsten\b',
    r'\bascendiant\b', r'\bthinkequity\b', r'\bcraig.hallum\b', r'\bbtig\b',
    r'\bu\.s\.\s+bancorp\b', r'\bcredit\s+agricole\b', r'\blloyds\b',
    r'\bnatwest\b', r'\bpnc\s+capital\b', r'\bregions\s+securities\b',
    r'\bcitizens\b', r'\bfifth\s+third\b',
    r'\bblackstone\s+(?:capital|securities)\b', r'\brothschild\b',
    r'\bcibc\b', r'\bkeybanc\b', r'\bsantander\b',
    r'\bsociete\s+generale\b', r'\bmacquarie\b',
    r'\bbny\s+(?:mellon|capital)\b', r'\bbank\s+of\s+montreal\b',
]


def _count_bank_hits(text: str) -> int:
    """Count how many distinct bank name patterns match in text."""
    return sum(1 for p in _BANK_PATTERNS if re.search(p, text, re.IGNORECASE))


def _clean_underwriter_name(name: str) -> str:
    """Clean extracted underwriter name."""
    name = re.sub(r'\n', ' ', name)
    for suffix in [r'\s+structuring\s+advisor', r'\s+lead\s+manager',
                   r'\s+joint\s+book', r'\s+co-?manager', r'\s+\([^)]*\)']:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip()


def extract_underwriting_from_tables(document) -> list:
    """
    Find underwriter/agent info from tables in a parsed Document.

    Uses three table patterns:
    - cover_grid: bank names as header cells (large-cap cover page layout)
    - allocation: 'Underwriter' header + bank names in rows
    - role_listing: first row is role label, second row is bank names

    Returns list of dicts with keys: type, names, role_label
    """
    ROLE_KEYWORDS = [
        'joint book', 'book-running', 'sole book', 'co-manager',
        'senior co-manager', 'lead manager', 'underwriter',
        'placement agent', 'sales agent', 'financial advisor',
        'structuring advisor', 'co-lead'
    ]
    results = []

    for i, table in enumerate(document.tables):
        headers_list = [c.text().strip() for h in table.headers for c in h if c.text().strip()]
        header_text = ' '.join(headers_list).lower()
        rows = _get_row_texts(table)
        row_cells = _get_table_cells(table)
        row_text = ' '.join(row_cells).lower()

        bank_hits_headers = _count_bank_hits(header_text)
        bank_hits_rows = _count_bank_hits(row_text)

        # Pattern A: Cover page grid — bank names as header cells
        is_cover_grid = bank_hits_headers >= 2 and len(table.rows) <= 2

        # Pattern B: Allocation table — 'Underwriter' in headers/first row + banks in rows
        has_underwriter_header = any(
            h.lower() in ('underwriter', 'underwriters')
            or 'number of shares' in h.lower()
            or 'principal amount' in h.lower()
            for h in headers_list
        )
        first_data_row = next((r for r in rows if r), None)
        has_row_based_header = False
        if first_data_row:
            first_row_text = ' '.join(first_data_row).lower()
            if 'underwriter' in first_row_text or 'number of shares' in first_row_text \
                    or 'principal amount' in first_row_text:
                has_row_based_header = True

        is_allocation = (
            (has_underwriter_header or has_row_based_header)
            and bank_hits_rows >= 1
            and len(table.rows) >= 2
        )

        # Pattern C: Role-label listing — role in row[0], banks in row[1]
        is_role_listing = False
        role_label = None
        if rows and len(rows) >= 2:
            first_row_text = ' '.join(rows[0]).lower()
            for kw in ROLE_KEYWORDS:
                if kw in first_row_text:
                    second_row = rows[1] if len(rows) > 1 else []
                    if _count_bank_hits(' '.join(second_row).lower()) >= 1:
                        is_role_listing = True
                        role_label = rows[0][0] if rows[0] else first_row_text
                        break

        if not (is_cover_grid or is_allocation or is_role_listing):
            continue

        table_type = (
            'cover_grid' if is_cover_grid else
            'role_listing' if is_role_listing else
            'allocation'
        )

        names = []
        allocations = []
        if is_cover_grid:
            names = [c for c in headers_list if _count_bank_hits(c.lower()) >= 1]
        elif is_allocation:
            start_row = 1 if has_row_based_header else 0
            for row in rows[start_row:]:
                if row and row[0]:
                    cell_lower = row[0].lower()
                    if cell_lower not in ('total', 'subtotal', '') and _count_bank_hits(cell_lower) >= 1:
                        clean = _clean_underwriter_name(row[0])
                        names.append(clean)
                        # Allocation amount is the last cell if numeric-looking
                        if len(row) >= 2 and re.match(r'[\d,.$]+', row[-1]):
                            allocations.append(row[-1])
                        else:
                            allocations.append(None)
        elif is_role_listing:
            if len(rows) > 1:
                for raw_name in rows[1]:
                    names.append(_clean_underwriter_name(raw_name))

        results.append({
            'table_index': i,
            'type': table_type,
            'names': names[:30],
            'allocations': allocations[:30],
            'role_label': role_label,
        })

    return results
