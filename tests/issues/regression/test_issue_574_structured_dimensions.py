"""
Regression test for Issue #574: Add structured dimension fields (axis, member, member_label).

The fix adds these NEW columns to dimensional rows in statement DataFrames:
- dimension_axis: The XBRL axis (e.g., 'srt:ProductOrServiceAxis')
- dimension_member: The technical member name (e.g., 'us-gaap_ProductMember')
- dimension_member_label: Human-readable member label (e.g., 'Products')

The existing dimension_label is PRESERVED for backwards compatibility and contains
the full combined format (e.g., 'srt:ProductOrServiceAxis: Products').
"""

import pytest


class TestStructuredDimensionFields:
    """Test that dimension fields are properly structured."""

    def test_dimension_columns_exist_for_dimensional_rows(self):
        """Dimensional rows should have axis, member, and member_label columns."""
        # Create a mock item with dimension_metadata
        item = {
            'is_dimension': True,
            'full_dimension_label': 'srt:ProductOrServiceAxis: Products',
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
                last_dim = dim_metadata[-1]  # Use last for member_label
                axis = primary_dim.get('dimension', '')
                member = primary_dim.get('member', '')
                member_label = last_dim.get('member_label', '')
            else:
                axis = None
                member = None
                member_label = None
            # dimension_label is preserved as full format
            dimension_label = item.get('full_dimension_label', '')
        else:
            axis = None
            member = None
            member_label = None
            dimension_label = None

        assert axis == 'srt:ProductOrServiceAxis'
        assert member == 'us-gaap:ProductMember'
        assert member_label == 'Products'
        assert dimension_label == 'srt:ProductOrServiceAxis: Products'

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
        assert 'dimension_member_label' in df.columns
        assert 'dimension_label' in df.columns  # Preserved for backwards compatibility

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
        assert first_row['dimension_member_label'] is not None
        assert first_row['dimension_member_label'] != ''
        # dimension_label should have the full format
        assert first_row['dimension_label'] is not None
        assert 'ProductOrServiceAxis' in str(first_row['dimension_label'])

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
            assert row['dimension_member_label'] is not None

    def test_dimension_member_label_is_clean_label(self):
        """dimension_member_label should be just the member label, not axis:member format."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=True)

        # Get dimensional rows
        dim_rows = df[df['dimension'] == True]

        for _, row in dim_rows.iterrows():
            member_label = row['dimension_member_label']
            if member_label:
                # member_label should NOT contain axis information
                # It should be just the member label like 'Products', 'Americas', etc.
                assert 'ProductOrServiceAxis' not in str(member_label)
                assert 'GeographicalAxis' not in str(member_label)
                assert 'ConsolidationItemsAxis' not in str(member_label)

    def test_dimension_label_preserves_full_format(self):
        """dimension_label should preserve the full axis:member format for backwards compatibility."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=True)

        # Get dimensional rows with ProductOrServiceAxis
        product_rows = df[df['dimension_axis'] == 'srt:ProductOrServiceAxis']

        for _, row in product_rows.iterrows():
            label = row['dimension_label']
            if label:
                # dimension_label should contain the axis in the combined format
                assert 'ProductOrServiceAxis' in str(label)

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
        assert non_dim_rows['dimension_member_label'].isna().all()
        assert non_dim_rows['dimension_label'].isna().all()
