"""
Regression test for Issue #412: Missing historical balance sheet data.

This test ensures that the fix for the filing priority bug continues to work.
The bug caused historical years to show sparse data (only cash values) instead 
of comprehensive balance sheet data due to incorrect period selection logic.
"""

import pytest
from edgar import Company
import pandas as pd


@pytest.mark.network
class TestIssue412Regression:
    """Regression tests for Issue #412 - Missing historical balance sheet data."""

    @pytest.mark.regression
    def test_tsla_historical_balance_sheet_completeness(self):
        """
        Test that TSLA balance sheet shows comprehensive data for historical years.
        
        Before fix: Historical years showed only 1-2 populated rows (sparse data)
        After fix: Historical years should show ~25+ populated rows (comprehensive data)
        """
        company = Company("TSLA")
        
        # Get balance sheet with enough periods to include historical data
        balance_sheet = company.balance_sheet(annual=True, periods=6)
        
        # Convert to dataframe for detailed analysis
        df = balance_sheet.to_dataframe()
        
        # Verify we have the expected structure
        assert len(balance_sheet.periods) >= 4, f"Expected at least 4 periods, got {len(balance_sheet.periods)}"
        assert len(df) > 30, f"Expected substantial balance sheet structure, got {len(df)} rows"
        
        # Check data completeness for historical periods (3rd and 4th periods)
        # Don't hardcode years - use relative positions
        periods = balance_sheet.periods
        
        if len(periods) >= 3:
            third_period = periods[2]  # 3rd most recent period
            third_period_completeness = self._calculate_completeness(df, third_period)
            
            # Historical period should have comprehensive data (>40% populated)
            # Before fix: ~2% populated, After fix: ~55% populated
            assert third_period_completeness > 0.40, (
                f"Third period ({third_period}) should have comprehensive data. "
                f"Got {third_period_completeness:.1%} populated, expected >40%"
            )
        
        if len(periods) >= 4:
            fourth_period = periods[3]  # 4th most recent period  
            fourth_period_completeness = self._calculate_completeness(df, fourth_period)
            
            assert fourth_period_completeness > 0.40, (
                f"Fourth period ({fourth_period}) should have comprehensive data. "
                f"Got {fourth_period_completeness:.1%} populated, expected >40%"
            )

    @pytest.mark.regression
    def test_tsla_balance_sheet_key_items_present(self):
        """
        Test that key balance sheet items are present in historical periods.
        
        Before fix: Only "Cash and Cash Equivalents" was populated
        After fix: Assets, Liabilities, Equity should all be populated
        """
        company = Company("TSLA")
        balance_sheet = company.balance_sheet(annual=True, periods=4)
        df = balance_sheet.to_dataframe()
        
        periods = balance_sheet.periods
        if len(periods) >= 3:
            third_period = periods[2]
            
            # Check for key balance sheet concepts in historical data
            key_concepts = [
                "Assets",
                "Liabilities", 
                "Stockholders' Equity",
                "Assets, Current"
            ]
            
            populated_key_concepts = 0
            for _, row in df.iterrows():
                label = row.get('label', '').lower()
                if any(concept.lower() in label for concept in key_concepts):
                    if pd.notna(row.get(third_period)):
                        populated_key_concepts += 1
            
            assert populated_key_concepts >= 3, (
                f"Expected at least 3 key balance sheet concepts populated in {third_period}, "
                f"but only found {populated_key_concepts}"
            )

    @pytest.mark.regression
    def test_rich_output_shows_historical_data(self):
        """
        Test that rich output (__rich__) shows data in historical columns.
        
        This is what users see when they print the balance sheet.
        """
        company = Company("TSLA")
        balance_sheet = company.balance_sheet(annual=True, periods=4)
        
        # Get the rich representation
        rich_repr = balance_sheet.__rich__()
        
        # Convert to string to analyze content
        from rich.console import Console
        console = Console(file=None, width=120)  # Wider to avoid truncation
        
        with console.capture() as capture:
            console.print(rich_repr)
        output = capture.get()
        
        # Check that historical periods show substantial data
        # Look for patterns like "$XX,XXX,..." which indicate populated values
        periods = balance_sheet.periods
        if len(periods) >= 3:
            third_period = periods[2]
            fourth_period = periods[3] if len(periods) >= 4 else None
            
            # Count value patterns in the output
            import re
            value_pattern = r'\$[\d,]+[.,…]'  # Matches $123,456... or $123,456,789
            
            # Split output by lines and look for lines with values
            lines_with_values = [line for line in output.split('\n') 
                               if re.search(value_pattern, line)]
            
            assert len(lines_with_values) >= 10, (
                f"Expected substantial data in rich output, but only found "
                f"{len(lines_with_values)} lines with values"
            )
            
            # Verify that historical periods appear in the header
            assert third_period in output, f"Third period {third_period} should appear in output"
            if fourth_period:
                assert fourth_period in output, f"Fourth period {fourth_period} should appear in output"

    @pytest.mark.regression
    def test_multiple_companies_no_regression(self):
        """
        Test that the fix doesn't break other companies.
        
        The fix should maintain or improve data completeness for other major companies.
        """
        test_companies = ["AAPL", "MSFT", "GOOGL"]
        
        for ticker in test_companies:
            try:
                company = Company(ticker)
                balance_sheet = company.balance_sheet(annual=True, periods=4)
                df = balance_sheet.to_dataframe()
                
                # Basic sanity checks
                assert len(balance_sheet.periods) >= 3, f"{ticker}: Expected at least 3 periods"
                assert len(df) > 20, f"{ticker}: Expected substantial balance sheet structure"
                
                # Check that recent periods are well-populated
                recent_period = balance_sheet.periods[0]
                recent_completeness = self._calculate_completeness(df, recent_period)
                
                assert recent_completeness > 0.30, (
                    f"{ticker}: Recent period should be well-populated. "
                    f"Got {recent_completeness:.1%}, expected >30%"
                )
                
            except Exception as e:
                pytest.fail(f"Regression detected for {ticker}: {e}")
    
    def _calculate_completeness(self, df: pd.DataFrame, period_column: str) -> float:
        """Calculate data completeness for a period column."""
        if period_column not in df.columns:
            return 0.0
        
        non_null_count = df[period_column].count()
        total_count = len(df)
        
        return non_null_count / total_count if total_count > 0 else 0.0


if __name__ == "__main__":
    # Run the regression tests
    test = TestIssue412Regression()
    
    print("🧪 Running Issue #412 Regression Tests...")
    
    try:
        test.test_tsla_historical_balance_sheet_completeness()
        print("✅ TSLA historical completeness test passed")
    except Exception as e:
        print(f"❌ TSLA historical completeness test failed: {e}")
    
    try:
        test.test_tsla_balance_sheet_key_items_present()
        print("✅ TSLA key items test passed")
    except Exception as e:
        print(f"❌ TSLA key items test failed: {e}")
    
    try:
        test.test_rich_output_shows_historical_data()
        print("✅ Rich output test passed")
    except Exception as e:
        print(f"❌ Rich output test failed: {e}")
    
    try:
        test.test_multiple_companies_no_regression()
        print("✅ Multi-company regression test passed")
    except Exception as e:
        print(f"❌ Multi-company regression test failed: {e}")
    
    print("🎉 All regression tests completed!")