"""
Regression test for bug #408 - Annual period selection issue.

Issue: Annual financial statements were showing quarterly values instead of full year.
Fix: Use period duration (>300 days) to distinguish annual from quarterly facts.
"""

import pytest


class TestAnnualPeriodSelection:
    """Test that annual=True returns full year values, not quarterly."""
    
    def _find_revenue_item(self, items):
        """Helper method to find total revenue item in statement"""
        for item in items:
            if item.label and 'Revenue' in item.label and 'Total' in item.label:
                return item
            # Check children
            if hasattr(item, 'children'):
                found = self._find_revenue_item(item.children)
                if found:
                    return found
        return None
    
    def _get_apple_annual_income(self, aapl_company):
        """Helper method to get Apple's annual income statement"""
        facts = aapl_company.facts
        return facts.income_statement(annual=True, periods=6)
    
    @pytest.mark.network
    @pytest.mark.slow
    @pytest.mark.parametrize("year,min_revenue_billions", [
        ("2021", 200),
        ("2020", 200),  # Should be ~$274B, not ~$64B
    ])
    def test_apple_annual_revenue_by_year(self, aapl_company, year, min_revenue_billions):
        """Bug #408: AAPL revenue was showing quarterly instead of annual values"""
        income = self._get_apple_annual_income(aapl_company)
        revenue_item = self._find_revenue_item(income.items)
        
        if not revenue_item:
            pytest.fail("Could not find Total Revenue in income statement")
        
        # Find the specified year value
        for period in income.periods:
            if year in str(period):
                value = revenue_item.values.get(period)
                if value:
                    numeric_value = float(value)
                    min_revenue = min_revenue_billions * 1_000_000_000
                    
                    assert numeric_value > min_revenue, \
                        f"FY {year} revenue should be > ${min_revenue_billions}B, got {numeric_value/1e9:.1f}B"
                    return
        
        pytest.fail(f"Could not find FY {year} in periods: {income.periods}")
    
    @pytest.mark.network
    @pytest.mark.slow
    @pytest.mark.parametrize("company_fixture,min_revenue_billions", [
        ("msft_company", 100),  # Microsoft should have > $100B annual revenue
        ("amzn_company", 200),  # Amazon should have > $200B annual revenue
    ])
    def test_other_companies_annual_revenue(self, company_fixture, min_revenue_billions, request):
        """
        Ensure other companies also get correct annual values.
        """
        company = request.getfixturevalue(company_fixture)
        facts = company.facts
        income = facts.income_statement(annual=True, periods=2)
        
        # Find revenue in most recent period
        def find_revenue_item(items):
            for item in items:
                if item.label and 'Revenue' in item.label:
                    return item
                # Check children
                if hasattr(item, 'children'):
                    found = find_revenue_item(item.children)
                    if found:
                        return found
            return None
        
        revenue_item = find_revenue_item(income.items)
        if not revenue_item:
            pytest.fail(f"Could not find Revenue for {company.tickers[0] if company.tickers else company.name}")
        
        # Get most recent period value
        if income.periods:
            most_recent_period = income.periods[0]  # First period is most recent
            value = revenue_item.values.get(most_recent_period)
            if value:
                # Values are already numeric
                numeric_value = float(value)
                
                min_revenue = min_revenue_billions * 1_000_000_000
                assert numeric_value > min_revenue, \
                    f"{company.tickers[0] if company.tickers else company.name} annual revenue should be > ${min_revenue_billions}B, got {numeric_value/1e9:.1f}B"
                return
        
        pytest.fail(f"Could not find revenue value for {company.tickers[0] if company.tickers else company.name}")