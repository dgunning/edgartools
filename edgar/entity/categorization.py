"""
Company business category classification.

This module provides classification of SEC filers into business categories
based on SIC codes, form types, entity type, and name patterns.

The classification uses a multi-signal approach with priority hierarchy:
1. Definitive SIC codes (REIT, SPAC, Bank, Insurance)
2. Investment company forms (ETF, Mutual Fund, Closed-End Fund)
3. SPAC name patterns (Acquisition Corp, Blank Check, etc.)
4. BDC indicators (N-2 forms only)
5. Investment manager indicators (13F, SIC)
6. Holding company (SIC 6719)
7. "ETF" in name (catches crypto/commodity ETFs)
8. SIC 6200s + fund/trust name (commodity trusts, crypto trusts)
9. Default to Operating Company
"""

from enum import Enum
from typing import Optional, Set, Union

__all__ = [
    'BusinessCategory',
    'classify_business_category',
    'sic_overrides_bdc',
    'SIC_CODES_REIT',
    'SIC_CODES_SPAC',
    'SIC_CODES_BANK',
    'SIC_CODES_INSURANCE',
    'SIC_CODES_INVESTMENT_MANAGER',
    'SIC_CODES_HOLDING_COMPANY',
    'PRIMARY_INVESTMENT_FORMS',
    'INVESTMENT_COMPANY_FORMS',
    'BDC_FORMS',
    'INVESTMENT_MANAGER_FORMS',
    'SPAC_NAME_PATTERNS',
]


class BusinessCategory(str, Enum):
    """
    Enumeration of company business categories.

    Categories are determined by a combination of SIC codes,
    SEC form types filed, and entity type.
    """
    OPERATING_COMPANY = "Operating Company"
    ETF = "ETF"
    MUTUAL_FUND = "Mutual Fund"
    CLOSED_END_FUND = "Closed-End Fund"
    BDC = "BDC"
    REIT = "REIT"
    INVESTMENT_MANAGER = "Investment Manager"
    BANK = "Bank"
    INSURANCE_COMPANY = "Insurance Company"
    SPAC = "SPAC"
    HOLDING_COMPANY = "Holding Company"
    UNKNOWN = "Unknown"


# =============================================================================
# SIC Code Classifications
# =============================================================================

# Real Estate Investment Trusts
SIC_CODES_REIT: Set[int] = {6798}

# Blank Check Companies (SPACs)
SIC_CODES_SPAC: Set[int] = {6770}

# Banks and Savings Institutions
SIC_CODES_BANK: Set[int] = {
    6021,  # National Commercial Banks
    6022,  # State Commercial Banks
    6029,  # Commercial Banks NEC
    6035,  # Savings Institutions, Federally Chartered
    6036,  # Savings Institutions, Not Federally Chartered
}

# Insurance Companies
SIC_CODES_INSURANCE: Set[int] = {
    6311,  # Life Insurance
    6321,  # Accident & Health Insurance
    6331,  # Fire, Marine & Casualty Insurance
    6351,  # Surety Insurance
    6361,  # Title Insurance
    6371,  # Pension, Health & Welfare Funds
}

# Investment Advisors and Brokers
SIC_CODES_INVESTMENT_MANAGER: Set[int] = {
    6211,  # Security Brokers, Dealers & Flotation Companies
    6282,  # Investment Advice
}

# Holding Companies
SIC_CODES_HOLDING_COMPANY: Set[int] = {6719}


# =============================================================================
# Form Type Classifications
# =============================================================================

# Primary Investment Company Forms (definitive signals for ETFs, Mutual Funds, CEFs)
# These forms are filed primarily by registered investment companies
PRIMARY_INVESTMENT_FORMS: Set[str] = {
    'N-CSR',      # Certified Shareholder Report
    'N-CSRS',     # Certified Shareholder Report (semi-annual)
    'NPORT-P',    # Portfolio Holdings
    'NPORT-EX',   # Portfolio Holdings (exhibit)
}

# Secondary Investment Company Forms (supplementary signals)
# N-PX and N-CEN can be filed by companies with investment activities
# but aren't definitive on their own
SECONDARY_INVESTMENT_FORMS: Set[str] = {
    'N-CEN',      # Annual Report for Investment Companies
    'N-PX',       # Proxy Voting Record
}

# All Investment Company Forms (for reference)
INVESTMENT_COMPANY_FORMS: Set[str] = PRIMARY_INVESTMENT_FORMS | SECONDARY_INVESTMENT_FORMS

# BDC-Specific Forms
BDC_FORMS: Set[str] = {
    'N-2',        # Registration Statement for BDCs
    'N-2ASR',     # Automatic Shelf Registration (BDC)
    'N-23C-2',    # Notice of Dividend Reinvestment Plan
}

# Investment Manager Forms
INVESTMENT_MANAGER_FORMS: Set[str] = {
    '13F-HR',     # Quarterly Holdings Report
    '13F-HR/A',   # Amended Quarterly Holdings Report
}

