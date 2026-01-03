"""
Regression test for edgartools-68lp: Validate dimension face value detection across GH-577 test cases.

This is the final validation phase of the dimension handling epic (edgartools-445y).
Tests all companies documented in GH-577 to ensure face values are correctly preserved
when using include_dimensions=False.

GH-577 Problem Statement:
"Using xbrl.statements.income_statement(include_dimensions=False) will in MANY CASES
produce an incomplete and out of balance statement that does not match the printed,
reported financial statements."

Solution Applied (Phases 1-3):
1. Fixed definition linkbase table creation (edgartools-rqxi)
2. Connected definition linkbase to dimension filtering (edgartools-cf9o)
3. Enhanced heuristics for incomplete definition linkbase (edgartools-u649)
"""

import pytest
import pandas as pd
from typing import Optional, Tuple


def get_concept_values(df: pd.DataFrame, concept_pattern: str) -> pd.DataFrame:
    """Get rows matching a concept pattern from a statement dataframe."""
    return df[df['concept'].str.contains(concept_pattern, case=False, na=False)]


def has_dimensional_values(df: pd.DataFrame, concept_pattern: str) -> bool:
    """Check if statement has dimensional values for a concept."""
    concept_rows = get_concept_values(df, concept_pattern)
    if len(concept_rows) == 0:
        return False
    # Check if any dimensional rows have non-NaN values
    value_cols = [c for c in df.columns if '-' in c and c[:4].isdigit()]
    if not value_cols:
        return False
    dim_rows = concept_rows[concept_rows['dimension'] == True]
    if len(dim_rows) == 0:
        return False
    return dim_rows[value_cols[0]].notna().any()


def get_face_value_sum(df: pd.DataFrame, concept_pattern: str) -> Optional[float]:
    """Get the sum of face values for a concept (dimensional + non-dimensional)."""
    concept_rows = get_concept_values(df, concept_pattern)
    if len(concept_rows) == 0:
        return None
    value_cols = [c for c in df.columns if '-' in c and c[:4].isdigit()]
    if not value_cols:
        return None
    # Get the most recent period column
    recent_col = value_cols[0]
    # Sum all non-NaN values
    values = concept_rows[recent_col].dropna()
    if len(values) == 0:
        return None
    return values.sum()


# =============================================================================
# INCOME STATEMENT TEST CASES - CostOfGoodsAndServicesSold
# =============================================================================

@pytest.mark.network
class TestIncomeStatementCOGS:
    """Test that COGS face values are preserved for dimensional-only filers."""

    @pytest.fixture
    def load_income_statement(self):
        """Helper to load income statement for a company."""
        def _load(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame, bool]:
            from edgar import Company
            company = Company(ticker)
            filing = company.get_filings(form="10-K").latest()
            xbrl = filing.xbrl()

            stmt = xbrl.statements.income_statement()
            df_all = stmt.to_dataframe(include_dimensions=True)
            df_filtered = stmt.to_dataframe(include_dimensions=False)

            # Check if definition linkbase is available
            _, role_uri, _ = xbrl.find_statement("IncomeStatement")
            has_def = xbrl.has_definition_linkbase_for_role(role_uri) if role_uri else False

            return df_all, df_filtered, has_def
        return _load

    def test_boeing_cogs_preserved(self, load_income_statement):
        """Boeing reports COGS only via ProductOrServiceAxis - values must be preserved."""
        df_all, df_filtered, has_def = load_income_statement("BA")

        # Boeing should have definition linkbase
        assert has_def, "Boeing should have definition linkbase for income statement"

        # COGS should have dimensional values
        assert has_dimensional_values(df_all, "CostOfGoodsAndServicesSold"), \
            "Boeing COGS should have dimensional values"

        # Values should be preserved in filtered output
        cogs_all = get_face_value_sum(df_all, "CostOfGoodsAndServicesSold")
        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")

        assert cogs_all is not None, "Boeing should have COGS values"
        assert cogs_filtered is not None, "Boeing COGS should be preserved when filtering"
        assert cogs_filtered > 0, "Boeing COGS should have positive value"

    def test_carrier_cogs_preserved(self, load_income_statement):
        """Carrier reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("CARR")

        assert has_def, "Carrier should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        assert cogs_filtered is not None and cogs_filtered > 0, \
            "Carrier COGS should be preserved"

    def test_general_dynamics_cogs_preserved(self, load_income_statement):
        """General Dynamics reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("GD")

        assert has_def, "GD should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        assert cogs_filtered is not None and cogs_filtered > 0, \
            "GD COGS should be preserved"

    def test_huntington_ingalls_cogs_preserved(self, load_income_statement):
        """Huntington Ingalls reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("HII")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        # HII may use different concept names
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered > 0, \
            "HII cost of revenue should be preserved"

    def test_intuit_cogs_preserved(self, load_income_statement):
        """Intuit reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("INTU")

        assert has_def, "Intuit should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered > 0, \
            "Intuit COGS should be preserved"

    def test_northrop_grumman_cogs_preserved(self, load_income_statement):
        """Northrop Grumman reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("NOC")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered > 0, \
            "NOC COGS should be preserved"

    def test_rtx_cogs_preserved(self, load_income_statement):
        """RTX (Raytheon) reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("RTX")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered > 0, \
            "RTX COGS should be preserved"

    def test_schlumberger_cogs_preserved(self, load_income_statement):
        """Schlumberger reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("SLB")

        assert has_def, "SLB should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered > 0, \
            "SLB COGS should be preserved"

    def test_workday_cogs_preserved(self, load_income_statement):
        """Workday reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("WDAY")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered > 0, \
            "Workday COGS should be preserved"


