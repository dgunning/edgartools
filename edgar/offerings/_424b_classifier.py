"""
424B* offering type classifier.

Uses a priority cascade over cover-page text signals to classify
the offering type. All primary signals appear in the first 3,000
characters (cover page); secondary signals in the first 8,000.

See docs/internal/research/424b-research-results/offering-type-classification.md
for validation results (12/12 = 100% accuracy).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['classify_offering_type']


def classify_offering_type(filing: 'Filing') -> dict:
    """
    Classify a 424B filing into an offering type.

    Args:
        filing: An EdgarTools Filing object with a 424B* form type.

    Returns:
        dict with keys:
          - type: str (firm_commitment, atm, best_efforts, pipe_resale,
                       rights_offering, exchange_offer, structured_note,
                       debt_offering, base_prospectus_update, unknown)
          - confidence: 'high' | 'medium' | 'low'
          - signals: list[str] of matched signal strings
          - sub_type: str | None
    """
    form = filing.form.replace('/A', '')

    # 424B7 is always a base prospectus update
    if form == '424B7':
        return {
            'type': 'base_prospectus_update',
            'confidence': 'high',
            'signals': ['form=424B7'],
            'sub_type': None,
        }

    try:
        doc = filing.parse()
        text = doc.text()
    except Exception as e:
        return {
            'type': 'unknown',
            'confidence': 'low',
            'signals': [f'parse_error: {e}'],
            'sub_type': None,
        }

    text_lower = text.lower()
    narrow_cover = text_lower[:3000]
    cover = text_lower[:8000]
    signals: dict[str, list[str]] = {}

    # --- Structured note ---
    sn: list[str] = []
    if 'pricing supplement' in narrow_cover:
        sn.append('pricing_supplement')
    if re.search(r'linked to (the |a )?(russell|s&p|nasdaq|dow|msci|ftse|nikkei|euro stoxx)', cover):
        sn.append('linked_to_index')
    if 'market-linked' in cover or 'market linked' in cover:
        sn.append('market_linked')
    if re.search(r'\b(buffer|trigger|barrier|principal at risk|capped buffered|step up)\b', cover):
        sn.append('structured_product_terms')
    if 'product supplement' in narrow_cover:
        sn.append('product_supplement')
    signals['structured_note'] = sn

    # --- ATM ---
    atm: list[str] = []
    if 'equity distribution agreement' in cover:
        atm.append('equity_distribution_agreement')
    if 'at-the-market' in cover or 'at the market offering' in cover:
        atm.append('at_the_market')
    if 'sales agreement' in narrow_cover and 'from time to time' in cover:
        atm.append('sales_agreement_cover')
    if re.search(r'as (?:our |its )?(?:sales |distribution )?agent', cover) and 'from time to time' in cover:
        atm.append('as_agent_ftt')
    signals['atm'] = atm

    # --- Exchange offer ---
    ex: list[str] = []
    if re.search(r'offer to exchange', narrow_cover):
        ex.append('offer_to_exchange_cover')
    elif re.search(r'offer to exchange', cover):
        ex.append('offer_to_exchange')
    if 'exchange agent' in cover:
        ex.append('exchange_agent')
    if 'tendering' in cover:
        ex.append('tendering')
    signals['exchange_offer'] = ex

    # --- Rights offering ---
    ro: list[str] = []
    if 'subscription rights' in narrow_cover:
        ro.append('subscription_rights_cover')
    if 'rights offering' in narrow_cover:
        ro.append('rights_offering_cover')
    if 'subscription price' in cover and 'rights' in cover:
        ro.append('subscription_price_rights')
    signals['rights_offering'] = ro

    # --- PIPE resale (narrow_cover only to avoid base-prospectus boilerplate) ---
    pr: list[str] = []
    if re.search(r'(offer and resale|resale by the selling stockholder|resale by the selling shareholder)', narrow_cover):
        pr.append('resale_by_selling_cover')
    if 'resale' in narrow_cover and 'direct listing' in narrow_cover:
        pr.append('direct_listing_resale_cover')
    if re.search(
        r'(will not receive any proceeds|not receive any of the proceeds|'
        r'not receive proceeds from the sale)', narrow_cover
    ):
        pr.append('no_proceeds_cover')
    if 'selling stockholder' in narrow_cover or 'selling shareholder' in narrow_cover:
        pr.append('selling_stockholder_cover')
    if 'private placement' in narrow_cover and 'resale' in narrow_cover:
        pr.append('private_placement_resale_cover')
    signals['pipe_resale'] = pr

    # --- Debt offering ---
    debt: list[str] = []
    if re.search(
        r'\d+\.\d+%\s*(?:senior|subordinated|unsecured|secured|fixed|floating)?\s*notes? due \d{4}',
        narrow_cover,
    ):
        debt.append('fixed_rate_notes_cover')
    if re.search(
        r'\$[\d,]+(?:,000,000|\.?\d*\s*(?:billion|million))\s*(?:aggregate principal|principal amount)',
        cover,
    ):
        debt.append('aggregate_principal')
    if 'senior notes' in narrow_cover or 'subordinated notes' in narrow_cover:
        debt.append('senior_sub_notes_cover')
    if 'indenture' in narrow_cover:
        debt.append('indenture_cover')
    signals['debt_offering'] = debt

    # --- Best efforts ---
    be: list[str] = []
    if re.search(r'offering directly to.{5,80}investor', narrow_cover):
        be.append('direct_to_investor_cover')
    if 'securities purchase agreement' in narrow_cover:
        be.append('securities_purchase_agreement_cover')
    if 'placement agent' in narrow_cover:
        pa_idx = narrow_cover.find('placement agent')
        pa_context = narrow_cover[max(0, pa_idx - 200):pa_idx + 200]
        if not re.search(r'(prior|previous|completed|closed|concurrent).{0,80}placement agent', pa_context):
            be.append('placement_agent_cover')
    if 'pre-funded warrant' in narrow_cover:
        be.append('prefunded_warrants_cover')
    be_match = re.search(r'best[- ]efforts', narrow_cover)
    if be_match:
        be_context = narrow_cover[be_match.start():be_match.start() + 150]
        if not re.search(r'best[- ]efforts.{0,100}(register|registration|effective)', be_context):
            be.append('best_efforts_cover')
    signals['best_efforts'] = be

    # --- Firm commitment ---
    fc: list[str] = []
    if re.search(r'public offering price\s+\$[\d.,]+', cover[:5000]):
        fc.append('public_offering_price_table')
    if re.search(r'underwriting discount|underwriters?\s+commission', cover[:5000]):
        fc.append('underwriting_discount')
    if re.search(r'(option|option to purchase).{0,100}additional (shares|units)', cover[:5000]):
        fc.append('overallotment_option')
    if re.search(
        r'(j\.p\. morgan|goldman sachs|morgan stanley|jefferies|piper sandler|'
        r'raymond james|stifel|b\. riley|rbc capital|wells fargo securities)',
        narrow_cover,
    ):
        fc.append('named_underwriter_cover')
    # IPO / SPAC patterns: prose-style price + underwriter references
    if 'initial public offering' in cover:
        fc.append('ipo_text')
    if re.search(r'the underwriters have a \d+[- ]day', cover):
        fc.append('underwriter_option_text')
    if re.search(r'(?:has a price of|price of) \$[\d.,]+\s+(?:per |and )', cover):
        fc.append('prose_price')
    if re.search(r'over[- ]?allotment', cover) and 'underwriter' in cover:
        fc.append('overallotment_underwriter')
    signals['firm_commitment'] = fc

    # --- Decision cascade (first match wins) ---

    # 1. Structured note
    if 'pricing_supplement' in signals['structured_note']:
        return _result('structured_note', 'high', signals['structured_note'])
    if len(signals['structured_note']) >= 2:
        return _result('structured_note', 'high', signals['structured_note'])

    # 2. Exchange offer
    if 'offer_to_exchange_cover' in signals['exchange_offer'] or len(signals['exchange_offer']) >= 2:
        return _result('exchange_offer', 'high', signals['exchange_offer'])

    # 3. Rights offering
    if 'subscription_rights_cover' in signals['rights_offering'] or \
       'rights_offering_cover' in signals['rights_offering']:
        return _result('rights_offering', 'high', signals['rights_offering'])

    # 4. ATM
    if 'equity_distribution_agreement' in signals['atm'] or \
       'at_the_market' in signals['atm'] or \
       len(signals['atm']) >= 2:
        return _result('atm', 'high', signals['atm'])

    # 5. PIPE resale (before best_efforts)
    if ('no_proceeds_cover' in signals['pipe_resale'] and
            'selling_stockholder_cover' in signals['pipe_resale']) or \
       'resale_by_selling_cover' in signals['pipe_resale'] or \
       'direct_listing_resale_cover' in signals['pipe_resale']:
        return _result('pipe_resale', 'high', signals['pipe_resale'], sub_type='equity_resale')

    # 6. Debt offering
    if len(signals['debt_offering']) >= 2:
        return _result('debt_offering', 'high', signals['debt_offering'])

    # 7. Best efforts
    if 'direct_to_investor_cover' in signals['best_efforts'] or \
       'securities_purchase_agreement_cover' in signals['best_efforts'] or \
       ('placement_agent_cover' in signals['best_efforts'] and len(signals['best_efforts']) >= 2):
        return _result('best_efforts', 'high', signals['best_efforts'])

    # 8. Firm commitment
    if 'public_offering_price_table' in signals['firm_commitment'] and \
       'underwriting_discount' in signals['firm_commitment']:
        return _result('firm_commitment', 'high', signals['firm_commitment'])
    if 'named_underwriter_cover' in signals['firm_commitment'] and \
       'underwriting_discount' in signals['firm_commitment']:
        return _result('firm_commitment', 'high', signals['firm_commitment'])
    # IPO / SPAC prose-style patterns (no tabular pricing)
    if 'ipo_text' in signals['firm_commitment'] and \
       'underwriter_option_text' in signals['firm_commitment']:
        return _result('firm_commitment', 'high', signals['firm_commitment'])
    if 'ipo_text' in signals['firm_commitment'] and \
       'overallotment_underwriter' in signals['firm_commitment']:
        return _result('firm_commitment', 'high', signals['firm_commitment'])
    if 'prose_price' in signals['firm_commitment'] and \
       'overallotment_underwriter' in signals['firm_commitment']:
        return _result('firm_commitment', 'high', signals['firm_commitment'])

    # Medium confidence fallbacks
    if len(signals['atm']) >= 1:
        return _result('atm', 'medium', signals['atm'])
    if len(signals['debt_offering']) == 1:
        return _result('debt_offering', 'medium', signals['debt_offering'])
    if 'best_efforts_cover' in signals['best_efforts'] or len(signals['best_efforts']) >= 2:
        return _result('best_efforts', 'medium', signals['best_efforts'])
    if 'underwriting_discount' in signals['firm_commitment']:
        return _result('firm_commitment', 'medium', signals['firm_commitment'])
    # IPO text alone is medium confidence
    if 'ipo_text' in signals['firm_commitment'] and len(signals['firm_commitment']) >= 2:
        return _result('firm_commitment', 'medium', signals['firm_commitment'])

    return _result('unknown', 'low', [])


def _result(type_: str, confidence: str, signals: list[str],
            sub_type: str | None = None) -> dict:
    return {
        'type': type_,
        'confidence': confidence,
        'signals': signals,
        'sub_type': sub_type,
    }
