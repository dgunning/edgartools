
"""
Example of Rolling TTM (Trailing Twelve Months) Analysis.

This script demonstrates how to use the new 'ttm' period type to generate
rolling TTM financial statements, allowing for trend analysis that smooths
out seasonality.
"""
import sys
import os

# Add parent directory (repo root) to sys.path to prefer local package over installed one
# Current dir is .../edgar/ (package root). Parent is .../edgartools_git/
# import edgar looks for .../edgartools_git/edgar
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
# To import 'edgar', we need the directory CONTAINING 'edgar' folder to be in path.
# If we are in 'edgar' folder, we need '..'
# But since we are running from 'edgar' folder, os.getcwd() is .../edgar.
# We need to add .../ (parent of edgar) to path.
parent_of_package = os.path.abspath(os.path.join(os.getcwd(), ".."))
if parent_of_package not in sys.path:
    sys.path.insert(0, parent_of_package)

from edgar import Company, set_identity
import edgar
print(f"Using edgar from: {edgar.__file__}")

import pandas as pd

def main():
    # 1. Setup
    # Replace with your identity
    set_identity("Demo Agent demo@example.com")
    
    print("Fetching Apple Inc. (AAPL) data...")
    company = Company("AAPL")
    
    # 2. Generate Rolling TTM Income Statement
    # periods=8 gives us 8 rolling windows (e.g., Q3 2024 LTM, Q2 2024 LTM...)
    print("\n--- Rolling TTM Income Statement (Last 8 Periods) ---")
    ttm_income = company.income_statement(periods=8, period='ttm')
    
    # Display rich table
    print(ttm_income)
    
    # 3. Analyze Trends with DataFrame
    print("\n--- Revenue & Profit Trend Analysis ---")
    df = ttm_income.to_dataframe()
    
    # Extract key rows
    # Note: Concepts might vary by company taxonomy, but EnhancedStatementBuilder normalizes structure
    try:
        # Find Revenue and Net Income rows
        revenue_row = df[df['label'].str.contains('Total Revenue', case=False)].iloc[0]
        income_row = df[df['label'].str.contains('Net Income', case=False) & df['is_total']].iloc[0]
        
        # Get period columns (exclude metadata columns)
        metadata_cols = ['label', 'depth', 'is_abstract', 'is_total', 'section', 'confidence']
        periods = [c for c in df.columns if c not in metadata_cols]
        
        # Build trend table
        trend_data = []
        for p in periods:
            rev = revenue_row[p]
            inc = income_row[p]
            margin = (inc / rev) if rev else 0
            trend_data.append({
                'Period': p,
                'Revenue': rev,
                'Net Income': inc,
                'Profit Margin': margin
            })
            
        trend_df = pd.DataFrame(trend_data)
        
        # Format for display
        pd.options.display.float_format = '{:,.2f}'.format
        trend_df['Revenue'] = trend_df['Revenue'].apply(lambda x: f"${x/1e9:,.1f}B")
        trend_df['Net Income'] = trend_df['Net Income'].apply(lambda x: f"${x/1e9:,.1f}B")
        trend_df['Profit Margin'] = trend_df['Profit Margin'].apply(lambda x: f"{x:.1%}")
        
        print(trend_df.to_string(index=False))
        
    except IndexError:
        print("Could not find standard Revenue/Net Income lines for trend analysis.")

    # 4. Cash Flow TTM
    print("\n--- Rolling TTM Cash Flow (Last 4 Periods) ---")
    ttm_cash = company.cash_flow(periods=4, period='ttm')
    print(ttm_cash)

if __name__ == "__main__":
    main()
