"""
Low-level parsing for registration fee tables.

Pure HTML/text/number parsing: turns an EX-FILING FEES exhibit (or a pre-EX-107
inline "Calculation of Registration Fee" table) into plain dicts. No filing I/O
and no dependency on the offering data models — the orchestration in
``extract`` builds ``RegistrationFeeTable`` objects from these dicts.
"""

from __future__ import annotations

import re
from typing import List, Optional


# A single numeric token: the first run of digits (with thousands commas and an
# optional decimal). Matching only the first token stops trailing footnote
# markers from being concatenated into the number — '$1 (1)(2)(3)(4)' must parse
# to 1.0, not 11234, and '$761.12 (3)' to 761.12, not 761123.
# The leading-decimal alternative ('.0000927') matters for the fee-rate cell,
# which filers write with no integer part ('$.0000927'); without it the leading
# '.' is skipped and '0000927' parses to 927.0 instead of 0.0000927.
_NUMERIC_TOKEN_RE = re.compile(r'\d[\d,]*(?:\.\d+)?|\.\d+')


def _parse_dollar_amount(text: str) -> Optional[float]:
    """Parse a dollar string like '$12,119.07' or '300,000,000' to float.

    Reads only the first numeric token so footnote markers appended to a value
    ('$1 (1)(2)(3)(4)', '$761.12 (3)') don't get fused into the digits.
    """
    if not text:
        return None
    m = _NUMERIC_TOKEN_RE.search(text)
    if not m:
        return None
    cleaned = m.group(0).replace(',', '')
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# Filers write the fee rate two ways: a raw per-dollar decimal ('0.00015310' /
# '$.0000927'), or an amount on a per-million basis ('$153.10 per $1,000,000').
# The second form is the SEC EX-107 template's own wording; _parse_dollar_amount
# reads only the leading token (153.10) and drops the basis, so the rate comes
# out 1,000,000x too large. Normalise it back to a per-dollar decimal.
_FEE_RATE_BASIS_RE = re.compile(r'per\s*\$?\s*([\d,]+)', re.IGNORECASE)


def _parse_fee_rate(text: str) -> Optional[float]:
    """Parse a fee-rate cell to a per-dollar decimal.

    '0.00015310'             -> 0.00015310   (raw per-dollar decimal)
    '$.0000927'              -> 0.0000927    (leading-decimal, no integer part)
    '$153.10 per $1,000,000' -> 0.00015310   (amount per $1,000,000 basis)
    """
    amount = _parse_dollar_amount(text)
    if amount is None:
        return None
    m = _FEE_RATE_BASIS_RE.search(text)
    if m:
        basis = float(m.group(1).replace(',', ''))
        if basis > 0:
            return amount / basis
    return amount


# The SEC registration fee rate is a uniquely tiny decimal (~0.0001 per dollar;
# it has ranged roughly 0.00005–0.00016 across fiscal years), distinct from
# prices, aggregates and share counts. Anchoring on it lets us recover the
# trailing [Maximum Aggregate, Fee Rate, Amount of Registration Fee] columns even
# when split footnote markers shift cells positionally.
_FEE_RATE_MIN = 1e-6
_FEE_RATE_MAX = 1e-3


def _refine_fee_columns(security: dict, texts: List[str]) -> None:
    """Re-derive max_aggregate / fee_rate / fee_amount by anchoring on the fee rate.

    The EX-107 fee table always ends with the column triple
    [Maximum Aggregate Offering Price, Fee Rate, Amount of Registration Fee].
    Positional parsing breaks when a footnote like ``(3)`` splits into two cells
    (``'(3'``, ``')'``) and shifts every later column right — the offering amount
    then lands in the fee column (333-275559). The fee rate is uniquely tiny, and
    the identity ``fee = aggregate x rate`` is self-validating, so we scan for a
    rate-band cell whose immediate numeric neighbours satisfy that identity and
    trust those over the positional guess. No-op when no such triple exists
    (carry-forward / deferred rows have no fee rate), so clean rows are unchanged.
    """
    # Neighbours (aggregate, fee) are plain dollar amounts; the rate candidate is
    # parsed with _parse_fee_rate so a 'per $1,000,000' cell (153.10 -> 0.0001531)
    # lands in the rate band and can still anchor a column-shift recovery.
    parsed = [_parse_dollar_amount(t) for t in texts]
    rates = [_parse_fee_rate(t) for t in texts]
    for i, rate in enumerate(rates):
        if rate is None or not (_FEE_RATE_MIN < rate < _FEE_RATE_MAX):
            continue
        agg = next((parsed[j] for j in range(i - 1, -1, -1)
                    if parsed[j] is not None and parsed[j] > 0), None)
        fee = next((parsed[j] for j in range(i + 1, len(parsed))
                    if parsed[j] is not None and parsed[j] > 0), None)
        if agg is None or fee is None:
            continue
        expected = agg * rate
        if expected > 0 and abs(expected - fee) <= max(0.02 * fee, 1.0):
            security['max_aggregate_amount'] = agg
            security['fee_rate'] = rate
            security['fee_amount'] = fee
            return


