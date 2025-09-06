#!/usr/bin/env python3
"""
Issue #427: XBRLS cap out at 2018 - User's Specific Pattern Investigation

The user reported that using XBRLS.from_filings() returns data that "caps out at 2018".
They provided their specific implementation pattern that shows:
- AAPL: Latest financial year 2017 instead of recent data  
- MSFT: Latest financial year 2018
- TSLA: Filing not found errors

This script reproduces their exact pattern to identify the root cause.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

import pandas as pd
from edgar import Company
from edgar.xbrl import XBRLS


def getIncomeStatement(c="AAPL", periods=1, form="10-K"):
    """User's exact function implementation"""
    co = Company(c)
    if not co.is_company: 
        print(f"Company with ticker {c} not found.")
        return pd.DataFrame()
    
    filings = co.get_filings(form=form).head(periods) 
    print(f"\n=== {c} - Retrieved {len(filings)} filings ===")
    
    # Show what filings we're getting
    for i, filing in enumerate(filings):
        print(f"  {i+1}. {filing.filing_date} - {filing.accession_number}")
    
    try:
        print(f"Creating XBRLS from {len(filings)} filings...")
        xbrls = XBRLS.from_filings(filings)
        print(f"XBRLS created successfully. Contains {len(xbrls.xbrl_list)} XBRL objects.")
        
        # Debug: Check what periods XBRLS thinks it has
        periods = xbrls.get_periods()
        period_end_dates = xbrls.get_period_end_dates()  # Use convenience method
        print(f"Available period end dates (first 10): {period_end_dates[:10]}")
        print(f"Period details (first 5): {[{'type': p.get('type'), 'key': p.get('key'), 'label': p.get('label')} for p in periods[:5]]}")
        
        income_stmt = xbrls.statements.income_statement()
        print(f"Income statement retrieved successfully")
        
        # Check the dataframe columns to see what periods we actually get
        df = income_stmt.to_dataframe()
        print(f"DataFrame shape: {df.shape}")
        if not df.empty:
            print(f"DataFrame columns (periods): {list(df.columns)}")
            print(f"Latest period in data: {max(df.columns) if len(df.columns) > 0 else 'None'}")
        
        return df
    except Exception as e:
        print(f"Error retrieving income statement for {c}: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def investigate_individual_filings(ticker, periods=5):
    """Compare XBRLS stitching vs individual filing analysis"""
    print(f"\n{'='*60}")
    print(f"INDIVIDUAL FILING ANALYSIS FOR {ticker}")
    print(f"{'='*60}")
    
    co = Company(ticker)
    filings = co.get_filings(form="10-K", amendments=False).head(periods)
    
    print(f"Analyzing first {periods} 10-K filings individually:")
    
    for i, filing in enumerate(filings):
        print(f"\n--- Filing {i+1}: {filing.filing_date} ({filing.accession_number}) ---")
        try:
            xbrl = filing.xbrl()
            if xbrl and xbrl.statements.income_statement():
                income_stmt = xbrl.statements.income_statement()
                # Get the periods this individual filing covers
                periods_data = income_stmt.to_dataframe()
                if not periods_data.empty:
                    cols = list(periods_data.columns)
                    print(f"  Individual filing periods: {cols}")
                    print(f"  Latest period: {max(cols) if cols else 'None'}")
                else:
                    print(f"  No income statement data")
            else:
                print(f"  No XBRL data or income statement")
        except Exception as e:
            print(f"  Error processing individual filing: {e}")


def main():
    """Test the user's exact scenario"""
    print("="*80)
    print("REPRODUCING ISSUE #427: XBRLS Stitching Investigation")
    print("User's exact pattern with getIncomeStatement() function")
    print("="*80)
    
    # Test with user's exact examples
    test_cases = [
        ("AAPL", 10, "Should show recent data, user sees latest 2017"),
        ("MSFT", 10, "Should show recent data, user sees latest 2018"),
        ("TSLA", 5, "Should work, user gets filing not found errors"),
    ]
    
    for ticker, periods, note in test_cases:
        print(f"\n{'='*60}")
        print(f"TESTING: {ticker} with {periods} periods")
        print(f"NOTE: {note}")
        print(f"{'='*60}")
        
        # First check what filings are available
        co = Company(ticker)
        all_filings = co.get_filings(form="10-K")
        print(f"Total 10-K filings available for {ticker}: {len(all_filings)}")
        if len(all_filings) > 0:
            print(f"Most recent 10-K: {all_filings[0].filing_date}")
            print(f"Oldest 10-K: {all_filings[-1].filing_date}")
        
        # Run user's function
        df = getIncomeStatement(c=ticker, periods=periods, form="10-K")
        
        if not df.empty:
            print(f"\nSUCCESS: Got DataFrame with {df.shape[0]} rows, {df.shape[1]} columns")
            print(f"Columns (periods): {list(df.columns)}")
            if df.columns.tolist():
                latest_period = max(df.columns)
                print(f"LATEST PERIOD IN STITCHED DATA: {latest_period}")
                
                # Compare with individual filings
                investigate_individual_filings(ticker, min(3, periods))
        else:
            print(f"\nFAILURE: Empty DataFrame returned")
        
        print("\n" + "-"*60)


if __name__ == "__main__":
    main()