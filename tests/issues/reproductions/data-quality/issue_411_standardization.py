"""
Issue #411: Standardization - Add standardized financial data accessor methods

This script reproduces the user's issue and demonstrates the current API capabilities
vs. what the user expects.

The user's issue:
- Wants standardized methods like get_revenue(), get_net_income(), get_total_assets()
- Wants these to work consistently across different companies regardless of custom concepts
- Example companies: AAPL, MSFT, GOOGL, AMZN, META, TSLA

Current state:
- EdgarTools has sophisticated standardization built into XBRL rendering
- But lacks simple accessor methods for common financial metrics
- User has to navigate through statements and understand XBRL structure
"""

import sys
import pandas as pd
from typing import Optional, Dict, Any

# Add the project root to Python path if needed
if '/Users/dwight/PycharmProjects/edgartools' not in sys.path:
    sys.path.insert(0, '/Users/dwight/PycharmProjects/edgartools')

from edgar import Company


def test_user_expected_api():
    """Test the API that the user expects to work (from the issue description)."""
    print("=" * 60)
    print("TESTING USER'S EXPECTED API (from issue description)")
    print("=" * 60)
    
    companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    for ticker in companies:
        print(f"\n--- Testing {ticker} ---")
        try:
            company = Company(ticker)
            print(f"✓ Company({ticker}) created successfully")
            
            # Test get_financials() - this should work
            financials = company.get_financials()
            if financials:
                print(f"✓ get_financials() returned: {type(financials)}")
                
                # Test the methods the user expects to work but don't exist
                try:
                    revenue = financials.get_revenue()
                    print(f"✓ get_revenue() = {revenue}")
                except AttributeError as e:
                    print(f"✗ get_revenue() failed: {e}")
                
                try:
                    net_income = financials.get_net_income()
                    print(f"✓ get_net_income() = {net_income}")
                except AttributeError as e:
                    print(f"✗ get_net_income() failed: {e}")
                    
                try:
                    total_assets = financials.get_total_assets()
                    print(f"✓ get_total_assets() = {total_assets}")
                except AttributeError as e:
                    print(f"✗ get_total_assets() failed: {e}")
                    
            else:
                print(f"✗ get_financials() returned None")
                
        except Exception as e:
            print(f"✗ Error creating Company({ticker}): {e}")


def test_current_api_capabilities():
    """Test what actually works in the current API."""
    print("\n" + "=" * 60)
    print("TESTING CURRENT API CAPABILITIES")
    print("=" * 60)
    
    companies = ["AAPL", "MSFT", "GOOGL"] # Test fewer for demonstration
    
    for ticker in companies:
        print(f"\n--- Testing {ticker} with current API ---")
        try:
            company = Company(ticker)
            financials = company.get_financials()
            
            if financials and financials.xb:
                # Test standardized statements (what actually works)
                income_stmt = financials.income_statement()
                if income_stmt:
                    print(f"✓ income_statement() works")
                    
                    # Test standard rendering (this is the key capability)
                    try:
                        rendered = income_stmt.render(standard=True)
                        df = rendered.to_dataframe()
                        print(f"✓ Standardized rendering works, shape: {df.shape}")
                        
                        # Show some key concepts that are standardized
                        if not df.empty:
                            revenue_concepts = df[df['label'].str.contains('Revenue', case=False, na=False)]
                            if not revenue_concepts.empty:
                                print(f"  - Found revenue concepts: {revenue_concepts['label'].iloc[0]}")
                            
                            net_income_concepts = df[df['label'].str.contains('Net Income', case=False, na=False)]
                            if not net_income_concepts.empty:
                                print(f"  - Found net income concepts: {net_income_concepts['label'].iloc[0]}")
                                
                    except Exception as e:
                        print(f"✗ Standardized rendering failed: {e}")
                        
                # Test balance sheet for assets
                balance_sheet = financials.balance_sheet()
                if balance_sheet:
                    try:
                        rendered_bs = balance_sheet.render(standard=True)
                        df_bs = rendered_bs.to_dataframe()
                        
                        assets_concepts = df_bs[df_bs['label'].str.contains('Total Assets', case=False, na=False)]
                        if not assets_concepts.empty:
                            print(f"  - Found total assets concepts: {assets_concepts['label'].iloc[0]}")
                            
                    except Exception as e:
                        print(f"✗ Balance sheet rendering failed: {e}")
                        
        except Exception as e:
            print(f"✗ Error testing {ticker}: {e}")


def demonstrate_standardization_power():
    """Demonstrate the power of the existing standardization system."""
    print("\n" + "=" * 60)
    print("DEMONSTRATING EXISTING STANDARDIZATION CAPABILITIES")
    print("=" * 60)
    
    try:
        # Test with a company known to have custom concepts (TSLA)
        company = Company("TSLA")
        financials = company.get_financials()
        
        if financials and financials.xb:
            print(f"✓ Testing TSLA (known for custom concepts)")
            
            # Get income statement both ways
            income_stmt = financials.income_statement()
            if income_stmt:
                # Non-standardized
                print("\n--- Non-standardized labels ---")
                rendered_raw = income_stmt.render(standard=False)
                df_raw = rendered_raw.to_dataframe()
                revenue_raw = df_raw[df_raw['label'].str.contains('Revenue|Sales', case=False, na=False)]
                if not revenue_raw.empty:
                    print(f"Raw revenue label: {revenue_raw['label'].iloc[0]}")
                
                # Standardized 
                print("\n--- Standardized labels ---")
                rendered_std = income_stmt.render(standard=True)
                df_std = rendered_std.to_dataframe()
                revenue_std = df_std[df_std['label'].str.contains('Revenue', case=False, na=False)]
                if not revenue_std.empty:
                    print(f"Standardized revenue label: {revenue_std['label'].iloc[0]}")
                
                print("\n✓ This shows standardization is working!")
                print("  The challenge is making it easily accessible to users.")
                
    except Exception as e:
        print(f"✗ Error demonstrating standardization: {e}")


if __name__ == "__main__":
    print("EdgarTools Issue #411 - Standardization Reproduction Script")
    print("Testing user's expected API vs. current capabilities")
    
    test_user_expected_api()
    test_current_api_capabilities()
    demonstrate_standardization_power()
    
    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("1. User's expected API (get_revenue, get_net_income, etc.) doesn't exist")
    print("2. EdgarTools has sophisticated standardization in XBRL rendering")
    print("3. Need to bridge gap with convenience methods on Financials class")
    print("4. Should leverage existing standard=True rendering capabilities")