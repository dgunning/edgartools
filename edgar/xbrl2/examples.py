"""
Examples demonstrating how to use the XBRL2 module.

This module provides multiple examples demonstrating different ways to use the XBRL2 module.
"""

from pathlib import Path
from rich.console import Console

from edgar import Filing
from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statements import Statements

def render_financial_statements():
    """
    Demonstrates how to render financial statements in a tabular format.
    """
    # Path to XBRL files
    sample_dir = Path(__file__).parent / "aapl"
    
    # Create an XBRL object by parsing the directory
    xbrl = XBRL.parse_directory(sample_dir)
    
    console = Console()
    
    # Display entity information
    console.print("\n[bold]Entity Information:[/bold]")
    for key, value in xbrl.entity_info.items():
        console.print(f"{key}: {value}")
    
    # Display available reporting periods
    console.print("\n[bold]Available Reporting Periods:[/bold]")
    for i, period in enumerate(xbrl.reporting_periods):
        if period['type'] == 'instant':
            console.print(f"{i+1}. As of {period['date']}")
        else:
            console.print(f"{i+1}. {period['start_date']} to {period['end_date']}")
    
    # Show available period views for each statement
    console.print("\n[bold]Available Period Views for Balance Sheet:[/bold]")
    bs_views = xbrl.get_period_views("BalanceSheet")
    for view in bs_views:
        console.print(f"- {view['name']}: {view['description']}")
    
    console.print("\n[bold]Available Period Views for Income Statement:[/bold]")
    is_views = xbrl.get_period_views("IncomeStatement")
    for view in is_views:
        console.print(f"- {view['name']}: {view['description']}")
    
    # Render Balance Sheet using default view
    console.print("\n[bold]Balance Sheet (Default View):[/bold]")
    balance_sheet = xbrl.render_statement("BalanceSheet")
    console.print(balance_sheet)
    
    # Render Balance Sheet with Current vs. Previous Period view if available
    if bs_views and any(v['name'] == 'Current vs. Previous Period' for v in bs_views):
        console.print("\n[bold]Balance Sheet (Current vs. Previous Period):[/bold]")
        current_vs_prev_bs = xbrl.render_statement("BalanceSheet", period_view="Current vs. Previous Period")
        console.print(current_vs_prev_bs)
    
    # Render Income Statement using default view
    console.print("\n[bold]Income Statement (Default View):[/bold]")
    income_statement = xbrl.render_statement("IncomeStatement")
    console.print(income_statement)
    
    # Render Income Statement with Annual Comparison view if available
    if is_views and any(v['name'] == 'Annual Comparison' for v in is_views):
        console.print("\n[bold]Income Statement (Annual Comparison):[/bold]")
        annual_is = xbrl.render_statement("IncomeStatement", period_view="Annual Comparison")
        console.print(annual_is)
    
    # Render Cash Flow Statement
    console.print("\n[bold]Cash Flow Statement:[/bold]")
    cash_flow = xbrl.render_statement("CashFlowStatement")
    console.print(cash_flow)
    
    # Get a specific period for rendering
    if xbrl.reporting_periods:
        # Use the most recent instant period for Balance Sheet
        instant_periods = [p for p in xbrl.reporting_periods if p['type'] == 'instant']
        
        if instant_periods:
            period = instant_periods[0]  # Most recent period
            period_key = f"instant_{period['date']}"
            
            console.print(f"\n[bold]Balance Sheet (As of {period['date']} only):[/bold]")
            single_period_bs = xbrl.render_statement("BalanceSheet", period_filter=period_key)
            console.print(single_period_bs)
        
        # Use most recent duration period for Income Statement
        duration_periods = [p for p in xbrl.reporting_periods if p['type'] == 'duration']
        
        if duration_periods:
            period = duration_periods[0]  # Most recent period
            period_key = f"duration_{period['start_date']}_{period['end_date']}"
            
            console.print(f"\n[bold]Income Statement ({period['start_date']} to {period['end_date']} only):[/bold]")
            single_period_is = xbrl.render_statement("IncomeStatement", period_filter=period_key)
            console.print(single_period_is)

