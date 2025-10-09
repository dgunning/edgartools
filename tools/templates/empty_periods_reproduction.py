"""
Issue Reproduction Template: Empty Periods Pattern
For issues like #408 where cash flow statements show empty columns

Replace the placeholders below with actual values from the issue report:
- ISSUE_NUMBER: GitHub issue number
- REPORTER_USERNAME: GitHub username who reported the issue
- ACCESSION_NUMBER: Filing accession number that shows the problem
- COMPANY_NAME: Company name
- EXPECTED_BEHAVIOR: What should happen
- ACTUAL_BEHAVIOR: What actually happens
"""

from edgar import set_identity, get_by_accession_number, Company
from rich.console import Console
import pandas as pd

# Set proper identity (CRITICAL for SEC API access)
set_identity("Research Team research@edgartools-investigation.com")

console = Console()

def reproduce_empty_periods_issue():
    """
    Issue #ISSUE_NUMBER: Empty Periods Reproduction

    Reporter: REPORTER_USERNAME
    Category: data-quality / xbrl-parsing

    Expected: EXPECTED_BEHAVIOR
    Actual: ACTUAL_BEHAVIOR
    """

    console.print("[bold blue]Issue #ISSUE_NUMBER: Empty Periods Reproduction[/bold blue]")
    console.print("Reporter: REPORTER_USERNAME")
    console.print("Company: COMPANY_NAME")

    # Test case details
    accession = "ACCESSION_NUMBER"
    console.print(f"Testing accession: {accession}")

    try:
        # Get the filing and cash flow statement
        filing = get_by_accession_number(accession)
        console.print(f"Filing: {filing.form} - {filing.company} - {filing.filing_date}")

        # Extract cash flow statement
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        df = cashflow_stmt.to_dataframe()

        # Analyze periods
        data_cols = [col for col in df.columns
                    if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

        console.print(f"\nFound {len(data_cols)} periods:")
        for col in data_cols:
            console.print(f"  - {col}")

        # Check for empty periods (Issue #408 pattern)
        empty_periods = []
        meaningful_periods = []

        for col in data_cols:
            # Count non-empty numeric values
            numeric_values = pd.to_numeric(df[col], errors='coerce').notna().sum()

            if numeric_values == 0:
                empty_periods.append(col)
                console.print(f"  ❌ {col}: NO meaningful data")
            else:
                meaningful_periods.append(col)
                console.print(f"  ✅ {col}: {numeric_values} meaningful values")

        # Report findings
        console.print(f"\n[bold]Results:[/bold]")
        console.print(f"Total periods: {len(data_cols)}")
        console.print(f"Meaningful periods: {len(meaningful_periods)}")
        console.print(f"Empty periods: {len(empty_periods)}")

        if empty_periods:
            console.print(f"\n[red]ISSUE CONFIRMED:[/red]")
            console.print(f"Empty periods found: {empty_periods}")
            console.print("This matches the Issue #408 pattern")

            # Show expected vs actual
            console.print(f"\n[yellow]Expected:[/yellow] All periods should have meaningful financial data")
            console.print(f"[red]Actual:[/red] {len(empty_periods)} periods contain only empty values")

            return {
                'issue_confirmed': True,
                'empty_periods': empty_periods,
                'total_periods': len(data_cols),
                'pattern': 'empty_string_periods'
            }
        else:
            console.print(f"\n[green]NO ISSUE FOUND:[/green]")
            console.print("All periods contain meaningful data")

            return {
                'issue_confirmed': False,
                'empty_periods': [],
                'total_periods': len(data_cols),
                'pattern': 'working_correctly'
            }

    except Exception as e:
        console.print(f"[red]ERROR: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())

        return {
            'error': str(e),
            'issue_confirmed': False
        }

def test_multiple_filings():
    """Test multiple filings to confirm pattern"""
    console.print("\n[bold blue]Testing Multiple Filings[/bold blue]")

    # Add additional test cases here
    test_cases = [
        "ACCESSION_NUMBER",  # Original problematic filing
        # Add more accession numbers mentioned in the issue
    ]

    results = []
    for accession in test_cases:
        console.print(f"\n[cyan]Testing: {accession}[/cyan]")
        # You can copy the analysis logic here or call reproduce_empty_periods_issue()

    return results

def compare_with_working_filing():
    """Compare with a known working filing"""
    console.print("\n[bold blue]Comparing with Working Filing[/bold blue]")

    # Use a recent filing that should work correctly
    working_accession = "0000320193-25-000073"  # Apple Q2 2025

    console.print(f"Comparing problematic vs working:")
    console.print(f"  Problematic: ACCESSION_NUMBER")
    console.print(f"  Working: {working_accession}")

    # Add comparison logic here

if __name__ == "__main__":
    # Main reproduction
    result = reproduce_empty_periods_issue()

    # Additional testing (uncomment as needed)
    # test_multiple_filings()
    # compare_with_working_filing()

    # Summary
    if result.get('issue_confirmed'):
        print(f"\n✅ Issue #ISSUE_NUMBER reproduced successfully")
        print(f"Pattern: {result.get('pattern', 'unknown')}")
    else:
        print(f"\n❌ Issue #ISSUE_NUMBER could not be reproduced")