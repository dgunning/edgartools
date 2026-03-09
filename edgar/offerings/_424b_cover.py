"""
424B* cover page field extraction.

Extracts 11 fields from the cover page of 424B* filings using
a combination of filing metadata and text regex patterns.

See docs/internal/research/424b-research-results/cover-page-patterns.md
for validation results (89% overall, near-zero true failures).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['extract_cover_page_fields']


def extract_cover_page_fields(filing: 'Filing') -> dict:
    """
    Extract all cover page fields from a 424B* filing.

    Returns a dict with 11 fields suitable for CoverPageData(**result).
    """
    doc = filing.parse()
    text = doc.text()
    cover = text[:15000]

    result: dict = {}

    # === METADATA FIELDS (from filing object, never parse text) ===
    result['company_name'] = filing.company

    try:
        file_nums = filing.header.file_numbers
        result['registration_number'] = file_nums[0] if file_nums else None
    except Exception:
        result['registration_number'] = None

    # === BOOLEAN FIELDS (fast keyword detection) ===
    result['is_supplement'] = bool(re.search(
        r'PROSPECTUS\s+SUPPLEMENT', cover))

    result['is_preliminary'] = bool(re.search(
        r'Subject\s+to\s+Completion|not\s+complete\s+and\s+may\s+be\s+changed|PRELIMINARY\s+PROSPECTUS',
        cover[:3000], re.IGNORECASE))

    result['is_atm'] = bool(re.search(
        r'at[\-\s]+the[\-\s]+market\s+offering|equity\s+distribution\s+agreement|"at\s+the\s+market"',
        cover, re.IGNORECASE))

    # === STRUCTURED TEXT FIELDS ===

    # rule_number
    m = re.search(r'Filed\s+[Pp]ursuant\s+to\s+Rule\s+424\(b\)\((\d+)\)', cover, re.IGNORECASE)
    if not m:
        m = re.search(r'Rule\s+424\(b\)\((\d+)\)', cover, re.IGNORECASE)
    if m:
        result['rule_number'] = m.group(1)
    else:
        fm = re.search(r'424B(\d+)', filing.form)
        result['rule_number'] = fm.group(1) if fm else None

    # base_prospectus_date (supplements only)
    m = re.search(
        r'\(To\s+[Pp]rospectus(?:\s+[Ss]upplement)?\s+dated\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\)',
        cover, re.IGNORECASE)
    result['base_prospectus_date'] = m.group(1) if m else None

    # security_description
    for p in [
        r'(\d[\d,]*\s+(?:Shares|Units|Notes?|Warrants?)\s+of\s+(?:Common|Preferred|Class [AB])?\s*(?:Stock|Shares)?(?:[^\n]{0,80}))',
        r'(Up\s+to\s+\$[\d,\.]+\s*(?:(?:million|billion|aggregate|of)[\s\w]*)?(?:Common\s+Stock|Class\s+[AB]\s+Common\s+Stock|Ordinary\s+Shares))',
        r'(\$[\d,\.]+\s+(?:aggregate principal amount|in principal)\s+[\w\s]+(?:Notes|Debentures))',
    ]:
        m = re.search(p, cover[:6000], re.IGNORECASE)
        if m:
            result['security_description'] = re.sub(r'\s+', ' ', m.group(1)[:120]).strip()
            break
    else:
        result['security_description'] = None

    # exchange_ticker (search wider area)
    for p in [
        r'under\s+the\s+symbol\s+["\u201c\u201d\u2018\u2019"]\s*([A-Z]{1,6})["\u201c\u201d\u2018\u2019".,]',
        r'under\s+the\s+(?:trading\s+)?symbol\s+.?\s*([A-Z]{2,6})\b',
    ]:
        m = re.search(p, text[:50000], re.IGNORECASE)
        if m:
            result['exchange_ticker'] = m.group(1)
            break
    else:
        result['exchange_ticker'] = None

    # offering_amount
    if re.search(r'\bexchange\s+offer\b', cover[:3000], re.IGNORECASE):
        result['offering_amount'] = 'exchange-offer'
    else:
        for p in [
            r'Up\s+to\s+\$([\d,\.]+(?:\s+(?:million|billion))?)\s*\n',
            r'aggregate\s+(?:offering\s+price|gross\s+proceeds)[^\$]*\$([\d,\.]+)',
            r'Total\s+\$([\d,\.]+)',
            r'^\$([\d,\.]+)\s*$',
        ]:
            m = re.search(p, cover[:8000], re.IGNORECASE | re.MULTILINE)
            if m:
                result['offering_amount'] = '$' + m.group(1)
                break
        else:
            result['offering_amount'] = None

    # offering_price
    if result['is_atm']:
        result['offering_price'] = 'at-the-market'
    elif re.search(r'\bexchange\s+offer\b', cover[:3000], re.IGNORECASE):
        result['offering_price'] = 'exchange-offer'
    elif result['is_preliminary']:
        result['offering_price'] = 'preliminary-TBD'
    else:
        for p in [
            r'Offering\s+price\s+\$\s*([\d,\.]+)',
            r'(?:Public\s+)?[Oo]ffering\s+[Pp]rice[^\$\n]{0,30}\$\s*([\d,\.]+)',
            r'Per\s+(?:Share|Note|Unit)[^\$\n]{0,30}\$\s*([\d,\.]+)',
        ]:
            m = re.search(p, text[:15000], re.IGNORECASE)
            if m:
                val = m.group(1).replace(',', '')
                try:
                    if float(val) >= 0.01:
                        result['offering_price'] = '$' + m.group(1)
                        break
                except ValueError:
                    continue
        else:
            if re.search(r'prevailing\s+market\s+price|at\s+various\s+prices', text, re.IGNORECASE):
                result['offering_price'] = 'market-price'
            else:
                result['offering_price'] = None

    return result
