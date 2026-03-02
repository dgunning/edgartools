"""
Archetype Definitions

This module defines the five accounting archetypes and their characteristics.

Each archetype specifies:
- SIC code ranges
- GICS sector/group codes
- Default strategies for each metric
- Industry-specific metric exclusions
"""

from enum import Enum
from typing import Dict, List, Any, Optional


class AccountingArchetype(Enum):
    """
    Five accounting archetypes for XBRL extraction strategy selection.

    These archetypes represent fundamentally different accounting models
    that require different extraction strategies.
    """
    A = "standard_industrial"    # ~60% - manufacturing, retail, tech hardware
    B = "inverted_financial"     # Banks - inverted P&L, interest is revenue
    C = "intangible_digital"     # SaaS, Pharma - high intangibles, R&D capitalization
    D = "asset_passthrough"      # REITs - property-based, FFO instead of EPS
    E = "probabilistic_liability"  # Insurance - underwriting, claims reserves


class BankSubArchetype(Enum):
    """
    Bank sub-archetypes for fine-grained extraction strategy selection.

    These sub-archetypes capture the operational differences between
    different types of banks within Archetype B.
    """
    COMMERCIAL = "commercial"  # WFC, USB, PNC - traditional banks
    DEALER = "dealer"          # GS, MS - investment banks
    CUSTODIAL = "custodial"    # BK, STT - custody banks
    HYBRID = "hybrid"          # JPM, BAC, C - universal banks
    REGIONAL = "regional"      # Smaller banks - fallback to commercial


# =============================================================================
# ARCHETYPE DEFINITIONS
# =============================================================================

ARCHETYPE_DEFINITIONS: Dict[AccountingArchetype, Dict[str, Any]] = {
    AccountingArchetype.A: {
        "name": "Standard Industrial",
        "description": "Traditional industrial companies with standard P&L structure",
        "coverage_pct": 60,
        "sic_ranges": [
            (1000, 5999),   # Agriculture, Mining, Construction, Manufacturing, Wholesale, Retail
            (7000, 7299),   # Hotels, Services (non-tech)
            (7500, 7599),   # Auto repair
            (7800, 7999),   # Entertainment
            (8000, 8999),   # Health, Legal, Education, Engineering
            (9000, 9999),   # Government (rare)
        ],
        "gics_sectors": [
            "10",  # Energy
            "15",  # Materials
            "20",  # Industrials
            "25",  # Consumer Discretionary
            "30",  # Consumer Staples
            "35",  # Health Care (non-pharma portions)
            "50",  # Communication Services (non-digital)
        ],
        "strategies": {
            "ShortTermDebt": "standard_debt",
            "Capex": "standard_capex",
            "OperatingIncome": "standard_opinc",
            "CashAndEquivalents": "standard_cash",
        },
        "excluded_metrics": [],
        "validation_tolerance_pct": 15.0,
    },

    AccountingArchetype.B: {
        "name": "Inverted Financial",
        "description": "Banks with inverted P&L - interest income is primary revenue",
        "coverage_pct": 8,
        "sic_ranges": [
            (6020, 6029),   # Commercial Banks
            (6035, 6036),   # Savings Institutions
            (6099, 6099),   # Functions Related to Deposit Banking
            (6111, 6111),   # Federal Credit Agencies
            (6153, 6153),   # Short-Term Business Credit
            (6159, 6159),   # Miscellaneous Business Credit
            (6199, 6199),   # Finance Services (AXP)
            (6200, 6211),   # Security Brokers, Dealers
            (6282, 6282),   # Investment Advice
        ],
        "gics_sectors": ["40"],  # Financials
        "gics_groups": [
            "4010",  # Banks
            "4020",  # Diversified Financials
        ],
        "strategies": {
            "ShortTermDebt": ["commercial_debt", "dealer_debt", "custodial_debt", "hybrid_debt"],
            "Capex": None,  # Excluded
            "OperatingIncome": "ppnr",  # Pre-Provision Net Revenue
            "CashAndEquivalents": "bank_cash_gaap",
        },
        "excluded_metrics": ["COGS", "SGA", "OperatingIncome", "Capex"],
        "validation_tolerance_pct": 20.0,
        "sub_archetypes": ["commercial", "dealer", "custodial", "hybrid", "regional"],
    },

    AccountingArchetype.C: {
        "name": "Intangible Digital",
        "description": "High intangibles, R&D capitalization - SaaS, Pharma, Tech",
        "coverage_pct": 15,
        "sic_ranges": [
            (2833, 2836),   # Pharmaceuticals
            (3570, 3579),   # Computer Equipment
            (3674, 3674),   # Semiconductors
            (7370, 7379),   # Computer Services (SaaS, Software)
            (7389, 7389),   # Business Services (V, MA - payment networks)
        ],
        "gics_sectors": ["45"],  # Information Technology
        "gics_groups": [
            "3520",  # Pharmaceuticals & Biotechnology
            "4520",  # Software & Services
        ],
        "strategies": {
            "ShortTermDebt": "standard_debt",
            "Capex": "saas_capex",  # Software capitalization aware
            "OperatingIncome": "standard_opinc",
            "CashAndEquivalents": "standard_cash",
        },
        "excluded_metrics": [],
        "validation_tolerance_pct": 15.0,
        "special_handling": {
            "R&D": "May be capitalized instead of expensed",
            "Intangibles": "High intangible assets",
            "SubscriptionRevenue": "Deferred revenue patterns",
        },
    },

    AccountingArchetype.D: {
        "name": "Asset Passthrough",
        "description": "REITs - property-based income, FFO instead of EPS",
        "coverage_pct": 5,
        "sic_ranges": [
            (6500, 6553),   # Real Estate
            (6798, 6798),   # Real Estate Investment Trusts
        ],
        "gics_sectors": ["60"],  # Real Estate
        "gics_groups": ["6010"],  # Equity REITs
        "strategies": {
            "ShortTermDebt": "standard_debt",
            "Capex": "standard_capex",
            "OperatingIncome": "noi",  # Net Operating Income
            "CashAndEquivalents": "standard_cash",
        },
        "excluded_metrics": [],
        "validation_tolerance_pct": 15.0,
        "special_handling": {
            "FFO": "Funds From Operations is primary metric",
            "PropertyExpenses": "Uses NOI instead of Operating Income",
            "Depreciation": "Large non-cash charges",
        },
    },

    AccountingArchetype.E: {
        "name": "Probabilistic Liability",
        "description": "Insurance - underwriting income, loss reserves",
        "coverage_pct": 5,
        "sic_ranges": [
            (6300, 6399),   # Insurance Carriers
            (6411, 6411),   # Insurance Agents
        ],
        "gics_sectors": ["40"],  # Financials
        "gics_groups": ["4030"],  # Insurance
        "strategies": {
            "ShortTermDebt": "standard_debt",
            "Capex": None,  # Often excluded
            "OperatingIncome": "underwriting",  # Underwriting income
            "CashAndEquivalents": "standard_cash",
        },
        "excluded_metrics": ["COGS"],
        "validation_tolerance_pct": 20.0,
        "special_handling": {
            "LossReserves": "Probabilistic liability estimation",
            "PremiumRevenue": "Earned vs Written premiums",
            "CombinedRatio": "Key profitability metric",
        },
    },
}