def _join_dollar_cells(texts: List[str]) -> List[str]:
    """Join adjacent '$' cells with the following numeric cell.

    Some filers split dollar values across two <TD> cells:
      ['$', '300,000,000'] -> ['$300,000,000']
    """
    result = []
    i = 0
    while i < len(texts):
        t = texts[i].strip()
        if t == '$' and i + 1 < len(texts):
            result.append('$' + texts[i + 1].strip())
            i += 2
        else:
            result.append(t)
            i += 1
    return result


def _extract_dollar_values(texts: List[str]) -> List[float]:
    """Extract all parseable dollar amounts from a list of cell texts."""
    values = []
    for t in texts:
        if re.search(r'[\d]', t):
            v = _parse_dollar_amount(t)
            if v is not None:
                values.append(v)
    return values


def _is_placeholder(text: str) -> bool:
    """Check if a cell contains a placeholder like '—', '(1)', '-', etc."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in ('—', '–', '-', 'N/A', 'n/a', '(*)'):
        return True
    if re.match(r'^\(\d+\)$', stripped):
        return True
    return False


def _table_text(table) -> str:
    """Lowercased, whitespace-normalized text of a table for header matching.

    Uses an explicit separator so header words split across inline tags
    (``<font>Security</font><font>Type</font>``) and non-breaking spaces don't
    collapse into ``securitytype`` and defeat substring matching.
    """
    return re.sub(r'\s+', ' ', table.get_text(separator=' ').replace('\xa0', ' ')).strip().lower()


def _find_fee_table(soup) -> Optional:
    """Find the main fee data table in the exhibit HTML."""
    for table in soup.find_all('table'):
        header_text = _table_text(table)
        if ('security type' in header_text or 'security class' in header_text
                or 'class of securities' in header_text):
            return table
    # Fallback: find table with 'registration fee' in header (legacy format)
    for table in soup.find_all('table'):
        header_text = _table_text(table)
        if 'registration fee' in header_text and ('amount' in header_text or 'aggregate' in header_text):
            return table
    return None


def _parse_fee_table_html(html: str, exhibit_url: Optional[str] = None) -> dict:
    """Parse an EX-FILING FEES HTML exhibit into structured data.

    Returns a dict with keys matching RegistrationFeeTable fields.
    """
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, 'lxml')
    fee_table = _find_fee_table(soup)

    result = {
        'total_offering_amount': None,
        'net_fee_due': None,
        'total_fees_previously_paid': None,
        'securities': [],
        'carry_forwards': [],
        'has_carry_forward': False,
        'fee_deferred': False,
        'exhibit_url': exhibit_url,
    }

    if fee_table is None:
        return result

    in_carry_forward = False

    for row in fee_table.find_all('tr'):
        cells = row.find_all(['td', 'th'])
        # Extract text from each cell, normalizing whitespace
        raw_texts = [re.sub(r'\s+', ' ', c.get_text(separator=' ', strip=True)) for c in cells]
        # Filter out whitespace-only cells but preserve order
        texts = [t for t in raw_texts if t.strip()]

        if not texts:
            continue

        # Join adjacent dollar-sign cells
        texts = _join_dollar_cells(texts)

        first = texts[0].lower().strip()

        # --- Section headers ---
        if 'newly registered' in first and len(texts) <= 2:
            in_carry_forward = False
            continue
        if 'carry forward securities' in first and len(texts) <= 2:
            in_carry_forward = True
            continue

        # --- Summary rows ---
        if 'total offering' in first:
            vals = _extract_dollar_values(texts[1:])
            if vals:
                result['total_offering_amount'] = vals[0]
            continue

        if 'net fee due' in first:
            vals = _extract_dollar_values(texts[1:])
            if vals:
                result['net_fee_due'] = vals[0]
            continue

        if 'total fees previously paid' in first or 'total fee' in first and 'previously' in first:
            vals = _extract_dollar_values(texts[1:])
            if vals:
                result['total_fees_previously_paid'] = vals[0]
            continue

        if 'total fee offset' in first:
            continue

        # --- Data rows ---
        if 'fees to be paid' in first or 'fees previously paid' in first:
            security = _parse_security_row(texts)
            if security and _has_data(security):
                result['securities'].append(security)
            continue

        if in_carry_forward and ('carry forward' in first or 'carry-forward' in first):
            cf = _parse_security_row(texts)
            if cf and _has_data(cf):
                result['carry_forwards'].append(cf)
            continue

        # 2022 format: data rows start directly with security type (no row category)
        _SECURITY_TYPES = ('equity', 'debt', 'other', 'unallocated')
        if first in _SECURITY_TYPES or first.startswith('unallocated'):
            security = _parse_security_row_no_category(texts)
            if security and _has_data(security):
                result['securities'].append(security)
            continue

    # Set has_carry_forward only if actual carry-forward data was found
    result['has_carry_forward'] = len(result['carry_forwards']) > 0

    # The "Total Offering Amounts" summary cell is the sum of the per-security
    # Maximum Aggregate Offering Price of the newly-registered rows. When the
    # summary is missing, or implausibly small relative to that sum, it has been
    # corrupted — it carried the fee instead of the amount (the 2022 format),
    # or a typo / split footnote mangled the digits ('$761,12' -> 76112,
    # '$1 (1)(2)(3)(4)' -> 1.0). The per-security aggregate is authoritative.
    aggregate_from_securities = sum(
        s.get('max_aggregate_amount') or 0
        for s in result['securities']
    )
    if aggregate_from_securities > 0:
        total = result['total_offering_amount']
        # A universal shelf may repeat the same capped aggregate on several
        # security lines while the "Total Offering Amounts" correctly reports the
        # single cap — there the summary equals the largest line and must be kept,
        # not inflated into the (double-counted) sum. Only override when the
        # summary is implausibly small relative to BOTH the sum and the largest
        # single line, i.e. it carried the fee / a corrupted figure.
        max_single = max((s.get('max_aggregate_amount') or 0)
                         for s in result['securities'])
        if total is None or (total < aggregate_from_securities * 0.5
                             and total < max_single * 0.99):
            result['total_offering_amount'] = aggregate_from_securities
    elif (result['carry_forwards']
          and (result['net_fee_due'] in (None, 0.0))
          and (result['total_offering_amount'] or 0) < 1000):
        # A carry-forward-only registration (Rule 415(a)(6)) with no newly-paid
        # fee registers an indeterminate amount carried from a prior statement;
        # the summary cell is a nominal placeholder ('$1') not real new capacity
        # (333-272539). Report None rather than a misleading token figure.
        result['total_offering_amount'] = None

    # Detect deferred fees (S-3ASR with Rule 457(r)). Consider only rows that
    # actually carry a fee rule — issuer sub-header rows ("Fees to Be Paid |
    # Welltower Inc.") have none and would otherwise defeat the all() check.
    rules_with_content = [r for s in result['securities']
                          if (r := s.get('fee_rule'))]
    if rules_with_content and all('457(r)' in r for r in rules_with_content):
        result['fee_deferred'] = True

    if result['net_fee_due'] is not None and result['net_fee_due'] == 0.0 and not result['total_offering_amount']:
        result['fee_deferred'] = True

    # An automatic shelf with deferred (pay-as-you-go) fees registers an
    # indeterminate amount; a parsed 0.0 is a placeholder, not real capacity.
    if result['fee_deferred'] and result['total_offering_amount'] == 0.0:
        result['total_offering_amount'] = None

    return result


def _parse_security_row_no_category(texts: List[str]) -> Optional[dict]:
    """Parse a security row that has no row category column (2022 format).

    Expected: [security_type, security_title, rule, amount, price, aggregate, rate, fee]
    """
    if len(texts) < 2:
        return None

    security = {
        'security_type': None,
        'security_title': None,
        'fee_rule': None,
        'amount_registered': None,
        'price_per_unit': None,
        'max_aggregate_amount': None,
        'fee_rate': None,
        'fee_amount': None,
    }

    data = texts  # No category to skip

    if len(data) >= 1 and not _is_placeholder(data[0]):
        security['security_type'] = data[0]
    if len(data) >= 2 and not _is_placeholder(data[1]):
        security['security_title'] = data[1]
    if len(data) >= 3 and not _is_placeholder(data[2]):
        security['fee_rule'] = data[2]
    if len(data) >= 4 and not _is_placeholder(data[3]):
        security['amount_registered'] = data[3]
    if len(data) >= 5 and not _is_placeholder(data[4]):
        security['price_per_unit'] = _parse_dollar_amount(data[4])
    if len(data) >= 6 and not _is_placeholder(data[5]):
        security['max_aggregate_amount'] = _parse_dollar_amount(data[5])
    if len(data) >= 7 and not _is_placeholder(data[6]):
        security['fee_rate'] = _parse_fee_rate(data[6])
    if len(data) >= 8 and not _is_placeholder(data[7]):
        security['fee_amount'] = _parse_dollar_amount(data[7])

    _refine_fee_columns(security, texts)
    return security


def _has_data(row: dict) -> bool:
    """Check if a parsed security row has any meaningful data (not all None/empty)."""
    data_fields = ['security_type', 'security_title', 'fee_rule',
                   'max_aggregate_amount', 'fee_amount', 'price_per_unit']
    return any(row.get(f) is not None for f in data_fields)


def _parse_security_row(texts: List[str]) -> Optional[dict]:
    """Parse a security data row into a dict.

    Expected column order (may have fewer columns):
    [row_category, security_type, security_title, rule, amount_registered,
     price_per_unit, max_aggregate, fee_rate, fee_amount, ...]
    """
    if len(texts) < 2:
        return None

    security = {
        'security_type': None,
        'security_title': None,
        'fee_rule': None,
        'amount_registered': None,
        'price_per_unit': None,
        'max_aggregate_amount': None,
        'fee_rate': None,
        'fee_amount': None,
    }

    # Skip the row category (first cell like "Fees to be Paid")
    data = texts[1:]

    if len(data) >= 1 and not _is_placeholder(data[0]):
        security['security_type'] = data[0]
    if len(data) >= 2 and not _is_placeholder(data[1]):
        security['security_title'] = data[1]
    if len(data) >= 3 and not _is_placeholder(data[2]):
        security['fee_rule'] = data[2]
    if len(data) >= 4 and not _is_placeholder(data[3]):
        security['amount_registered'] = data[3]
    if len(data) >= 5 and not _is_placeholder(data[4]):
        security['price_per_unit'] = _parse_dollar_amount(data[4])
    if len(data) >= 6 and not _is_placeholder(data[5]):
        security['max_aggregate_amount'] = _parse_dollar_amount(data[5])
    if len(data) >= 7 and not _is_placeholder(data[6]):
        security['fee_rate'] = _parse_fee_rate(data[6])
    if len(data) >= 8 and not _is_placeholder(data[7]):
        security['fee_amount'] = _parse_dollar_amount(data[7])

    _refine_fee_columns(security, texts)
    return security


# Pre-EX-107 inline fee tables
# ---------------------------------------------------------------------------
# A "clean" dollar amount cell: only "$", digits, commas and an optional
# decimal (after _join_dollar_cells merges a lone "$" with its number). This
# deliberately rejects prose cells like "par value $0.001 per share" so an
# embedded par value can never be mistaken for an offering amount.
_DOLLAR_RE = re.compile(r'^\$\s*[\d,]+(?:\.\d+)?$')
_DEFERRAL_MARKERS = ('457(r)', 'pay-as-you-go', 'pay as you go')


def _parse_inline_fee_table(html: str, form: Optional[str] = None) -> dict:
    """Parse a pre-EX-107 inline "Calculation of Registration Fee" table.

    Before the Filing Fee Exhibit (Exhibit 107) regime (~2022), registration
    statements carried the fee table inline in the document body, in column
    layouts that predate the structured exhibit. The registered capacity is the
    "Proposed maximum aggregate offering price" — reliably the largest clean
    dollar amount in the table: the fee is that figure x ~0.0001, the per-unit
    price is smaller, and share counts are unpriced (no "$"). A table with no
    dollar amount at all is an indeterminate pay-as-you-go (Rule 457(r)) shelf,
    the inline equivalent of a deferred ASR.

    Returns a dict with the same keys as _parse_fee_table_html. Limitation: a
    multi-class table with no "Total" row reports the largest single row, not
    the sum — such tables almost always carry an explicit Total.
    """
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

    result = {
        'total_offering_amount': None,
        'net_fee_due': None,
        'total_fees_previously_paid': None,
        'securities': [],
        'carry_forwards': [],
        'has_carry_forward': False,
        'fee_deferred': False,
        'exhibit_url': None,
    }

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, 'lxml')
    table = _find_fee_table(soup)
    if table is None:
        return result

    dollar_values = []
    for row in table.find_all('tr'):
        raw = [re.sub(r'\s+', ' ', c.get_text(' ', strip=True)) for c in row.find_all(['td', 'th'])]
        cells = _join_dollar_cells([t for t in raw if t.strip()])
        for c in cells:
            if _DOLLAR_RE.match(c.strip()):
                v = _parse_dollar_amount(c)
                if v and v > 0:
                    dollar_values.append(v)

    if dollar_values:
        agg = max(dollar_values)
        if 0 < agg < 1e12:  # > $1T registered capacity is implausible
            result['total_offering_amount'] = agg
    else:
        # No concrete amount anywhere — an indeterminate Rule 457(r) shelf.
        base = (form or '').replace('/A', '')
        doc_text = re.sub(r'\s+', ' ', soup.get_text(' ')).lower()
        if base.endswith('ASR') or any(m in doc_text for m in _DEFERRAL_MARKERS):
            result['fee_deferred'] = True

    return result
