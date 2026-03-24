"""
Registration fee table extraction from EX-FILING FEES exhibits (Exhibit 107).

Parses the HTML fee table attached to registration statements (S-3, F-3, S-1, etc.)
to extract total offering capacity, per-security breakdowns, and fee calculations.

Works with both plain HTML and inline XBRL exhibits (2022-2025+).
Uses HTML table parsing as the universal approach.

See: docs-internal/research/sec-filings/forms/s-3/registration-fee-table-analysis.md
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['extract_registration_fee_table']

log = logging.getLogger(__name__)


def _get_filing_fees_attachment(filing: 'Filing'):
    """Find the EX-FILING FEES attachment, returns None if not present."""
    for att in filing.attachments:
        doc_type = getattr(att, 'document_type', None)
        if doc_type == 'EX-FILING FEES':
            return att
    return None


def _parse_dollar_amount(text: str) -> Optional[float]:
    """Parse a dollar string like '$12,119.07' or '300,000,000' to float."""
    if not text:
        return None
    cleaned = re.sub(r'[^\d.]', '', text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


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


def _find_fee_table(soup) -> Optional:
    """Find the main fee data table in the exhibit HTML."""
    for table in soup.find_all('table'):
        header_text = table.get_text().lower()
        if ('security type' in header_text or 'security class' in header_text
                or 'class of securities' in header_text):
            return table
    # Fallback: find table with 'registration fee' in header (legacy format)
    for table in soup.find_all('table'):
        header_text = table.get_text().lower()
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

    # If total_offering_amount was not found in summary rows, or if the summary
    # "Total Offering Amounts" row only had the fee (common in 2022 format),
    # compute from per-security max_aggregate_amount values.
    aggregate_from_securities = sum(
        s.get('max_aggregate_amount') or 0
        for s in result['securities']
    )
    if aggregate_from_securities > 0:
        if result['total_offering_amount'] is None:
            result['total_offering_amount'] = aggregate_from_securities
        elif (result['net_fee_due'] is not None
              and result['total_offering_amount'] == result['net_fee_due']
              and aggregate_from_securities > result['total_offering_amount']):
            # Summary row had only fee amount, not offering amount (2022 format)
            result['total_offering_amount'] = aggregate_from_securities

    # Detect deferred fees (S-3ASR with Rule 457(r))
    all_rules = [s.get('fee_rule', '') for s in result['securities']]
    if all_rules and all('457(r)' in (r or '') for r in all_rules):
        result['fee_deferred'] = True

    if result['net_fee_due'] is not None and result['net_fee_due'] == 0.0 and not result['total_offering_amount']:
        result['fee_deferred'] = True

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
        security['fee_rate'] = _parse_dollar_amount(data[6])
    if len(data) >= 8 and not _is_placeholder(data[7]):
        security['fee_amount'] = _parse_dollar_amount(data[7])

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
        security['fee_rate'] = _parse_dollar_amount(data[6])
    if len(data) >= 8 and not _is_placeholder(data[7]):
        security['fee_amount'] = _parse_dollar_amount(data[7])

    return security


def extract_registration_fee_table(filing: 'Filing'):
    """Extract the registration fee table from a filing's EX-FILING FEES exhibit.

    Works with any filing that has an EX-FILING FEES attachment:
    S-3, S-3ASR, F-3, S-1, S-4, and their amendments.

    Returns a RegistrationFeeTable or None if no exhibit found.

    Usage:
        from edgar import find
        filing = find(form="S-3", ticker="ADCT")
        fee_table = extract_registration_fee_table(filing)
        print(fee_table.total_offering_amount)  # e.g., 79157878.46
    """
    from edgar.offerings.prospectus import RegistrationFeeTable, FeeTableSecurity

    fee_att = _get_filing_fees_attachment(filing)
    if not fee_att:
        return None

    try:
        content = fee_att.download()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
    except Exception:
        log.debug("Failed to download fee exhibit for %s", filing.accession_no)
        return None

    exhibit_url = getattr(fee_att, 'url', None)
    data = _parse_fee_table_html(content, exhibit_url=exhibit_url)

    securities = []
    for row in data.get('securities', []):
        securities.append(FeeTableSecurity(
            security_type=row.get('security_type'),
            security_title=row.get('security_title'),
            fee_rule=row.get('fee_rule'),
            amount_registered=row.get('amount_registered'),
            price_per_unit=row.get('price_per_unit'),
            max_aggregate_amount=row.get('max_aggregate_amount'),
            fee_rate=row.get('fee_rate'),
            fee_amount=row.get('fee_amount'),
        ))

    carry_forwards = []
    for row in data.get('carry_forwards', []):
        carry_forwards.append(FeeTableSecurity(
            security_type=row.get('security_type'),
            security_title=row.get('security_title'),
            fee_rule=row.get('fee_rule'),
            amount_registered=row.get('amount_registered'),
            price_per_unit=row.get('price_per_unit'),
            max_aggregate_amount=row.get('max_aggregate_amount'),
            fee_rate=row.get('fee_rate'),
            fee_amount=row.get('fee_amount'),
        ))

    return RegistrationFeeTable(
        total_offering_amount=data.get('total_offering_amount'),
        net_fee_due=data.get('net_fee_due'),
        total_fees_previously_paid=data.get('total_fees_previously_paid'),
        securities=securities,
        carry_forwards=carry_forwards,
        has_carry_forward=data.get('has_carry_forward', False),
        fee_deferred=data.get('fee_deferred', False),
        exhibit_url=data.get('exhibit_url'),
    )