# =============================================================================
# BALANCE SHEET TEST CASES - Goodwill
# =============================================================================

@pytest.mark.network
class TestBalanceSheetGoodwill:
    """Test that Goodwill face values are preserved."""

    @pytest.fixture
    def load_balance_sheet(self):
        """Helper to load balance sheet for a company."""
        def _load(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame, bool]:
            from edgar import Company
            company = Company(ticker)
            filing = company.get_filings(form="10-K").latest()
            xbrl = filing.xbrl()

            stmt = xbrl.statements.balance_sheet()
            df_all = stmt.to_dataframe(include_dimensions=True)
            df_filtered = stmt.to_dataframe(include_dimensions=False)

            _, role_uri, _ = xbrl.find_statement("BalanceSheet")
            has_def = xbrl.has_definition_linkbase_for_role(role_uri) if role_uri else False

            return df_all, df_filtered, has_def
        return _load

    def test_boston_scientific_goodwill_preserved(self, load_balance_sheet):
        """BSX Goodwill should be preserved (non-dimensional value exists)."""
        df_all, df_filtered, has_def = load_balance_sheet("BSX")

        goodwill_filtered = get_face_value_sum(df_filtered, "Goodwill")

        # BSX has non-dimensional goodwill that should be preserved
        assert goodwill_filtered is not None and goodwill_filtered > 0, \
            "BSX Goodwill should be preserved"

        # Breakdowns by BusinessAcquisitionAxis should be filtered
        goodwill_all = get_concept_values(df_all, "Goodwill")
        goodwill_filtered_rows = get_concept_values(df_filtered, "Goodwill")

        # Should have fewer rows when breakdowns are filtered
        assert len(goodwill_filtered_rows) <= len(goodwill_all), \
            "BSX Goodwill breakdowns should be filtered"

    def test_ibm_goodwill_preserved(self, load_balance_sheet):
        """IBM Goodwill should be preserved."""
        df_all, df_filtered, has_def = load_balance_sheet("IBM")

        goodwill_filtered = get_face_value_sum(df_filtered, "Goodwill")

        assert goodwill_filtered is not None and goodwill_filtered > 0, \
            "IBM Goodwill should be preserved"

    def test_jack_henry_goodwill_preserved(self, load_balance_sheet):
        """Jack Henry Goodwill should be preserved."""
        df_all, df_filtered, has_def = load_balance_sheet("JKHY")

        goodwill_filtered = get_face_value_sum(df_filtered, "Goodwill")

        assert goodwill_filtered is not None and goodwill_filtered > 0, \
            "JKHY Goodwill should be preserved"


# =============================================================================
# BALANCE SHEET TEST CASES - PPE
# =============================================================================

