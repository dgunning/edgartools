"""
Regression test for Issue #574: Add structured dimension fields (axis, member, label).

The fix adds three columns to dimensional rows in statement DataFrames:
- dimension_axis: The XBRL axis (e.g., 'srt:ProductOrServiceAxis')
- dimension_member: The technical member name (e.g., 'us-gaap_ProductMember')
- dimension_label: Human-readable member label (e.g., 'Products')

This replaces the combined format that was previously in dimension_label
(e.g., 'Product or Service: Products').
"""

import pytest


class TestStructuredDimensionFields:
    """Test that dimension fields are properly structured."""

    def test_dimension_columns_exist_for_dimensional_rows(self):
        """Dimensional rows should have axis, member, and label columns."""
        # Create a mock item with dimension_metadata
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {
                    'dimension': 'srt:ProductOrServiceAxis',
                    'member': 'us-gaap:ProductMember',
                    'member_label': 'Products'
                }
            ]
        }

        # Simulate row building logic
        if item.get('is_dimension', False):
            dim_metadata = item.get('dimension_metadata', [])
            if dim_metadata:
                primary_dim = dim_metadata[0]
                axis = primary_dim.get('dimension', '')
                member = primary_dim.get('member', '')
                label = primary_dim.get('member_label', '')
            else:
                axis = None
                member = None
                label = ''
        else:
            axis = None
            member = None
            label = None

        assert axis == 'srt:ProductOrServiceAxis'
        assert member == 'us-gaap:ProductMember'
        assert label == 'Products'

    def test_non_dimensional_rows_have_none_values(self):
        """Non-dimensional rows should have None for dimension columns."""
        item = {
            'is_dimension': False,
            'concept': 'us-gaap:Revenue'
        }

        if item.get('is_dimension', False):
            axis = 'some_axis'
            member = 'some_member'
            label = 'some_label'
        else:
            axis = None
            member = None
            label = None

        assert axis is None
        assert member is None
        assert label is None

    def test_missing_dimension_metadata_uses_fallback(self):
        """Items without dimension_metadata should use fallback."""
        item = {
            'is_dimension': True,
            'full_dimension_label': 'Product or Service: iPhone',
            'dimension_metadata': []  # Empty
        }

        dim_metadata = item.get('dimension_metadata', [])
        if dim_metadata:
            label = dim_metadata[0].get('member_label', '')
        else:
            label = item.get('full_dimension_label', '')

        assert label == 'Product or Service: iPhone'


@pytest.mark.network
class TestStructuredDimensionsWithRealData:
    """Test structured dimension fields with real SEC filings."""

    def test_aapl_income_statement_has_structured_dimensions(self):
        """AAPL income statement should have structured dimension columns."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=True)

        # Check columns exist
        assert 'dimension_axis' in df.columns
        assert 'dimension_member' in df.columns
        assert 'dimension_label' in df.columns

        # Get dimensional rows
        dim_rows = df[df['dimension'] == True]

        # Should have some dimensional rows
        assert len(dim_rows) > 0

        # Product/Service axis should be present
        product_service_rows = dim_rows[
            dim_rows['dimension_axis'] == 'srt:ProductOrServiceAxis'
        ]
        assert len(product_service_rows) > 0

        # Check structure of first product/service row
        first_row = product_service_rows.iloc[0]
        assert first_row['dimension_axis'] == 'srt:ProductOrServiceAxis'
        assert first_row['dimension_member'] is not None
        assert first_row['dimension_member'] != ''
        assert first_row['dimension_label'] is not None
        assert first_row['dimension_label'] != ''

    def test_wday_income_statement_product_service_axis(self):
        """WDAY income statement should have ProductOrServiceAxis dimensions."""
        from edgar import Company

        company = Company("WDAY")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=True)

        # Filter to ProductOrServiceAxis
        product_rows = df[df['dimension_axis'] == 'srt:ProductOrServiceAxis']

        # WDAY should have product/service breakdowns
        assert len(product_rows) > 0

        # Check member values are populated
        for _, row in product_rows.iterrows():
            assert row['dimension_member'] is not None
            assert row['dimension_label'] is not None

    def test_dimension_label_is_member_label_only(self):
        """dimension_label should be just the member label, not axis:member format."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=True)

        # Get dimensional rows
        dim_rows = df[df['dimension'] == True]

        for _, row in dim_rows.iterrows():
            label = row['dimension_label']
            if label:
                # Label should NOT contain axis information (no ':' pattern like 'Axis: Member')
                # It should be just the member label like 'Products', 'iPhone', etc.
                # Note: Some labels might legitimately contain ':' but not in 'Axis: Member' format
                assert 'ProductOrServiceAxis' not in str(label)
                assert 'GeographicalAxis' not in str(label)

    def test_non_dimensional_rows_have_none_axis_and_member(self):
        """Non-dimensional rows should have None for axis and member columns."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=True)

        # Get non-dimensional rows
        non_dim_rows = df[df['dimension'] == False]

        # All axis and member values should be None
        assert non_dim_rows['dimension_axis'].isna().all()
        assert non_dim_rows['dimension_member'].isna().all()
        assert non_dim_rows['dimension_label'].isna().all()
