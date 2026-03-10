"""
424B* EX-FILING FEES XBRL extraction.

Parses the EX-FILING FEES Inline XBRL exhibit attached to some 424B filings.
This exhibit provides machine-readable offering amounts, security types,
and fee calculations.

Coverage: ~43% of 424B2, ~23% of 424B5, ~7% of 424B3, 0% of 424B1/424B4.
Available from early 2022 onwards (SEC Rule 408).

See xbrl-filing-fees-extraction research for implementation details.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['extract_filing_fees_xbrl']


def _get_filing_fees_attachment(filing: 'Filing'):
    """Find the EX-FILING FEES attachment, returns None if not present."""
    for att in filing.attachments:
        doc_type = getattr(att, 'document_type', None)
        if doc_type == 'EX-FILING FEES':
            return att
    return None


def _get_row_num(ctx: str) -> Optional[int]:
    """Extract 1-based row number from iXBRL context ID."""
    m = re.search(r'offrl_(\d+)', ctx)
    if m:
        return int(m.group(1))
    m = re.search(r'_(\d+)TypedMember', ctx)
    if m:
        return int(m.group(1))
    return None


def extract_filing_fees_xbrl(filing: 'Filing') -> dict:
    """
    Extract structured data from EX-FILING FEES Inline XBRL exhibit.

    Returns dict with:
      - has_exhibit: bool
      - exhibit_url: str | None
      - form_type: str | None (e.g. 'S-3')
      - registration_file_number: str | None
      - total_offering_amount: str | None
      - total_fee_amount: str | None
      - offering_rows: list[dict] — per-row security type, title, amount, fee
      - is_final_prospectus: bool
    """
    fee_att = _get_filing_fees_attachment(filing)
    if not fee_att:
        return {'has_exhibit': False}

    try:
        from bs4 import BeautifulSoup
        content = fee_att.download()
        soup = BeautifulSoup(content, 'lxml')
    except Exception:
        return {'has_exhibit': False}

    metadata: dict[str, str] = {}
    summary: dict[str, str] = {}
    rows: dict[str, dict[str, str]] = {}
    seen_keys: set = set()

    ROW_CONTEXT_PATTERNS = ['TypedMemberffdOfferingAxis', 'offrl_', 'offt_']
    SUMMARY_PREFIXES = ('ffd:Ttl', 'ffd:Net', 'ffd:Nrrtv')

    for elem in soup.find_all(lambda tag: tag.name in ('ix:nonnumeric', 'ix:nonfraction')):
        name = elem.get('name', '')
        if not name:
            continue

        ctx = elem.get('contextref') or elem.get('contextRef', '')
        value = elem.get_text(strip=True)

        if elem.get('xsi:nil') == 'true':
            continue

        key = (name, ctx)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        is_row_ctx = any(p in ctx for p in ROW_CONTEXT_PATTERNS)

        if is_row_ctx:
            row_num = _get_row_num(ctx)
            row_key = str(row_num) if row_num is not None else ctx
            if row_key not in rows:
                rows[row_key] = {}
            rows[row_key][name] = value
        elif name.startswith(SUMMARY_PREFIXES):
            summary[name] = value
        else:
            metadata[name] = value

    # Build offering_rows list
    offering_rows = []
    def _row_sort_key(k):
        try:
            return (0, int(k))
        except ValueError:
            return (1, k)

    for row_key in sorted(rows.keys(), key=_row_sort_key):
        row = rows[row_key]
        offering_rows.append({
            'security_type': row.get('ffd:OfferingSctyTp'),
            'security_title': row.get('ffd:OfferingSctyTitl'),
            'max_aggregate_offering_price': row.get('ffd:MaxAggtOfferingPric'),
            'fee_rate': row.get('ffd:FeeRate'),
            'fee_amount': row.get('ffd:FeeAmt'),
            'fee_rule': row.get('ffd:Rule457rFlg') or row.get('ffd:Rule457oFlg')
                        or row.get('ffd:FeesOthrRuleFlg'),
        })

    # Check final prospectus flag
    is_final = metadata.get('ffd:FnlPrspctsFlg', '').lower() == 'true'

    return {
        'has_exhibit': True,
        'exhibit_url': fee_att.url,
        'form_type': metadata.get('ffd:FormTp'),
        'registration_file_number': metadata.get('ffd:RegnFileNb'),
        'total_offering_amount': summary.get('ffd:TtlOfferingAmt')
                                 or summary.get('ffd:NrrtvMaxAggtOfferingPric'),
        'total_fee_amount': summary.get('ffd:TtlFeeAmt'),
        'offering_rows': offering_rows,
        'is_final_prospectus': is_final,
    }
