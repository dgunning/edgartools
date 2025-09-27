"""
Issue #408: Period analysis for cash flow statements
Understanding why empty periods are being displayed
"""

from edgar import set_identity, get_by_accession_number
from rich.console import Console
from rich.table import Table

console = Console()

def analyze_periods_and_data(accession_number: str, description: str = ""):
    """Analyze available periods and their data content"""

    console.print(f"\n[bold blue]Period Analysis: {description}[/bold blue]")
    console.print(f"Accession: {accession_number}")

    try:
        filing = get_by_accession_number(accession_number)
        console.print(f"Filing: {filing.form} - {filing.company} - {filing.filing_date}")

        # Get cash flow statement
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()

        # Get raw dataframe to examine all periods
        df = cashflow_stmt.to_dataframe()

        console.print(f"DataFrame shape: {df.shape}")
        console.print(f"All columns: {list(df.columns)}")

        # Analyze each data column (not metadata columns)
        data_columns = [col for col in df.columns
                       if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

        console.print(f"\n[bold]Data Column Analysis:[/bold]")

        table = Table(title="Period Data Analysis")
        table.add_column("Period", style="cyan")
        table.add_column("Non-Empty Values", style="green")
        table.add_column("Empty Values", style="red")
        table.add_column("Percentage Empty", style="yellow")
        table.add_column("Status", style="magenta")

        for col in data_columns:
            non_empty = df[col].notna().sum()
            empty = df[col].isna().sum()
            pct_empty = (empty / len(df)) * 100

            if pct_empty == 100:
                status = "🚫 COMPLETELY EMPTY"
            elif pct_empty > 80:
                status = "⚠️ MOSTLY EMPTY"
            elif pct_empty > 50:
                status = "🔶 HALF EMPTY"
            else:
                status = "✅ HAS DATA"

            table.add_row(
                col,
                str(non_empty),
                str(empty),
                f"{pct_empty:.1f}%",
                status
            )

        console.print(table)

        # Show specific examples of empty vs filled cells
        console.print(f"\n[bold]Sample Data for Analysis:[/bold]")

        # Show first few rows focusing on data columns only
        sample_data = df[['label'] + data_columns].head(10)
        print(sample_data)

        # Count empty periods
        empty_periods = [col for col in data_columns
                        if df[col].isna().sum() == len(df)]

        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"Total periods: {len(data_columns)}")
        console.print(f"Periods with data: {len(data_columns) - len(empty_periods)}")
        console.print(f"Empty periods: {len(empty_periods)}")

        if empty_periods:
            console.print(f"[red]Empty periods: {empty_periods}[/red]")

        return {
            'total_periods': len(data_columns),
            'empty_periods': len(empty_periods),
            'empty_period_names': empty_periods,
            'data_columns': data_columns,
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
    """Compare period structures between working and problematic filings"""

    console.print("[bold green]Cash Flow Period Analysis - Issue #408[/bold green]")

    test_cases = [
        {
            'accession': '0000320193-25-000073',
            'description': 'Recent Apple Q2 2025 - Working (baseline)'
        },
        {
            'accession': '0000320193-18-000070',
            'description': 'Apple Q1 2018 - User reported empty columns'
        },
        {
            'accession': '0000320193-17-000009',
            'description': 'Apple Q3 2017 - User reported problematic'
        }
    ]

    results = []
    for case in test_cases:
        result = analyze_periods_and_data(case['accession'], case['description'])
        result.update(case)
        results.append(result)

    # Summary comparison
    console.print("\n[bold green]COMPARATIVE ANALYSIS[/bold green]")

    summary_table = Table(title="Filing Comparison")
    summary_table.add_column("Filing", style="cyan")
    summary_table.add_column("Total Periods", style="blue")
    summary_table.add_column("Empty Periods", style="red")
    summary_table.add_column("Data Periods", style="green")
    summary_table.add_column("Issue Status", style="magenta")

    for result in results:
        if result.get('success', False):
            desc = result.get('description', 'Unknown')
            total = result.get('total_periods', 0)
            empty = result.get('empty_periods', 0)
            data = total - empty

            if empty > 0:
                status = f"❌ HAS {empty} EMPTY PERIODS"
            else:
                status = "✅ ALL PERIODS HAVE DATA"

            summary_table.add_row(
                desc,
                str(total),
                str(empty),
                str(data),
                status
            )

    console.print(summary_table)

    return results

if __name__ == "__main__":
    set_identity("Research Team research@edgartools-investigation.com")
    main()