# =============================================================================
# BANK SUB-ARCHETYPE DEFINITIONS
# =============================================================================

BANK_SUB_ARCHETYPE_DEFINITIONS: Dict[BankSubArchetype, Dict[str, Any]] = {
    BankSubArchetype.COMMERCIAL: {
        "name": "Commercial Bank",
        "description": "Traditional banks with deposit-taking and lending",
        "examples": ["WFC", "USB", "PNC"],
        "sic_codes": [6020, 6022],
        "characteristics": {
            "high_loan_book": True,
            "repos_bundled_in_stb": True,
            "trading_minimal": True,
        },
        "strategy": "commercial_debt",
        "strategy_params": {
            "subtract_repos_from_stb": True,
            "subtract_trading_from_stb": True,
            "safe_fallback": True,
        },
    },

    BankSubArchetype.DEALER: {
        "name": "Dealer/Investment Bank",
        "description": "Investment banks with trading and market-making",
        "examples": ["GS", "MS"],
        "sic_codes": [6211],
        "characteristics": {
            "high_trading_assets": True,
            "repos_separate_line_item": True,
            "uses_unsecured_stb_tag": True,
        },
        "strategy": "dealer_debt",
        "strategy_params": {
            "use_unsecured_stb": True,
            "safe_fallback": True,
        },
    },

    BankSubArchetype.CUSTODIAL: {
        "name": "Custodial Bank",
        "description": "Custody and asset servicing banks",
        "examples": ["BK", "STT"],
        "sic_codes": [6022, 6282],
        "characteristics": {
            "minimal_stb": True,
            "repos_as_financing": True,
            "never_fuzzy_match": True,
        },
        "strategy": "custodial_debt",
        "strategy_params": {
            "repos_as_debt": False,
            "safe_fallback": False,  # CRITICAL: Never fuzzy match
        },
    },

    BankSubArchetype.HYBRID: {
        "name": "Hybrid/Universal Bank",
        "description": "Universal banks with both commercial and investment operations",
        "examples": ["JPM", "BAC", "C"],
        "sic_codes": [6020, 6021],
        "characteristics": {
            "commercial_and_dealer": True,
            "check_nesting_before_subtract": True,
            "repos_often_separate": True,
        },
        "strategy": "hybrid_debt",
        "strategy_params": {
            "subtract_repos_from_stb": False,
            "check_nesting": True,
            "safe_fallback": True,
        },
    },

    BankSubArchetype.REGIONAL: {
        "name": "Regional Bank",
        "description": "Smaller regional banks - fallback to commercial rules",
        "examples": [],
        "sic_codes": [6022],
        "characteristics": {
            "smaller_balance_sheet": True,
            "traditional_banking": True,
        },
        "strategy": "commercial_debt",
        "strategy_params": {
            "subtract_repos_from_stb": True,
            "subtract_trading_from_stb": True,
            "safe_fallback": True,
        },
    },
}


def get_archetype_definition(archetype: AccountingArchetype) -> Dict[str, Any]:
    """
    Get the full definition for an archetype.

    Args:
        archetype: The accounting archetype

    Returns:
        Dictionary with archetype definition including strategies and exclusions
    """
    return ARCHETYPE_DEFINITIONS.get(archetype, ARCHETYPE_DEFINITIONS[AccountingArchetype.A])


def get_bank_sub_archetype_definition(sub_archetype: BankSubArchetype) -> Dict[str, Any]:
    """
    Get the full definition for a bank sub-archetype.

    Args:
        sub_archetype: The bank sub-archetype

    Returns:
        Dictionary with sub-archetype definition including strategy and params
    """
    return BANK_SUB_ARCHETYPE_DEFINITIONS.get(
        sub_archetype,
        BANK_SUB_ARCHETYPE_DEFINITIONS[BankSubArchetype.COMMERCIAL]
    )
