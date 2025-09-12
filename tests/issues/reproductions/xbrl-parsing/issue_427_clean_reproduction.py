#!/usr/bin/env python3
"""
Issue #427: Clean reproduction of user's exact issue

User reports that XBRLS.from_filings() caps data at 2018.
This script tests their exact pattern with proper analysis.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

import pandas as pd
from edgar import Company
from edgar.xbrl import XBRLS


def test_user_pattern(ticker, periods=10):
    """Test user's exact pattern and show detailed results"""
    print(f"\n{'='*60}")
    print(f"TESTING {ticker} with {periods} periods")
    print(f"{'='*60}")
    
    # User's exact pattern
    co = Company(ticker)
    if not co.is_company: 
        print(f"Company with ticker {ticker} not found.")
        return None
        
    filings = co.get_filings(form="10-K").head(periods)
    print(f"Retrieved {len(filings)} filings:")
    for i in range(min(5, len(filings))):  # Show first 5
        filing = filings[i]
        print(f"  {i+1}. {filing.filing_date} - {filing.accession_number}")
    if len(filings) > 5:
        print(f"  ... and {len(filings) - 5} more")
    
    try:
        print(f"\nCreating XBRLS from {len(filings)} filings...")
        xbrls = XBRLS.from_filings(filings)
        
        print(f"Getting income statement...")
        income_stmt = xbrls.statements.income_statement()
        
        print(f"Converting to dataframe...")
        df = income_stmt.to_dataframe()
        
        if df.empty:
            print("❌ EMPTY DATAFRAME")
            return None
        
        print(f"✅ SUCCESS: Got DataFrame with {df.shape[0]} rows, {df.shape[1]} columns")
        
        # Analyze the periods (exclude label/concept columns)
        date_columns = [col for col in df.columns if col not in ['label', 'concept']]
        print(f"Date columns found: {len(date_columns)}")
        
        if date_columns:
            sorted_dates = sorted(date_columns)
            print(f"Earliest period: {sorted_dates[0]}")
            print(f"Latest period: {sorted_dates[-1]}")
            print(f"All periods: {sorted_dates}")
            
            # Check if it really "caps out at 2018"
            latest_year = int(sorted_dates[-1].split('-')[0])
            earliest_year = int(sorted_dates[0].split('-')[0])
            
            print(f"\n📊 ANALYSIS:")
            print(f"   Latest year: {latest_year}")
            print(f"   Earliest year: {earliest_year}")
            print(f"   Year range: {latest_year - earliest_year + 1} years")
            
            if latest_year <= 2018:
                print(f"🚨 CONFIRMED: Data caps out at {latest_year} (at or before 2018)")
            else:
                print(f"✅ NO ISSUE: Data goes up to {latest_year} (after 2018)")
                
            return df
        else:
            print("❌ NO DATE COLUMNS FOUND")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Test the exact scenarios the user reported"""
    print("="*80)
    print("ISSUE #427 CLEAN REPRODUCTION")
    print("Testing user's exact pattern: XBRLS.from_filings() + income_statement()")
    print("="*80)
    
    # User's exact test cases
    test_cases = [
        ("AAPL", 10, "User reports: latest 2017"),
        ("MSFT", 10, "User reports: latest 2018"),
        ("TSLA", 5, "User reports: filing not found errors"),
    ]
    
    for ticker, periods, note in test_cases:
        print(f"\n{note}")
        result = test_user_pattern(ticker, periods)
        
        if result is not None:
            print(f"✅ {ticker}: Success - got {result.shape[0]} rows, {result.shape[1]} columns")
        else:
            print(f"❌ {ticker}: Failed")


if __name__ == "__main__":
    main()