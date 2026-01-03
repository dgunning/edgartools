"""
Regression test for edgartools-u649: Enhanced heuristics for incomplete definition linkbase.

The fix:
1. Expanded FACE_AXES with commonly used face-level axes (ProductOrServiceAxis, etc.)
2. Expanded BREAKDOWN_AXES with notes disclosure axes from GH-577 analysis
3. Added confidence scoring via classify_dimension_with_confidence()

These tests verify that the expanded axis lists correctly classify dimensions
when definition linkbase is unavailable.
"""

import pytest

from edgar.xbrl.dimensions import (
    FACE_AXES,
    BREAKDOWN_AXES,
    DimensionConfidence,
    is_breakdown_dimension,
    classify_dimension_with_confidence,
)


class TestExpandedAxisLists:
    """Test that axis lists contain the expected axes from GH-577 analysis."""

    def test_face_axes_contains_product_service_axis(self):
        """ProductOrServiceAxis should be in FACE_AXES for heuristic fallback."""
        assert 'ProductOrServiceAxis' in FACE_AXES
        assert 'srt:ProductOrServiceAxis' in FACE_AXES

    def test_face_axes_contains_debt_axes(self):
        """Debt-related axes should be in FACE_AXES."""
        assert 'DebtInstrumentAxis' in FACE_AXES
        assert 'LongtermDebtTypeAxis' in FACE_AXES
        assert 'ShortTermDebtTypeAxis' in FACE_AXES

    def test_face_axes_contains_contract_axes(self):
        """Contract-related axes should be in FACE_AXES (for defense contractors)."""
        assert 'ContracttypeAxis' in FACE_AXES
        assert 'MajorProgramsAxis' in FACE_AXES

    def test_breakdown_axes_contains_customer_concentration(self):
        """Customer and concentration axes should be in BREAKDOWN_AXES."""
        assert 'MajorCustomersAxis' in BREAKDOWN_AXES
        assert 'ConcentrationRiskByTypeAxis' in BREAKDOWN_AXES
        assert 'ConcentrationRiskByBenchmarkAxis' in BREAKDOWN_AXES

    def test_breakdown_axes_contains_restatement(self):
        """Restatement and accounting change axes should be in BREAKDOWN_AXES."""
        assert 'RestatementAxis' in BREAKDOWN_AXES
        assert 'ChangeInAccountingEstimateByTypeAxis' in BREAKDOWN_AXES

    def test_breakdown_axes_contains_retirement_plan(self):
        """Retirement plan axes should be in BREAKDOWN_AXES."""
        assert 'RetirementPlanTypeAxis' in BREAKDOWN_AXES
        assert 'RetirementPlanSponsorLocationAxis' in BREAKDOWN_AXES

    def test_breakdown_axes_contains_contingency(self):
        """Contingency and litigation axes should be in BREAKDOWN_AXES."""
        assert 'LossContingenciesByNatureOfContingencyAxis' in BREAKDOWN_AXES

    def test_breakdown_axes_contains_geographic_distribution(self):
        """Geographic distribution axis should be in BREAKDOWN_AXES."""
        assert 'GeographicDistributionAxis' in BREAKDOWN_AXES


class TestConfidenceScoring:
    """Test the classify_dimension_with_confidence function."""

    def test_non_dimensional_returns_none_confidence(self):
        """Non-dimensional items should return 'none' classification."""
        item = {'is_dimension': False}
        classification, confidence, reason = classify_dimension_with_confidence(item)

        assert classification == 'none'
        assert confidence == DimensionConfidence.NONE
        assert 'Non-dimensional' in reason

    def test_face_axis_returns_medium_confidence(self):
        """Face axis from FACE_AXES should return MEDIUM confidence."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'us-gaap:PropertyPlantAndEquipmentByTypeAxis', 'member': 'us-gaap:LandMember'}
            ]
        }
        classification, confidence, reason = classify_dimension_with_confidence(item)

        assert classification == 'face'
        assert confidence == DimensionConfidence.MEDIUM
        assert 'FACE_AXES' in reason

    def test_breakdown_axis_returns_medium_confidence(self):
        """Breakdown axis from BREAKDOWN_AXES should return MEDIUM confidence."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'us-gaap:MajorCustomersAxis', 'member': 'company:CustomerMember'}
            ]
        }
        classification, confidence, reason = classify_dimension_with_confidence(item)

        assert classification == 'breakdown'
        assert confidence == DimensionConfidence.MEDIUM
        assert 'BREAKDOWN_AXES' in reason

    def test_pattern_match_returns_low_confidence(self):
        """Axis matching breakdown pattern should return LOW confidence."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'us-gaap:FairValueByAssetClassAxis', 'member': 'company:AssetMember'}
            ]
        }
        classification, confidence, reason = classify_dimension_with_confidence(item)

        assert classification == 'breakdown'
        assert confidence == DimensionConfidence.LOW
        assert 'pattern' in reason.lower()

    def test_unknown_axis_returns_low_confidence_face(self):
        """Unknown axis that doesn't match criteria should default to face with LOW confidence."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'company:CustomUnknownAxis', 'member': 'company:SomeMember'}
            ]
        }
        classification, confidence, reason = classify_dimension_with_confidence(item)

        assert classification == 'face'
        assert confidence == DimensionConfidence.LOW
        assert 'default' in reason.lower()


