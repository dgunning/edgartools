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

Uses a tiered approach:
1. **Definition Linkbase (Authoritative)**: If XBRL and role_uri are provided,
   check hypercube definitions to determine if dimension is valid for this role.
   Dimensions declared in the definition linkbase are face values.
   Confidence: HIGH
2. **Heuristic Fallback**: When definition linkbase unavailable, use:
   - Explicit BREAKDOWN_AXES set for known breakdown dimensions
   - Pattern-based detection (BREAKDOWN_PATTERNS) for scalability
   - Explicit FACE_AXES set for dimensions that should always show
   Confidence: MEDIUM (explicit lists) or LOW (pattern matching)

Issue #569: URI balance sheet was missing PPE values because ALL dimensional items
were being filtered, including face-level classification dimensions.

Issue #577 / edgartools-cf9o: Connect definition linkbase to dimension filtering.
Many filers (Boeing, Carrier, GD, etc.) report face values ONLY through dimensional
XBRL. The definition linkbase is the authoritative source for which dimensions are
valid for each statement.

Issue edgartools-u649: Enhanced heuristics for incomplete definition linkbase.
Expanded axis lists based on empirical patterns from GH-577 test cases.
Added confidence scoring to track classification source.
"""

import re
from enum import Enum
from typing import Dict, List, Any, Set, Optional, Tuple


class DimensionConfidence(Enum):
    """Confidence level for dimension classification."""
    HIGH = "high"       # From definition linkbase (authoritative)
    MEDIUM = "medium"   # From explicit FACE_AXES or BREAKDOWN_AXES lists
    LOW = "low"         # From pattern matching
    NONE = "none"       # No classification applied (non-dimensional)

# =============================================================================
# EXPLICIT AXIS LISTS
# =============================================================================

# Axes that are ALWAYS breakdown (notes disclosure, not face)
# These are checked first, before pattern matching
# Expanded based on GH-577 empirical analysis (edgartools-u649)
BREAKDOWN_AXES: Set[str] = {
    # Geographic breakdowns
    'StatementGeographicalAxis',
    'srt:StatementGeographicalAxis',
    'GeographicDistributionAxis',

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

    # Customer and concentration breakdowns (notes disclosure)
    'MajorCustomersAxis',
    'srt:MajorCustomersAxis',
    'ConcentrationRiskByTypeAxis',
    'ConcentrationRiskByBenchmarkAxis',

    # Restatement and accounting changes (notes disclosure)
    'RestatementAxis',
    'ChangeInAccountingEstimateByTypeAxis',
    'ReclassificationOutOfAccumulatedOtherComprehensiveIncomeAxis',

    # Contingency and litigation (notes disclosure)
    'LossContingenciesByNatureOfContingencyAxis',

    # Impairment detail (notes disclosure)
    'ImpairedLongLivedAssetsHeldAndUsedByTypeAxis',

    # Tax authority (notes disclosure)
    'IncomeTaxAuthorityAxis',

    # Retirement and pension plan breakdowns (notes disclosure)
    'RetirementPlanTypeAxis',
    'RetirementPlanSponsorLocationAxis',
    'RetirementPlanTaxStatusAxis',
    'RetirementPlanNameAxis',

    # Disposal groups (notes disclosure)
    'DisposalGroupClassificationAxis',
    'IncomeStatementBalanceSheetAndAdditionalDisclosuresByDisposalGroupsIncludingDiscontinuedOperationsAxis',

    # Other detailed breakdowns
    'OtherComprehensiveIncomeLocationAxis',
    'CreditFacilityAxis',
    'FuelTypeAxis',
    'OwnershipAxis',
    'AccountsNotesLoansAndFinancingReceivablesByLegalEntityOfCounterpartyTypeAxis',
}

# Axes that should ALWAYS show on face (classification dimensions)
# These override pattern matching
# Expanded based on GH-577 empirical analysis (edgartools-u649)
FACE_AXES: Set[str] = {
    # Product/Service breakdown - very commonly used for face values
    # (Also handled by definition linkbase, but included as heuristic fallback)
    'ProductOrServiceAxis',
    'srt:ProductOrServiceAxis',

    # Related party transactions - shows on face for debt, receivables, etc.
    'RelatedPartyTransactionsByRelatedPartyAxis',

    # PPE by type - shows on face for rental companies, etc.
    'PropertyPlantAndEquipmentByTypeAxis',

    # Debt instrument type - shows on face for debt schedule
    'LongtermDebtTypeAxis',
    'ShortTermDebtTypeAxis',
    'DebtInstrumentAxis',

    # Class of stock - shows on face
    'StatementClassOfStockAxis',

    # Contract type - shows on face for defense contractors
    'ContracttypeAxis',

    # Major programs - shows on face for defense contractors
    'MajorProgramsAxis',

    # Contract pricing basis - sometimes on face for revenue
    'ContractWithCustomerBasisOfPricingAxis',
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


def is_breakdown_dimension(item: Dict[str, Any], statement_type: Optional[str] = None,
                           xbrl: Optional[Any] = None, role_uri: Optional[str] = None) -> bool:
    """
    Determine if a dimensional item is a breakdown (detail) vs classification (face).

    Uses a tiered approach:

    **Tier 1 - Definition Linkbase (Authoritative)**:
    If xbrl and role_uri are provided and definition linkbase data exists,
    check if the dimension is declared valid for this role's hypercubes.
    Dimensions declared in the definition linkbase are face values, not breakdowns.

    **Tier 2 - Heuristic Fallback**:
    When definition linkbase unavailable:
    1. Check FACE_AXES - if axis is here, it's NOT a breakdown (show on face)
    2. Check BREAKDOWN_AXES - if axis is here, it IS a breakdown (hide)
    3. Check BREAKDOWN_PATTERNS - if axis matches a pattern, it's a breakdown

    Some axes are context-dependent:
    - StatementEquityComponentsAxis is a BREAKDOWN on Balance Sheet
    - StatementEquityComponentsAxis is STRUCTURAL on Statement of Equity

    Args:
        item: Raw statement item dictionary with 'dimension_metadata' key
        statement_type: Optional statement type for context-aware filtering
        xbrl: Optional XBRL object for definition linkbase-based checking
        role_uri: Optional role URI for definition linkbase lookup

    Returns:
        True if this is a breakdown dimension (should hide with include_dimensions=False)
        False if this is a classification dimension (should show on face)
    """
    dim_metadata = item.get('dimension_metadata', [])
    if not dim_metadata:
        return False

    # Get structural axes for this statement type (if any)
    structural_axes = STATEMENT_STRUCTURAL_AXES.get(statement_type, set()) if statement_type else set()

    # Check if we can use definition linkbase (Tier 1)
    use_definition_linkbase = (
        xbrl is not None and
        role_uri is not None and
        hasattr(xbrl, 'has_definition_linkbase_for_role') and
        xbrl.has_definition_linkbase_for_role(role_uri)
    )

    for dim_info in dim_metadata:
        dimension = dim_info.get('dimension', '')
        prefix, axis_name = _normalize_axis_name(dimension)

        # Check if this is a structural axis for this statement type
        if axis_name in structural_axes:
            continue  # Not a breakdown for this statement

        # TIER 1: Definition Linkbase (Authoritative)
        # If dimension is declared valid for this role's hypercubes, it's a face value
        if use_definition_linkbase:
            if xbrl.is_dimension_valid_for_role(dimension, role_uri):
                continue  # Dimension is valid per definition linkbase - not a breakdown
            else:
                # Dimension NOT in definition linkbase for this role
                # This is a breakdown dimension (or note disclosure dimension)
                return True

        # TIER 2: Heuristic Fallback (when no definition linkbase)
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


def classify_dimension_with_confidence(
    item: Dict[str, Any],
    statement_type: Optional[str] = None,
    xbrl: Optional[Any] = None,
    role_uri: Optional[str] = None
) -> Tuple[str, DimensionConfidence, str]:
    """
    Classify a dimensional item and return classification with confidence.

    This function provides detailed information about how a dimension was
    classified, including the confidence level and the source of the decision.

    Args:
        item: Raw statement item dictionary with 'dimension_metadata' key
        statement_type: Optional statement type for context-aware filtering
        xbrl: Optional XBRL object for definition linkbase-based checking
        role_uri: Optional role URI for definition linkbase lookup

    Returns:
        Tuple of (classification, confidence, reason):
        - classification: 'face', 'breakdown', or 'none'
        - confidence: DimensionConfidence enum value
        - reason: Human-readable explanation of the classification
    """
    if not item.get('is_dimension', False):
        return ('none', DimensionConfidence.NONE, 'Non-dimensional item')

    dim_metadata = item.get('dimension_metadata', [])
    if not dim_metadata:
        return ('face', DimensionConfidence.NONE, 'No dimension metadata')

    # Get structural axes for this statement type (if any)
    structural_axes = STATEMENT_STRUCTURAL_AXES.get(statement_type, set()) if statement_type else set()

    # Check if we can use definition linkbase (Tier 1)
    use_definition_linkbase = (
        xbrl is not None and
        role_uri is not None and
        hasattr(xbrl, 'has_definition_linkbase_for_role') and
        xbrl.has_definition_linkbase_for_role(role_uri)
    )

    for dim_info in dim_metadata:
        dimension = dim_info.get('dimension', '')
        prefix, axis_name = _normalize_axis_name(dimension)

        # Check if this is a structural axis for this statement type
        if axis_name in structural_axes:
            continue  # Not a breakdown for this statement

        # TIER 1: Definition Linkbase (Authoritative) - HIGH confidence
        if use_definition_linkbase:
            if xbrl.is_dimension_valid_for_role(dimension, role_uri):
                continue  # Dimension is valid per definition linkbase
            else:
                return (
                    'breakdown',
                    DimensionConfidence.HIGH,
                    f'{axis_name} not declared in definition linkbase for this role'
                )

        # TIER 2: Heuristic Fallback - MEDIUM confidence for explicit lists
        # 1. Check FACE_AXES first (should show on face)
        if axis_name in FACE_AXES:
            continue  # This is a face dimension, check next

        # 2. Check explicit BREAKDOWN_AXES
        if axis_name in BREAKDOWN_AXES or f'{prefix}:{axis_name}' in BREAKDOWN_AXES:
            return (
                'breakdown',
                DimensionConfidence.MEDIUM,
                f'{axis_name} in BREAKDOWN_AXES list'
            )

        # 3. Check pattern-based detection - LOW confidence
        if _matches_breakdown_pattern(axis_name):
            return (
                'breakdown',
                DimensionConfidence.LOW,
                f'{axis_name} matches breakdown pattern'
            )

    # If we get here with definition linkbase, it's a face value with HIGH confidence
    if use_definition_linkbase:
        return (
            'face',
            DimensionConfidence.HIGH,
            'All dimensions declared in definition linkbase'
        )

    # If we get here via heuristics, it's face with MEDIUM confidence
    # (either in FACE_AXES or not matching any breakdown criteria)
    face_axes_used = [
        dim_info.get('dimension', '').split(':')[-1]
        for dim_info in dim_metadata
        if dim_info.get('dimension', '').split(':')[-1] in FACE_AXES
    ]
    if face_axes_used:
        return (
            'face',
            DimensionConfidence.MEDIUM,
            f'{", ".join(face_axes_used)} in FACE_AXES list'
        )

    # Unknown dimension that didn't match any criteria - default to face with LOW confidence
    return (
        'face',
        DimensionConfidence.LOW,
        'No breakdown criteria matched (default to face)'
    )
