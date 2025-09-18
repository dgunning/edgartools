"""
Examples demonstrating how to use the XBRL2 module.

This module provides multiple examples demonstrating different ways to use the XBRL2 module.
"""

from pathlib import Path

from rich import print
from rich.console import Console

from edgar import Company, Filing
from edgar.xbrl.statements import Statements
from edgar.xbrl.xbrl import XBRL


def render_financial_statements(ticker="AAPL"):
    """
    Demonstrates how to render financial statements in a tabular format.
    """
    company = Company("AAPL")

    # Get the latest filing
    filing = company.latest("10-K")

    # Create an XBRL object
    xbrl = XBRL.from_filing(filing)

    # Display entity information
    print("\n[bold]Entity Information:[/bold]")
    for key, value in xbrl.entity_info.items():
        print(f"{key}: {value}")

    # Display available reporting periods
    print("\n[bold]Available Reporting Periods:[/bold]")
    for i, period in enumerate(xbrl.reporting_periods):
        if period['type'] == 'instant':
            print(f"{i + 1}. As of {period['date']}")
        else:
            print(f"{i + 1}. {period['start_date']} to {period['end_date']}")

    # Show available period views for each statement
    print("\n[bold]Available Period Views for Balance Sheet:[/bold]")
    bs_views = xbrl.get_period_views("BalanceSheet")
    for view in bs_views:
        print(f"- {view['name']}: {view['description']}")

    print("\n[bold]Available Period Views for Income Statement:[/bold]")
    is_views = xbrl.get_period_views("IncomeStatement")
    for view in is_views:
        print(f"- {view['name']}: {view['description']}")

    # Render Balance Sheet using default view
    print("\n[bold]Balance Sheet (Default View):[/bold]")
    balance_sheet = xbrl.render_statement("BalanceSheet")
    print(balance_sheet)

    # Render Balance Sheet with Current vs. Previous Period view if available
    if bs_views and any(v['name'] == 'Current vs. Previous Period' for v in bs_views):
        print("\n[bold]Balance Sheet (Current vs. Previous Period):[/bold]")
        current_vs_prev_bs = xbrl.render_statement("BalanceSheet", period_view="Current vs. Previous Period")
        print(current_vs_prev_bs)

    # Render Income Statement using default view
    print("\n[bold]Income Statement (Default View):[/bold]")
    income_statement = xbrl.render_statement("IncomeStatement")
    print(income_statement)

    # Render Income Statement with Annual Comparison view if available
    if is_views and any(v['name'] == 'Annual Comparison' for v in is_views):
        print("\n[bold]Income Statement (Annual Comparison):[/bold]")
        annual_is = xbrl.render_statement("IncomeStatement", period_view="Annual Comparison")
        print(annual_is)

    # Render Cash Flow Statement
    print("\n[bold]Cash Flow Statement:[/bold]")
    cash_flow = xbrl.render_statement("CashFlowStatement")
    print(cash_flow)

    # Get a specific period for rendering
    if xbrl.reporting_periods:
        # Use the most recent instant period for Balance Sheet
        instant_periods = [p for p in xbrl.reporting_periods if p['type'] == 'instant']

        if instant_periods:
            period = instant_periods[0]  # Most recent period
            period_key = f"instant_{period['date']}"

            print(f"\n[bold]Balance Sheet (As of {period['date']} only):[/bold]")
            single_period_bs = xbrl.render_statement("BalanceSheet", period_filter=period_key)
            print(single_period_bs)

        # Use most recent duration period for Income Statement
        duration_periods = [p for p in xbrl.reporting_periods if p['type'] == 'duration']

        if duration_periods:
            period = duration_periods[0]  # Most recent period
            period_key = f"duration_{period['start_date']}_{period['end_date']}"

            print(f"\n[bold]Income Statement ({period['start_date']} to {period['end_date']} only):[/bold]")
            single_period_is = xbrl.render_statement("IncomeStatement", period_filter=period_key)
            print(single_period_is)

