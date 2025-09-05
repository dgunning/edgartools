#!/usr/bin/env python3
"""
Extended investigation for GitHub Issue #427
XBRLS cap out at 2018 - Focus on XBRLS class

The initial reproduction with regular filings did NOT reproduce the issue.
This script investigates if the issue is specific to:
1. XBRLS (stitched XBRL data) vs regular filings
2. Specific companies or CIKs
3. Usage patterns involving XBRL processing
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
from edgar.xbrl.stitching.xbrls import XBRLS


def test_xbrls_functionality(ticker: str, company_name: str) -> Dict[str, Any]:
    """Test XBRLS functionality to check for the 2018 cap issue."""
    
    print(f"\n{'='*60}")
    print(f"Testing XBRLS for {company_name} ({ticker})")
    print(f"{'='*60}")
    
    try:
        # Get the company
        company = Company(ticker)
        print(f"Company: {company.name}")
        print(f"CIK: {company.cik}")
        
        # Get 10-K filings with XBRL data
        tenk_filings = company.get_filings(form='10-K', is_xbrl=True)
        print(f"Total 10-K XBRL filings found: {len(tenk_filings)}")
        
        if len(tenk_filings) == 0:
            return {
                'ticker': ticker,
                'company_name': company_name,
                'success': False,
                'error': 'No XBRL 10-K filings found'
            }
        
        # Test XBRLS creation with head() filings
        print("Testing XBRLS.from_filings() with .head() method...")
        head_filings = tenk_filings.head(5)  # Get first 5 filings
        print(f"Head filings count: {len(head_filings)}")
        
        # Show filing dates in head result
        filing_dates = []
        print("Filing dates in head(5):")
        for i, filing in enumerate(head_filings):
            filing_dates.append(filing.filing_date)
            print(f"  {i+1}. {filing.filing_date} - {filing.accession_number}")
        
        filing_dates.sort(reverse=True)
        latest_date = filing_dates[0]
        has_recent_xbrl = latest_date.year > 2018
        
        print(f"Latest XBRL filing date: {latest_date}")
        print(f"Has XBRL filings newer than 2018: {has_recent_xbrl}")
        
        # Try creating XBRLS object
        try:
            print("\nTesting XBRLS.from_filings()...")
            xbrls = XBRLS.from_filings(head_filings)
            print(f"XBRLS created successfully: {xbrls}")
            
            # Test XBRLS periods
            periods = xbrls.get_periods()
            print(f"XBRLS periods count: {len(periods)}")
            
            if len(periods) > 0:
                period_years = []
                for period in periods[:10]:  # Show first 10 periods
                    if period.get('date'):
                        year = period['date'][:4]
                        period_years.append(int(year))
                    elif period.get('end_date'):
                        year = period['end_date'][:4]
                        period_years.append(int(year))
                
                if period_years:
                    latest_period_year = max(period_years)
                    earliest_period_year = min(period_years)
                    print(f"XBRLS period years range: {earliest_period_year} - {latest_period_year}")
                    has_recent_periods = latest_period_year > 2018
                    print(f"Has periods newer than 2018: {has_recent_periods}")
                    
                    return {
                        'ticker': ticker,
                        'company_name': company_name,
                        'total_xbrl_10k_count': len(tenk_filings),
                        'head_count': len(head_filings),
                        'latest_filing_date': latest_date,
                        'has_recent_xbrl': has_recent_xbrl,
                        'xbrls_periods_count': len(periods),
                        'latest_period_year': latest_period_year,
                        'earliest_period_year': earliest_period_year,
                        'has_recent_periods': has_recent_periods,
                        'success': True
                    }
            
        except Exception as xbrls_error:
            print(f"Error creating XBRLS: {str(xbrls_error)}")
            return {
                'ticker': ticker,
                'company_name': company_name,
                'success': False,
                'error': f'XBRLS creation failed: {str(xbrls_error)}'
            }
        
        return {
            'ticker': ticker,
            'company_name': company_name,
            'total_xbrl_10k_count': len(tenk_filings),
            'head_count': len(head_filings),
            'latest_filing_date': latest_date,
            'has_recent_xbrl': has_recent_xbrl,
            'success': True
        }
        
    except Exception as e:
        print(f"Error testing {ticker}: {str(e)}")
        return {
            'ticker': ticker,
            'company_name': company_name,
            'success': False,
            'error': str(e)
        }


def test_specific_older_company():
    """Test with a company that has been around longer and might show the issue."""
    print(f"\n{'='*60}")
    print("Testing older, established companies for 2018 cap pattern")
    print(f"{'='*60}")
    
    # Test companies that have been public for a long time
    older_companies = [
        ('IBM', 'International Business Machines Corporation'),
        ('GE', 'General Electric Company'),  
        ('F', 'Ford Motor Company'),
        ('KO', 'The Coca-Cola Company'),
        ('JNJ', 'Johnson & Johnson')
    ]
    
    results = []
    for ticker, company_name in older_companies:
        result = test_xbrls_functionality(ticker, company_name)
        results.append(result)
    
    return results


def main():
    """Main function to investigate XBRLS-specific issues."""
    
    print("GitHub Issue #427 Extended Investigation")
    print("Focus on XBRLS vs regular filings")
    print("="*60)
    
    # Test the same companies but focus on XBRLS functionality
    companies_to_test = [
        ('AAPL', 'Apple Inc.'),
        ('MSFT', 'Microsoft Corporation'),
    ]
    
    results = []
    
    print("Testing XBRLS functionality with major companies...")
    for ticker, company_name in companies_to_test:
        result = test_xbrls_functionality(ticker, company_name)
        results.append(result)
    
    # Test older companies that might have different data patterns
    older_results = test_specific_older_company()
    results.extend(older_results)
    
    # Analysis
    print(f"\n{'='*60}")
    print("XBRLS INVESTIGATION SUMMARY")
    print(f"{'='*60}")
    
    successful_tests = [r for r in results if r['success']]
    companies_with_recent_xbrl = [r for r in successful_tests if r.get('has_recent_periods', r.get('has_recent_xbrl', False))]
    companies_capped_at_2018 = [r for r in successful_tests if not r.get('has_recent_periods', r.get('has_recent_xbrl', True))]
    
    print(f"Successful XBRLS tests: {len(successful_tests)}")
    print(f"Companies with XBRL data newer than 2018: {len(companies_with_recent_xbrl)}")
    print(f"Companies appearing capped at 2018: {len(companies_capped_at_2018)}")
    
    if companies_capped_at_2018:
        print("\n🚨 Companies showing 2018 cap pattern:")
        for result in companies_capped_at_2018:
            latest_year = result.get('latest_period_year', result.get('latest_filing_date', 'Unknown'))
            print(f"  - {result['ticker']}: Latest data {latest_year}")
    
    if companies_with_recent_xbrl:
        print("\n✅ Companies with recent XBRL data:")
        for result in companies_with_recent_xbrl:
            latest_year = result.get('latest_period_year', result.get('latest_filing_date', 'Unknown'))
            print(f"  - {result['ticker']}: Latest data {latest_year}")
    
    # Show any errors
    failed_tests = [r for r in results if not r['success']]
    if failed_tests:
        print(f"\n⚠️  Failed tests ({len(failed_tests)}):")
        for result in failed_tests:
            print(f"  - {result['ticker']}: {result.get('error', 'Unknown error')}")
    
    return results


if __name__ == "__main__":
    results = main()