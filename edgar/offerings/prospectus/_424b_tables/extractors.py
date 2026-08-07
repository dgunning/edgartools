"""Structured-data extraction from classified 424B tables.

Each ``extract_*`` reads an already-classified ``TableNode`` into the matching
pydantic model from ``edgar.offerings.prospectus`` (pricing, offering terms,
dilution, capitalization, selling stockholders, structured-note terms). The
prospectus models are imported lazily inside each function to avoid an import
cycle with the prospectus package.
"""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

from edgar.offerings.prospectus._424b_tables.helpers import (
    _WS_RE,
    _get_all_cells_including_headers,
    _extract_row_label_and_values,
    _prefix_dollar,
)

if TYPE_CHECKING:
    from edgar.documents.table_nodes import TableNode


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

    # Fallback: column-header-based layout (headers are "Price to Public", "Discount", "Proceeds")
    # Used by SPAC 424B4 and some structured note filings where row labels are "Per Unit"/"Total"
    if num_cols == 0 and raw_rows:
        col_headers = []
        for c in _get_all_cells_including_headers(table):
            cn = _WS_RE.sub(' ',c).strip().lower()
            if cn:
                col_headers.append(cn)
        # Map header labels to column indices
        price_idx = fee_idx = proceeds_idx = None
        for idx, h in enumerate(col_headers):
            if 'offering price' in h or 'price to public' in h:
                price_idx = idx
            elif any(kw in h for kw in ('discount', 'commission', 'sales load',
                                         'placement agent', "agent's fee")):
                fee_idx = idx
            elif 'proceeds' in h:
                proceeds_idx = idx
        if price_idx is not None or proceeds_idx is not None:
            # Determine column order from header positions
            detected = []
            if price_idx is not None:
                detected.append((price_idx, 'price'))
            if fee_idx is not None:
                detected.append((fee_idx, 'fee'))
            if proceeds_idx is not None:
                detected.append((proceeds_idx, 'proceeds'))
            detected.sort()
            field_order = [f for _, f in detected]  # e.g. ['price', 'fee', 'proceeds']

            columns = []
            for raw in raw_rows:
                label = _WS_RE.sub(' ', raw[0]).strip() if raw else ''
                vals = raw[1:] if len(raw) > 1 else []
                # Filter to numeric-looking values (skip footnote refs like "(1)")
                num_vals = [v for v in vals if re.search(r'\d', v) and not re.fullmatch(r'\(\d+\)', v)]
                if not num_vals:
                    continue
                # Map values to fields by detected column order
                fields: dict[str, str | None] = {}
                for i, fname in enumerate(field_order):
                    fields[fname] = _prefix_dollar(num_vals[i]) if i < len(num_vals) else None
                columns.append(PricingColumnData(
                    column_label=label,
                    offering_price=fields.get('price'),
                    fee_or_discount=fields.get('fee'),
                    proceeds=fields.get('proceeds'),
                ))
            if columns:
                fee_type = 'underwriting_discount' if fee_idx is not None else None
                return PricingData(
                    columns=columns,
                    fee_type=fee_type,
                    raw_rows=raw_rows,
                )

    if num_cols == 0:
        return PricingData(raw_rows=raw_rows)

    columns = []
    for i in range(num_cols):
        col_label = header_labels[i] if i < len(header_labels) else None
        columns.append(PricingColumnData(
            column_label=col_label,
            offering_price=_prefix_dollar(offering_price_vals[i]) if i < len(offering_price_vals) else None,
            fee_or_discount=_prefix_dollar(fee_vals[i]) if i < len(fee_vals) else None,
            proceeds=_prefix_dollar(proceeds_vals[i]) if i < len(proceeds_vals) else None,
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
            additional['Subscription Price'] = value
        elif 'subscription rights' in key:
            additional['Subscription Rights'] = value
        elif 'record date' in key:
            additional['Record Date'] = value
        elif 'over-subscription' in key or 'over subscription' in key:
            additional['Over-Subscription Privilege'] = value
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

        # Format with $ (negatives in parens are left as-is). _prefix_dollar is a
        # no-op when the cell already carries its own '$' — a value cell rendered
        # as '$5.10' (rather than a separate '$' spacer cell) must not become
        # '$$5.10'.
        formatted = val if val.startswith('(') else _prefix_dollar(val)

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


def _build_column_map(header_cells: list) -> dict:
    """Map header text to semantic column roles.

    Returns a dict like {'before': 0, 'offered': 1, 'after': 2, 'warrant': 3}
    mapping role names to numeric-column indices (0-based among numeric columns).
    """
    col_map = {}
    numeric_idx = 0
    pct_idx = 0
    for h in header_cells:
        hl = h.lower()
        is_pct = 'percent' in hl or '%' in hl
        is_numeric_header = any(kw in hl for kw in (
            'shares', 'number', 'amount', 'beneficial', 'warrant',
            'issuable', 'exercise', 'conversion', 'percent', '%',
            'before', 'after', 'offered', 'registered',
        ))
        if not is_numeric_header:
            continue

        if is_pct:
            if 'after' in hl:
                col_map['pct_after'] = pct_idx
            elif any(kw in hl for kw in ('before', 'prior', 'owned')):
                col_map['pct_before'] = pct_idx
            pct_idx += 1
        else:
            if any(kw in hl for kw in ('warrant', 'issuable', 'exercise', 'conversion')):
                col_map['warrant'] = numeric_idx
            elif 'after' in hl:
                # Check 'after' before 'before' — headers like
                # "shares beneficially owned after offering" contain 'owned'
                # which would otherwise match the 'before' category
                col_map['after'] = numeric_idx
            elif any(kw in hl for kw in ('offered', 'registered', 'to be sold', 'being offered')):
                col_map['offered'] = numeric_idx
            elif any(kw in hl for kw in ('before', 'prior', 'owned', 'beneficial')):
                col_map['before'] = numeric_idx
            numeric_idx += 1

    return col_map


def _assign_entry_values(entry, numeric_vals, pct_vals, col_map):
    """Assign numeric/pct values to a SellingStockholderEntry using header mapping or positional fallback."""
    if col_map:
        # Header-aware mapping
        for role, idx in col_map.items():
            if role == 'before' and idx < len(numeric_vals):
                entry.shares_before_offering = numeric_vals[idx]
            elif role == 'offered' and idx < len(numeric_vals):
                entry.shares_offered = numeric_vals[idx]
            elif role == 'after' and idx < len(numeric_vals):
                entry.shares_after_offering = numeric_vals[idx]
            elif role == 'warrant' and idx < len(numeric_vals):
                entry.warrants_or_convertible = numeric_vals[idx]
            elif role == 'pct_before' and idx < len(pct_vals):
                entry.pct_before_offering = pct_vals[idx]
            elif role == 'pct_after' and idx < len(pct_vals):
                entry.pct_after_offering = pct_vals[idx]
    else:
        # Positional fallback: before, offered, after
        if len(numeric_vals) >= 3:
            entry.shares_before_offering = numeric_vals[0]
            entry.shares_offered = numeric_vals[1]
            entry.shares_after_offering = numeric_vals[2]
            if len(numeric_vals) >= 4:
                entry.warrants_or_convertible = numeric_vals[3]
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


def extract_selling_stockholders_data(table: 'TableNode'):
    """
    Extract selling stockholder entries from a selling_stockholders table.

    These tables list stockholders with shares before/after the offering.
    Uses header-aware column mapping when headers are available,
    with positional fallback for tables without clear headers.
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

    # Build semantic column map from headers
    col_map = _build_column_map(header_cells)

    # Parse data rows
    for row in table.rows:
        cells = [c.text().strip() for c in row.cells]
        non_empty = [c for c in cells if c and c != '$']
        if not non_empty:
            continue

        # Skip header-like rows
        first_lower = non_empty[0].lower()
        row_text = ' '.join(c.lower() for c in non_empty)
        _header_kws = ('name', 'selling stockholder', 'selling shareholder', 'selling security',
                        'beneficial owner', 'number of shares', 'shares beneficially',
                        'before offering', 'before the offering', 'after offering',
                        'after the offering', 'class a', 'class b', 'ordinary shares')
        if any(kw in first_lower for kw in _header_kws):
            if len(non_empty) > 1 and any(kw in row_text for kw in
                                          ('shares', 'before', 'number', 'percent', 'offered',
                                           'after', 'beneficial', 'class')):
                continue
            # Single-cell header (e.g. "Number of shares owned" spanning columns)
            if len(non_empty) == 1 and any(kw in first_lower for kw in
                                            ('shares', 'before', 'after', 'number', 'percent', 'beneficial')):
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
            # Check percentage before is_numeric — some parsers mark % cells as numeric
            if '%' in t or re.match(r'^[\d.]+\s*%$', t):
                pct_vals.append(t)
            elif c.is_numeric:
                # Skip dash placeholders (—, –, -, --) used as zero/null
                if t in ('—', '–', '-', '--', '*'):
                    continue
                numeric_vals.append(t)
            elif not name:
                name = t

        if not name or name.lower() in ('total', 'subtotal', ''):
            if name.lower() == 'total' and numeric_vals:
                total_offered = numeric_vals[0]
            continue

        # Skip header fragments that weren't caught above
        name_lower = name.lower().strip()
        if (name_lower.startswith('number') and not numeric_vals) or \
           name_lower in ('shares', 'percent', 'percentage'):
            continue

        # Skip long text (footnotes/disclaimers)
        if len(name) > 120:
            continue

        entry = SellingStockholderEntry(name=name)
        _assign_entry_values(entry, numeric_vals, pct_vals, col_map)
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

    _BULLETS = frozenset(('·', '•', '●', '-', '—', '■', '▪'))

    for row in table.rows:
        cells = [c.text().strip() for c in row.cells if c.text().strip()]
        # Skip leading bullet cells (e.g. ['•', 'Issue Date:', '$15M'])
        while cells and cells[0] in _BULLETS:
            cells = cells[1:]
        if len(cells) < 2:
            continue

        key = _WS_RE.sub(' ', cells[0]).rstrip(':').strip()
        value = cells[-1].strip()
        key_lower = key.lower().rstrip('*')

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
        elif 'maturity date' in key_lower or 'stated maturity' in key_lower or 'final valuation' in key_lower:
            fields['maturity_date'] = value
        elif 'underlying' in key_lower or 'reference asset' in key_lower or 'market measure' in key_lower:
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
