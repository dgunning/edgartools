"""
Regression test for bug #408 - Annual period selection issue.

Issue: Annual financial statements were showing quarterly values instead of full year.
Fix: Use period duration (>300 days) to distinguish annual from quarterly facts.
"""

import pytest
from edgar import Company


class TestAnnualPeriodSelection:
    """Test that annual=True returns full year values, not quarterly."""
    
    def test_apple_annual_revenue_2020(self):
        """
        Bug #408: AAPL 2020 revenue was showing $64B (Q4) instead of $274B (annual).
        """
        # Get Apple facts
        aapl = Company("AAPL")
        facts = aapl.facts
        
        # Get income statement with annual=True
        income = facts.income_statement(annual=True, periods=6)
        
        # Check FY 2020 revenue (should be ~$274B, not ~$64B)
        # The statement returns a MultiPeriodStatement with items
        for item in income.items:
            if item.label and 'Revenue' in item.label and 'Total' in item.label:
                # Find the FY 2020 value
                for i, period in enumerate(income.periods):
                    if '2020' in str(period):
                        value = item.values[i]
                        if value:
                            # Parse the value (remove formatting)
                            if isinstance(value, str):
                                # Remove $, commas, and suffixes like 'B' or 'M'
                                clean_value = value.replace('$', '').replace(',', '')
                                if 'B' in clean_value or 'M' in clean_value:
                                    # Handle formatted values like "$274.5B"
                                    numeric_part = float(clean_value.replace('B', '').replace('M', ''))
                                    if 'B' in clean_value:
                                        numeric_value = numeric_part * 1_000_000_000
                                    else:
                                        numeric_value = numeric_part * 1_000_000
                                else:
                                    numeric_value = float(clean_value)
                            else:
                                numeric_value = float(value)
                            
                            # Revenue should be > $200B for annual, not ~$64B for quarterly
                            assert numeric_value > 200_000_000_000, \
                                f"FY 2020 revenue should be ~$274B, got {numeric_value/1e9:.1f}B"
                            return  # Test passed
        
        # If we get here, we didn't find the revenue
        pytest.fail("Could not find Total Revenue in income statement")
    
    def test_apple_annual_revenue_2019(self):
        """
        Bug #408: AAPL 2019 revenue was showing $64B (Q4) instead of $260B (annual).
        """
        # Get Apple facts
        aapl = Company("AAPL")
        facts = aapl.facts
        
        # Get income statement with annual=True
        income = facts.income_statement(annual=True, periods=6)
        
        # Check FY 2019 revenue (should be ~$260B, not ~$64B)
        for item in income.items:
            if item.label and 'Revenue' in item.label and 'Total' in item.label:
                # Find the FY 2019 value
                for i, period in enumerate(income.periods):
                    if '2019' in str(period):
                        value = item.values[i]
                        if value:
                            # Parse the value
                            if isinstance(value, str):
                                clean_value = value.replace('$', '').replace(',', '')
                                if 'B' in clean_value or 'M' in clean_value:
                                    numeric_part = float(clean_value.replace('B', '').replace('M', ''))
                                    if 'B' in clean_value:
                                        numeric_value = numeric_part * 1_000_000_000
                                    else:
                                        numeric_value = numeric_part * 1_000_000
                                else:
                                    numeric_value = float(clean_value)
                            else:
                                numeric_value = float(value)
                            
                            # Revenue should be > $200B for annual, not ~$64B for quarterly
                            assert numeric_value > 200_000_000_000, \
                                f"FY 2019 revenue should be ~$260B, got {numeric_value/1e9:.1f}B"
                            return
        
        pytest.fail("Could not find Total Revenue in income statement")
    
    @pytest.mark.parametrize("ticker,min_revenue_billions", [
        ("MSFT", 100),  # Microsoft should have > $100B annual revenue
        ("AMZN", 200),  # Amazon should have > $200B annual revenue
    ])
    def test_other_companies_annual_revenue(self, ticker, min_revenue_billions):
        """
        Ensure other companies also get correct annual values.
        """
        company = Company(ticker)
        facts = company.facts
        income = facts.income_statement(annual=True, periods=2)
        
        # Find revenue in most recent period
        for item in income.items:
            if item.label and 'Revenue' in item.label:
                value = item.values[0] if item.values else None
                if value:
                    # Parse the value
                    if isinstance(value, str):
                        clean_value = value.replace('$', '').replace(',', '')
                        if 'B' in clean_value:
                            numeric_value = float(clean_value.replace('B', '')) * 1_000_000_000
                        elif 'M' in clean_value:
                            numeric_value = float(clean_value.replace('M', '')) * 1_000_000
                        else:
                            numeric_value = float(clean_value)
                    else:
                        numeric_value = float(value)
                    
                    min_revenue = min_revenue_billions * 1_000_000_000
                    assert numeric_value > min_revenue, \
                        f"{ticker} annual revenue should be > ${min_revenue_billions}B, got {numeric_value/1e9:.1f}B"
                    return
        
        pytest.fail(f"Could not find Revenue for {ticker}")