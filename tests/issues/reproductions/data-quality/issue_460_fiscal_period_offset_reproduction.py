"""
Reproduction script for Issue #460: Income statement fiscal periods are incorrect

Reporter: akelleh (Adam Kelleher)
Issue: AAPL income statements show fiscal periods offset by:
  - Annual statements: 2 years offset
  - Quarterly statements: 1 year offset

Expected: Periods should match official SEC filings and other sources
Actual: All periods are shifted forward incorrectly

This reproduction script will:
1. Fetch AAPL income statements (both annual and quarterly)
2. Display the periods shown by EdgarTools
3. Compare with known correct values from SEC filings
4. Verify the offset pattern described in the issue
"""

from edgar import Company, set_identity
from rich import print as rprint
from rich.table import Table
from rich.console import Console
import os

console = Console()

def main():
    # Set identity from environment or use test identity
    identity = os.getenv('EDGAR_IDENTITY')
    if identity:
        set_identity(identity)

    console.print("\n[bold]Issue #460: AAPL Income Statement Fiscal Period Offset[/bold]\n")

    # Fetch AAPL company
    company = Company("AAPL")
    console.print(f"Company: {company.name} ({company.tickers})")
    console.print(f"Fiscal Year End: September (Q4 ends in September)\n")

    # Get annual income statements
    console.print("[bold cyan]Annual Income Statements (last 5 years):[/bold cyan]")
    annual_income = company.income_statement(periods=5, annual=True)
    console.print(annual_income)

    # Get quarterly income statements
    console.print("\n[bold cyan]Quarterly Income Statements (last 10 quarters):[/bold cyan]")
    quarterly_income = company.income_statement(periods=10, annual=False)
    console.print(quarterly_income)

    # Expected values from external sources for verification
    # From https://www.macrotrends.net/stocks/charts/AAPL/apple/revenue
    # and https://finance.yahoo.com/quote/AAPL/financials/
    console.print("\n[bold yellow]Expected Annual Total Revenue (Fiscal Year End Sept):[/bold yellow]")
    expected_annual = Table(show_header=True)
    expected_annual.add_column("Fiscal Year")
    expected_annual.add_column("Total Revenue (B)")
    expected_annual.add_column("Source")

    expected_annual.add_row("FY 2024 (ended Sept 2024)", "$391.0B", "Yahoo Finance")
    expected_annual.add_row("FY 2023 (ended Sept 2023)", "$383.3B", "Yahoo Finance")
    expected_annual.add_row("FY 2022 (ended Sept 2022)", "$394.3B", "Yahoo Finance")
    expected_annual.add_row("FY 2021 (ended Sept 2021)", "$365.8B", "Yahoo Finance")
    expected_annual.add_row("FY 2020 (ended Sept 2020)", "$274.5B", "Yahoo Finance")

    console.print(expected_annual)

    console.print("\n[bold yellow]Expected Quarterly Total Revenue (Recent Quarters):[/bold yellow]")
    expected_quarterly = Table(show_header=True)
    expected_quarterly.add_column("Quarter")
    expected_quarterly.add_column("Period End")
    expected_quarterly.add_column("Total Revenue (B)")

    expected_quarterly.add_row("Q4 2024", "Sept 28, 2024", "$94.9B")
    expected_quarterly.add_row("Q3 2024", "June 29, 2024", "$85.8B")
    expected_quarterly.add_row("Q2 2024", "Mar 30, 2024", "$90.8B")
    expected_quarterly.add_row("Q1 2024", "Dec 30, 2023", "$119.6B")
    expected_quarterly.add_row("Q4 2023", "Sept 30, 2023", "$89.5B")
    expected_quarterly.add_row("Q3 2023", "July 1, 2023", "$81.8B")

    console.print(expected_quarterly)

    console.print("\n[bold red]Issue Verification:[/bold red]")
    console.print("Compare the fiscal periods shown in EdgarTools output above")
    console.print("with the expected periods from official sources.")
    console.print("\nReported offset pattern:")
    console.print("  - Annual statements: 2 years ahead")
    console.print("  - Quarterly statements: 1 year ahead")
    console.print("\nIf the issue exists, EdgarTools will show FY2026/FY2025")
    console.print("instead of FY2024/FY2023, and quarters will be shifted forward by 1 year.")

if __name__ == "__main__":
    main()
