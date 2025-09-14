"""
Test MultiPeriodStatement objects returned by Company API to see if they're actually blank.
This should reveal the root cause of the user's issue.
"""

import edgar
from rich import print
import traceback
import pandas as pd

def test_multiperiod_statements():
    """Test MultiPeriodStatement objects for blank data"""
    
    companies = ['AAPL', 'MSFT', 'GOOGL']
    
    for ticker in companies[:1]:  # Start with just AAPL
        print(f"\n[bold blue]Testing {ticker} MultiPeriodStatement objects[/bold blue]")
        
        try:
            company = edgar.Company(ticker)
            
            # Test Balance Sheet
            print(f"\n[yellow]Testing {ticker} Balance Sheet (MultiPeriodStatement):[/yellow]")
            try:
                balance_sheet = company.balance_sheet(periods=4, annual=True)
                print(f"Type: {type(balance_sheet)}")
                print(f"Dir: {[attr for attr in dir(balance_sheet) if not attr.startswith('_')]}")
                
                # Try to access the data
                if hasattr(balance_sheet, 'data'):
                    data = balance_sheet.data
                    print(f"Data attribute: {type(data)}")
                    if hasattr(data, 'empty'):
                        print(f"Data empty: {data.empty}")
                    if hasattr(data, 'shape'):
                        print(f"Data shape: {data.shape}")
                    if hasattr(data, 'columns'):
                        print(f"Data columns: {list(data.columns)}")
                        
                # Try to convert to DataFrame  
                if hasattr(balance_sheet, 'to_dataframe'):
                    try:
                        df = balance_sheet.to_dataframe()
                        print(f"DataFrame: {type(df)}")
                        if isinstance(df, pd.DataFrame):
                            print(f"DataFrame shape: {df.shape}")
                            print(f"DataFrame empty: {df.empty}")
                            print(f"DataFrame columns: {list(df.columns)}")
                            if not df.empty:
                                print(f"Sample data:\n{df.head(3)}")
                            else:
                                print("[red]DataFrame is EMPTY[/red]")
                    except Exception as e:
                        print(f"to_dataframe() error: {e}")
                        
                # Try direct attribute access
                if hasattr(balance_sheet, 'df'):
                    df = balance_sheet.df
                    print(f"Direct df attribute: {type(df)}")
                    if isinstance(df, pd.DataFrame):
                        print(f"DF shape: {df.shape}, empty: {df.empty}")
                        
            except Exception as e:
                print(f"    [red]Balance Sheet error: {e}[/red]")
                traceback.print_exc()
            
            # Test Cash Flow
            print(f"\n[yellow]Testing {ticker} Cash Flow (MultiPeriodStatement):[/yellow]")
            try:
                cash_flow = company.cash_flow(periods=4, annual=True)
                print(f"Type: {type(cash_flow)}")
                
                # Try to convert to DataFrame  
                if hasattr(cash_flow, 'to_dataframe'):
                    try:
                        df = cash_flow.to_dataframe()
                        print(f"DataFrame: {type(df)}")
                        if isinstance(df, pd.DataFrame):
                            print(f"DataFrame shape: {df.shape}")
                            print(f"DataFrame empty: {df.empty}")
                            print(f"DataFrame columns: {list(df.columns)}")
                            if not df.empty:
                                print(f"Sample data:\n{df.head(3)}")
                            else:
                                print("[red]DataFrame is EMPTY[/red]")
                    except Exception as e:
                        print(f"to_dataframe() error: {e}")
                        
            except Exception as e:
                print(f"    [red]Cash Flow error: {e}[/red]")
                traceback.print_exc()
                
            # Test Income Statement for comparison
            print(f"\n[yellow]Testing {ticker} Income Statement (MultiPeriodStatement):[/yellow]")
            try:
                income_stmt = company.income_statement(periods=4, annual=True)
                print(f"Type: {type(income_stmt)}")
                
                # Try to convert to DataFrame  
                if hasattr(income_stmt, 'to_dataframe'):
                    try:
                        df = income_stmt.to_dataframe()
                        print(f"DataFrame: {type(df)}")
                        if isinstance(df, pd.DataFrame):
                            print(f"DataFrame shape: {df.shape}")
                            print(f"DataFrame empty: {df.empty}")
                            print(f"DataFrame columns: {list(df.columns)}")
                            if not df.empty:
                                print(f"Sample data:\n{df.head(3)}")
                            else:
                                print("[red]DataFrame is EMPTY[/red]")
                    except Exception as e:
                        print(f"to_dataframe() error: {e}")
                        
            except Exception as e:
                print(f"    [red]Income Statement error: {e}[/red]")
                traceback.print_exc()
                
        except Exception as e:
            print(f"[red]Failed to process {ticker}: {e}[/red]")
            traceback.print_exc()

