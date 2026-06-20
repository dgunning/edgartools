"""
Registration fee table extraction from EX-FILING FEES exhibits (Exhibit 107).

Parses the HTML fee table attached to registration statements (S-3, F-3, S-1, etc.)
to extract total offering capacity, per-security breakdowns, and fee calculations.

Works with both plain HTML and inline XBRL exhibits (2022-2025+). For pre-EX-107
registration statements (~pre-2022) that carried the fee table inline in the
document body instead of an exhibit, falls back to _extract_inline_fee_table.
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


# Base registration forms that register capacity (and so carry — or whose
# file-number family carries — a fee exhibit). ASR variants and POS AM are
# handled separately in _is_registration_form.
_FEE_BEARING_BASE_FORMS = {'S-1', 'S-3', 'F-1', 'F-3', 'S-4', 'F-4', 'S-11'}


def _is_registration_form(form: Optional[str]) -> bool:
    """Whether ``form`` registers securities (vs. a takedown/notice/report)."""
    base = (form or '').replace('/A', '')
    return base in _FEE_BEARING_BASE_FORMS or base.endswith('ASR') or base == 'POS AM'


def _resolve_fee_source(filing: 'Filing'):
    """Find the fee-bearing registration for an amendment that omits its exhibit.

    Registration amendments (S-3/A, F-3/A, POS AM) routinely drop the fee
    exhibit because no additional fee is due — the fee was paid with the original
    registration, and the registered capacity still lives in that filing's
    Exhibit 107. Walk the file-number family and return the most recent
    fee-bearing registration filing dated at or before this one (falling back to
    the earliest if all are later). Returns None when ``filing`` is not itself a
    registration form or no such source exists, so non-registration filings
    (424B takedowns, 10-Ks) keep their current None result.
    """
    if not _is_registration_form(filing.form):
        return None
    try:
        related = filing.related_filings()
    except Exception:
        log.debug("related_filings() failed for %s", filing.accession_no)
        return None
    own_date = str(filing.filing_date)
    candidates = [rf for rf in related
                  if rf.accession_no != filing.accession_no
                  and _is_registration_form(rf.form)
                  and _get_filing_fees_attachment(rf) is not None]
    if not candidates:
        return None
    at_or_before = [rf for rf in candidates if str(rf.filing_date) <= own_date]
    return max(at_or_before or candidates, key=lambda rf: str(rf.filing_date))


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


# Pre-EX-107 inline fee tables
# ---------------------------------------------------------------------------
# A "clean" dollar amount cell: only "$", digits, commas and an optional
# decimal (after _join_dollar_cells merges a lone "$" with its number). This
# deliberately rejects prose cells like "par value $0.001 per share" so an
# embedded par value can never be mistaken for an offering amount.
_DOLLAR_RE = re.compile(r'^\$\s*[\d,]+(?:\.\d+)?$')
_DEFERRAL_MARKERS = ('457(r)', 'pay-as-you-go', 'pay as you go')


def _data_to_fee_table(data: dict):
    """Build a RegistrationFeeTable from a parsed-data dict (shared by both the
    EX-107 exhibit path and the pre-2022 inline path)."""
    from edgar.offerings.prospectus import RegistrationFeeTable, FeeTableSecurity

    def _securities(rows):
        return [FeeTableSecurity(
            security_type=r.get('security_type'),
            security_title=r.get('security_title'),
            fee_rule=r.get('fee_rule'),
            amount_registered=r.get('amount_registered'),
            price_per_unit=r.get('price_per_unit'),
            max_aggregate_amount=r.get('max_aggregate_amount'),
            fee_rate=r.get('fee_rate'),
            fee_amount=r.get('fee_amount'),
        ) for r in rows]

    return RegistrationFeeTable(
        total_offering_amount=data.get('total_offering_amount'),
        net_fee_due=data.get('net_fee_due'),
        total_fees_previously_paid=data.get('total_fees_previously_paid'),
        securities=_securities(data.get('securities', [])),
        carry_forwards=_securities(data.get('carry_forwards', [])),
        has_carry_forward=data.get('has_carry_forward', False),
        fee_deferred=data.get('fee_deferred', False),
        exhibit_url=data.get('exhibit_url'),
    )


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


def _extract_inline_fee_table(filing: 'Filing'):
    """Fee table from a pre-EX-107 registration statement's inline body table."""
    try:
        html = filing.html()
    except Exception:
        log.debug("Failed to load primary document for %s", filing.accession_no)
        return None
    if not html:
        return None
    data = _parse_inline_fee_table(html, form=filing.form)
    if data['total_offering_amount'] is None and not data['fee_deferred']:
        return None
    return _data_to_fee_table(data)


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
    fee_att = _get_filing_fees_attachment(filing)
    if not fee_att:
        # A registration amendment may omit its fee exhibit; recover it from the
        # original registration in the same file-number family.
        source = _resolve_fee_source(filing)
        if source is not None:
            src_att = _get_filing_fees_attachment(source)
            if src_att is not None:
                fee_att, filing = src_att, source
    if not fee_att:
        # No EX-FILING FEES exhibit anywhere in the family. Pre-EX-107 (~pre-2022)
        # registration statements carry the fee table inline in the body instead;
        # fall back to that. Non-registration forms (424B takedowns, reports) have
        # no such table and keep returning None.
        if _is_registration_form(filing.form):
            return _extract_inline_fee_table(filing)
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
    return _data_to_fee_table(data)