def using_statements_api():
    """
    Demonstrates the use of the user-friendly Statements API.
    """
    # Path to XBRL files
    sample_dir = Path(__file__).parent / "aapl"
    
    # Create an XBRL object by parsing the directory
    xbrl = XBRL.parse_directory(sample_dir)
    
    # Create a Statements object for easier access
    statements = Statements(xbrl)
    
    console = Console()
    
    # Display available statements
    console.print("\n[bold]Available Statements:[/bold]")
    console.print(statements)
    
    # Display balance sheet
    console.print("\n[bold]Balance Sheet:[/bold]")
    balance_sheet = statements.balance_sheet()
    console.print(balance_sheet)
    
    # Display income statement
    console.print("\n[bold]Income Statement:[/bold]")
    income_statement = statements.income_statement()
    console.print(income_statement)
    
    # Display cash flow statement
    console.print("\n[bold]Cash Flow Statement:[/bold]")
    cash_flow = statements.cash_flow_statement()
    console.print(cash_flow)
    
    # Get available period views
    console.print("\n[bold]Available Period Views for Income Statement:[/bold]")
    period_views = statements.get_period_views("IncomeStatement")
    for view in period_views:
        console.print(f"- {view['name']}: {view['description']}")
    
    # Display with specific period view if available
    if period_views:
        view_name = period_views[0]['name']
        console.print(f"\n[bold]Income Statement with {view_name} Period View:[/bold]")
        income_statement_view = statements.income_statement(period_view=view_name)
        console.print(income_statement_view)
    
    # Convert to dataframe
    console.print("\n[bold]Converting to DataFrame:[/bold]")
    df = statements.to_dataframe("IncomeStatement")
    console.print(f"DataFrame shape: {df.shape}")
    console.print(df.head(3))

def example_with_real_filing():
    """
    Example using a real filing from SEC.
    Note: This requires internet access.
    """
    console = Console()
    console.print("[bold]Example with Real Filing[/bold]")
    
    try:
        # Get a filing with XBRL attachments
        filing = Filing.get('0000320193-23-000077')  # Apple 10-K
        console.print(f"Retrieved filing: {filing.form} for {filing.company} ({filing.filing_date})")
        
        # Parse XBRL data
        xbrl = XBRL.from_filing(filing)
        
        # Create Statements object
        statements = Statements(xbrl)
        
        # Display entity information
        console.print("\n[bold]Entity Information:[/bold]")
        entity_info = {
            'entity_name': xbrl.entity_info.get('entity_name'),
            'ticker': xbrl.entity_info.get('ticker'),
            'document_type': xbrl.entity_info.get('document_type'),
            'fiscal_year': xbrl.entity_info.get('fiscal_year'),
            'fiscal_period': xbrl.entity_info.get('fiscal_period')
        }
        for key, value in entity_info.items():
            console.print(f"{key}: {value}")
        
        # Display balance sheet
        console.print("\n[bold]Balance Sheet:[/bold]")
        balance_sheet = statements.balance_sheet()
        console.print(balance_sheet)
        
    except Exception as e:
        console.print(f"[bold red]Error loading real filing: {str(e)}[/bold red]")
        console.print("[yellow]Note: This example requires internet access to fetch filings from SEC EDGAR.[/yellow]")

if __name__ == "__main__":
    console = Console()
    console.print("[bold cyan]XBRL2 Module Examples[/bold cyan]")
    console.print("[yellow]Choose an example to run:[/yellow]")
    console.print("1. Render Financial Statements (Direct XBRL API)")
    console.print("2. Using Statements API (User-friendly API)")
    console.print("3. Example with Real Filing (Requires Internet)")
    console.print("4. Run All Examples")
    
    try:
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == "1":
            render_financial_statements()
        elif choice == "2":
            using_statements_api()
        elif choice == "3":
            example_with_real_filing()
        elif choice == "4":
            console.print("\n[bold]Running All Examples[/bold]\n")
            console.print("\n[bold cyan]Example 1: Render Financial Statements[/bold cyan]\n")
            render_financial_statements()
            console.print("\n" + "-" * 80 + "\n")
            console.print("\n[bold cyan]Example 2: Using Statements API[/bold cyan]\n")
            using_statements_api()
            console.print("\n" + "-" * 80 + "\n")
            console.print("\n[bold cyan]Example 3: Example with Real Filing[/bold cyan]\n")
            example_with_real_filing()
        else:
            console.print("[bold red]Invalid choice. Please run the script again and select a valid option.[/bold red]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Examples cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error running examples: {str(e)}[/bold red]")