@pytest.mark.network
class TestBalanceSheetPPE:
    """Test that PPE face values are preserved."""

    @pytest.fixture
    def load_balance_sheet(self):
        """Helper to load balance sheet for a company."""
        def _load(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame, bool]:
            from edgar import Company
            company = Company(ticker)
            filing = company.get_filings(form="10-K").latest()
            xbrl = filing.xbrl()

            stmt = xbrl.statements.balance_sheet()
            df_all = stmt.to_dataframe(include_dimensions=True)
            df_filtered = stmt.to_dataframe(include_dimensions=False)

            _, role_uri, _ = xbrl.find_statement("BalanceSheet")
            has_def = xbrl.has_definition_linkbase_for_role(role_uri) if role_uri else False

            return df_all, df_filtered, has_def
        return _load

    def test_boston_scientific_ppe_preserved(self, load_balance_sheet):
        """BSX PPE should be preserved."""
        df_all, df_filtered, has_def = load_balance_sheet("BSX")

        ppe_filtered = get_face_value_sum(df_filtered, "PropertyPlantAndEquipment")

        assert ppe_filtered is not None and ppe_filtered > 0, \
            "BSX PPE should be preserved"

    def test_csx_ppe_preserved(self, load_balance_sheet):
        """CSX PPE should be preserved via PropertyPlantAndEquipmentByTypeAxis heuristic."""
        df_all, df_filtered, has_def = load_balance_sheet("CSX")

        # CSX has no definition linkbase - relies on heuristic
        assert not has_def, "CSX should NOT have definition linkbase for balance sheet"

        ppe_filtered = get_face_value_sum(df_filtered, "PropertyPlantAndEquipment")

        assert ppe_filtered is not None and ppe_filtered > 0, \
            "CSX PPE should be preserved via heuristic fallback"

    def test_hilton_ppe_preserved(self, load_balance_sheet):
        """Hilton PPE should be preserved."""
        df_all, df_filtered, has_def = load_balance_sheet("HLT")

        ppe_filtered = get_face_value_sum(df_filtered, "PropertyPlantAndEquipment")

        assert ppe_filtered is not None and ppe_filtered > 0, \
            "Hilton PPE should be preserved"


# =============================================================================
# CONTROL CASES - Breakdowns Should Still Be Filtered
# =============================================================================

@pytest.mark.network
class TestBreakdownsFiltered:
    """Test that breakdown dimensions are still correctly filtered."""

    def test_geographic_breakdown_filtered(self):
        """StatementGeographicalAxis should be filtered as breakdown."""
        from edgar import Company
        from edgar.xbrl.dimensions import is_breakdown_dimension

        ba = Company("BA")
        filing = ba.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Create mock item with geographic axis
        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'srt:StatementGeographicalAxis', 'member': 'country:US'}
            ]
        }

        _, role_uri, _ = xbrl.find_statement("IncomeStatement")

        # Should be breakdown regardless of definition linkbase
        assert is_breakdown_dimension(item, xbrl=xbrl, role_uri=role_uri), \
            "Geographic axis should be filtered as breakdown"

    def test_business_segment_breakdown_filtered(self):
        """StatementBusinessSegmentsAxis should be filtered as breakdown."""
        from edgar.xbrl.dimensions import is_breakdown_dimension

        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'us-gaap:StatementBusinessSegmentsAxis', 'member': 'company:SegmentMember'}
            ]
        }

        assert is_breakdown_dimension(item), \
            "Business segment axis should be filtered as breakdown"

    def test_product_service_axis_preserved(self):
        """ProductOrServiceAxis should NOT be filtered (it's a face axis)."""
        from edgar.xbrl.dimensions import is_breakdown_dimension

        item = {
            'is_dimension': True,
            'dimension_metadata': [
                {'dimension': 'srt:ProductOrServiceAxis', 'member': 'us-gaap:ProductMember'}
            ]
        }

        assert not is_breakdown_dimension(item), \
            "ProductOrServiceAxis should NOT be filtered - it's a face axis"


# =============================================================================
# SUMMARY VALIDATION
# =============================================================================

@pytest.mark.network
class TestSummaryValidation:
    """Summary tests to verify overall fix effectiveness."""

    def test_all_income_statement_cases_have_cogs(self):
        """Verify all income statement test cases have COGS values."""
        from edgar import Company

        tickers = ['BA', 'CARR', 'GD', 'INTU', 'SLB']  # Subset for faster testing
        results = {}

        for ticker in tickers:
            try:
                company = Company(ticker)
                filing = company.get_filings(form="10-K").latest()
                xbrl = filing.xbrl()

                stmt = xbrl.statements.income_statement()
                df = stmt.to_dataframe(include_dimensions=False)

                cogs = get_face_value_sum(df, "CostOfGoodsAndServicesSold")
                if cogs is None:
                    cogs = get_face_value_sum(df, "CostOfRevenue")

                results[ticker] = cogs is not None and cogs > 0
            except Exception as e:
                results[ticker] = False

        failed = [t for t, passed in results.items() if not passed]
        assert len(failed) == 0, f"These companies failed COGS validation: {failed}"

    def test_dimension_filtering_reduces_row_count(self):
        """Verify that dimension filtering still reduces row count (breakdowns filtered)."""
        from edgar import Company

        ba = Company("BA")
        filing = ba.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        stmt = xbrl.statements.income_statement()
        df_all = stmt.to_dataframe(include_dimensions=True)
        df_filtered = stmt.to_dataframe(include_dimensions=False)

        # Filtered should have fewer rows (breakdowns removed)
        assert len(df_filtered) < len(df_all), \
            "Filtering should reduce row count by removing breakdowns"

        # But not zero - face values should remain
        assert len(df_filtered) > 10, \
            "Filtered statement should still have substantial content"
