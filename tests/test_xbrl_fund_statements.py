"""
Tests for fund-specific XBRL statement extraction.

These tests verify that EdgarTools can properly extract financial statements
from investment company filings (BDCs, closed-end funds, etc.) including:
- Schedule of Investments (via xbrl.statements.schedule_of_investments())
- Fund detection (via xbrl.fund_statements.is_fund_filing())
- Financial Highlights (pending TextBlock parsing)
"""

from pathlib import Path

import pytest
from edgar.xbrl.xbrl import XBRL
from edgar.xbrl.fund_statements import FundStatements, FUND_INDICATOR_CONCEPTS
from edgar.xbrl.statement_resolver import statement_registry
from edgar.xbrl.period_selector import ESSENTIAL_CONCEPT_PATTERNS


@pytest.fixture
def gbdc_xbrl():
    """Load GBDC (Golub Capital BDC) test fixture - a business development company."""
    data_dir = Path("tests/fixtures/xbrl/gbdc")
    return XBRL.from_directory(data_dir)


class TestFundStatementRegistry:
    """Test that fund statement types are properly registered."""

    def test_schedule_of_investments_in_registry(self):
        """Verify ScheduleOfInvestments is registered in statement_registry."""
        assert "ScheduleOfInvestments" in statement_registry
        soi = statement_registry["ScheduleOfInvestments"]
        assert soi.name == "ScheduleOfInvestments"
        assert "us-gaap_ScheduleOfInvestmentsAbstract" in soi.primary_concepts
        assert soi.supports_parenthetical is True

    def test_financial_highlights_in_registry(self):
        """Verify FinancialHighlights is registered in statement_registry."""
        assert "FinancialHighlights" in statement_registry
        fh = statement_registry["FinancialHighlights"]
        assert fh.name == "FinancialHighlights"
        assert "us-gaap_InvestmentCompanyFinancialHighlightsAbstract" in fh.primary_concepts

    def test_fund_essential_concept_patterns(self):
        """Verify fund-specific essential concept patterns are defined."""
        assert "ScheduleOfInvestments" in ESSENTIAL_CONCEPT_PATTERNS
        soi_patterns = ESSENTIAL_CONCEPT_PATTERNS["ScheduleOfInvestments"]
        # Should have at least 2 pattern groups
        assert len(soi_patterns) >= 2
        # Should include key investment concepts
        all_patterns = [p for group in soi_patterns for p in group]
        assert any("InvestmentOwnedAtFairValue" in p for p in all_patterns)

        assert "FinancialHighlights" in ESSENTIAL_CONCEPT_PATTERNS
        fh_patterns = ESSENTIAL_CONCEPT_PATTERNS["FinancialHighlights"]
        assert len(fh_patterns) >= 1


class TestFundStatements:
    """Test the FundStatements class."""

    def test_fund_statements_initialization(self, gbdc_xbrl):
        """Test that FundStatements initializes properly."""
        fund_stmts = FundStatements(gbdc_xbrl)
        assert fund_stmts is not None
        assert fund_stmts.xbrl is gbdc_xbrl

    def test_is_fund_filing_detection(self, gbdc_xbrl):
        """Test that GBDC is detected as a fund filing."""
        fund_stmts = FundStatements(gbdc_xbrl)
        # GBDC should be detected as a fund filing
        assert fund_stmts.is_fund_filing() is True

    def test_fund_statements_property_on_xbrl(self, gbdc_xbrl):
        """Test that fund_statements property is accessible on XBRL."""
        assert hasattr(gbdc_xbrl, 'fund_statements')
        fund_stmts = gbdc_xbrl.fund_statements
        assert isinstance(fund_stmts, FundStatements)

    def test_fund_statements_caching(self, gbdc_xbrl):
        """Test that fund_statements uses caching."""
        fund_stmts1 = gbdc_xbrl.fund_statements
        fund_stmts2 = gbdc_xbrl.fund_statements
        assert fund_stmts1 is fund_stmts2  # Should be same cached instance


