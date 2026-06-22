"""
S-1 offering type classifier.

Uses a priority cascade over cover-page text signals to classify
the S-1 registration sub-type: IPO, SPAC, Resale, Debt, or Follow-On.

Signals are detected in the first 5,000-8,000 characters of the
primary document text (cover page area).
"""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['classify_s1_offering_type']


def classify_s1_offering_type(filing: 'Filing', html: Optional[str] = None) -> dict:
    """
    Classify an S-1 filing into an offering sub-type.

    Args:
        filing: An EdgarTools Filing object with an S-1/S-1/A form type.
        html: Pre-fetched HTML string. If None, fetched from filing.

    Returns:
        dict with keys:
          - type: str (ipo, spac, resale, debt, follow_on, unknown)
          - confidence: 'high' | 'medium' | 'low'
          - signals: list[str] of matched signal strings
          - sub_type: str | None
    """
    if html is None:
        html = filing.html() or ''

    # Strip HTML tags to get plain text for signal detection.
    # S-1 HTML is very verbose — 8K of raw HTML may only contain ~2K of text.
    # We take a larger window and strip to get enough signal content.
    raw_text = re.sub(r'<[^>]+>', ' ', html[:80000])
    raw_text = re.sub(r'&\w+;', ' ', raw_text)
    raw_text = re.sub(r'\s+', ' ', raw_text).lower()
    text_lower = raw_text[:10000]
    narrow = raw_text[:5000]
    signals: dict[str, list[str]] = {}

    # --- SPAC ---
    spac: list[str] = []
    if 'blank check' in narrow or 'blank check' in narrow.replace('\xa0', ' '):
        spac.append('blank_check')
    if 'business combination' in narrow:
        spac.append('business_combination')
    if 'trust account' in text_lower:
        spac.append('trust_account')
    if 'special purpose acquisition' in text_lower:
        spac.append('special_purpose_acquisition')
    if re.search(r'(?:initial\s+)?public\s+offering.*?unit', narrow):
        if 'trust' in text_lower or 'blank check' in text_lower:
            spac.append('ipo_units_with_trust')
    signals['spac'] = spac

    # --- Resale ---
    resale: list[str] = []
    if re.search(r'resale\b', text_lower):
        resale.append('resale_cover')
    if re.search(r'selling\s+(?:stock|security|share)holders?', narrow):
        resale.append('selling_stockholder')
    if re.search(r'not\s+receive\s+any\s+(?:of\s+the\s+)?proceeds', text_lower):
        resale.append('no_proceeds')
    if 'registration rights agreement' in text_lower:
        resale.append('registration_rights')
    signals['resale'] = resale

    # --- Debt ---
    debt: list[str] = []
    if re.search(r'(?:senior|subordinated|unsecured)\s+notes?\s+due\s+\d{4}', narrow):
        debt.append('notes_due')
    if re.search(r'aggregate\s+principal\s+amount', narrow):
        debt.append('aggregate_principal')
    if 'indenture' in narrow:
        debt.append('indenture')
    if re.search(r'interest\s+rate.*?\d+\.\d+%', text_lower) and 'notes' in narrow:
        debt.append('interest_rate_notes')
    signals['debt'] = debt

    # --- IPO ---
    ipo: list[str] = []
    if 'initial public offering' in text_lower:
        ipo.append('ipo_text')
    if re.search(r'no\s+(?:established\s+)?(?:public\s+)?(?:trading\s+)?market', text_lower):
        ipo.append('no_public_market')
    if re.search(r'(?:has been|have been|will be)\s+approved\s+for\s+(?:listing|trading)', text_lower):
        ipo.append('listing_approval')
    if re.search(r'(?:apply|applied|application)\s+(?:to\s+)?(?:list|have)', text_lower) and \
       re.search(r'(?:nasdaq|nyse|new york stock exchange|cboe|american)', text_lower):
        ipo.append('listing_application')
    if 'underwriter' in text_lower and re.search(r'(?:public\s+)?offering\s+price', text_lower):
        ipo.append('underwriter_offering_price')
    signals['ipo'] = ipo

    # --- Follow-on ---
    follow_on: list[str] = []
    if re.search(r'(?:common\s+stock|ordinary\s+shares).*?(?:listed|traded)\s+on', text_lower):
        follow_on.append('already_listed')
    if re.search(r'under\s+the\s+(?:trading\s+)?symbol\s+["\u201c]', text_lower):
        follow_on.append('existing_symbol')
    # Follow-on: has underwriter but NOT "initial public offering"
    if 'underwriter' in narrow and 'initial public offering' not in text_lower:
        if 'resale' not in narrow and 'selling stockholder' not in narrow:
            follow_on.append('underwritten_non_ipo')
    signals['follow_on'] = follow_on

    # --- Decision cascade ---

    # 1. SPAC (highest priority — very distinctive signals)
    if 'blank_check' in signals['spac'] or len(signals['spac']) >= 2:
        return _result('spac', 'high', signals['spac'])

    # 2. Resale
    if 'no_proceeds' in signals['resale'] and 'selling_stockholder' in signals['resale']:
        return _result('resale', 'high', signals['resale'])
    if 'resale_cover' in signals['resale'] and 'selling_stockholder' in signals['resale']:
        return _result('resale', 'high', signals['resale'])
    if 'resale_cover' in signals['resale'] and 'no_proceeds' in signals['resale']:
        return _result('resale', 'high', signals['resale'])

    # 3. Debt
    if len(signals['debt']) >= 2:
        return _result('debt', 'high', signals['debt'])

    # 4. IPO
    if 'ipo_text' in signals['ipo'] and len(signals['ipo']) >= 2:
        return _result('ipo', 'high', signals['ipo'])
    if 'no_public_market' in signals['ipo'] and 'listing_application' in signals['ipo']:
        return _result('ipo', 'high', signals['ipo'])
    if 'no_public_market' in signals['ipo'] and 'underwriter_offering_price' in signals['ipo']:
        return _result('ipo', 'high', signals['ipo'])

    # 5. Follow-on
    if 'underwritten_non_ipo' in signals['follow_on'] and 'already_listed' in signals['follow_on']:
        return _result('follow_on', 'high', signals['follow_on'])

    # --- Medium confidence fallbacks ---
    if len(signals['resale']) >= 2:
        return _result('resale', 'medium', signals['resale'])
    if 'ipo_text' in signals['ipo']:
        return _result('ipo', 'medium', signals['ipo'])
    if 'no_public_market' in signals['ipo']:
        return _result('ipo', 'medium', signals['ipo'])
    if len(signals['debt']) == 1:
        return _result('debt', 'medium', signals['debt'])
    if len(signals['follow_on']) >= 2:
        return _result('follow_on', 'medium', signals['follow_on'])
    if len(signals['spac']) == 1:
        return _result('spac', 'medium', signals['spac'])

    return _result('unknown', 'low', [])


def _result(type_: str, confidence: str, signals: list[str],
            sub_type: str | None = None) -> dict:
    return {
        'type': type_,
        'confidence': confidence,
        'signals': signals,
        'sub_type': sub_type,
    }
