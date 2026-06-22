"""424B* Prospectus parsing.

Handles all 424B form variants (424B1 through 424B8) including amendments (/A):
cover-page extraction, offering-type classification, shelf lifecycle, and a
normalized Deal summary.

This package preserves the original ``edgar.offerings.prospectus`` import
surface — every name that was importable from the former single module is
re-exported here.
"""

from __future__ import annotations

from edgar.offerings.prospectus.parsing import (
    _parse_filing_date,
    _plus_three_years,
    _parse_sec_number,
    _parse_sec_int,
)
from edgar.offerings.prospectus.models import (
    PROSPECTUS_FORMS,
    OfferingType,
    CoverPageData,
    PricingColumnData,
    PricingData,
    OfferingTerms,
    SellingStockholderEntry,
    SellingStockholdersData,
    UnderwriterEntry,
    UnderwritingInfo,
    StructuredNoteTerms,
    DilutionData,
    CapitalizationData,
    FilingFeesRow,
    FilingFeesData,
    FeeTableSecurity,
    RegistrationFeeTable,
    _build_filing_fees_data,
)
from edgar.offerings.prospectus.lifecycle import ShelfLifecycle
from edgar.offerings.prospectus.deal import (
    Deal,
    _MIN_PLAUSIBLE_DEAL_SIZE,
    _extract_amendment_number,
)
from edgar.offerings.prospectus.document import Prospectus424B

__all__ = [
    'Prospectus424B',
    'ShelfLifecycle',
    'Deal',
    'OfferingType',
    'CoverPageData',
    'SellingStockholdersData',
    'SellingStockholderEntry',
    'PROSPECTUS_FORMS',
    'PricingColumnData',
    'PricingData',
    'OfferingTerms',
    'UnderwriterEntry',
    'UnderwritingInfo',
    'StructuredNoteTerms',
    'DilutionData',
    'CapitalizationData',
    'FilingFeesRow',
    'FilingFeesData',
    'FeeTableSecurity',
    'RegistrationFeeTable',
]
