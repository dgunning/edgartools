#!/usr/bin/env python3
"""
Issue #427: XBRL data "caps out at 2018" - Historical Data Investigation
Re-investigation based on correct understanding that user means data doesn't go back before 2018.

GitHub Issue: https://github.com/dgunning/edgartools/issues/427
"""

from edgar import Company
from edgar.xbrl.stitching import XBRLS
from rich import print
import traceback


def investigate_historical_xbrl_data():
    """Investigate whether XBRL data is available for years before 2018."""
    
    print("🔍 [bold blue]Issue #427 Investigation: Historical XBRL Data Availability[/bold blue]")
    print("Testing whether XBRL data 'caps out at 2018' (i.e., no data before 2018)")
    print("=" * 80)
    
    # Test companies that should have long filing histories
    test_companies = [
        ("AAPL", "Apple Inc."),
        ("MSFT", "Microsoft Corp."),
        ("IBM", "IBM Corp."),
        ("GE", "General Electric"),
        ("KO", "Coca-Cola"),
        ("JNJ", "Johnson & Johnson"),
        ("PG", "Procter & Gamble")
    ]
    
    for ticker, name in test_companies:
        print(f"\n📊 Testing {ticker} ({name})")
        print("-" * 50)
        
        try:
            company = Company(ticker)
            
            # Get many 10-K filings to test historical range
            filings = company.get_filings(form="10-K", amendments=False).head(15)
            print(f"Retrieved {len(filings)} 10-K filings")
            
            # Check filing date range
            if len(filings) > 0:
                latest_date = filings[0].filing_date
                oldest_date = filings[-1].filing_date if len(filings) > 1 else latest_date
                print(f"Filing date range: {oldest_date} to {latest_date}")
                
                # Test XBRL availability across different years
                years_with_xbrl = []
                years_without_xbrl = []
                
                for i, filing in enumerate(filings):
                    if i >= 10:  # Test first 10 for performance
                        break
                        
                    try:
                        xbrl = filing.xbrl()
                        if xbrl and xbrl._facts:
                            years_with_xbrl.append(filing.filing_date.year)
                            print(f"  ✅ {filing.filing_date.year}: XBRL available ({len(xbrl._facts)} facts)")
                        else:
                            years_without_xbrl.append(filing.filing_date.year)
                            print(f"  ❌ {filing.filing_date.year}: No XBRL data")
                    except Exception as e:
                        years_without_xbrl.append(filing.filing_date.year)
                        print(f"  ⚠️  {filing.filing_date.year}: XBRL error - {str(e)[:50]}")
                
                # Analyze the results
                if years_with_xbrl:
                    earliest_xbrl = min(years_with_xbrl)
                    latest_xbrl = max(years_with_xbrl)
                    print(f"\n📈 XBRL Data Range: {earliest_xbrl} to {latest_xbrl}")
                    
                    if earliest_xbrl >= 2018:
                        print(f"🚨 [red]CONFIRMED: XBRL data caps out at {earliest_xbrl} for {ticker}[/red]")
                    elif earliest_xbrl < 2018:
                        print(f"✅ [green]XBRL data available before 2018 (earliest: {earliest_xbrl})[/green]")
                else:
                    print("❌ [red]No XBRL data found at all[/red]")
                    
                # Test stitched XBRLS if we have multiple filings with XBRL
                if len([y for y in years_with_xbrl if y >= 2018]) >= 3:
                    print(f"\n🔗 Testing XBRLS stitching for {ticker}...")
                    try:
                        xbrl_filings = [f for f in filings[:5] if f.filing_date.year in years_with_xbrl][:3]
                        xbrls = XBRLS.from_filings(xbrl_filings)
                        
                        if xbrls:
                            print(f"  ✅ XBRLS created successfully")
                            # Test getting historical data via stitching
                            revenue_data = xbrls.facts.query().by_concept("Revenue").to_dataframe()
                            if not revenue_data.empty:
                                years_in_stitched = sorted(revenue_data['fiscal_year'].unique())
                                print(f"  📊 Revenue data years in stitched XBRLS: {years_in_stitched}")
                                
                                earliest_stitched = min(years_in_stitched)
                                if earliest_stitched >= 2018:
                                    print(f"  🚨 [red]Stitched data also caps at {earliest_stitched}[/red]")
                                else:
                                    print(f"  ✅ [green]Stitched data goes back to {earliest_stitched}[/green]")
                            else:
                                print("  ⚠️  No revenue data in stitched XBRLS")
                        else:
                            print("  ❌ Failed to create XBRLS")
                    except Exception as e:
                        print(f"  ❌ XBRLS error: {str(e)[:100]}")
                        
        except Exception as e:
            print(f"❌ Error testing {ticker}: {e}")
            traceback.print_exc()
            
        print()  # Extra spacing between companies
    
    print("\n" + "=" * 80)
    print("🎯 [bold]Investigation Summary[/bold]")
    print("If any companies show 'XBRL data caps out at 2018 or later',")
    print("this confirms the user's reported issue.")
    print("If companies show XBRL data before 2018, the issue may be:")
    print("- Usage pattern specific")
    print("- Company specific")  
    print("- Environment specific")


def test_specific_historical_years():
    """Test specific years before 2018 to understand the cutoff."""
    
    print("\n🎯 [bold blue]Testing Specific Historical Years[/bold blue]")
    print("=" * 50)
    
    # Test Apple for specific years around the potential cutoff
    company = Company("AAPL")
    test_years = [2010, 2012, 2015, 2017, 2018, 2019, 2020]
    
    print("Testing Apple 10-K filings for specific years...")
    
    for year in test_years:
        try:
            # Get filings from specific year
            all_filings = company.get_filings(form="10-K", amendments=False)
            year_filings = [f for f in all_filings if f.filing_date.year == year]
            
            if year_filings:
                filing = year_filings[0]  # Get first filing from that year
                print(f"\n📅 Year {year}:")
                print(f"  Filing date: {filing.filing_date}")
                
                try:
                    xbrl = filing.xbrl()
                    if xbrl and xbrl._facts:
                        fact_count = len(xbrl._facts)
                        print(f"  ✅ XBRL available: {fact_count} facts")
                        
                        # Test if we can get income statement
                        try:
                            income = xbrl.statements.income_statement()
                            if income:
                                print(f"  📊 Income statement available")
                            else:
                                print(f"  ⚠️  No income statement found")
                        except Exception as e:
                            print(f"  ⚠️  Income statement error: {str(e)[:50]}")
                    else:
                        print(f"  ❌ No XBRL data")
                except Exception as e:
                    print(f"  ❌ XBRL error: {str(e)[:50]}")
            else:
                print(f"\n📅 Year {year}: No 10-K filings found")
                
        except Exception as e:
            print(f"\n📅 Year {year}: Error - {e}")


if __name__ == "__main__":
    investigate_historical_xbrl_data()
    test_specific_historical_years()
    
    print("\n" + "=" * 80)
    print("📝 [bold]Next Steps[/bold]")
    print("1. Run this script to see historical data availability")
    print("2. If data caps out at 2018+, issue is confirmed")
    print("3. If data goes back further, request specific reproduction case from user")
    print("4. Consider that XBRL mandate started around 2009-2011 for large companies")