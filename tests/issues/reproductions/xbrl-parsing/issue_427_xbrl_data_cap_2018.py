#!/usr/bin/env python3
"""
Reproduction script for GitHub Issue #427
XBRLS cap out at 2018

Issue description:
The user reports that when using .head on XBRL data, results appear to be
limited to data from 2018 and earlier for 10-K filings across many companies.

This script attempts to reproduce the issue by:
1. Getting filings for several well-known companies  
2. Filtering for 10-K forms
3. Checking if .head() returns filings newer than 2018
4. Investigating the data retrieval and filtering mechanisms
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add the project root to the Python path
project_root = os.path.join(os.path.dirname(__file__), "../../../../../")
sys.path.insert(0, project_root)

import edgar
from edgar import Company


def analyze_company_filings(ticker: str, company_name: str) -> Dict[str, Any]:
    """Analyze a company's filings to check for the 2018 cap issue."""
    
    print(f"\n{'='*60}")
    print(f"Analyzing {company_name} ({ticker})")
    print(f"{'='*60}")
    
    try:
        # Get the company
        company = Company(ticker)
        print(f"Company: {company.name}")
        print(f"CIK: {company.cik}")
        
        # Get 10-K filings specifically
        tenk_filings = company.get_filings(form='10-K')
        print(f"Total 10-K filings found: {len(tenk_filings)}")
        
        # Check the head(10) results
        head_filings = tenk_filings.head(10)
        print(f"Head(10) filings count: {len(head_filings)}")
        
        # Analyze the dates in head results
        if len(head_filings) > 0:
            filing_dates = []
            for filing in head_filings:
                filing_dates.append(filing.filing_date)
                
            # Sort dates to see the range
            filing_dates.sort(reverse=True)
            latest_date = filing_dates[0]  # Most recent
            earliest_date = filing_dates[-1]  # Oldest in the head results
            
            print(f"Date range in head(10):")
            print(f"  Latest: {latest_date}")
            print(f"  Earliest: {earliest_date}")
            
            # Check if we have filings after 2018
            latest_year = latest_date.year
            has_recent_filings = latest_year > 2018
            
            print(f"Has filings newer than 2018: {has_recent_filings}")
            
            # Show all dates for detailed analysis
            print(f"All filing dates in head(10):")
            for i, date in enumerate(filing_dates):
                print(f"  {i+1}. {date} ({date.year})")
            
            return {
                'ticker': ticker,
                'company_name': company_name,
                'total_10k_count': len(tenk_filings),
                'head_count': len(head_filings),
                'latest_date': latest_date,
                'earliest_date': earliest_date,
                'has_recent_filings': has_recent_filings,
                'latest_year': latest_year,
                'filing_dates': filing_dates,
                'success': True
            }
        else:
            print("No 10-K filings found!")
            return {
                'ticker': ticker,
                'company_name': company_name,
                'total_10k_count': 0,
                'head_count': 0,
                'success': False,
                'error': 'No 10-K filings found'
            }
            
    except Exception as e:
        print(f"Error analyzing {ticker}: {str(e)}")
        return {
            'ticker': ticker,
            'company_name': company_name,
            'success': False,
            'error': str(e)
        }


def main():
    """Main function to reproduce the issue."""
    
    print("GitHub Issue #427 Reproduction Script")
    print("XBRLS cap out at 2018")
    print("="*60)
    
    # Test with several well-known companies that should have recent 10-K filings
    companies_to_test = [
        ('AAPL', 'Apple Inc.'),
        ('MSFT', 'Microsoft Corporation'),
        ('GOOGL', 'Alphabet Inc.'),
        ('TSLA', 'Tesla, Inc.'),
        ('NVDA', 'NVIDIA Corporation')
    ]
    
    results = []
    
    for ticker, company_name in companies_to_test:
        result = analyze_company_filings(ticker, company_name)
        results.append(result)
    
    # Summary analysis
    print(f"\n{'='*60}")
    print("SUMMARY ANALYSIS")
    print(f"{'='*60}")
    
    successful_analyses = [r for r in results if r['success']]
    companies_with_recent_filings = [r for r in successful_analyses if r.get('has_recent_filings', False)]
    companies_capped_at_2018 = [r for r in successful_analyses if not r.get('has_recent_filings', False)]
    
    print(f"Companies successfully analyzed: {len(successful_analyses)}")
    print(f"Companies with filings newer than 2018: {len(companies_with_recent_filings)}")
    print(f"Companies appearing capped at 2018: {len(companies_capped_at_2018)}")
    
    if companies_capped_at_2018:
        print("\nCompanies that appear to be capped at 2018:")
        for result in companies_capped_at_2018:
            latest_year = result.get('latest_year', 'Unknown')
            print(f"  - {result['ticker']} ({result['company_name']}): Latest year {latest_year}")
    
    if companies_with_recent_filings:
        print("\nCompanies with recent filings (newer than 2018):")
        for result in companies_with_recent_filings:
            latest_year = result.get('latest_year', 'Unknown')
            print(f"  - {result['ticker']} ({result['company_name']}): Latest year {latest_year}")
    
    # Issue reproduction conclusion
    print(f"\n{'='*60}")
    print("ISSUE REPRODUCTION CONCLUSION")
    print(f"{'='*60}")
    
    if len(companies_capped_at_2018) > 0:
        print("🚨 ISSUE CONFIRMED: Some companies appear to have filings capped at 2018 or earlier")
        print("This confirms the reported issue in GitHub #427")
    else:
        print("✅ ISSUE NOT REPRODUCED: All tested companies have recent filings available")
        print("The reported issue may be specific to certain companies or usage patterns")
    
    # Additional debugging information
    print(f"\n{'='*60}")
    print("DEBUGGING INFORMATION")
    print(f"{'='*60}")
    
    print(f"EdgarTools version: {getattr(edgar, '__version__', 'Unknown')}")
    print(f"Current date: {datetime.now().strftime('%Y-%m-%d')}")
    
    return results


if __name__ == "__main__":
    results = main()