"""
Dimension classification for XBRL statement filtering.

This module provides utilities to classify dimension axes as "breakdown" vs "classification"
dimensions, enabling smart filtering for include_dimensions=False scenarios.

**Classification Dimensions** (face values):
    Dimensions that distinguish types on the face of the statement.
    Examples: PropertyPlantAndEquipmentByTypeAxis, RelatedPartyTransactionsByRelatedPartyAxis
    These should SHOW when include_dimensions=False.

**Breakdown Dimensions** (detail):
    Dimensions that add drill-down detail beyond the face presentation.
    Examples: StatementGeographicalAxis, FairValueByFairValueHierarchyLevelAxis
    These should HIDE when include_dimensions=False.

Uses a hybrid approach:
1. Explicit BREAKDOWN_AXES set for known breakdown dimensions
2. Pattern-based detection (BREAKDOWN_PATTERNS) for scalability
3. Explicit FACE_AXES set for dimensions that should always show

Issue #569: URI balance sheet was missing PPE values because ALL dimensional items
were being filtered, including face-level classification dimensions.
"""

import re
from typing import Dict, List, Any, Set, Optional

# =============================================================================
# EXPLICIT AXIS LISTS
# =============================================================================

# Axes that are ALWAYS breakdown (notes disclosure, not face)
# These are checked first, before pattern matching
BREAKDOWN_AXES: Set[str] = {
    # Geographic breakdowns
    'StatementGeographicalAxis',
    'srt:StatementGeographicalAxis',

    # Business segment breakdowns
    'StatementBusinessSegmentsAxis',
    'srt:StatementBusinessSegmentsAxis',

    # Consolidation detail
    'ConsolidationItemsAxis',
    'srt:ConsolidatedEntitiesAxis',
    'ConsolidatedEntitiesAxis',

    # Acquisition-specific detail
    'BusinessAcquisitionAxis',
    'AssetAcquisitionAxis',

    # Legal entity breakdowns
    'LegalEntityAxis',
    'dei:LegalEntityAxis',

    # Reporting unit breakdown (typically for goodwill impairment)
    'ReportingUnitAxis',

    # Intangible asset type breakdowns (notes disclosure, not face)
    'FiniteLivedIntangibleAssetsByMajorClassAxis',
    'IndefiniteLivedIntangibleAssetsByMajorClassAxis',

    # Equity method investment breakdowns (notes disclosure, not face)
    'EquityMethodInvestmentNonconsolidatedInvesteeAxis',
    'srt:ScheduleOfEquityMethodInvestmentEquityMethodInvesteeNameAxis',

    # Equity component axis - context-dependent (see STATEMENT_STRUCTURAL_AXES)
    'StatementEquityComponentsAxis',
}

# Axes that should ALWAYS show on face (classification dimensions)
# These override pattern matching
FACE_AXES: Set[str] = {
    # Related party transactions - shows on face for debt, receivables, etc.
    'RelatedPartyTransactionsByRelatedPartyAxis',

    # PPE by type - shows on face for rental companies, etc.
    'PropertyPlantAndEquipmentByTypeAxis',

    # Debt instrument type - sometimes on face
    'LongtermDebtTypeAxis',
    'ShortTermDebtTypeAxis',

    # Class of stock - shows on face
    'StatementClassOfStockAxis',
}

# =============================================================================
# PATTERN-BASED DETECTION
# =============================================================================

# Regex patterns that indicate BREAKDOWN dimensions (notes disclosure)
# If an axis matches any of these patterns and is not in FACE_AXES, it's a breakdown
BREAKDOWN_PATTERNS: List[str] = [
    # Fair value disclosures
    r'FairValue.*Axis',
    r'.*HierarchyLevelAxis',
    r'.*MeasurementBasisAxis',
    r'.*MeasurementFrequencyAxis',

    # Financial instrument details
    r'FinancialInstrumentAxis',
    r'.*PortfolioSegmentAxis',

    # Collateral and pledging
    r'PledgedStatusAxis',
    r'RecourseStatusAxis',

    # Accounting changes
    r'CumulativeEffect.*Axis',
    r'AdjustmentsForNewAccountingPronouncementsAxis',

    # Counterparty and concentration
    r'CounterpartyNameAxis',
    r'ConcentrationRisk.*Axis',

    # Restructuring
    r'RestructuringPlanAxis',

    # Industry/security classification
    r'EquitySecuritiesBy.*Axis',
    r'.*ByLiabilityClassAxis',
]

