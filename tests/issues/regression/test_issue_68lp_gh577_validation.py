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

Offline: each company's XBRL is read from verbatim SEC files committed gzipped under
tests/fixtures/xbrl_gz/ (accessions and checksums in its README), instead of the
company's latest 10-K, so the filing under test no longer changes when a company files
again. For every filing used here, XBRL.from_directory() on those files gives the same
statements as filing.xbrl() on the live filing (checked 2026-11-22).

Ground truth, read directly from the instance documents (not through edgartools):
- Boeing 10-K, accession 0001628280-26-004357, FY2025: CostOfGoodsAndServicesSold is
  reported only on srt:ProductOrServiceAxis, ProductMember 73,761,000,000 and
  ServiceMember 11,413,000,000 (together 85,174,000,000).
- CSX 10-K, accession 0000277948-26-000006, at 2025-12-31: PropertyPlantAndEquipmentNet
  with no dimension is 36,811,000,000; Road and track assets (RoadTotalMember) is
  27,300,000,000 on PropertyPlantAndEquipmentByTypeAxis.
- Boston Scientific 10-K, accession 0000885725-26-000010, at 2025-12-31: Goodwill with no
  dimension is 18,282,000,000; on BusinessAcquisitionAxis, AllOtherMember is 507,000,000.
"""

import gzip
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import pytest

from edgar.xbrl import XBRL

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl_gz"

# ticker -> fixture directory (see tests/fixtures/xbrl_gz/README.md for accessions)
FILINGS = {
    "BA": "ba/10k_2025",
    "BSX": "bsx/10k_2025",
    "CARR": "carr/10k_2025",
    "CSX": "csx/10k_2025",
    "GD": "gd/10k_2025",
    "HII": "hii/10k_2025",
    "HLT": "hlt/10k_2025",
    "IBM": "ibm/10k_2025",
    "INTU": "intu/10k_2026",
    "JKHY": "jkhy/10k_2026",
    "NOC": "noc/10k_2025",
    "RTX": "rtx/10k_2025",
    "SLB": "slb/10k_2025",
    "WDAY": "wday/10k_2026",
}


@pytest.fixture(scope="module")
def load_xbrl(tmp_path_factory):
    """Decompress a company's fixture files into a temp directory and parse them, once per module."""
    cache = {}

    def _load(ticker: str) -> XBRL:
        if ticker not in cache:
            src = FIXTURES / FILINGS[ticker]
            gz_files = sorted(src.glob("*.gz"))
            assert gz_files, f"No XBRL fixture files in {src}"
            dest = tmp_path_factory.mktemp(ticker.lower())
            for gz in gz_files:
                (dest / gz.name[:-3]).write_bytes(gzip.decompress(gz.read_bytes()))
            cache[ticker] = XBRL.from_directory(dest)
        return cache[ticker]

    return _load


def test_the_fixtures_are_present():
    """Absent is not passing: every company has an instance and a schema."""
    for ticker, rel in FILINGS.items():
        src = FIXTURES / rel
        assert list(src.glob("*_htm.xml.gz")), f"{ticker}: no instance in {src}"
        assert list(src.glob("*.xsd.gz")), f"{ticker}: no schema in {src}"


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
    dim_rows = concept_rows[concept_rows['dimension'].eq(True)]
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


def concept_rows(df: pd.DataFrame, concept: str) -> pd.DataFrame:
    """Rows for exactly one concept, with the most recent period's value as `value`."""
    value_col = [c for c in df.columns if '-' in c and c[:4].isdigit()][0]
    rows = df[df['concept'] == concept]
    return rows.assign(value=rows[value_col])


# =============================================================================
# INCOME STATEMENT TEST CASES - CostOfGoodsAndServicesSold
# =============================================================================