# Known ETF fund families
ETF_FUND_FAMILIES: Set[str] = {
    'ISHARES',
    'SPDR',
    'PROSHARES',
    'INVESCO',
    'WISDOMTREE',
    'VANECK',
    'FIRST TRUST',
    'GLOBAL X',
    'ARK',
}

# SPAC name patterns — high confidence, standard naming conventions
SPAC_NAME_PATTERNS: list[str] = [
    'ACQUISITION CORP',    # Most common SPAC naming pattern
    'ACQUISITION CO',      # Catches "Acquisition Company", "Acquisition Co"
    'ACQUISITION INC',     # Less common variant
    'BLANK CHECK',         # SEC standard term for SPACs
]


# =============================================================================
# Helper Functions
# =============================================================================

def _is_spac_by_name(name_upper: str) -> bool:
    """Check if company name matches known SPAC patterns."""
    return any(pattern in name_upper for pattern in SPAC_NAME_PATTERNS)


def _parse_sic(sic: Optional[Union[int, str]]) -> Optional[int]:
    """
    Parse SIC code to integer.

    Args:
        sic: SIC code as int, str, or None

    Returns:
        SIC code as integer, or None if invalid/missing
    """
    if sic is None:
        return None
    if isinstance(sic, int):
        return sic
    if isinstance(sic, str):
        try:
            return int(sic)
        except (ValueError, TypeError):
            return None
    return None


# =============================================================================
# Classification Functions
# =============================================================================

def classify_business_category(
    sic: Optional[Union[int, str]],
    entity_type: Optional[str],
    name: str,
    form_types: Set[str]
) -> str:
    """
    Classify a company into a business category.

    Uses a priority-based decision tree:
    1. Definitive SIC codes (REIT, SPAC, Bank, Insurance)
    2. Investment company forms (ETF, Mutual Fund, Closed-End Fund)
    3. BDC indicators
    4. Investment manager indicators
    5. Holding company
    6. Default to Operating Company

    Args:
        sic: SIC code as integer or string (or None if not available)
        entity_type: Entity type from SEC ('operating', 'investment', 'other', etc.)
        name: Company name
        form_types: Set of form types filed by this company

    Returns:
        Business category string (one of BusinessCategory values)
    """
    # Convert SIC to integer for comparison
    sic_int = _parse_sic(sic)
    name_upper = name.upper() if name else ''

    # Step 1: Check definitive SIC codes
    if sic_int is not None:
        if sic_int in SIC_CODES_REIT:
            return BusinessCategory.REIT.value

        if sic_int in SIC_CODES_SPAC:
            return BusinessCategory.SPAC.value

        if sic_int in SIC_CODES_BANK:
            return BusinessCategory.BANK.value

        if sic_int in SIC_CODES_INSURANCE:
            return BusinessCategory.INSURANCE_COMPANY.value

    # Step 2: Check investment company forms (primary forms only)
    # N-CSR and NPORT are definitive signals for investment companies
    has_primary_investment_forms = bool(form_types & PRIMARY_INVESTMENT_FORMS)

    if has_primary_investment_forms:
        return _classify_investment_company_type(entity_type, name)

    # Step 3: SPAC name patterns — before BDC to avoid false positives
    if _is_spac_by_name(name_upper):
        return BusinessCategory.SPAC.value

    # Step 4: Check BDC signals (forms only — no name pattern)
    if _is_bdc(entity_type, form_types, sic=sic_int):
        return BusinessCategory.BDC.value

    # Step 5: Check investment manager signals
    if _is_investment_manager(sic_int, form_types, name_upper):
        return BusinessCategory.INVESTMENT_MANAGER.value

    # Step 6: Check holding company
    if sic_int is not None and sic_int in SIC_CODES_HOLDING_COMPANY:
        return BusinessCategory.HOLDING_COMPANY.value

    # Step 7: "ETF" in name — catches crypto/commodity ETFs
    # that don't file investment company forms (N-CSR, NPORT-P).
    # Placed after Investment Manager to avoid catching "ETF Managers Group" etc.
    if 'ETF' in name_upper:
        return BusinessCategory.ETF.value

    # Step 8: SIC 6200s + fund/trust name → ETF
    # Commodity trusts, crypto trusts, commodity fund LPs
    # Excludes royalty trusts (oil & gas income vehicles, not ETFs)
    if sic_int is not None and 6200 <= sic_int < 6300:
        if ('TRUST' in name_upper or 'FUND' in name_upper) and 'ROYALTY' not in name_upper:
            return BusinessCategory.ETF.value

    # Step 9: Default to operating company
    # If we have a SIC code and nothing above matched, the entity is an
    # operating company regardless of entity_type. This handles foreign/Canadian
    # filers (entity_type='other') that have clear SIC codes.
    if sic_int is not None:
        return BusinessCategory.OPERATING_COMPANY.value

    # entity_type='operating' with no SIC is still an operating company
    if entity_type in ('operating', '', None):
        return BusinessCategory.OPERATING_COMPANY.value

    # Step 10: Unknown (no SIC and non-operating entity_type)
    return BusinessCategory.UNKNOWN.value