def test_historical_years():
    """Test if historical years are actually available in MultiPeriodStatement"""
    
    print(f"\n[bold blue]Testing Historical Years Availability[/bold blue]")
    
    try:
        company = edgar.Company("AAPL")
        
        # Test with maximum periods to get historical data
        print("\nTesting AAPL with 20 annual periods (maximum historical data):")
        
        balance_sheet = company.balance_sheet(periods=20, annual=True)
        if balance_sheet and hasattr(balance_sheet, 'to_dataframe'):
            df = balance_sheet.to_dataframe()
            if isinstance(df, pd.DataFrame) and not df.empty:
                print(f"Balance Sheet DataFrame columns: {list(df.columns)}")
                
                # Check what years are available (format is "FY YYYY")
                year_cols = [col for col in df.columns if isinstance(col, str) and col.startswith('FY ')]
                if year_cols:
                    # Extract year numbers and sort
                    year_numbers = []
                    for col in year_cols:
                        try:
                            year_num = int(col.split(' ')[1])
                            year_numbers.append((year_num, col))
                        except:
                            pass
                    year_numbers.sort(reverse=True)
                    print(f"Available years in Balance Sheet: {[y[0] for y in year_numbers]}")
                    
                    # Check if 2022 and earlier are present
                    years_2022_earlier = [(year, col) for year, col in year_numbers if year <= 2022]
                    if years_2022_earlier:
                        print(f"Years 2022 and earlier: {[y[0] for y in years_2022_earlier]}")
                        
                        # Check if these columns have data
                        for year, col_name in years_2022_earlier[:3]:  # Check first 3
                            non_null_count = df[col_name].count()
                            total_non_abstract = len(df[~df['is_abstract']])  # Don't count abstract items
                            print(f"  {year} ({col_name}): {non_null_count} non-null values out of {len(df)} total ({total_non_abstract} non-abstract)")
                            if non_null_count == 0:
                                print(f"    [red]{year} Balance Sheet data is ALL NULL[/red]")
                            else:
                                # Show some sample values
                                sample_data = df[~df['is_abstract']][col_name].dropna().head(3)
                                if len(sample_data) > 0:
                                    print(f"    Sample values: {list(sample_data.values)}")
                                else:
                                    print(f"    [red]{year} has no non-abstract values with data[/red]")
                    else:
                        print("[red]No years 2022 or earlier found in Balance Sheet[/red]")
                else:
                    print("[red]No FY year columns found in Balance Sheet[/red]")
            else:
                print("[red]Balance Sheet DataFrame is empty[/red]")
        
        # Test Cash Flow
        cash_flow = company.cash_flow(periods=20, annual=True)
        if cash_flow and hasattr(cash_flow, 'to_dataframe'):
            df = cash_flow.to_dataframe()
            if isinstance(df, pd.DataFrame) and not df.empty:
                print(f"Cash Flow DataFrame columns: {list(df.columns)}")
                
                # Check what years are available (format is "FY YYYY")
                year_cols = [col for col in df.columns if isinstance(col, str) and col.startswith('FY ')]
                if year_cols:
                    # Extract year numbers and sort
                    year_numbers = []
                    for col in year_cols:
                        try:
                            year_num = int(col.split(' ')[1])
                            year_numbers.append((year_num, col))
                        except:
                            pass
                    year_numbers.sort(reverse=True)
                    print(f"Available years in Cash Flow: {[y[0] for y in year_numbers]}")
                    
                    # Check if 2021 and earlier are present
                    years_2021_earlier = [(year, col) for year, col in year_numbers if year <= 2021]
                    if years_2021_earlier:
                        print(f"Years 2021 and earlier: {[y[0] for y in years_2021_earlier]}")
                        
                        # Check if these columns have data
                        for year, col_name in years_2021_earlier[:3]:  # Check first 3
                            non_null_count = df[col_name].count()
                            total_non_abstract = len(df[~df['is_abstract']])  # Don't count abstract items
                            print(f"  {year} ({col_name}): {non_null_count} non-null values out of {len(df)} total ({total_non_abstract} non-abstract)")
                            if non_null_count == 0:
                                print(f"    [red]{year} Cash Flow data is ALL NULL[/red]")
                            else:
                                # Show some sample values
                                sample_data = df[~df['is_abstract']][col_name].dropna().head(3)
                                if len(sample_data) > 0:
                                    print(f"    Sample values: {list(sample_data.values)}")
                                else:
                                    print(f"    [red]{year} has no non-abstract values with data[/red]")
                    else:
                        print("[red]No years 2021 or earlier found in Cash Flow[/red]")
                else:
                    print("[red]No FY year columns found in Cash Flow[/red]")
            else:
                print("[red]Cash Flow DataFrame is empty[/red]")
                
    except Exception as e:
        print(f"Error testing historical years: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("[bold green]Testing MultiPeriodStatement objects (Issue #412 follow-up)[/bold green]")
    print("Investigating blank balance sheets and cash flow statements")
    
    test_multiperiod_statements()
    test_historical_years()