class TestHeuristicFallback:
    """Test that heuristic fallback works correctly without definition linkbase."""

    def test_product_service_axis_is_face_without_xbrl(self):
        """ProductOrServiceAxis should be classified as face via heuristic."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'srt:ProductOrServiceAxis', 'member': 'us-gaap:ProductMember'}
            ]
        }
        # Without xbrl/role_uri, should use heuristic
        assert not is_breakdown_dimension(item)

    def test_geographic_axis_is_breakdown_without_xbrl(self):
        """StatementGeographicalAxis should be breakdown via heuristic."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'srt:StatementGeographicalAxis', 'member': 'country:US'}
            ]
        }
        assert is_breakdown_dimension(item)

    def test_major_customers_axis_is_breakdown(self):
        """MajorCustomersAxis (new in u649) should be breakdown."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'srt:MajorCustomersAxis', 'member': 'company:USGovernmentMember'}
            ]
        }
        assert is_breakdown_dimension(item)

    def test_restatement_axis_is_breakdown(self):
        """RestatementAxis (new in u649) should be breakdown."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'us-gaap:RestatementAxis', 'member': 'us-gaap:ScenarioPreviouslyReportedMember'}
            ]
        }
        assert is_breakdown_dimension(item)

    def test_retirement_plan_axis_is_breakdown(self):
        """RetirementPlanTypeAxis (new in u649) should be breakdown."""
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'us-gaap:RetirementPlanTypeAxis', 'member': 'us-gaap:PensionPlansDefinedBenefitMember'}
            ]
        }
        assert is_breakdown_dimension(item)


@pytest.mark.network
class TestGH577Cases:
    """Test GH-577 specific cases with the enhanced heuristics."""

    def test_csx_ppe_shows_with_heuristic(self):
        """CSX PPE should show via PropertyPlantAndEquipmentByTypeAxis heuristic."""
        from edgar import Company

        csx = Company("CSX")
        filing = csx.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # CSX has no definition linkbase for balance sheet
        _, role_uri, _ = xbrl.find_statement("BalanceSheet")
        assert not xbrl.has_definition_linkbase_for_role(role_uri)

        # Get balance sheet with dimensions filtered
        stmt = xbrl.statements.balance_sheet()
        df = stmt.to_dataframe(include_dimensions=False)

        # PPE rows should still be present due to PropertyPlantAndEquipmentByTypeAxis in FACE_AXES
        ppe_rows = df[df['concept'].str.contains('PropertyPlant', case=False, na=False)]
        assert len(ppe_rows) > 0, "PPE rows should be present via heuristic fallback"

    def test_bsx_goodwill_breakdowns_filtered(self):
        """BSX Goodwill breakdowns should be filtered correctly."""
        from edgar import Company

        bsx = Company("BSX")
        filing = bsx.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # BSX has no definition linkbase for balance sheet
        _, role_uri, _ = xbrl.find_statement("BalanceSheet")
        assert not xbrl.has_definition_linkbase_for_role(role_uri)

        stmt = xbrl.statements.balance_sheet()

        # With dimensions
        df_all = stmt.to_dataframe(include_dimensions=True)
        goodwill_all = df_all[df_all['concept'].str.contains('Goodwill', case=False, na=False)]

        # Without dimensions (breakdowns filtered)
        df_filtered = stmt.to_dataframe(include_dimensions=False)
        goodwill_filtered = df_filtered[df_filtered['concept'].str.contains('Goodwill', case=False, na=False)]

        # Should have fewer rows when filtering
        assert len(goodwill_filtered) < len(goodwill_all), (
            "BusinessAcquisitionAxis should be filtered as breakdown"
        )

        # The non-dimensional goodwill should be present
        assert len(goodwill_filtered) > 0, "Non-dimensional Goodwill should be present"
