"""
Archetype Classifier

This module provides functions to classify companies into accounting archetypes
based on their SIC code, GICS sector, or balance sheet characteristics.

Classification Priority:
1. Config override (companies.yaml archetype field)
2. GICS sector/group
3. SIC code ranges
4. Balance sheet analysis (for bank sub-archetypes)
"""

import logging
from typing import Any, Dict, Optional, Tuple

from .definitions import (
    AccountingArchetype,
    BankSubArchetype,
    ARCHETYPE_DEFINITIONS,
    BANK_SUB_ARCHETYPE_DEFINITIONS,
)

logger = logging.getLogger(__name__)


def classify_company(
    ticker: Optional[str] = None,
    sic: Optional[str] = None,
    gics: Optional[str] = None,
    config: Optional[Dict] = None,
    facts_df: Any = None,
) -> Tuple[AccountingArchetype, Optional[BankSubArchetype]]:
    """
    Classify a company into an accounting archetype.

    Classification Priority:
    1. Config override (companies.yaml archetype field)
    2. GICS sector/group classification
    3. SIC code classification
    4. Default to Standard Industrial (A)

    Args:
        ticker: Company ticker symbol (for config lookup)
        sic: SIC code (4-digit string)
        gics: GICS code (2-8 digit string: sector, group, industry, sub-industry)
        config: Pre-loaded company config dict
        facts_df: XBRL facts DataFrame (for bank sub-archetype detection)

    Returns:
        Tuple of (AccountingArchetype, Optional[BankSubArchetype])
    """
    sub_archetype = None

    # 1. Check config override first
    if config and config.get('archetype_override', False):
        archetype_code = config.get('archetype', 'A')
        archetype = _code_to_archetype(archetype_code)

        # Check for bank sub-archetype in config
        if archetype == AccountingArchetype.B and config.get('bank_archetype'):
            sub_archetype = _string_to_sub_archetype(config['bank_archetype'])

        logger.debug(f"[{ticker}] Archetype from config: {archetype.value} (sub: {sub_archetype})")
        return archetype, sub_archetype

    # 2. Try GICS classification
    if gics:
        archetype = classify_by_gics(gics)
        if archetype:
            # If bank, detect sub-archetype
            if archetype == AccountingArchetype.B and facts_df is not None:
                sub_archetype = detect_bank_sub_archetype(facts_df, ticker)
            logger.debug(f"[{ticker}] Archetype from GICS {gics}: {archetype.value}")
            return archetype, sub_archetype

    # 3. Try SIC classification
    if sic:
        archetype = classify_by_sic(sic)
        # If bank, detect sub-archetype
        if archetype == AccountingArchetype.B and facts_df is not None:
            sub_archetype = detect_bank_sub_archetype(facts_df, ticker)
        logger.debug(f"[{ticker}] Archetype from SIC {sic}: {archetype.value}")
        return archetype, sub_archetype

    # 4. Default to Standard Industrial
    logger.debug(f"[{ticker}] Archetype defaulted to: {AccountingArchetype.A.value}")
    return AccountingArchetype.A, None


def classify_by_sic(sic: str) -> AccountingArchetype:
    """
    Classify by SIC code.

    Args:
        sic: 4-digit SIC code

    Returns:
        AccountingArchetype based on SIC code ranges
    """
    try:
        sic_int = int(sic)
    except (ValueError, TypeError):
        return AccountingArchetype.A

    # Check each archetype's SIC ranges
    for archetype, definition in ARCHETYPE_DEFINITIONS.items():
        for start, end in definition.get('sic_ranges', []):
            if start <= sic_int <= end:
                return archetype

    return AccountingArchetype.A


def classify_by_gics(gics: str) -> Optional[AccountingArchetype]:
    """
    Classify by GICS code.

    GICS codes are hierarchical:
    - 2 digits: Sector (e.g., "40" = Financials)
    - 4 digits: Industry Group (e.g., "4010" = Banks)
    - 6 digits: Industry
    - 8 digits: Sub-Industry

    Args:
        gics: GICS code (2-8 digits)

    Returns:
        AccountingArchetype based on GICS, or None if no match
    """
    if not gics:
        return None

    gics_str = str(gics).strip()

    # Extract sector (first 2 digits) and group (first 4 digits)
    sector = gics_str[:2] if len(gics_str) >= 2 else None
    group = gics_str[:4] if len(gics_str) >= 4 else None

    # Check each archetype
    for archetype, definition in ARCHETYPE_DEFINITIONS.items():
        # Check industry groups first (more specific)
        if group and 'gics_groups' in definition:
            if group in definition['gics_groups']:
                return archetype

        # Check sectors
        if sector and 'gics_sectors' in definition:
            if sector in definition['gics_sectors']:
                return archetype

    return None


