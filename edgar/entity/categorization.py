"""
Company business category classification.

This module provides classification of SEC filers into business categories
based on SIC codes, form types, entity type, and name patterns.

The classification uses a multi-signal approach with priority hierarchy:
1. Definitive SIC codes (REIT, SPAC, Bank, Insurance)
2. Investment company forms (ETF, Mutual Fund, Closed-End Fund)
3. BDC indicators (N-2 forms, name patterns)
4. Investment manager indicators (13F, SIC)
5. Holding company (SIC 6719)
6. Default to Operating Company
"""

from enum import Enum
from typing import Optional, Set, Union

__all__ = [
    'BusinessCategory',
    'classify_business_category',
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


# =============================================================================
# Helper Functions
# =============================================================================

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

    # Step 3: Check BDC signals (operating company with BDC forms or name pattern)
    if _is_bdc(entity_type, name, form_types):
        return BusinessCategory.BDC.value

    # Step 4: Check investment manager signals
    if _is_investment_manager(sic_int, form_types):
        return BusinessCategory.INVESTMENT_MANAGER.value

    # Step 5: Check holding company
    if sic_int is not None and sic_int in SIC_CODES_HOLDING_COMPANY:
        return BusinessCategory.HOLDING_COMPANY.value

    # Step 6: Default to operating company
    # Most SEC filers are operating companies unless classified otherwise
    # entity_type='operating' or missing/empty entity_type defaults to Operating Company
    if entity_type in ('operating', '', None):
        return BusinessCategory.OPERATING_COMPANY.value

    # Step 7: Unknown (rare - only for explicitly non-operating entities without other classification)
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


def _is_bdc(
    entity_type: Optional[str],
    name: str,
    form_types: Set[str]
) -> bool:
    """
    Check if company is a Business Development Company.

    BDCs are unique:
    - Entity type is 'operating' (not 'investment')
    - File some investment company forms (N-2, N-23C-2)
    - Usually have "Capital Corp" in name

    Args:
        entity_type: Entity type from SEC
        name: Company name
        form_types: Set of form types filed by this company

    Returns:
        True if company appears to be a BDC
    """
    # BDCs file as operating companies
    if entity_type != 'operating':
        return False

    # Check for BDC-specific forms
    has_bdc_forms = bool(form_types & BDC_FORMS)
    if has_bdc_forms:
        return True

    # Name pattern: "Capital Corp" or "Capital Corporation"
    name_upper = name.upper() if name else ''
    if 'CAPITAL CORP' in name_upper:
        return True

    return False


def _is_investment_manager(
    sic: Optional[int],
    form_types: Set[str]
) -> bool:
    """
    Check if company is an investment manager/asset manager.

    Investment managers:
    - File 13F-HR if managing $100M+ in equities
    - SIC 6211 (Security Brokers) or 6282 (Investment Advice)

    Args:
        sic: SIC code as integer
        form_types: Set of form types filed by this company

    Returns:
        True if company appears to be an investment manager
    """
    # Check for 13F filing (institutional investment managers)
    has_13f = bool(form_types & INVESTMENT_MANAGER_FORMS)

    # Check for investment-related SIC codes
    inv_sic = sic is not None and sic in SIC_CODES_INVESTMENT_MANAGER

    # Strong signal: both 13F and investment SIC
    if has_13f and inv_sic:
        return True

    # Investment SIC alone is a signal
    if inv_sic:
        return True

    return False