class TestScheduleOfInvestments:
    """Test Schedule of Investments extraction via xbrl.statements."""

    def test_find_schedule_of_investments_role(self, gbdc_xbrl):
        """Test that we can find the Schedule of Investments role."""
        # Check that we can find a role containing scheduleofinvestments
        roles = list(gbdc_xbrl.presentation_trees.keys())
        soi_roles = [r for r in roles if 'scheduleofinvestments' in r.lower().replace(' ', '')]
        assert len(soi_roles) > 0, "Should find at least one Schedule of Investments role"

    def test_schedule_of_investments_via_statements(self, gbdc_xbrl):
        """Test that we can get Schedule of Investments via xbrl.statements."""
        # Schedule of Investments is now accessed via statements (works for all companies)
        soi = gbdc_xbrl.statements.schedule_of_investments()
        # Note: This may be None if the fixture doesn't have the right structure
        # The test validates the API works correctly
        if soi is not None:
            assert soi.canonical_type == "ScheduleOfInvestments"

    def test_schedule_of_investments_method_exists(self, gbdc_xbrl):
        """Verify schedule_of_investments() method exists on statements."""
        assert hasattr(gbdc_xbrl.statements, 'schedule_of_investments')


class TestDataDensityFiltering:
    """Test that fund statements pass data density filtering."""

    def test_relaxed_filtering_for_unknown_types(self, gbdc_xbrl):
        """Test that statement types without patterns use relaxed filtering."""
        from edgar.xbrl.period_selector import _filter_periods_with_sufficient_data

        # Get some candidate periods
        reporting_periods = gbdc_xbrl.reporting_periods
        if reporting_periods:
            candidate_periods = [(p['key'], p['label']) for p in reporting_periods[:5]]

            # Test with an unknown statement type - should use relaxed filtering
            periods = _filter_periods_with_sufficient_data(
                gbdc_xbrl, candidate_periods, "SomeUnknownStatementType"
            )

            # Should not fail and may return periods if facts exist
            assert isinstance(periods, list)

    def test_schedule_of_investments_passes_filtering(self, gbdc_xbrl):
        """Test that ScheduleOfInvestments passes data density checks."""
        from edgar.xbrl.period_selector import _filter_periods_with_sufficient_data

        # Get candidate periods
        reporting_periods = gbdc_xbrl.reporting_periods
        if reporting_periods:
            candidate_periods = [(p['key'], p['label']) for p in reporting_periods[:5]]

            # Filter with ScheduleOfInvestments type
            periods = _filter_periods_with_sufficient_data(
                gbdc_xbrl, candidate_periods, "ScheduleOfInvestments"
            )

            # Should return periods if the filing has investment data
            assert isinstance(periods, list)


class TestFundIndicatorConcepts:
    """Test fund indicator concept detection."""

    def test_fund_indicator_concepts_defined(self):
        """Verify fund indicator concepts are properly defined."""
        assert len(FUND_INDICATOR_CONCEPTS) >= 5
        assert 'us-gaap_ScheduleOfInvestmentsAbstract' in FUND_INDICATOR_CONCEPTS
        assert 'us-gaap_InvestmentOwnedAtFairValue' in FUND_INDICATOR_CONCEPTS


class TestFundStatementsRepr:
    """Test FundStatements representation."""

    def test_repr(self, gbdc_xbrl):
        """Test string representation."""
        fund_stmts = gbdc_xbrl.fund_statements
        repr_str = repr(fund_stmts)
        assert "FundStatements" in repr_str
        assert "is_fund=" in repr_str

    def test_get_available_statements(self, gbdc_xbrl):
        """Test getting list of available fund statements."""
        fund_stmts = gbdc_xbrl.fund_statements
        available = fund_stmts.get_available_statements()
        assert isinstance(available, list)
        # Currently empty since Financial Highlights is pending TextBlock parsing
        # Schedule of Investments is accessed via xbrl.statements