class TestIncomeStatementCOGS:
    """Test that COGS face values are preserved for dimensional-only filers."""

    @pytest.fixture
    def load_income_statement(self, load_xbrl):
        """Helper to load income statement for a company."""
        def _load(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame, bool]:
            xbrl = load_xbrl(ticker)

            stmt = xbrl.statements.income_statement()
            df_all = stmt.to_dataframe(view='detailed')
            df_filtered = stmt.to_dataframe(view='standard')

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
        assert cogs_filtered is not None and cogs_filtered != 0, "Boeing COGS should have non-zero value"

    def test_boeing_cogs_face_values_match_the_filing(self, load_income_statement):
        """The filtered view keeps Boeing's product and service COGS at the filed amounts.

        Boeing tags CostOfGoodsAndServicesSold only on ProductOrServiceAxis, so filtering that
        axis out as a breakdown would drop its cost of sales from the face statement.
        """
        _, df_filtered, _ = load_income_statement("BA")

        rows = concept_rows(df_filtered, "us-gaap_CostOfGoodsAndServicesSold")
        amounts = {abs(v) for v in rows["value"].dropna()}

        assert {73_761_000_000, 11_413_000_000} <= amounts, amounts
        total = rows[rows["dimension"].eq(False)]["value"].abs()
        assert list(total) == [85_174_000_000]

    def test_carrier_cogs_preserved(self, load_income_statement):
        """Carrier reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("CARR")

        assert has_def, "Carrier should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        assert cogs_filtered is not None and cogs_filtered != 0, \
            "Carrier COGS should be preserved"

    def test_general_dynamics_cogs_preserved(self, load_income_statement):
        """General Dynamics reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("GD")

        assert has_def, "GD should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        assert cogs_filtered is not None and cogs_filtered != 0, \
            "GD COGS should be preserved"

    def test_huntington_ingalls_cogs_preserved(self, load_income_statement):
        """Huntington Ingalls reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("HII")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        # HII may use different concept names
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered != 0, \
            "HII cost of revenue should be preserved"

    def test_intuit_cogs_preserved(self, load_income_statement):
        """Intuit reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("INTU")

        assert has_def, "Intuit should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered != 0, \
            "Intuit COGS should be preserved"

    def test_northrop_grumman_cogs_preserved(self, load_income_statement):
        """Northrop Grumman reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("NOC")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered != 0, \
            "NOC COGS should be preserved"

    def test_rtx_cogs_preserved(self, load_income_statement):
        """RTX (Raytheon) reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("RTX")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered != 0, \
            "RTX COGS should be preserved"

    def test_schlumberger_cogs_preserved(self, load_income_statement):
        """Schlumberger reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("SLB")

        assert has_def, "SLB should have definition linkbase"

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered != 0, \
            "SLB COGS should be preserved"

    def test_workday_cogs_preserved(self, load_income_statement):
        """Workday reports COGS via ProductOrServiceAxis."""
        df_all, df_filtered, has_def = load_income_statement("WDAY")

        cogs_filtered = get_face_value_sum(df_filtered, "CostOfGoodsAndServicesSold")
        if cogs_filtered is None:
            cogs_filtered = get_face_value_sum(df_filtered, "CostOfRevenue")

        assert cogs_filtered is not None and cogs_filtered != 0, \
            "Workday COGS should be preserved"


# =============================================================================
# BALANCE SHEET TEST CASES - Goodwill
# =============================================================================

@pytest.fixture
def load_balance_sheet(load_xbrl):
    """Helper to load balance sheet for a company."""
    def _load(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame, bool]:
        xbrl = load_xbrl(ticker)

        stmt = xbrl.statements.balance_sheet()
        df_all = stmt.to_dataframe(view='detailed')
        df_filtered = stmt.to_dataframe(view='standard')

        _, role_uri, _ = xbrl.find_statement("BalanceSheet")
        has_def = xbrl.has_definition_linkbase_for_role(role_uri) if role_uri else False

        return df_all, df_filtered, has_def
    return _load


class TestBalanceSheetGoodwill:
    """Test that Goodwill face values are preserved."""

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

    def test_boston_scientific_goodwill_matches_the_filing(self, load_balance_sheet):
        """BSX's face goodwill is kept at the filed amount; its acquisition breakdown is not."""
        df_all, df_filtered, _ = load_balance_sheet("BSX")

        filtered = concept_rows(df_filtered, "us-gaap_Goodwill")
        assert list(filtered["value"]) == [18_282_000_000]
        assert list(filtered["dimension"]) == [False]

        detailed = concept_rows(df_all, "us-gaap_Goodwill")
        assert 507_000_000 in set(detailed["value"].dropna()), \
            "the All Other acquisition breakdown should still be in the detailed view"

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