# Compile patterns for efficiency
_COMPILED_BREAKDOWN_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BREAKDOWN_PATTERNS]

# =============================================================================
# STATEMENT-SPECIFIC OVERRIDES
# =============================================================================

# Axes that are STRUCTURAL (not breakdown) for specific statement types
STATEMENT_STRUCTURAL_AXES: Dict[str, Set[str]] = {
    # Statement of Equity uses EquityComponentsAxis as columns
    'StatementOfEquity': {'StatementEquityComponentsAxis'},
    'StatementOfStockholdersEquity': {'StatementEquityComponentsAxis'},
    'StatementOfChangesInEquity': {'StatementEquityComponentsAxis'},
}

# =============================================================================
# CLASSIFICATION FUNCTIONS
# =============================================================================

def _matches_breakdown_pattern(axis_name: str) -> bool:
    """Check if an axis name matches any breakdown pattern."""
    for pattern in _COMPILED_BREAKDOWN_PATTERNS:
        if pattern.search(axis_name):
            return True
    return False


def _normalize_axis_name(dimension: str) -> tuple:
    """
    Extract prefix and axis name from dimension string.

    Returns:
        Tuple of (prefix, axis_name) where prefix may be empty string
    """
    if ':' in dimension:
        prefix, axis_name = dimension.split(':', 1)
        return prefix, axis_name
    return '', dimension


def is_breakdown_dimension(item: Dict[str, Any], statement_type: Optional[str] = None) -> bool:
    """
    Determine if a dimensional item is a breakdown (detail) vs classification (face).

    Uses a three-tier approach:
    1. Check FACE_AXES - if axis is here, it's NOT a breakdown (show on face)
    2. Check BREAKDOWN_AXES - if axis is here, it IS a breakdown (hide)
    3. Check BREAKDOWN_PATTERNS - if axis matches a pattern, it's a breakdown

    Some axes are context-dependent:
    - StatementEquityComponentsAxis is a BREAKDOWN on Balance Sheet
    - StatementEquityComponentsAxis is STRUCTURAL on Statement of Equity

    Args:
        item: Raw statement item dictionary with 'dimension_metadata' key
        statement_type: Optional statement type for context-aware filtering

    Returns:
        True if this is a breakdown dimension (should hide with include_dimensions=False)
        False if this is a classification dimension (should show on face)
    """
    dim_metadata = item.get('dimension_metadata', [])
    if not dim_metadata:
        return False

    # Get structural axes for this statement type (if any)
    structural_axes = STATEMENT_STRUCTURAL_AXES.get(statement_type, set()) if statement_type else set()

    for dim_info in dim_metadata:
        dimension = dim_info.get('dimension', '')
        prefix, axis_name = _normalize_axis_name(dimension)

        # Check if this is a structural axis for this statement type
        if axis_name in structural_axes:
            continue  # Not a breakdown for this statement

        # 1. Check FACE_AXES first (should show on face)
        if axis_name in FACE_AXES:
            continue  # This is a face dimension, check next

        # 2. Check explicit BREAKDOWN_AXES
        if axis_name in BREAKDOWN_AXES:
            return True
        if f'{prefix}:{axis_name}' in BREAKDOWN_AXES:
            return True

        # 3. Check pattern-based detection
        if _matches_breakdown_pattern(axis_name):
            return True

    return False


def get_dimension_classification(item: Dict[str, Any], statement_type: Optional[str] = None) -> str:
    """
    Get a human-readable classification of a dimensional item.

    Args:
        item: Raw statement item dictionary with 'dimension_metadata' key
        statement_type: Optional statement type for context-aware classification

    Returns:
        One of: 'face', 'breakdown', 'none'
    """
    if not item.get('is_dimension', False):
        return 'none'

    if is_breakdown_dimension(item, statement_type=statement_type):
        return 'breakdown'

    return 'face'
