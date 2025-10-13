#!/usr/bin/env python3
"""
Regression test for GitHub Issue #446: Missing values in 20-F filings

This test ensures that 20-F filings using IFRS taxonomy properly return
financial statement data and prevents regression of the fix.

Issue: https://github.com/dgunning/edgartools/issues/446
Root Cause: statement_resolver.py only had US-GAAP patterns, missing IFRS equivalents
Fix: Added IFRS alternative concepts and key concepts to statement registry

Created: 2025-09-23
"""

import pytest
from edgar import Company, set_identity


class TestIssue446_20F_IFRS_Statements:
    """Regression tests for 20-F IFRS statement resolution."""

    def test_bntx_20f_statements_have_data(self):
        """Test that BioNTech 20-F statements return data with IFRS concepts.

        This was the primary failing case in issue #446.
        """
        # Get BioNTech latest 20-F filing
        bntx = Company('0001776985')  # BioNTech SE
        filing_20f = bntx.get_filings(form="20-F", amendments=False).latest()

        assert filing_20f is not None, "BioNTech should have 20-F filings"
        assert filing_20f.form == "20-F", "Should be a 20-F form"

        xbrl = filing_20f.xbrl()
        statements = xbrl.statements

        # Test Balance Sheet
        balance_sheet = statements.balance_sheet()
        print(balance_sheet)
        assert balance_sheet is not None, "Balance sheet should be found"

        bs_raw_data = balance_sheet.get_raw_data()
        assert bs_raw_data is not None, "Balance sheet should have raw data"
        assert len(bs_raw_data) > 0, "Balance sheet should have line items"

        # Should have items with values (not just empty concepts)
        items_with_values = sum(1 for item in bs_raw_data if item.get('values', {}))
        assert items_with_values > 0, "Balance sheet should have items with actual values"

        # Test Income Statement
        income_statement = statements.income_statement()
        assert income_statement is not None, "Income statement should be found"

        income_raw_data = income_statement.get_raw_data()
        assert income_raw_data is not None, "Income statement should have raw data"
        assert len(income_raw_data) > 0, "Income statement should have line items"

        # Should have items with values
        items_with_values = sum(1 for item in income_raw_data if item.get('values', {}))
        assert items_with_values > 0, "Income statement should have items with actual values"

        # Test Cash Flow Statement
        cashflow_statement = statements.cashflow_statement()
        assert cashflow_statement is not None, "Cash flow statement should be found"

        cf_raw_data = cashflow_statement.get_raw_data()
        assert cf_raw_data is not None, "Cash flow statement should have raw data"
        assert len(cf_raw_data) > 0, "Cash flow statement should have line items"

        # Should have items with values
        items_with_values = sum(1 for item in cf_raw_data if item.get('values', {}))
        assert items_with_values > 0, "Cash flow statement should have items with actual values"

    def test_ifrs_concepts_detected_in_xbrl(self):
        """Test that IFRS concepts are properly detected in XBRL structure."""
        bntx = Company('0001776985')  # BioNTech SE
        filing_20f = bntx.get_filings(form="20-F", amendments=False).latest()

        xbrl = filing_20f.xbrl()

        # Test that IFRS concepts are present in facts
        facts_df = xbrl.facts.query().limit(100).to_dataframe()
        assert len(facts_df) > 0, "Should have facts available"

        # Look for IFRS concepts in the facts
        ifrs_concepts = facts_df[facts_df['concept'].str.contains('ifrs-full', na=False)]
        assert len(ifrs_concepts) > 0, "Should find IFRS concepts in facts"

        # Test that common IFRS revenue/income concepts are found
        revenue_facts = xbrl.facts.query().by_concept('ifrs-full_Revenue').to_dataframe()
        profit_loss_facts = xbrl.facts.query().by_concept('ifrs-full_ProfitLoss').to_dataframe()

        # Should find at least one of these common IFRS concepts
        total_key_facts = len(revenue_facts) + len(profit_loss_facts)
        assert total_key_facts > 0, "Should find key IFRS financial concepts (Revenue or ProfitLoss)"

    def test_statement_resolver_handles_ifrs_patterns(self):
        """Test that statement resolver properly handles IFRS concept patterns."""
        bntx = Company('0001776985')  # BioNTech SE
        filing_20f = bntx.get_filings(form="20-F", amendments=False).latest()

        xbrl = filing_20f.xbrl()

        # Test that statements are properly resolved by type
        income_data = xbrl.get_statement("IncomeStatement")
        assert income_data is not None, "Should resolve IncomeStatement with IFRS concepts"
        assert len(income_data) > 0, "Income statement should have data"

        balance_data = xbrl.get_statement("BalanceSheet")
        assert balance_data is not None, "Should resolve BalanceSheet with IFRS concepts"
        assert len(balance_data) > 0, "Balance sheet should have data"

        cashflow_data = xbrl.get_statement("CashFlowStatement")
        assert cashflow_data is not None, "Should resolve CashFlowStatement with IFRS concepts"
        assert len(cashflow_data) > 0, "Cash flow statement should have data"

    def test_rendered_statements_display_properly(self):
        """Test that 20-F statements render properly with actual values."""
        bntx = Company('0001776985')  # BioNTech SE
        filing_20f = bntx.get_filings(form="20-F", amendments=False).latest()

        xbrl = filing_20f.xbrl()
        statements = xbrl.statements

        # Test that statements can be rendered (this was failing before the fix)
        income_statement = statements.income_statement()
        rendered_income = str(income_statement)
        assert len(rendered_income) > 100, "Income statement should render to substantial content"

        # Should contain actual financial data, not just headers
        # Look for common patterns that indicate actual data is present
        assert any(char.isdigit() for char in rendered_income), "Should contain numeric values"

        balance_sheet = statements.balance_sheet()
        rendered_balance = str(balance_sheet)
        assert len(rendered_balance) > 100, "Balance sheet should render to substantial content"
        assert any(char.isdigit() for char in rendered_balance), "Should contain numeric values"


if __name__ == "__main__":
    # Run the tests directly
    pytest.main([__file__, "-v"])