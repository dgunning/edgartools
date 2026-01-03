"""
Regression test for edgartools-cf9o: Connect definition linkbase to dimension filtering.

The fix: Modified is_breakdown_dimension() to use definition linkbase data when
available. Dimensions declared in the definition linkbase hypercubes are treated
as face values (not breakdowns) and are included even when include_dimensions=False.

This is critical for filers like Boeing who report face values ONLY through
dimensional XBRL (e.g., CostOfGoodsAndServicesSold via ProductOrServiceAxis).
"""

import pytest


@pytest.mark.network
def test_boeing_product_service_axis_not_breakdown():
    """
    Boeing's ProductOrServiceAxis should NOT be classified as breakdown.

    The definition linkbase declares ProductOrServiceAxis as valid for the
    income statement, so these dimensional values are face values.
    """
    from edgar import Company

    ba = Company("BA")
    filing = ba.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    stmt = xbrl.statements.income_statement()
    df = stmt.to_dataframe(include_dimensions=False)

    # Find rows with ProductOrServiceAxis
    product_service_rows = df[
        df['dimension_label'].str.contains('ProductOrService', case=False, na=False)
    ]

    # These should be included (not filtered out)
    assert len(product_service_rows) > 0, (
        "ProductOrServiceAxis dimensional values should be included "
        "because they are declared in definition linkbase"
    )

    # They should NOT be marked as breakdown
    assert not product_service_rows['is_breakdown'].any(), (
        "ProductOrServiceAxis should not be classified as breakdown "
        "because it is declared in the definition linkbase"
    )


@pytest.mark.network
def test_boeing_geographic_axis_is_breakdown():
    """
    Boeing's StatementGeographicalAxis should be classified as breakdown.

    This axis is NOT declared in the definition linkbase for the income statement,
    so these dimensional values are breakdowns (note disclosures) not face values.
    """
    from edgar import Company

    ba = Company("BA")
    filing = ba.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    role = "http://www.boeing.com/role/ConsolidatedStatementsofOperations"

    # Verify definition linkbase classification
    is_valid = xbrl.is_dimension_valid_for_role("us-gaap:StatementGeographicalAxis", role)
    assert not is_valid, "StatementGeographicalAxis should NOT be valid for income statement"

    # Verify ProductOrServiceAxis IS valid
    is_valid = xbrl.is_dimension_valid_for_role("srt:ProductOrServiceAxis", role)
    assert is_valid, "ProductOrServiceAxis should be valid for income statement"


@pytest.mark.network
def test_xbrl_dimension_validation_methods():
    """
    Test the new XBRL dimension validation methods.
    """
    from edgar import Company

    ba = Company("BA")
    filing = ba.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    role = "http://www.boeing.com/role/ConsolidatedStatementsofOperations"

    # Test has_definition_linkbase_for_role
    assert xbrl.has_definition_linkbase_for_role(role), (
        "Boeing income statement should have definition linkbase data"
    )

    # Test get_valid_dimensions_for_role
    valid_dims = xbrl.get_valid_dimensions_for_role(role)
    assert len(valid_dims) > 0, "Should have valid dimensions for income statement"
    assert any('ProductOrService' in d for d in valid_dims), (
        "ProductOrServiceAxis should be in valid dimensions"
    )

    # Test is_dimension_valid_for_role with both formats
    assert xbrl.is_dimension_valid_for_role("srt:ProductOrServiceAxis", role)
    assert xbrl.is_dimension_valid_for_role("srt_ProductOrServiceAxis", role)


@pytest.mark.network
def test_fallback_to_heuristic_when_no_definition_linkbase():
    """
    When definition linkbase is not available, fall back to heuristic filtering.
    """
    from edgar.xbrl.dimensions import is_breakdown_dimension

    # Create a mock item with geographic breakdown
    item = {
        'is_dimension': True,
        'dimension_metadata': [
            {'dimension': 'us-gaap:StatementGeographicalAxis', 'member': 'us-gaap:NorthAmericaMember'}
        ]
    }

    # Without xbrl/role_uri, should use heuristic (geographic = breakdown)
    assert is_breakdown_dimension(item, statement_type="IncomeStatement"), (
        "StatementGeographicalAxis should be breakdown via heuristic fallback"
    )

    # Face dimension should still work via heuristic
    item_face = {
        'is_dimension': True,
        'dimension_metadata': [
            {'dimension': 'us-gaap:PropertyPlantAndEquipmentByTypeAxis', 'member': 'us-gaap:LandMember'}
        ]
    }

    assert not is_breakdown_dimension(item_face, statement_type="BalanceSheet"), (
        "PropertyPlantAndEquipmentByTypeAxis should NOT be breakdown via heuristic"
    )
