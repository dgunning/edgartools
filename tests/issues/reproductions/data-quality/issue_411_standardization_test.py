#!/usr/bin/env python3
"""
Issue #411 - Standardization Test
Reproduction script for testing the standardized financial data extraction methods.

User reported AttributeError: 'Financials' object has no attribute 'get_revenue'
but we can see from financials.py that these methods should exist.

Let's test what's actually happening.
"""

import sys
from pathlib import Path

# Add the edgar package to path
sys.path.insert(0, str(Path(__file__).parents[4]))

from edgar import Company
import pytest

@pytest.mark.regression
def test_standardization_issue():
    """Test the standardization functionality with companies mentioned in the issue."""
    
    companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]
    
    for ticker in companies:
        print(f"\n=== Testing {ticker} ===")
        try:
            company = Company(ticker)
            print(f"Company: {company.name}")
            
            # Test getting financials
            financials = company.get_financials()
            print(f"Financials object: {type(financials)}")
            
            if financials is None:
                print(f"No financials available for {ticker}")
                continue
                
            # Test if methods exist
            methods_to_test = [
                'get_revenue',
                'get_net_income', 
                'get_total_assets',
                'get_financial_metrics'
            ]
            
            for method_name in methods_to_test:
                if hasattr(financials, method_name):
                    print(f"✓ Has method: {method_name}")
                    try:
                        method = getattr(financials, method_name)
                        result = method()
                        print(f"  {method_name}(): {result}")
                    except Exception as e:
                        print(f"  ERROR calling {method_name}(): {e}")
                else:
                    print(f"✗ Missing method: {method_name}")
                    
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_standardization_issue()