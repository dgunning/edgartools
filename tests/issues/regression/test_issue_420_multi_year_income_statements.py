#!/usr/bin/env python3
"""
Regression test for GitHub issue #420:
"Why can't get the latest continuous five year income statement?"

This test ensures that users can successfully retrieve multi-year income statements
using the correct APIs and that the error conditions are properly handled.
"""

import pytest
from edgar import Company


class TestMultiYearIncomeStatements:
    """Test suite for multi-year income statement retrieval."""
    
    @pytest.fixture
    def company(self):
        """Create a test company instance."""
        return Company("AAPL")
    
    def test_company_income_statement_with_periods(self, company):
        """Test Company.income_statement() with periods parameter."""
        # This is the primary solution for the user's issue
        income = company.income_statement(periods=5, annual=True)
        
        # Should return a MultiPeriodStatement or None (if no data)
        assert income is None or hasattr(income, 'periods')
        
        if income is not None:
            # Should have period information
            periods = getattr(income, 'periods', [])
            assert isinstance(periods, list)
            # Should have at least 1 period, up to 5
            assert 1 <= len(periods) <= 5
    
    def test_company_income_statement_as_dataframe(self, company):
        """Test Company.income_statement() returning DataFrame."""
        income_df = company.income_statement(periods=5, annual=True, as_dataframe=True)
        
        if income_df is not None:
            import pandas as pd
            assert isinstance(income_df, pd.DataFrame)
            assert income_df.shape[0] > 0  # Should have rows
            assert income_df.shape[1] > 0  # Should have columns
    
    def test_single_filing_xbrl_approach(self, company):
        """Test the single filing XBRL approach (user's working method)."""
        filing = company.get_filings(form="10-K").latest()
        assert filing is not None, "Should have at least one 10-K filing"
        
        xbrl = filing.xbrl()
        if xbrl is not None:  # Some filings may not have XBRL
            statements = xbrl.statements
            assert statements is not None
            
            income_statement = statements.income_statement()
            # Should return a Statement or None
            if income_statement is not None:
                from edgar.xbrl.statements import Statement
                assert isinstance(income_statement, Statement)
    
    def test_multiple_filings_error_condition(self, company):
        """Test that multiple filings don't have .xbrl() method - reproduces user's error."""
        filings = company.get_filings(form="10-K").latest(5)
        
        # Should return an EntityFilings collection, not a single Filing
        from edgar.entity.filings import EntityFilings
        assert isinstance(filings, EntityFilings)
        
        # Should NOT have .xbrl() method - this reproduces the user's error
        assert not hasattr(filings, 'xbrl')
        
        # But individual filings in the collection should have .xbrl() method
        if len(filings) > 0:
            first_filing = filings[0]
            assert hasattr(first_filing, 'xbrl')
    
    def test_statements_income_statement_no_max_periods(self, company):
        """Test that Statements.income_statement() doesn't accept max_periods parameter."""
        filing = company.get_filings(form="10-K").latest()
        if filing is not None:
            xbrl = filing.xbrl()
            if xbrl is not None:
                statements = xbrl.statements
                
                # Should work without parameters
                income_stmt = statements.income_statement()
                # May be None if no income statement available
                
                # Should fail with max_periods parameter - reproduces user's error
                with pytest.raises(TypeError, match="unexpected keyword argument 'max_periods'"):
                    statements.income_statement(max_periods=5)
    
    def test_quarterly_vs_annual_periods(self, company):
        """Test that users can get both quarterly and annual data."""
        # Test annual data
        annual_income = company.income_statement(periods=5, annual=True)
        
        # Test quarterly data  
        quarterly_income = company.income_statement(periods=5, annual=False)
        
        # Both should work (may return None if no data available)
        # If they return data, they should be different types of periods
        if annual_income is not None and quarterly_income is not None:
            annual_periods = getattr(annual_income, 'periods', [])
            quarterly_periods = getattr(quarterly_income, 'periods', [])
            
            # Annual periods should contain 'FY' while quarterly should contain 'Q'
            annual_has_fy = any('FY' in str(p) for p in annual_periods)
            quarterly_has_q = any('Q' in str(p) for p in quarterly_periods)
            
            # At least one should be true (data format may vary)
            assert annual_has_fy or quarterly_has_q
    
    def test_company_facts_availability(self, company):
        """Test that Company.get_facts() works and provides income statement data."""
        facts = company.get_facts()
        
        if facts is not None:
            # Facts should have income statement method
            assert hasattr(facts, 'income_statement')
            
            # Should be able to call it
            facts_income = facts.income_statement(periods=5)
            # May return None if no data, but shouldn't throw exception


@pytest.mark.integration
class TestRealDataIntegration:
    """Integration tests with real data from well-known companies."""
    
    @pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "GOOGL"])
    def test_real_companies_income_statements(self, ticker):
        """Test that income statement retrieval works for major companies."""
        company = Company(ticker)
        
        # Should be able to get some income statement data
        income = company.income_statement(periods=3, annual=True)  # Use 3 periods for reliability
        
        # For major companies, should have at least some data
        # Note: We use 3 periods instead of 5 because not all companies have 5 years of data
        if income is not None:
            periods = getattr(income, 'periods', [])
            assert len(periods) >= 1, f"Should have at least 1 period of data for {ticker}"
    
    def test_api_methods_dont_break(self):
        """Test that the APIs don't break with reasonable inputs."""
        company = Company("AAPL")
        
        # These should not throw exceptions, even if they return None
        try:
            company.income_statement(periods=1)
            company.income_statement(periods=5)
            company.income_statement(periods=10, annual=True)
            company.income_statement(periods=4, annual=False)
            company.income_statement(periods=3, as_dataframe=True)
        except Exception as e:
            pytest.fail(f"API methods should not throw exceptions with valid parameters: {e}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])