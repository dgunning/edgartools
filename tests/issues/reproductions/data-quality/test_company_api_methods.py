"""
Test the Company-level API methods that the user is likely using based on the multi-year guide.
This tests company.balance_sheet() and company.cash_flow() methods.
"""

import edgar
from rich import print
import traceback
import pandas as pd
import pytest

@pytest.mark.regression
def test_company_api_methods():
    """Test the Company-level methods for financial statements"""
    
    companies = ['AAPL', 'MSFT', 'GOOGL']
    
    for ticker in companies:
        print(f"\n[bold blue]Testing {ticker} Company-level API methods[/bold blue]")
        
        try:
            company = edgar.Company(ticker)
            
            # Test Balance Sheet using Company API
            print(f"\n[yellow]Testing {ticker} Balance Sheet (Company API):[/yellow]")
            try:
                # Test with different periods and annual/quarterly
                for periods in [4, 2]:
                    for annual in [True, False]:
                        period_type = "Annual" if annual else "Quarterly" 
                        print(f"\n  Testing {periods} {period_type} periods:")
                        
                        balance_sheet = company.balance_sheet(periods=periods, annual=annual)
                        
                        if balance_sheet is None:
                            print(f"    [red]Balance Sheet is None for {periods} {period_type} periods[/red]")
                        elif hasattr(balance_sheet, 'empty') and balance_sheet.empty:
                            print(f"    [red]Balance Sheet is EMPTY for {periods} {period_type} periods[/red]")
                        elif isinstance(balance_sheet, pd.DataFrame) and len(balance_sheet) == 0:
                            print(f"    [red]Balance Sheet DataFrame has 0 rows for {periods} {period_type} periods[/red]")
                        else:
                            print(f"    [green]Balance Sheet OK: {type(balance_sheet)} with {len(balance_sheet)} items/rows[/green]")
                            if hasattr(balance_sheet, 'columns'):
                                print(f"      Columns: {list(balance_sheet.columns)}")
                            if hasattr(balance_sheet, 'index'):
                                print(f"      Sample indices: {list(balance_sheet.index[:3])}")
                        
            except Exception as e:
                print(f"    [red]Balance Sheet error: {e}[/red]")
                traceback.print_exc()
            
            # Test Cash Flow using Company API  
            print(f"\n[yellow]Testing {ticker} Cash Flow (Company API):[/yellow]")
            try:
                # Test with different periods and annual/quarterly
                for periods in [4, 2]:
                    for annual in [True, False]:
                        period_type = "Annual" if annual else "Quarterly"
                        print(f"\n  Testing {periods} {period_type} periods:")
                        
                        cash_flow = company.cash_flow(periods=periods, annual=annual)
                        
                        if cash_flow is None:
                            print(f"    [red]Cash Flow is None for {periods} {period_type} periods[/red]")
                        elif hasattr(cash_flow, 'empty') and cash_flow.empty:
                            print(f"    [red]Cash Flow is EMPTY for {periods} {period_type} periods[/red]")
                        elif isinstance(cash_flow, pd.DataFrame) and len(cash_flow) == 0:
                            print(f"    [red]Cash Flow DataFrame has 0 rows for {periods} {period_type} periods[/red]")
                        else:
                            print(f"    [green]Cash Flow OK: {type(cash_flow)} with {len(cash_flow)} items/rows[/green]")
                            if hasattr(cash_flow, 'columns'):
                                print(f"      Columns: {list(cash_flow.columns)}")
                            if hasattr(cash_flow, 'index'):
                                print(f"      Sample indices: {list(cash_flow.index[:3])}")
                        
            except Exception as e:
                print(f"    [red]Cash Flow error: {e}[/red]")
                traceback.print_exc()
                
            # Test Income Statement for comparison
            print(f"\n[yellow]Testing {ticker} Income Statement (Company API):[/yellow]")
            try:
                income_stmt = company.income_statement(periods=4, annual=True)
                
                if income_stmt is None:
                    print(f"    [red]Income Statement is None[/red]")
                elif hasattr(income_stmt, 'empty') and income_stmt.empty:
                    print(f"    [red]Income Statement is EMPTY[/red]")
                elif isinstance(income_stmt, pd.DataFrame) and len(income_stmt) == 0:
                    print(f"    [red]Income Statement DataFrame has 0 rows[/red]")
                else:
                    print(f"    [green]Income Statement OK: {type(income_stmt)} with {len(income_stmt)} items/rows[/green]")
                    
            except Exception as e:
                print(f"    [red]Income Statement error: {e}[/red]")
                traceback.print_exc()
                
        except Exception as e:
            print(f"[red]Failed to process {ticker}: {e}[/red]")
            traceback.print_exc()

@pytest.mark.regression
def test_specific_years_company_api():
    """Test specific years that user mentioned as problematic"""
    
    print(f"\n[bold blue]Testing specific problematic years with Company API[/bold blue]")
    print("User reported: Balance sheets blank 2022 and earlier, Cash flow blank 2021 and earlier")
    
    # The Company API doesn't let us specify specific years directly,
    # but let's see what years we get when requesting historical data
    
    try:
        company = edgar.Company("AAPL")
        
        # Request maximum periods to see historical data
        print("\nTesting AAPL with maximum historical periods:")
        
        balance_sheet = company.balance_sheet(periods=20, annual=True)  # Max periods
        print(f"Balance Sheet: {type(balance_sheet)}")
        if balance_sheet is not None and hasattr(balance_sheet, 'columns'):
            print(f"  Columns (years): {list(balance_sheet.columns)}")
            # Check if 2022 and earlier are in the data
            if hasattr(balance_sheet.columns, 'tolist'):
                years = [str(col) for col in balance_sheet.columns if str(col).isdigit() or '202' in str(col)]
                print(f"  Year columns found: {years}")
                
        cash_flow = company.cash_flow(periods=20, annual=True)  # Max periods  
        print(f"Cash Flow: {type(cash_flow)}")
        if cash_flow is not None and hasattr(cash_flow, 'columns'):
            print(f"  Columns (years): {list(cash_flow.columns)}")
            # Check if 2021 and earlier are in the data
            if hasattr(cash_flow.columns, 'tolist'):
                years = [str(col) for col in cash_flow.columns if str(col).isdigit() or '202' in str(col)]
                print(f"  Year columns found: {years}")
                
    except Exception as e:
        print(f"Error testing historical data: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("[bold green]Testing Company-level API methods (Issue #412 follow-up)[/bold green]")
    print("Based on multi-year financial data guide: company.balance_sheet() and company.cash_flow()")
    
    test_company_api_methods()
    test_specific_years_company_api()