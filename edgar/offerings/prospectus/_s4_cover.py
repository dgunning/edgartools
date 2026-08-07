"""
S-4 / F-4 cover-page extraction and offering-type classification.

Mirrors the S-1/S-3 layout (``_s1_cover`` / ``_s3_cover``): the cover-page
model, field extraction, and offering-type classification live here, separate
from the ``RegistrationS4`` data object in ``registration_s4``.

S-4 (domestic) and F-4 (foreign private issuer) register securities issued in
business combinations — mergers, acquisitions, de-SPAC transactions — and in
security exchange offers. Their cover pages carry the same registrant metadata
block (state/SIC/EIN, filer-category checkboxes, registration number) as the
other registration forms, so the robust S-1 cover extractor is reused here
verbatim; only the offering-type classification is S-4-specific.

Known limitation (Phase 1): S-4 filings frequently include a "Table of
Additional Registrants" (co-registrant subsidiary guarantors). Only the primary
(top) registrant's state/SIC/EIN are extracted; co-registrants are not
enumerated. See beads edgartools-6yis / edgartools-ssl6 for the follow-on
business-combination narrative extraction (parties, consideration, exchange
ratio), which is out of scope here.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['S4OfferingType', 'S4CoverPage', '_extract_s4_cover_page',
           '_classify_s4_offering']


# ---------------------------------------------------------------------------
# Offering Type
# ---------------------------------------------------------------------------

class S4OfferingType(str, Enum):
    """Classification of S-4 / F-4 registration types.

    S-4/F-4 register securities issued in a transaction rather than sold for
    cash, so the categories differ from S-1/S-3 (IPO / shelf / resale):

    - ``business_combination`` — merger, acquisition, or de-SPAC (securities
      issued as deal consideration). The common case.
    - ``exchange_offer`` — offer to exchange outstanding securities for newly
      registered ones (frequently debt-for-debt, e.g. A/B exchange offers).
    - ``unknown`` — could not be classified from the cover text.
    """
    BUSINESS_COMBINATION = "business_combination"
    EXCHANGE_OFFER = "exchange_offer"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return {
            "business_combination": "Business Combination",
            "exchange_offer": "Exchange Offer",
            "unknown": "Unknown",
        }[self.value]


# ---------------------------------------------------------------------------
# Cover Page Model
# ---------------------------------------------------------------------------

class S4CoverPage(BaseModel):
    """Extracted cover page fields from an S-4 / F-4 filing.

    Mirrors ``S1CoverPage`` / ``S3CoverPage``. Reflects the *primary*
    registrant only (co-registrants in a "Table of Additional Registrants" are
    not enumerated in Phase 1).
    """
    company_name: str
    registration_number: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    sic_code: Optional[str] = None
    ein: Optional[str] = None

    # Filer category checkboxes
    is_large_accelerated_filer: Optional[bool] = None
    is_accelerated_filer: Optional[bool] = None
    is_non_accelerated_filer: Optional[bool] = None
    is_smaller_reporting_company: Optional[bool] = None
    is_emerging_growth_company: Optional[bool] = None

    # Rule checkboxes
    is_rule_415: bool = False
    is_rule_462b: bool = False
    is_rule_462e: bool = False

    # Extraction confidence
    confidence: str = "low"  # low, medium, high


# ---------------------------------------------------------------------------
# Cover Page Extraction
# ---------------------------------------------------------------------------

def _extract_s4_cover_page(filing: 'Filing', html: Optional[str] = None) -> S4CoverPage:
    """Extract cover page fields from an S-4 / F-4 filing.

    Reuses the S-1 cover extractor (header-based registration number, structured
    state/SIC/EIN table parsing, and single-pass checkbox mapping), which is
    markedly more robust on S-4/F-4 cover layouts than the S-3 regex path.
    """
    from edgar.offerings.prospectus._s1_cover import extract_s1_cover_page

    data = extract_s1_cover_page(filing, html)

    # S1CoverPage's dict is a superset; keep the registrant-metadata subset that
    # applies to a business-combination cover (drop S-1-only security_description,
    # which is tuned to cash-IPO "N shares of Common Stock" phrasing that a merger
    # consideration description does not match).
    return S4CoverPage(
        company_name=data.get('company_name') or filing.company,
        registration_number=data.get('registration_number'),
        state_of_incorporation=data.get('state_of_incorporation'),
        sic_code=data.get('sic_code'),
        ein=data.get('ein'),
        is_large_accelerated_filer=data.get('is_large_accelerated_filer'),
        is_accelerated_filer=data.get('is_accelerated_filer'),
        is_non_accelerated_filer=data.get('is_non_accelerated_filer'),
        is_smaller_reporting_company=data.get('is_smaller_reporting_company'),
        is_emerging_growth_company=data.get('is_emerging_growth_company'),
        is_rule_415=bool(data.get('is_rule_415')),
        is_rule_462b=bool(data.get('is_rule_462b')),
        is_rule_462e=bool(data.get('is_rule_462e')),
        confidence=data.get('confidence', 'low'),
    )


# ---------------------------------------------------------------------------
# Offering Type Classification
# ---------------------------------------------------------------------------

# Distinctive multi-word phrases that mark a business-combination registration.
# Bare "merger" / "business combination" are deliberately excluded — they appear
# in risk-factor and forward-looking boilerplate ("our ability to consummate
# acquisitions or business combinations"), which would misclassify a debt
# exchange-offer S-4. Only deal-document phrasing is used. Foreign (F-4) deals
# use "amalgamation" / "arrangement" instead of "merger".
_COMBINATION_MARKERS = (
    'business combination agreement',
    'agreement and plan of merger',
    'plan of merger',
    'merger agreement',
    'merger consideration',
    'will merge',
    'to be merged',
    'de-spac',
    'plan of amalgamation',
    'plan of arrangement',
    'scheme of arrangement',
)
# Phrases that mark a security exchange offer.
_EXCHANGE_MARKERS = (
    'exchange offer',
    'offer to exchange',
    'exchange agent',
)

# S-4/F-4 filings are large (often 10-24 MB) and the deal-document language sits
# well past the cover letter, so scan a generous leading window rather than just
# the cover page.
_CLASSIFY_WINDOW = 300_000

# Strip HTML tags so a marker split across element boundaries
# ("Agreement and Plan of <br/>Merger", "<b>Business</b> <b>Combination</b>")
# still matches as a contiguous phrase.
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def _classify_s4_offering(filing: 'Filing',
                          html: Optional[str] = None) -> S4OfferingType:
    """Classify an S-4 / F-4 offering as business combination vs exchange offer.

    Heuristic keyword scan over a leading window of the primary document.
    Business-combination markers win ties because a debt exchange offer wrapped
    inside a broader merger is still, at the registration level, a business
    combination.
    """
    if html is None:
        html = filing.html()
    if not html:
        return S4OfferingType.UNKNOWN

    # Strip tags and collapse whitespace so multi-word markers match even when
    # the cover renders them across HTML element boundaries.
    window = _TAG_RE.sub(' ', html[:_CLASSIFY_WINDOW])
    cover = _WS_RE.sub(' ', window).lower()

    has_combination = any(m in cover for m in _COMBINATION_MARKERS)
    has_exchange = any(m in cover for m in _EXCHANGE_MARKERS)

    if has_combination:
        return S4OfferingType.BUSINESS_COMBINATION
    if has_exchange:
        return S4OfferingType.EXCHANGE_OFFER
    return S4OfferingType.UNKNOWN