def using_statements_api(ticker="TSLA"):
    """
    Demonstrates the use of the user-friendly Statements API.
    """
    company = Company(ticker)

    # Get the latest filing
    filing = company.latest("10-K")

    # Create an XBRL object
    xbrl = XBRL.from_filing(filing)

    # Create a Statements object for easier access
    statements = Statements(xbrl)

    # Display available statements
    print("\n[bold]Available Statements:[/bold]")
    print(statements)

    # Display balance sheet
    print("\n[bold]Balance Sheet:[/bold]")
    balance_sheet = statements.balance_sheet()
    print(balance_sheet)

    # Display income statement
    print("\n[bold]Income Statement:[/bold]")
    income_statement = statements.income_statement()
    print(income_statement)

    # Display cash flow statement
    print("\n[bold]Cash Flow Statement:[/bold]")
    cash_flow = statements.cashflow_statement()
    print(cash_flow)

    # Get available period views
    print("\n[bold]Available Period Views for Income Statement:[/bold]")
    period_views = statements.get_period_views("IncomeStatement")
    for view in period_views:
        print(f"- {view['name']}: {view['description']}")

    # Display with specific period view if available
    if period_views:
        view_name = period_views[0]['name']
        print(f"\n[bold]Income Statement with {view_name} Period View:[/bold]")
        income_statement_view = statements.income_statement(period_view=view_name)
        print(income_statement_view)

    # Display three-column view if available
    print("\n[bold]Three-Column Statement View (if available):[/bold]")
    period_views = statements.get_period_views("BalanceSheet")
    three_year_view = next((v for v in period_views if "Three" in v['name']), None)
    if three_year_view:
        print(f"\n[bold]Balance Sheet with Three Periods ({three_year_view['name']}):[/bold]")
        print(f"Description: {three_year_view['description']}")
        three_col_bs = statements.balance_sheet(period_view=three_year_view['name'])
        print(three_col_bs)
    else:
        print("[yellow]No three-period view available for this filing.[/yellow]")

    # Convert to dataframe
    print("\n[bold]Converting to DataFrame:[/bold]")
    df = statements.to_dataframe("IncomeStatement")
    print(f"DataFrame shape: {df.shape}")
    print(df.head(3))

def example_with_real_filing():
    """
    Example using a real filing from SEC.
    Note: This requires internet access.
    """
    # Using print directly with rich formatting instead of console
    print("[bold]Example with Real Filing[/bold]")

    try:
        # Get a filing with XBRL attachments
        filing = Filing.get('0000320193-23-000077')  # Apple 10-K
        print(f"Retrieved filing: {filing.form} for {filing.company} ({filing.filing_date})")

        # Parse XBRL data
        xbrl = XBRL.from_filing(filing)

        # Create Statements object
        statements = Statements(xbrl)

        # Display entity information
        print("\n[bold]Entity Information:[/bold]")
        entity_info = {
            'entity_name': xbrl.entity_info.get('entity_name'),
            'ticker': xbrl.entity_info.get('ticker'),
            'document_type': xbrl.entity_info.get('document_type'),
            'fiscal_year': xbrl.entity_info.get('fiscal_year'),
            'fiscal_period': xbrl.entity_info.get('fiscal_period')
        }
        for key, value in entity_info.items():
            print(f"{key}: {value}")

        # Display balance sheet
        print("\n[bold]Balance Sheet:[/bold]")
        balance_sheet = statements.balance_sheet()
        print(balance_sheet)

    except Exception as e:
        print(f"[bold red]Error loading real filing: {str(e)}[/bold red]")
        print("[yellow]Note: This example requires internet access to fetch filings from SEC EDGAR.[/yellow]")


