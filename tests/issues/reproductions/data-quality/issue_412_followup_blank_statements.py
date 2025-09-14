"""
Investigation for Issue #412 Follow-up Comment
User reports balance sheets and cash flow statements showing as blank for major companies (AAPL, MSFT, GOOGL) 
for years 2022 and earlier when using multi-year financial data API.

Original issue was about TSLA revenue access and AAPL quarterly vs annual revenue - both fixed.
This is a new issue about blank financial statements for major companies in earlier years.
"""

import edgar
from rich import print

def test_multi_year_financial_data():
    """Test multi-year financial data access as described in the user's guide reference"""
    
    companies = ['AAPL', 'MSFT', 'GOOGL']
    
    for ticker in companies:
        print(f"\n[bold blue]Testing {ticker} multi-year financial data[/bold blue]")
        
        try:
            company = edgar.Company(ticker)
            
            # Get recent 10-K filings - test 2020-2023 range
            filings = company.get_filings(form="10-K").filter(date="2020-01-01:2024-01-01")
            
            print(f"Found {len(filings)} 10-K filings for {ticker}")
            
            for filing in filings[:3]:  # Test first 3 filings
                print(f"\n  Filing: {filing.accession_no} - {filing.filing_date}")
                
                try:
                    xbrl = filing.xbrl()
                    if xbrl is None:
                        print(f"    [red]XBRL data not available for {filing.filing_date}[/red]")
                        continue
                    
                    # Test Balance Sheet
                    try:
                        balance_sheet = xbrl.get_statement_by_type("BalanceSheet")
                        if balance_sheet is None or (hasattr(balance_sheet, 'empty') and balance_sheet.empty) or len(balance_sheet) == 0:
                            print(f"    [red]Balance Sheet: BLANK/EMPTY for {filing.filing_date}[/red]")
                        else:
                            print(f"    [green]Balance Sheet: OK ({len(balance_sheet)} rows)[/green]")
                            # Show a sample of data
                            if len(balance_sheet) > 0 and hasattr(balance_sheet, 'index'):
                                print(f"      Sample concepts: {list(balance_sheet.index[:3])}")
                    except Exception as e:
                        print(f"    [red]Balance Sheet ERROR: {e}[/red]")
                    
                    # Test Cash Flow Statement  
                    try:
                        cash_flow = xbrl.get_statement_by_type("CashFlowStatement")
                        if cash_flow is None or (hasattr(cash_flow, 'empty') and cash_flow.empty) or len(cash_flow) == 0:
                            print(f"    [red]Cash Flow Statement: BLANK/EMPTY for {filing.filing_date}[/red]")
                        else:
                            print(f"    [green]Cash Flow Statement: OK ({len(cash_flow)} rows)[/green]")
                            # Show a sample of data
                            if len(cash_flow) > 0 and hasattr(cash_flow, 'index'):
                                print(f"      Sample concepts: {list(cash_flow.index[:3])}")
                    except Exception as e:
                        print(f"    [red]Cash Flow Statement ERROR: {e}[/red]")
                        
                    # Test Income Statement for comparison (should work based on previous fixes)
                    try:
                        income_stmt = xbrl.get_statement_by_type("IncomeStatement") 
                        if income_stmt is None or (hasattr(income_stmt, 'empty') and income_stmt.empty) or len(income_stmt) == 0:
                            print(f"    [red]Income Statement: BLANK/EMPTY for {filing.filing_date}[/red]")
                        else:
                            print(f"    [green]Income Statement: OK ({len(income_stmt)} rows)[/green]")
                    except Exception as e:
                        print(f"    [red]Income Statement ERROR: {e}[/red]")
                        
                except Exception as e:
                    print(f"    [red]XBRL access failed: {e}[/red]")
                    
        except Exception as e:
            print(f"[red]Failed to process {ticker}: {e}[/red]")

def test_specific_years():
    """Test specific years mentioned by user - 2022 and earlier"""
    
    print(f"\n[bold blue]Testing specific problematic years (2022 and earlier)[/bold blue]")
    
    # Test AAPL 2021 (should be problematic according to user)
    try:
        company = edgar.Company("AAPL")
        filings_2021 = company.get_filings(form="10-K").filter(date="2021-01-01:2022-01-01")
        
        if len(filings_2021) > 0:
            filing = filings_2021[0]
            print(f"\nAAPL 2021 filing: {filing.filing_date}")
            
            xbrl = filing.xbrl()
            if xbrl:
                balance_sheet = xbrl.get_statement_by_type("BalanceSheet")
                cash_flow = xbrl.get_statement_by_type("CashFlowStatement")
                
                bs_empty = balance_sheet is None or (hasattr(balance_sheet, 'empty') and balance_sheet.empty) or len(balance_sheet) == 0
                cf_empty = cash_flow is None or (hasattr(cash_flow, 'empty') and cash_flow.empty) or len(cash_flow) == 0
                
                print(f"  Balance Sheet: {'EMPTY' if bs_empty else f'{len(balance_sheet)} rows'}")
                print(f"  Cash Flow: {'EMPTY' if cf_empty else f'{len(cash_flow)} rows'}")
                
                if not bs_empty and hasattr(balance_sheet, 'index'):
                    print(f"  Balance Sheet concepts: {list(balance_sheet.index[:5])}")
                if not cf_empty and hasattr(cash_flow, 'index'):
                    print(f"  Cash Flow concepts: {list(cash_flow.index[:5])}")
            else:
                print("  XBRL data not available")
        else:
            print("No 2021 10-K filing found for AAPL")
            
    except Exception as e:
        print(f"Error testing AAPL 2021: {e}")

if __name__ == "__main__":
    print("[bold green]EdgarTools Issue #412 Follow-up Investigation[/bold green]")
    print("Testing blank balance sheets and cash flow statements for major companies")
    print("User report: Balance sheets blank 2022 and earlier, Cash flow statements blank 2021 and earlier")
    
    test_multi_year_financial_data()
    test_specific_years()