def _classify_investment_company_type(
    entity_type: Optional[str],
    name: str
) -> str:
    """
    Classify the specific type of investment company.

    Args:
        entity_type: Entity type from SEC
        name: Company name

    Returns:
        'ETF', 'Mutual Fund', or 'Closed-End Fund'
    """
    name_upper = name.upper() if name else ''

    # ETF: Explicit in name
    if 'ETF' in name_upper:
        return BusinessCategory.ETF.value

    # ETF: Known fund families with "Trust" pattern
    for family in ETF_FUND_FAMILIES:
        if family in name_upper:
            # These families typically have ETFs when structured as trusts
            if 'TRUST' in name_upper:
                return BusinessCategory.ETF.value

    # Closed-End Fund: entity_type='other' and has investment forms
    if entity_type == 'other':
        # Could be CEF or ETF structured as 'other'
        # ETFs are more commonly 'other' with "Trust" in name
        if 'TRUST' in name_upper and 'FUND' not in name_upper:
            return BusinessCategory.ETF.value
        return BusinessCategory.CLOSED_END_FUND.value

    # Mutual Fund: entity_type='investment'
    if entity_type == 'investment':
        # Could be ETF or Mutual Fund
        if 'FUND' in name_upper and 'ETF' not in name_upper:
            return BusinessCategory.MUTUAL_FUND.value
        # Default to ETF for ambiguous investment entities
        return BusinessCategory.ETF.value

    # Fallback
    return BusinessCategory.MUTUAL_FUND.value


def sic_overrides_bdc(sic: Optional[int]) -> bool:
    """
    Check if SIC code definitively indicates a non-BDC category.

    BDC subsidiaries' 814- file numbers and N-2 forms can bleed into
    parent entities on EDGAR. If the entity's SIC code clearly indicates
    it's a bank, insurer, REIT, utility, manufacturer, etc., the BDC
    signal should be overridden.

    Args:
        sic: SIC code as integer

    Returns:
        True if SIC indicates a non-BDC business
    """
    if sic is None:
        return False

    # Definitive SIC-based categories take priority over BDC
    if sic in SIC_CODES_REIT:
        return True
    if sic in SIC_CODES_BANK:
        return True
    if sic in SIC_CODES_INSURANCE:
        return True
    if sic in SIC_CODES_SPAC:
        return True

    # Non-financial SIC codes (outside 6000-6999) are never BDCs
    if sic < 6000 or sic >= 7000:
        return True

    # SIC 6282 (Investment Advice) — parent asset managers are not BDCs
    # SIC 6211 (Security Brokers) — investment banks are not BDCs
    if sic in SIC_CODES_INVESTMENT_MANAGER:
        return True

    return False


def _is_bdc(
    entity_type: Optional[str],
    form_types: Set[str],
    sic: Optional[int] = None
) -> bool:
    """
    Check if company is a Business Development Company.

    BDCs are identified by filing BDC-specific forms (N-2, N-2ASR, N-23C-2)
    while having entity_type='operating'. SIC codes that definitively
    indicate another category (bank, insurance, REIT, non-financial) block
    BDC classification even if BDC forms are present.

    Args:
        entity_type: Entity type from SEC
        form_types: Set of form types filed by this company
        sic: SIC code as integer (used to block false positives)

    Returns:
        True if company appears to be a BDC
    """
    # BDCs file as operating companies
    if entity_type != 'operating':
        return False

    # SIC guardrail: definitive non-BDC SICs block BDC classification
    if sic is not None and sic_overrides_bdc(sic):
        return False

    # Check for BDC-specific forms only
    return bool(form_types & BDC_FORMS)


def _is_investment_manager(
    sic: Optional[int],
    form_types: Set[str],
    name_upper: str = ''
) -> bool:
    """
    Check if company is an investment manager/asset manager.

    Investment managers are identified by:
    - SIC 6282 (Investment Advice) — sufficient on its own
    - SIC 6211 (Security Brokers/Dealers) — sufficient unless name
      contains "Trust"/"Fund"/"ETF" (could be commodity ETF)
    - 13F-HR filing + investment SIC (always sufficient)

    By this point in the classification flow, entities that are BDCs,
    ETFs, Mutual Funds, Closed-End Funds, and SPACs have already been
    classified. So SIC 6282/6211 reaching here is a strong signal.

    Args:
        sic: SIC code as integer
        form_types: Set of form types filed by this company
        name_upper: Uppercased company name for heuristic checks

    Returns:
        True if company appears to be an investment manager
    """
    inv_sic = sic is not None and sic in SIC_CODES_INVESTMENT_MANAGER

    if not inv_sic:
        return False

    # With 13F: always Investment Manager (even if "Trust" in name)
    has_13f = bool(form_types & INVESTMENT_MANAGER_FORMS)
    if has_13f:
        return True

    # SIC 6282 alone is sufficient — these are investment advisers
    if sic == 6282:
        return True

    # SIC 6211 without 13F: only if not a trust/fund (could be commodity ETF)
    if sic == 6211:
        if 'TRUST' in name_upper or 'FUND' in name_upper:
            return False  # Let commodity trust/ETF logic handle it
        if 'ETF' in name_upper:
            return False  # Let ETF-in-name logic handle it
        return True

    return False
