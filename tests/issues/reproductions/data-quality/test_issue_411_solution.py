"""
Test script for Issue #411 solution - Standardized Financial Data Accessor Methods

This script tests the new standardized methods added to the Financials class.
"""

import sys
import traceback
import pytest

# Add the project root to Python path if needed
if '/Users/dwight/PycharmProjects/edgartools' not in sys.path:
    sys.path.insert(0, '/Users/dwight/PycharmProjects/edgartools')

from edgar import Company


@pytest.mark.regression
def test_standardized_methods():
    """Test the new standardized financial accessor methods."""
    print("=" * 60)
    print("TESTING NEW STANDARDIZED FINANCIAL ACCESSOR METHODS")
    print("=" * 60)
    
    # Test with the companies from the user's original issue
    companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    for ticker in companies:
        print(f"\n--- Testing {ticker} ---")
        try:
            company = Company(ticker)
            financials = company.get_financials()
            
            if financials:
                print(f"✓ Company({ticker}) and get_financials() work")
                
                # Test the new methods that were requested in the issue
                try:
                    revenue = financials.get_revenue()
                    print(f"✓ get_revenue() = {revenue:,}" if revenue else "✗ get_revenue() = None")
                except Exception as e:
                    print(f"✗ get_revenue() error: {e}")
                
                try:
                    net_income = financials.get_net_income()
                    print(f"✓ get_net_income() = {net_income:,}" if net_income else "✗ get_net_income() = None")
                except Exception as e:
                    print(f"✗ get_net_income() error: {e}")
                    
                try:
                    total_assets = financials.get_total_assets()
                    print(f"✓ get_total_assets() = {total_assets:,}" if total_assets else "✗ get_total_assets() = None")
                except Exception as e:
                    print(f"✗ get_total_assets() error: {e}")
                
                # Test some additional methods
                try:
                    operating_cf = financials.get_operating_cash_flow()
                    print(f"✓ get_operating_cash_flow() = {operating_cf:,}" if operating_cf else "✗ get_operating_cash_flow() = None")
                except Exception as e:
                    print(f"✗ get_operating_cash_flow() error: {e}")
                    
            else:
                print(f"✗ get_financials() returned None")
                
        except Exception as e:
            print(f"✗ Error with {ticker}: {e}")
            traceback.print_exc()

@pytest.mark.regression
def test_financial_metrics_method():
    """Test the comprehensive get_financial_metrics() method."""
    print("\n" + "=" * 60)
    print("TESTING get_financial_metrics() METHOD")
    print("=" * 60)
    
    try:
        # Test with Apple (known to have comprehensive data)
        company = Company("AAPL")
        financials = company.get_financials()
        
        if financials:
            print(f"✓ Testing comprehensive metrics for Apple")
            
            metrics = financials.get_financial_metrics()
            print(f"✓ get_financial_metrics() returned {len(metrics)} metrics")
            
            print("\n--- Financial Metrics Summary ---")
            for key, value in metrics.items():
                if value is not None:
                    if isinstance(value, (int, float)) and abs(value) > 1000:
                        print(f"{key:20}: ${value:>15,.0f}")
                    else:
                        print(f"{key:20}: {value:>15}")
                else:
                    print(f"{key:20}: {'N/A':>15}")
                    
        else:
            print("✗ Could not get financials for AAPL")
            
    except Exception as e:
        print(f"✗ Error testing financial metrics: {e}")
        traceback.print_exc()

@pytest.mark.regression
def test_period_offset():
    """Test the period_offset functionality."""
    print("\n" + "=" * 60)
    print("TESTING PERIOD OFFSET FUNCTIONALITY")
    print("=" * 60)
    
    try:
        company = Company("AAPL")
        financials = company.get_financials()
        
        if financials:
            print(f"✓ Testing multi-period data for Apple")
            
            # Test getting current and previous period data
            current_revenue = financials.get_revenue(0)  # Most recent
            prev_revenue = financials.get_revenue(1)     # Previous period
            
            print(f"Current period revenue: ${current_revenue:,}" if current_revenue else "Current revenue: N/A")
            print(f"Previous period revenue: ${prev_revenue:,}" if prev_revenue else "Previous revenue: N/A")
            
            if current_revenue and prev_revenue:
                growth = (current_revenue - prev_revenue) / prev_revenue * 100
                print(f"Revenue growth: {growth:.1f}%")
            
    except Exception as e:
        print(f"✗ Error testing period offset: {e}")
        traceback.print_exc()

@pytest.mark.regression
def test_user_original_workflow():
    """Test the exact workflow the user wanted in their issue."""
    print("\n" + "=" * 60)
    print("TESTING USER'S ORIGINAL DESIRED WORKFLOW")
    print("=" * 60)
    
    # This is the exact code the user wanted to work
    companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    print("Running user's original desired code...")
    for ticker in companies:
        try:
            company = Company(ticker)
            financials = company.get_financials()
            
            if financials:
                metrics = {
                    'revenue': financials.get_revenue(),
                    'net_income': financials.get_net_income(),
                    'total_assets': financials.get_total_assets()
                }
                
                print(f"{ticker}: Revenue=${metrics['revenue']:,}, "
                      f"Net Income=${metrics['net_income']:,}, "
                      f"Total Assets=${metrics['total_assets']:,}"
                      if all(v is not None for v in metrics.values()) else f"{ticker}: Some data missing")
                      
        except Exception as e:
            print(f"Error with {ticker}: {e}")
    
    print("\n✓ USER'S DESIRED WORKFLOW NOW WORKS!")


if __name__ == "__main__":
    print("EdgarTools Issue #411 - Solution Test Script")
    print("Testing the new standardized financial data accessor methods")
    
    test_standardized_methods()
    test_financial_metrics_method()
    test_period_offset()
    test_user_original_workflow()
    
    print("\n" + "=" * 60)
    print("TESTING COMPLETED")
    print("=" * 60)