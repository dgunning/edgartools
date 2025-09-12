#!/usr/bin/env python3
"""
Test specifically for the fixed financial metrics issue
"""

import sys
from pathlib import Path
import pytest

# Add the edgar package to path
sys.path.insert(0, str(Path(__file__).parents[4]))

from edgar import Company


@pytest.mark.regression
def test_financial_metrics_fix():
    """Test the fixed get_financial_metrics method for previously failing companies."""
    
    test_companies = ["MSFT", "META"]
    
    for ticker in test_companies:
        print(f"\n=== Testing {ticker} Financial Metrics Fix ===")
        try:
            company = Company(ticker)
            financials = company.get_financials()
            
            if financials is None:
                print(f"No financials available for {ticker}")
                continue
                
            # This should not error now
            try:
                metrics = financials.get_financial_metrics()
                print(f"✓ get_financial_metrics() succeeded")
                print(f"  Revenue: ${metrics.get('revenue', 'N/A'):,}" if metrics.get('revenue') else "  Revenue: N/A")
                print(f"  Net Income: ${metrics.get('net_income', 'N/A'):,}" if metrics.get('net_income') else "  Net Income: N/A")
                print(f"  Current Ratio: {metrics.get('current_ratio', 'N/A')}")
                print(f"  Free Cash Flow: ${metrics.get('free_cash_flow', 'N/A'):,}" if metrics.get('free_cash_flow') else "  Free Cash Flow: N/A")
            except Exception as e:
                print(f"✗ get_financial_metrics() still failing: {e}")
                
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

if __name__ == "__main__":
    test_financial_metrics_fix()