class TestBalanceSheetPPE:
    """Test that PPE face values are preserved."""

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

    def test_csx_ppe_net_matches_the_filing(self, load_balance_sheet):
        """CSX's net PP&E stays at the filed amount and its by-type breakdown is filtered out."""
        df_all, df_filtered, _ = load_balance_sheet("CSX")

        filtered = concept_rows(df_filtered, "us-gaap_PropertyPlantAndEquipmentNet")
        assert list(filtered["value"]) == [36_811_000_000]
        assert list(filtered["dimension"]) == [False]

        detailed = concept_rows(df_all, "us-gaap_PropertyPlantAndEquipmentNet")
        assert 27_300_000_000 in set(detailed["value"].dropna()), \
            "Road and track assets should still be in the detailed view"

    def test_hilton_ppe_preserved(self, load_balance_sheet):
        """Hilton PPE should be preserved."""
        df_all, df_filtered, has_def = load_balance_sheet("HLT")

        ppe_filtered = get_face_value_sum(df_filtered, "PropertyPlantAndEquipment")

        assert ppe_filtered is not None and ppe_filtered > 0, \
            "Hilton PPE should be preserved"


# =============================================================================
# CONTROL CASES - Breakdowns Should Still Be Filtered
# =============================================================================

class TestBreakdownsFiltered:
    """Test that breakdown dimensions are still correctly filtered."""

    def test_geographic_breakdown_filtered(self, load_xbrl):
        """StatementGeographicalAxis should be filtered as breakdown."""
        from edgar.xbrl.dimensions import is_breakdown_dimension

        xbrl = load_xbrl("BA")

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

class TestSummaryValidation:
    """Summary tests to verify overall fix effectiveness."""

    def test_all_income_statement_cases_have_cogs(self, load_xbrl):
        """Verify all income statement test cases have COGS values."""
        tickers = ['BA', 'CARR', 'GD', 'INTU', 'SLB']  # Subset for faster testing
        results = {}

        for ticker in tickers:
            try:
                xbrl = load_xbrl(ticker)

                stmt = xbrl.statements.income_statement()
                df = stmt.to_dataframe(view='standard')

                cogs = get_face_value_sum(df, "CostOfGoodsAndServicesSold")
                if cogs is None:
                    cogs = get_face_value_sum(df, "CostOfRevenue")

                results[ticker] = (
                    None if (cogs is not None and cogs != 0)
                    else f"COGS resolved to {cogs!r}"
                )
            except Exception as e:  # noqa: BLE001 — recorded, not swallowed
                # Keeping the exception matters: this branch turns any failure
                # into "failed COGS validation", so a connection error used to
                # be reported as a data-correctness defect in five companies at
                # once. The cause now travels with the failure.
                results[ticker] = f"{type(e).__name__}: {e}"

        failed = {t: why for t, why in results.items() if why is not None}
        assert not failed, f"These companies failed COGS validation: {failed}"

    def test_dimension_filtering_reduces_row_count(self, load_xbrl):
        """Verify that dimension filtering still reduces row count (breakdowns filtered)."""
        xbrl = load_xbrl("BA")

        stmt = xbrl.statements.income_statement()
        df_all = stmt.to_dataframe(view='detailed')
        df_filtered = stmt.to_dataframe(view='standard')

        # Filtered should have fewer rows (breakdowns removed)
        assert len(df_filtered) < len(df_all), \
            "Filtering should reduce row count by removing breakdowns"

        # But not zero - face values should remain
        assert len(df_filtered) > 10, \
            "Filtered statement should still have substantial content"
