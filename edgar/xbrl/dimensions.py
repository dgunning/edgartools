"""
Dimension classification for XBRL statement filtering.

This module provides utilities to classify dimension axes as "breakdown" vs "classification"
dimensions, enabling smart filtering for include_dimensions=False scenarios.

**Classification Dimensions** (face values):
    Dimensions that distinguish types on the face of the statement.
    Examples: PropertyPlantAndEquipmentByTypeAxis, EquityComponentsAxis
    These should SHOW when include_dimensions=False.

**Breakdown Dimensions** (detail):
    Dimensions that add drill-down detail beyond the face presentation.
    Examples: StatementGeographicalAxis, StatementBusinessSegmentsAxis
    These should HIDE when include_dimensions=False.

Issue #569: URI balance sheet was missing PPE values because ALL dimensional items
were being filtered, including face-level classification dimensions.
"""

from typing import Dict, List, Any, Set

# Standard XBRL axes that indicate BREAKDOWN detail (not face values)
# These dimensions typically add geographic, segment, or disclosure-level breakdowns
# beyond what appears on the face of the financial statement.
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

    # Legal entity breakdowns
    'LegalEntityAxis',
    'dei:LegalEntityAxis',

    # Reporting unit breakdown (typically for goodwill impairment)
    'ReportingUnitAxis',

    # Intangible asset type breakdowns (notes disclosure, not face)
    # SEC filings show "Other intangible assets, net" on face, breakdowns in notes
    'FiniteLivedIntangibleAssetsByMajorClassAxis',
    'IndefiniteLivedIntangibleAssetsByMajorClassAxis',

    # Equity component breakdowns (duplicates non-dimensional face values)
    # SEC filings show equity components as direct line items, not dimensional children
    'StatementEquityComponentsAxis',
}

def is_breakdown_dimension(item: Dict[str, Any]) -> bool:
    """
    Determine if a dimensional item is a breakdown (detail) vs classification (face).

    Breakdown dimensions add drill-down detail beyond the face presentation.
    Classification dimensions distinguish types on the face of the statement.

    Note: Members not in the presentation linkbase are filtered at a higher level
    (in XBRL._generate_line_items) using presentation-based member validation.
    This function only checks for known breakdown axes.

    Args:
        item: Raw statement item dictionary, expected to have 'dimension_metadata' key
              containing a list of dimension info dicts with 'dimension' and 'member_label'.

    Returns:
        True if this is a breakdown dimension (should hide with include_dimensions=False)
        False if this is a classification dimension (should show on face)

    Examples:
        >>> # Face-level PPE by type (should show)
        >>> item = {'dimension_metadata': [{'dimension': 'us-gaap:PropertyPlantAndEquipmentByTypeAxis', 'member_label': 'Property and equipment'}]}
        >>> is_breakdown_dimension(item)
        False

        >>> # Geographic breakdown (should hide)
        >>> item = {'dimension_metadata': [{'dimension': 'srt:StatementGeographicalAxis', 'member_label': 'UNITED STATES'}]}
        >>> is_breakdown_dimension(item)
        True

        >>> # Multi-dimensional: PPE type + Geography = breakdown
        >>> item = {'dimension_metadata': [
        ...     {'dimension': 'us-gaap:PropertyPlantAndEquipmentByTypeAxis', 'member_label': 'Property'},
        ...     {'dimension': 'srt:StatementGeographicalAxis', 'member_label': 'UNITED STATES'}
        ... ]}
        >>> is_breakdown_dimension(item)
        True
    """
    dim_metadata = item.get('dimension_metadata', [])
    if not dim_metadata:
        return False

    for dim_info in dim_metadata:
        dimension = dim_info.get('dimension', '')
        # Extract axis name, handling various formats:
        # - 'us-gaap:StatementGeographicalAxis' -> 'StatementGeographicalAxis'
        # - 'srt:StatementGeographicalAxis' -> 'srt:StatementGeographicalAxis' (keep prefix for srt)
        # - 'StatementGeographicalAxis' -> 'StatementGeographicalAxis'

        if ':' in dimension:
            prefix, axis_name = dimension.split(':', 1)
            # Check both with and without prefix
            if axis_name in BREAKDOWN_AXES:
                return True
            if f'{prefix}:{axis_name}' in BREAKDOWN_AXES:
                return True
        else:
            if dimension in BREAKDOWN_AXES:
                return True

    return False


def get_dimension_classification(item: Dict[str, Any]) -> str:
    """
    Get a human-readable classification of a dimensional item.

    Args:
        item: Raw statement item dictionary with 'dimension_metadata' key

    Returns:
        One of: 'face', 'breakdown', 'none'
    """
    if not item.get('is_dimension', False):
        return 'none'

    if is_breakdown_dimension(item):
        return 'breakdown'

    return 'face'