def standardized_statements_example():
    """
    Demonstrates the use of standardized concept labels.
    """
    # Path to XBRL files
    sample_dir = Path(__file__).parent / "aapl"

    # Create an XBRL object by parsing the directory
    xbrl = XBRL.from_directory(sample_dir)

    # Create a Statements object for easier access
    statements = Statements(xbrl)

    # Display original income statement
    print("\n[bold]Income Statement (Original Labels):[/bold]")
    income_statement = statements.income_statement()
    print(income_statement)

    # Display standardized income statement
    print("\n[bold]Income Statement (Standardized Labels):[/bold]")
    income_statement_std = statements.income_statement(standard=True)
    print(income_statement_std)

    # Display original balance sheet
    print("\n[bold]Balance Sheet (Original Labels):[/bold]")
    balance_sheet = statements.balance_sheet()
    print(balance_sheet)

    # Display standardized balance sheet
    print("\n[bold]Balance Sheet (Standardized Labels):[/bold]")
    balance_sheet_std = statements.balance_sheet(standard=True)
    print(balance_sheet_std)

    # Show standardized statement with a specific period view
    period_views = statements.get_period_views("BalanceSheet")
    if period_views:
        view_name = period_views[0]['name']
        print(f"\n[bold]Balance Sheet ({view_name}) with Standardized Labels:[/bold]")
        balance_sheet_view_std = statements.balance_sheet(period_view=view_name, standard=True)
        print(balance_sheet_view_std)

    # Demonstrate standardized DataFrames
    print("\n[bold]Converting to DataFrame with Standardized Labels:[/bold]")

    # Original DataFrame
    print("\n[bold]Original DataFrame:[/bold]")
    df_orig = statements.to_dataframe("IncomeStatement", standard=False)
    if not df_orig.empty:
        print(f"DataFrame shape: {df_orig.shape}")
        print(df_orig[['concept', 'label']].head(3))

    # Standardized DataFrame
    print("\n[bold]Standardized DataFrame:[/bold]")
    df_std = statements.to_dataframe("IncomeStatement", standard=True)
    if not df_std.empty:
        print(f"DataFrame shape: {df_std.shape}")
        if 'original_label' in df_std.columns:
            print(df_std[['concept', 'label', 'original_label']].head(3))
        else:
            print(df_std[['concept', 'label']].head(3))

if __name__ == "__main__":
    console = Console()
    print("[bold cyan]XBRL2 Module Examples[/bold cyan]")
    print("[yellow]Choose an example to run:[/yellow]")
    print("1. Render Financial Statements (Direct XBRL API)")
    print("2. Using Statements API (User-friendly API)")
    print("3. Example with Real Filing (Requires Internet)")
    print("4. Standardized Statements (Concept Standardization)")
    print("5. Run All Examples")

    try:
        choice = input("\nEnter your choice (1-5): ")

        if choice == "1":
            render_financial_statements()
        elif choice == "2":
            using_statements_api()
        elif choice == "3":
            example_with_real_filing()
        elif choice == "4":
            standardized_statements_example()
        elif choice == "5":
            print("\n[bold]Running All Examples[/bold]\n")
            print("\n[bold cyan]Example 1: Render Financial Statements[/bold cyan]\n")
            render_financial_statements()
            print("\n" + "-" * 80 + "\n")
            print("\n[bold cyan]Example 2: Using Statements API[/bold cyan]\n")
            using_statements_api()
            print("\n" + "-" * 80 + "\n")
            print("\n[bold cyan]Example 3: Example with Real Filing[/bold cyan]\n")
            example_with_real_filing()
            print("\n" + "-" * 80 + "\n")
            print("\n[bold cyan]Example 4: Standardized Statements[/bold cyan]\n")
            standardized_statements_example()
        else:
            print("[bold red]Invalid choice. Please run the script again and select a valid option.[/bold red]")

    except KeyboardInterrupt:
        print("\n[yellow]Examples cancelled by user.[/yellow]")
    except Exception as e:
        print(f"[bold red]Error running examples: {str(e)}[/bold red]")
