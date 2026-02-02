"""
XBRL Standardization Package

Sector-aware learning and mapping generation for SEC filers.

This package provides tools to:
- Learn XBRL concept patterns from SEC filings grouped by sector
- Generate data-driven mappings from learned concept trees
- Apply sector-specific rules for financial statement standardization

Sectors are defined by business model and statement structure similarity,
not just SIC codes. This ensures companies with similar XBRL patterns
are grouped together for more accurate concept learning.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional

__version__ = "1.0.0"

# ==============================================================================
# SECTOR DEFINITIONS
# ==============================================================================
# Sectors group companies by financial statement structure and XBRL patterns.
# Each sector has:
# - name: Display name
# - sic_ranges: List of (start, end) SIC code ranges
# - key_concepts: Distinctive XBRL concepts that characterize this sector
# - min_companies: Minimum companies needed for statistical validity
# - default_threshold: Occurrence threshold for concept learning
# - description: What distinguishes this sector's financials

SECTORS: Dict[str, Dict] = {
    'financials_banking': {
        'name': 'Financials - Banking',
        'sic_ranges': [
            (6020, 6029),  # Commercial banks
            (6030, 6036),  # Savings institutions
            (6061, 6062),  # Federal credit unions
        ],
        'key_concepts': [
            'InterestIncomeExpenseNet',
            'NoninterestIncome',
            'NoninterestExpense',
            'ProvisionForLoanLossesExpensed'
        ],
        'min_companies': 50,
        'default_threshold': 0.30,  # Homogeneous sector
        'description': 'Commercial banks, thrifts, credit unions - interest-based revenue model'
    },

    'financials_securities': {
        'name': 'Financials - Securities & Investment',
        'sic_ranges': [
            (6200, 6289),  # Securities brokers, dealers
            (6720, 6799),  # Investment advisors, asset management
        ],
        'key_concepts': [
            'BrokerageCommissionsRevenue',
            'InvestmentBankingRevenue',
            'AssetManagementFees',
            'SecuritiesPrincipalTransactionsRevenue'
        ],
        'min_companies': 40,
        'default_threshold': 0.25,
        'description': 'Broker-dealers, investment banks, asset managers - fee-based revenue'
    },

    'financials_insurance': {
        'name': 'Financials - Insurance',
        'sic_ranges': [
            (6300, 6399),  # Insurance carriers
            (6411, 6411),  # Insurance agents/brokers
        ],
        'key_concepts': [
            'PremiumsEarnedNet',
            'PolicyholderBenefitsAndClaimsIncurred',
            'DeferredPolicyAcquisitionCostAmortizationExpense',
            'InsuranceServicesRevenue'
        ],
        'min_companies': 30,
        'default_threshold': 0.25,
        'description': 'Insurance companies - premium/claims model'
    },

    'financials_realestate': {
        'name': 'Financials - Real Estate & REITs',
        'sic_ranges': [
            (6500, 6553),  # Real estate operators
            (6798, 6799),  # REITs
        ],
        'key_concepts': [
            'OperatingLeasesIncomeStatementLeaseRevenue',
            'RealEstateRevenueNet',
            'RealEstateExpenseOperating',
            'PropertyManagementFeeRevenue'
        ],
        'min_companies': 40,
        'default_threshold': 0.20,
        'description': 'REITs, real estate operators - rental income model'
    },

    'energy_utilities': {
        'name': 'Energy - Utilities',
        'sic_ranges': [
            (4910, 4941),  # Electric, gas, water utilities
        ],
        'key_concepts': [
            'RegulatedAndUnregulatedOperatingRevenue',
            'UtilitiesOperatingExpense',
            'FuelCosts',
            'PowerPurchasedForResale'
        ],
        'min_companies': 50,
        'default_threshold': 0.25,
        'description': 'Regulated utilities - rate-based revenue'
    },

    'energy_oilgas': {
        'name': 'Energy - Oil & Gas',
        'sic_ranges': [
            (1300, 1399),  # Oil & gas extraction
            (2911, 2911),  # Petroleum refining
        ],
        'key_concepts': [
            'OilAndGasSalesRevenue',
            'ProductionCosts',
            'ExplorationExpense',
            'LeasingAndRentalRevenue'
        ],
        'min_companies': 40,
        'default_threshold': 0.22,
        'description': 'Oil & gas exploration, production, refining'
    },

    'industrials_general': {
        'name': 'Industrials - General Manufacturing',
        'sic_ranges': [
            (2000, 3999),  # Manufacturing (broad range)
        ],
        'key_concepts': [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'CostOfGoodsAndServicesSold',
            'SellingGeneralAndAdministrativeExpense',
            'GrossProfit'
        ],
        'min_companies': 100,
        'default_threshold': 0.30,
        'description': 'Manufacturing, standard COGS model - baseline for most companies'
    },

    'technology': {
        'name': 'Technology - Software & Hardware',
        'sic_ranges': [
            (3570, 3579),  # Computer equipment
            (7370, 7379),  # Software, IT services
        ],
        'key_concepts': [
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'ResearchAndDevelopmentExpense',
            'SoftwareRevenue',
            'CloudServicesRevenue'
        ],
        'min_companies': 60,
        'default_threshold': 0.28,
        'description': 'Technology companies, SaaS, hardware - R&D intensive'
    },

    'healthcare': {
        'name': 'Healthcare - Pharma & Services',
        'sic_ranges': [
            (2833, 2836),  # Pharmaceuticals
            (8000, 8099),  # Health services
        ],
        'key_concepts': [
            'HealthCareOrganizationRevenue',
            'ResearchAndDevelopmentExpense',
            'PatientServiceRevenue',
            'PharmaceuticalRevenue'
        ],
        'min_companies': 50,
        'default_threshold': 0.25,
        'description': 'Pharma, biotech, health services - R&D and specialized revenue'
    },

    'consumer': {
        'name': 'Consumer - Retail & Goods',
        'sic_ranges': [
            (5000, 5999),  # Retail
            (2000, 2399),  # Consumer goods manufacturing
        ],
        'key_concepts': [
            'SalesRevenueNet',
            'CostOfGoodsAndServicesSold',
            'SellingGeneralAndAdministrativeExpense',
            'RetailRelatedRevenue'
        ],
        'min_companies': 80,
        'default_threshold': 0.28,
        'description': 'Retail, consumer products - standard merchandise model'
    },
}

# Sector priority for overlay generation (most divergent from standard first)
# This order determines which overlays are built first and which sectors
# get priority when there are concept conflicts.
SECTOR_PRIORITY: List[str] = [
    'financials_banking',      # Most unique - interest-based model
    'financials_insurance',     # Very unique - premium/claims model
    'energy_utilities',         # Regulated, rate-based model
    'financials_securities',    # Unique fee structure
    'financials_realestate',    # REIT-specific concepts
    'energy_oilgas',           # Commodity-based
    'industrials_general',     # BASELINE (standard GAAP)
    'technology',              # Mostly standard + R&D
    'healthcare',              # Mostly standard + R&D
    'consumer',                # Standard retail model
]

# ==============================================================================
# DEFAULT CONFIGURATION
# ==============================================================================

# Default occurrence threshold for global (cross-sector) learning
DEFAULT_GLOBAL_THRESHOLD = 0.10  # 10% of companies must use a concept

# Default occurrence threshold for sector-specific learning
# (lower than global because sectors are more homogeneous)
DEFAULT_SECTOR_THRESHOLD = 0.10  # 10% within sector

# Number of companies to sample for learning runs
DEFAULT_GLOBAL_SAMPLE_SIZE = 500
DEFAULT_SECTOR_SAMPLE_SIZE = 150

# ==============================================================================
# DIRECTORY UTILITIES
# ==============================================================================

def get_package_dir() -> Path:
    """Get the xbrl_standardize package directory."""
    return Path(__file__).parent

def get_map_dir() -> Path:
    """Get the map directory for mapping files."""
    map_dir = get_package_dir() / "map"
    map_dir.mkdir(exist_ok=True)
    return map_dir

def get_overlays_dir() -> Path:
    """Get directory for sector overlay files."""
    overlays_dir = get_map_dir() / "map_overlays"
    overlays_dir.mkdir(exist_ok=True)
    return overlays_dir

def get_output_dir() -> Path:
    """
    Get output directory for generated files.

    Links to edgar/entity/training/output/ for consistency with
    existing learning infrastructure.
    """
    # Reference the edgar training output directory
    edgar_training_output = Path(__file__).parent.parent.parent / "training" / "output"
    if edgar_training_output.exists():
        return edgar_training_output

    # Fallback: create local output directory
    output_dir = get_package_dir() / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir

# ==============================================================================
# SECTOR UTILITIES
# ==============================================================================

def get_sector_info(sector_key: str) -> Optional[Dict]:
    """
    Get sector configuration by key.

    Args:
        sector_key: Sector identifier (e.g., 'financials_banking')

    Returns:
        Sector configuration dict or None if not found
    """
    return SECTORS.get(sector_key)

def get_all_sector_keys() -> List[str]:
    """Get list of all defined sector keys."""
    return list(SECTORS.keys())

def get_sector_by_sic(sic_code: int) -> Optional[str]:
    """
    Find sector key for a given SIC code.

    Args:
        sic_code: Standard Industrial Classification code

    Returns:
        Sector key or None if SIC not found in any sector
    """
    for sector_key, sector_info in SECTORS.items():
        for sic_start, sic_end in sector_info['sic_ranges']:
            if sic_start <= sic_code <= sic_end:
                return sector_key
    return None

def get_sic_ranges_for_sector(sector_key: str) -> List[Tuple[int, int]]:
    """
    Get SIC code ranges for a sector.

    Args:
        sector_key: Sector identifier

    Returns:
        List of (start, end) SIC code tuples
    """
    sector_info = get_sector_info(sector_key)
    return sector_info['sic_ranges'] if sector_info else []

def validate_sector_key(sector_key: str) -> bool:
    """
    Validate that a sector key exists.

    Args:
        sector_key: Sector identifier to validate

    Returns:
        True if valid sector key
    """
    return sector_key in SECTORS

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

__all__ = [
    # Version
    '__version__',

    # Sector definitions
    'SECTORS',
    'SECTOR_PRIORITY',

    # Configuration
    'DEFAULT_GLOBAL_THRESHOLD',
    'DEFAULT_SECTOR_THRESHOLD',
    'DEFAULT_GLOBAL_SAMPLE_SIZE',
    'DEFAULT_SECTOR_SAMPLE_SIZE',

    # Directory utilities
    'get_package_dir',
    'get_map_dir',
    'get_overlays_dir',
    'get_output_dir',

    # Sector utilities
    'get_sector_info',
    'get_all_sector_keys',
    'get_sector_by_sic',
    'get_sic_ranges_for_sector',
    'validate_sector_key',
]
