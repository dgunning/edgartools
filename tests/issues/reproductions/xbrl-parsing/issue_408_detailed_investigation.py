"""
Issue #408: Detailed investigation of cash flow statement display
Testing what the user actually sees vs the underlying data
"""

from edgar import set_identity, Company, get_by_accession_number
from rich.console import Console

console = Console()

def investigate_cashflow_display(accession_number: str, description: str = ""):
    """Investigate what the user sees when calling cashflow_statement()"""

    console.print(f"\n[bold blue]Detailed Investigation: {description}[/bold blue]")
    console.print(f"Accession: {accession_number}")

    try:
        filing = get_by_accession_number(accession_number)
        console.print(f"Filing: {filing.form} - {filing.company} - {filing.filing_date}")

        # Get the statements object
        statements = filing.xbrl().statements
        console.print(f"Statements object: {type(statements)}")

        # Get the cash flow statement object (not dataframe yet)
        cashflow_stmt = statements.cashflow_statement()
        console.print(f"Cash flow statement type: {type(cashflow_stmt)}")

        # Look at the raw data structure
        raw_data = cashflow_stmt.get_raw_data()
        console.print(f"Raw data shape: {raw_data.shape if hasattr(raw_data, 'shape') else 'No shape'}")
        console.print(f"Raw data type: {type(raw_data)}")

        if hasattr(raw_data, 'columns'):
            console.print(f"Raw data columns: {list(raw_data.columns)}")
            # Check for empty columns
            for col in raw_data.columns:
                if col not in ['concept', 'label', 'level', 'abstract', 'dimension']:
                    non_empty = raw_data[col].notna().sum()
                    console.print(f"  {col}: {non_empty} non-empty values")

        # Test the render method (what user sees)
        console.print("\n[bold]Testing render() method (what user typically sees):[/bold]")
        try:
            rendered = cashflow_stmt.render()
            console.print(f"Rendered type: {type(rendered)}")
            if hasattr(rendered, 'shape'):
                console.print(f"Rendered shape: {rendered.shape}")
                console.print(f"Rendered columns: {list(rendered.columns)}")

                # Check if rendered version has empty columns
                for col in rendered.columns:
                    if col not in ['concept', 'label', 'level', 'abstract', 'dimension']:
                        non_empty = rendered[col].notna().sum()
                        empty_values = rendered[col].isna().sum()
                        console.print(f"  {col}: {non_empty} non-empty, {empty_values} empty")

                # Show sample of rendered data
                console.print("\n[bold]Rendered data sample:[/bold]")
                print(rendered.head(10))

        except Exception as e:
            console.print(f"[red]Render failed: {str(e)}[/red]")

        # Test to_dataframe method
        console.print("\n[bold]Testing to_dataframe() method:[/bold]")
        try:
            df = cashflow_stmt.to_dataframe()
            console.print(f"DataFrame shape: {df.shape}")
            console.print(f"DataFrame columns: {list(df.columns)}")

            # Check specific data columns for emptiness
            for col in df.columns:
                if col not in ['concept', 'label', 'level', 'abstract', 'dimension']:
                    non_empty = df[col].notna().sum()
                    empty_values = df[col].isna().sum()
                    console.print(f"  {col}: {non_empty} non-empty, {empty_values} empty")

        except Exception as e:
            console.print(f"[red]to_dataframe failed: {str(e)}[/red]")

        return {
            'filing': filing,
            'cashflow_stmt': cashflow_stmt,
            'success': True
        }

    except Exception as e:
        console.print(f"[red]ERROR: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'success': False
        }

def main():
    """Main detailed investigation"""

    console.print("[bold green]Detailed Cash Flow Statement Investigation - Issue #408[/bold green]")

    # Test the specific problematic case mentioned by user in original issue
    test_cases = [
        {
            'accession': '0000320193-18-000070',
            'description': 'Apple 2018 Q1 - User reported as empty'
        },
        {
            'accession': '0000320193-25-000073',
            'description': 'Recent Apple Q2 2025 - Should work (baseline)'
        }
    ]

    for case in test_cases:
        investigate_cashflow_display(case['accession'], case['description'])

if __name__ == "__main__":
    main()