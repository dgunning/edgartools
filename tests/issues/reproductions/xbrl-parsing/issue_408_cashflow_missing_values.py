"""
Issue #408: Cash flow statement missing values
https://github.com/dgunning/edgartools/issues/408

Investigation into cash flow statement parsing issues for specific older filings.

Problem:
- General fix works for recent Apple 10-Q filings (shows fiscal YTD correctly)
- Some older filings still show empty cash flow statements
- Need to determine if this is a data issue, parsing issue, or expected behavior

Test Cases:
1. Recent Apple 10-Q (should work - fiscal YTD display)
2. Problematic older filings mentioned in issue:
   - 0000320193-18-000070 (Apple 2018)
   - 0000320193-17-000009 (Apple 2017)
   - 0001628280-17-004790 (Other company 2017)
   - 0001628280-16-017809 (Other company 2016)
"""

from edgar import set_identity, Company, get_by_accession_number
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()

def test_cashflow_statement(accession_number: str, company_ticker: str = None, description: str = ""):
    """Test cash flow statement for a specific filing"""

    console.print(f"\n[bold blue]Testing: {description}[/bold blue]")
    console.print(f"Accession: {accession_number}")

    try:
        # Get filing by accession number
        filing = get_by_accession_number(accession_number)

        console.print(f"Filing: {filing.form} - {filing.company} - {filing.filing_date}")

        # Get cash flow statement
        statements = filing.xbrl().statements
        cashflow_stmt = statements.cashflow_statement()

        # Convert to dataframe for analysis
        cashflow = cashflow_stmt.to_dataframe()

        # Display basic info about the cash flow statement
        console.print(f"Cash flow shape: {cashflow.shape}")
        console.print(f"Columns: {list(cashflow.columns)}")

        # Check for empty data
        non_empty_cells = cashflow.notna().sum().sum()
        total_cells = cashflow.shape[0] * cashflow.shape[1]
        empty_percentage = (total_cells - non_empty_cells) / total_cells * 100

        console.print(f"Non-empty cells: {non_empty_cells}/{total_cells} ({100-empty_percentage:.1f}% filled)")

        if non_empty_cells == 0:
            console.print("[red]WARNING: Cash flow statement is completely empty![/red]")
        elif empty_percentage > 80:
            console.print(f"[yellow]WARNING: Cash flow statement is mostly empty ({empty_percentage:.1f}% empty)[/yellow]")
        else:
            console.print("[green]Cash flow statement has substantial data[/green]")

        # Show sample of the data
        console.print("\n[bold]Sample data (first 10 rows):[/bold]")
        print(cashflow.head(10))

        # Analyze periods available
        if hasattr(cashflow, 'columns'):
            console.print(f"\n[bold]Available periods:[/bold]")
            for col in cashflow.columns:
                if col != 'concept':
                    non_empty_in_col = cashflow[col].notna().sum()
                    console.print(f"  {col}: {non_empty_in_col} non-empty values")

        return {
            'filing': filing,
            'cashflow': cashflow,
            'shape': cashflow.shape,
            'non_empty_cells': non_empty_cells,
            'empty_percentage': empty_percentage,
            'success': True
        }

    except Exception as e:
        console.print(f"[red]ERROR: {str(e)}[/red]")
        return {
            'error': str(e),
            'success': False
        }

def main():
    """Main investigation function"""

    console.print("[bold green]Cash Flow Statement Investigation - Issue #408[/bold green]")
    console.print("Testing both working and problematic filings to identify patterns\n")

    # Test cases
    test_cases = [
        {
            'accession': None,  # Will get latest
            'ticker': 'AAPL',
            'description': 'Recent Apple 10-Q (should work - baseline)'
        },
        {
            'accession': '0000320193-18-000070',
            'ticker': 'AAPL',
            'description': 'Apple 2018 (reported as problematic)'
        },
        {
            'accession': '0000320193-17-000009',
            'ticker': 'AAPL',
            'description': 'Apple 2017 (reported as problematic)'
        },
        {
            'accession': '0001628280-17-004790',
            'ticker': None,
            'description': 'Other company 2017 (reported as problematic)'
        },
        {
            'accession': '0001628280-16-017809',
            'ticker': None,
            'description': 'Other company 2016 (reported as problematic)'
        }
    ]

    results = []

    for i, case in enumerate(test_cases):
        try:
            if case['accession'] is None:
                # Get latest filing for baseline test
                console.print(f"\n[bold blue]Test {i+1}: {case['description']}[/bold blue]")
                company = Company(case['ticker'])
                filing = company.get_filings(form='10-Q').latest()
                console.print(f"Latest filing: {filing.accession_number}")
                result = test_cashflow_statement(filing.accession_number, case['ticker'], case['description'])
            else:
                result = test_cashflow_statement(case['accession'], case['ticker'], case['description'])

            result.update(case)
            results.append(result)

        except Exception as e:
            console.print(f"[red]Failed to test case {i+1}: {str(e)}[/red]")
            results.append({
                'error': str(e),
                'success': False,
                **case
            })

    # Summary analysis
    console.print("\n[bold green]SUMMARY ANALYSIS[/bold green]")

    successful_tests = [r for r in results if r.get('success', False)]
    failed_tests = [r for r in results if not r.get('success', False)]

    console.print(f"Successful tests: {len(successful_tests)}")
    console.print(f"Failed tests: {len(failed_tests)}")

    if successful_tests:
        console.print("\n[bold]Data Quality Summary:[/bold]")
        for result in successful_tests:
            desc = result.get('description', 'Unknown')
            empty_pct = result.get('empty_percentage', 0)
            status = "✓ Good" if empty_pct < 50 else "⚠ Mostly Empty" if empty_pct < 90 else "✗ Empty"
            console.print(f"  {desc}: {status} ({empty_pct:.1f}% empty)")

    if failed_tests:
        console.print("\n[bold red]Failed Tests:[/bold red]")
        for result in failed_tests:
            desc = result.get('description', 'Unknown')
            error = result.get('error', 'Unknown error')
            console.print(f"  {desc}: {error}")

    return results

if __name__ == "__main__":
    # Set identity for SEC API (required)
    set_identity("Research Team research@edgartools-investigation.com")

    results = main()