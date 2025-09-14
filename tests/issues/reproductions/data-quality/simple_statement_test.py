"""
Simple test to investigate blank statements issue for Issue #412 follow-up
"""

import edgar
from rich import print
import traceback

def simple_test():
    """Test one company's statements"""
    
    print("[bold blue]Testing AAPL 2021 filing for blank statements[/bold blue]")
    
    try:
        company = edgar.Company("AAPL")
        filings = company.get_filings(form="10-K").filter(date="2021-01-01:2022-01-01")
        
        print(f"Found {len(filings)} 10-K filings")
        
        if len(filings) > 0:
            filing = filings[0]
            print(f"Filing date: {filing.filing_date}")
            print(f"Accession: {filing.accession_no}")
            
            print("\nTesting XBRL access...")
            xbrl = filing.xbrl()
            
            if xbrl is None:
                print("[red]XBRL is None[/red]")
                return
                
            print("[green]XBRL loaded successfully[/green]")
            
            # Test available statements
            print("\nTesting statements object:")
            if hasattr(xbrl, 'statements'):
                print(f"Statements type: {type(xbrl.statements)}")
                print(f"Statements dir: {[attr for attr in dir(xbrl.statements) if not attr.startswith('_')]}")
                
                # Try to get different statement types
                try:
                    balance_sheet_obj = xbrl.statements.balance_sheet
                    print(f"Balance sheet object: {type(balance_sheet_obj)}")
                except:
                    print("No balance_sheet attribute")
                    
                try:
                    cash_flow_obj = xbrl.statements.cash_flow
                    print(f"Cash flow object: {type(cash_flow_obj)}")
                except:
                    print("No cash_flow attribute")
                    
                try:
                    income_obj = xbrl.statements.income
                    print(f"Income object: {type(income_obj)}")
                except:
                    print("No income attribute")
            
            print("\nTesting specific statement types...")
            
            # Test Balance Sheet
            print("\n[yellow]Testing Balance Sheet:[/yellow]")
            try:
                balance_sheet = xbrl.get_statement_by_type("BalanceSheet")
                print(f"Type: {type(balance_sheet)}")
                print(f"Is None: {balance_sheet is None}")
                if balance_sheet is not None and isinstance(balance_sheet, dict):
                    print(f"Keys: {list(balance_sheet.keys())}")
                    data = balance_sheet.get('data')
                    if data is not None:
                        print(f"Data type: {type(data)}")
                        print(f"Data length: {len(data) if hasattr(data, '__len__') else 'No length'}")
                        if hasattr(data, '__len__') and len(data) > 0:
                            if isinstance(data, dict):
                                print(f"Data keys (first 5): {list(data.keys())[:5]}")
                            elif hasattr(data, 'index'):  # DataFrame-like
                                print(f"Data index (first 5): {list(data.index[:5])}")
                        else:
                            print("[red]Balance Sheet data is EMPTY[/red]")
                    else:
                        print("[red]Balance Sheet has no 'data' key[/red]")
                else:
                    print("[red]Balance Sheet is None or not a dict[/red]")
            except Exception as e:
                print(f"[red]Balance Sheet error: {e}[/red]")
                traceback.print_exc()
            
            # Test Cash Flow
            print("\n[yellow]Testing Cash Flow Statement:[/yellow]")
            try:
                cash_flow = xbrl.get_statement_by_type("CashFlowStatement")
                print(f"Type: {type(cash_flow)}")
                print(f"Is None: {cash_flow is None}")
                if cash_flow is not None and isinstance(cash_flow, dict):
                    print(f"Keys: {list(cash_flow.keys())}")
                    data = cash_flow.get('data')
                    if data is not None:
                        print(f"Data type: {type(data)}")
                        print(f"Data length: {len(data) if hasattr(data, '__len__') else 'No length'}")
                        if hasattr(data, '__len__') and len(data) > 0:
                            if isinstance(data, dict):
                                print(f"Data keys (first 5): {list(data.keys())[:5]}")
                            elif hasattr(data, 'index'):  # DataFrame-like
                                print(f"Data index (first 5): {list(data.index[:5])}")
                        else:
                            print("[red]Cash Flow data is EMPTY[/red]")
                    else:
                        print("[red]Cash Flow has no 'data' key[/red]")
                else:
                    print("[red]Cash Flow is None or not a dict[/red]")
            except Exception as e:
                print(f"[red]Cash Flow error: {e}[/red]")
                traceback.print_exc()
                
            # Test Income Statement for comparison
            print("\n[yellow]Testing Income Statement:[/yellow]")
            try:
                income_stmt = xbrl.get_statement_by_type("IncomeStatement")
                print(f"Type: {type(income_stmt)}")
                print(f"Is None: {income_stmt is None}")
                if income_stmt is not None and isinstance(income_stmt, dict):
                    print(f"Keys: {list(income_stmt.keys())}")
                    data = income_stmt.get('data')
                    if data is not None:
                        print(f"Data type: {type(data)}")
                        print(f"Data length: {len(data) if hasattr(data, '__len__') else 'No length'}")
                        if hasattr(data, '__len__') and len(data) > 0:
                            if isinstance(data, dict):
                                print(f"Data keys (first 5): {list(data.keys())[:5]}")
                            elif hasattr(data, 'index'):  # DataFrame-like
                                print(f"Data index (first 5): {list(data.index[:5])}")
                        else:
                            print("[red]Income Statement data is EMPTY[/red]")
                    else:
                        print("[red]Income Statement has no 'data' key[/red]")
                else:
                    print("[red]Income Statement is None or not a dict[/red]")
            except Exception as e:
                print(f"[red]Income Statement error: {e}[/red]")
                traceback.print_exc()
        
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        traceback.print_exc()

if __name__ == "__main__":
    simple_test()