def detect_bank_sub_archetype(
    facts_df: Any,
    ticker: Optional[str] = None
) -> BankSubArchetype:
    """
    Detect bank sub-archetype from balance sheet characteristics.

    Detection Logic:
    1. Check for dealer characteristics (high trading assets)
    2. Check for custodial characteristics (minimal STB)
    3. Check for hybrid characteristics (both commercial and dealer traits)
    4. Default to commercial

    Args:
        facts_df: XBRL facts DataFrame
        ticker: Optional ticker for logging

    Returns:
        BankSubArchetype
    """
    if facts_df is None or len(facts_df) == 0:
        return BankSubArchetype.COMMERCIAL

    # Helper to get fact value
    def get_value(concept: str) -> float:
        if facts_df is None or len(facts_df) == 0:
            return 0.0

        concept_lower = concept.lower()
        mask = facts_df['concept'].str.lower().str.contains(concept_lower, na=False)
        matches = facts_df[mask]

        if len(matches) == 0:
            return 0.0

        # Filter non-dimensional
        if 'full_dimension_label' in matches.columns:
            matches = matches[matches['full_dimension_label'].isna()]

        if len(matches) == 0:
            return 0.0

        if 'numeric_value' in matches.columns:
            values = matches['numeric_value'].dropna()
            if len(values) > 0:
                return float(values.iloc[0])

        return 0.0

    # Get key balance sheet items
    total_assets = get_value('Assets') or 1  # Avoid division by zero
    trading_assets = get_value('TradingAssets')
    loans = get_value('LoansAndLeasesReceivable') or get_value('LoansReceivable')
    deposits = get_value('Deposits')
    stb = get_value('ShortTermBorrowings')
    unsecured_stb = get_value('UnsecuredShortTermBorrowings')

    # Calculate ratios
    trading_ratio = trading_assets / total_assets if total_assets > 0 else 0
    loan_ratio = loans / total_assets if total_assets > 0 else 0

    # Detection rules
    if trading_ratio > 0.15:
        # High trading assets indicates dealer
        if unsecured_stb > 0:
            logger.debug(f"[{ticker}] Bank sub-archetype: DEALER (trading_ratio={trading_ratio:.2%})")
            return BankSubArchetype.DEALER

    if stb == 0 or (stb > 0 and stb < total_assets * 0.01):
        # Minimal STB indicates custodial
        logger.debug(f"[{ticker}] Bank sub-archetype: CUSTODIAL (minimal STB)")
        return BankSubArchetype.CUSTODIAL

    if trading_ratio > 0.05 and loan_ratio > 0.20:
        # Significant both trading and loans indicates hybrid
        logger.debug(f"[{ticker}] Bank sub-archetype: HYBRID (trading={trading_ratio:.2%}, loans={loan_ratio:.2%})")
        return BankSubArchetype.HYBRID

    if loan_ratio > 0.30:
        # High loan book indicates commercial
        logger.debug(f"[{ticker}] Bank sub-archetype: COMMERCIAL (loan_ratio={loan_ratio:.2%})")
        return BankSubArchetype.COMMERCIAL

    # Default to regional (treated like commercial)
    logger.debug(f"[{ticker}] Bank sub-archetype: REGIONAL (default)")
    return BankSubArchetype.REGIONAL


def _code_to_archetype(code: str) -> AccountingArchetype:
    """Convert archetype code (A-E) to enum."""
    code_map = {
        'A': AccountingArchetype.A,
        'B': AccountingArchetype.B,
        'C': AccountingArchetype.C,
        'D': AccountingArchetype.D,
        'E': AccountingArchetype.E,
        'standard_industrial': AccountingArchetype.A,
        'inverted_financial': AccountingArchetype.B,
        'intangible_digital': AccountingArchetype.C,
        'asset_passthrough': AccountingArchetype.D,
        'probabilistic_liability': AccountingArchetype.E,
    }
    return code_map.get(code.upper() if len(code) == 1 else code, AccountingArchetype.A)


def _string_to_sub_archetype(name: str) -> BankSubArchetype:
    """Convert sub-archetype string to enum."""
    name_map = {
        'commercial': BankSubArchetype.COMMERCIAL,
        'dealer': BankSubArchetype.DEALER,
        'custodial': BankSubArchetype.CUSTODIAL,
        'hybrid': BankSubArchetype.HYBRID,
        'regional': BankSubArchetype.REGIONAL,
    }
    return name_map.get(name.lower(), BankSubArchetype.COMMERCIAL)
