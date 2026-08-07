"""Semantic table-type classification for 424B filings.

Predicates that label a ``TableNode`` (pricing, dilution, capitalization,
selling-stockholders, underwriting syndicate, etc.) plus the ``classify_table``
dispatcher and the document-level sweep ``classify_tables_in_document``.

See table-classification research for validation results and edge cases.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from edgar.offerings.prospectus._424b_tables.helpers import (
    _get_table_cells,
    _get_full_text,
    _get_row_texts,
    _fraction_long_cells,
    _has_numeric_cells,
)

if TYPE_CHECKING:
    from edgar.documents.table_nodes import TableNode


# Matches SEC page numbers: plain digits (1-999), roman numerals, or
# supplement-prefixed variants like "S-9", "S- ii" (with optional space).
_PAGE_NUMBER_RE = re.compile(
    r'^(S-\s*[ivxlIVXL]+|S-\s*\d+|[ivxlIVXL]+|\d{1,3})$', re.IGNORECASE
)


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
        if _PAGE_NUMBER_RE.match(v):
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
    page_matches = 0
    valid_rows = 0
    for row in rows:
        if len(row) >= 2:
            valid_rows += 1
            if _PAGE_NUMBER_RE.match(row[-1].strip()):
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
                    'subscription price' in text or 'price to public' in text)
    has_proceeds = 'proceeds' in text
    has_fee = ('discount' in text or 'commission' in text or
               'placement agent' in text or 'placement agents' in text or
               "agent's fee" in text or "agent fees" in text or
               'underwriting' in text or 'sales load' in text)
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
    has_shares_offered = 'shares offered' in text or 'shares to be offered' in text
    has_numeric = _has_numeric_cells(table)
    if has_selling_kw and has_numeric and len(table.rows) >= 3:
        return True
    if has_before_after and has_name and has_numeric:
        return True
    if has_before_after and has_shares_offered and has_numeric:
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
    core_keywords = ['cusip', 'maturity date', 'stated maturity', 'underlying',
                     'market measure', 'pricing date',
                     'issue date', 'valuation date', 'denominations',
                     'upside participation', 'max return', 'threshold value']
    supporting_keywords = ['issuer', 'guarantor', 'notes offered', 'term:',
                           'redemption amount', 'indenture', 'calculation agent',
                           'selling agent', 'face amount', 'original offering price']
    core_matches = sum(1 for kw in core_keywords if kw in text)
    supp_matches = sum(1 for kw in supporting_keywords if kw in text)
    # Use median non-empty column count — a few pricing rows at the bottom
    # shouldn't disqualify a 20-row key-value table, and layout tables may
    # pad with many empty cells.
    ne_counts = sorted(
        sum(1 for c in r.cells if c.text().strip()) for r in table.rows
    )
    ncols_median = ne_counts[len(ne_counts) // 2] if ne_counts else 0
    if ncols_median <= 3 and (core_matches >= 2 or (core_matches >= 1 and supp_matches >= 3)):
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
        r'\bmerrill lynch\b', r'\bbarclays\b', r'\bcitigroup\b', r'\bcitibank\b',
        r'\bwells fargo\b', r'\bbofa securities\b',
        r'\bcredit suisse\b', r'\bdeutsche bank\b', r'\bubs\b',
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
    # key_terms checked early — bulleted or wide-layout key-value tables
    # would otherwise be swallowed by _is_layout_table
    if _is_key_terms(table):
        return 'key_terms'
    if _is_layout_table(table):
        return 'layout'
    if _is_toc_table(table):
        return 'toc'
    if _is_pricing_table(table):
        return 'pricing_table'
    if _is_selling_stockholders(table):
        return 'selling_stockholders'
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
