"""
Regression tests for Issue #569: Balance sheet missing PPE values with include_dimensions=False

Issue: https://github.com/dgunning/edgartools/issues/569

Problem: When include_dimensions=False, URI balance sheet was missing "Property and equipment, net"
($1,034M) because it was tagged with PropertyPlantAndEquipmentByTypeAxis dimension. The filtering
was too aggressive - it was removing ALL dimensional items instead of just breakdown details.

Key Concepts:
- **Classification dimensions** (face values): Dimensions that distinguish types on the face of
  the statement, like PropertyPlantAndEquipmentByTypeAxis. These should SHOW with include_dimensions=False.
- **Breakdown dimensions** (detail): Dimensions that add drill-down detail beyond face presentation,
  like StatementGeographicalAxis. These should HIDE with include_dimensions=False.

Fix: Created is_breakdown_dimension() function to classify dimension axes and only filter breakdown
dimensions when include_dimensions=False.
"""

import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.regression
class TestIssue569DimensionalPPE:
    """Test that classification dimensions appear with include_dimensions=False."""

    @pytest.fixture(scope="class")
    def uri_xbrl(self):
        """Get URI 10-K XBRL data."""
        company = Company("URI")
        filing = company.get_filings(form="10-K").latest(1)
        return filing.xbrl()

    def test_ppe_shows_with_dimensions_false(self, uri_xbrl):
        """Property and equipment, net should appear with include_dimensions=False.

        Before fix: PPE row existed but had NaN value because the actual $1,034M value
        was attached to a PropertyPlantAndEquipmentByTypeAxis dimension member and was filtered.

        After fix: PPE row shows the actual $1,034M value (or current period equivalent).
        """
        balance_sheet = uri_xbrl.statements.balance_sheet(include_dimensions=False)
        df = balance_sheet.to_dataframe()

        # Find PPE rows
        ppe_rows = df[df['label'].str.contains('Property and equipment, net', case=False, na=False)]

        # Should have at least one row
        assert len(ppe_rows) > 0, "PPE row 'Property and equipment, net' should exist"

        # Find date columns (2024-12-31 or similar)
        date_cols = [c for c in df.columns if c.startswith('20') and '-' in c]
        assert len(date_cols) > 0, "Should have at least one date column"

        # At least one PPE row should have an actual value (not NaN)
        has_value = False
        for col in date_cols:
            if ppe_rows[col].notna().any():
                has_value = True
                break

        assert has_value, (
            "PPE 'Property and equipment, net' should have an actual value, not just NaN. "
            "This suggests classification dimension filtering is broken."
        )

    def test_geographic_breakdown_hidden_with_dimensions_false(self, uri_xbrl):
        """Geographic breakdowns should be hidden with include_dimensions=False.

        Rows like "UNITED STATES - Total equipment rentals" or "Foreign - Property and equipment"
        are breakdown details that should NOT appear on the face of the statement.
        """
        balance_sheet = uri_xbrl.statements.balance_sheet(include_dimensions=False)
        df = balance_sheet.to_dataframe()

        # Should NOT have geographic prefixed items
        us_rows = df[df['label'].str.contains('UNITED STATES -', case=False, na=False)]
        foreign_rows = df[df['label'].str.contains('Foreign -', case=False, na=False)]

        assert len(us_rows) == 0, (
            f"Geographic breakdown 'UNITED STATES -' should be hidden with include_dimensions=False, "
            f"but found {len(us_rows)} rows"
        )
        assert len(foreign_rows) == 0, (
            f"Geographic breakdown 'Foreign -' should be hidden with include_dimensions=False, "
            f"but found {len(foreign_rows)} rows"
        )

    def test_all_dimensions_show_with_dimensions_true(self, uri_xbrl):
        """All dimensional items should appear with include_dimensions=True."""
        balance_sheet = uri_xbrl.statements.balance_sheet(include_dimensions=True)
        df = balance_sheet.to_dataframe()

        # Should have both face values AND geographic breakdowns
        ppe_rows = df[df['label'].str.contains('Property and equipment', case=False, na=False)]

        # Should have multiple rows (face value + geographic breakdowns)
        assert len(ppe_rows) >= 3, (
            f"Expected multiple PPE rows with include_dimensions=True (face + breakdowns), "
            f"but found only {len(ppe_rows)}"
        )

        # Geographic breakdowns should be present
        geo_rows = df[df['label'].str.contains('UNITED STATES -|Foreign -', case=False, na=False)]
        assert len(geo_rows) > 0, (
            "Geographic breakdown rows should appear with include_dimensions=True"
        )

    def test_is_breakdown_column_present(self, uri_xbrl):
        """DataFrame should include is_breakdown column for user filtering.

        This allows users to filter breakdown vs face dimensions themselves.
        """
        balance_sheet = uri_xbrl.statements.balance_sheet(include_dimensions=True)
        df = balance_sheet.to_dataframe()

        assert 'is_breakdown' in df.columns, "is_breakdown column should be present"

        # Verify classification: geographic items should be marked as breakdowns
        geo_rows = df[df['label'].str.contains('UNITED STATES -|Foreign -', case=False, na=False)]
        if len(geo_rows) > 0:
            assert geo_rows['is_breakdown'].all(), (
                "Geographic items should be marked as is_breakdown=True"
            )

    def test_face_dimensions_not_marked_as_breakdown(self, uri_xbrl):
        """Face-level classification dimensions should not be marked as breakdowns.

        PPE by type (PropertyPlantAndEquipmentByTypeAxis) is a classification dimension
        that appears on the face of the statement, not a breakdown.
        """
        balance_sheet = uri_xbrl.statements.balance_sheet(include_dimensions=True)
        df = balance_sheet.to_dataframe()

        # Find PPE dimension rows that are NOT geographic
        ppe_dim_rows = df[
            (df['label'].str.contains('Property and equipment|Rental equipment', case=False, na=False)) &
            (df['dimension'] == True) &
            (~df['label'].str.contains('UNITED STATES|Foreign', case=False, na=False))
        ]

        if len(ppe_dim_rows) > 0:
            # These should NOT be marked as breakdown
            non_breakdown = ppe_dim_rows[ppe_dim_rows['is_breakdown'] == False]
            assert len(non_breakdown) > 0, (
                "PPE classification dimensions (without geographic qualifier) should not be "
                "marked as breakdown"
            )
