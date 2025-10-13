"""
Issue #408: Final Root Cause Analysis and Solution
Cash flow statement missing values - empty string vs null value issue

ROOT CAUSE IDENTIFIED:
- Some older filings have periods with empty strings ('') instead of null values
- These empty strings are counted as "data" in non-null checks, but display as empty
- The XBRL parsing includes periods that have no actual financial data

SOLUTION NEEDED:
- Filter out periods where all values are empty strings or whitespace
- Improve period selection logic to exclude periods with no meaningful data
"""

from edgar import set_identity, get_by_accession_number
from rich.console import Console
from rich.table import Table
import pandas as pd

console = Console()

def analyze_empty_string_issue(accession_number: str, description: str = ""):
    """Deep analysis of empty string vs null value issue"""

    console.print(f"\n[bold blue]Empty String Analysis: {description}[/bold blue]")
    console.print(f"Accession: {accession_number}")

    try:
        filing = get_by_accession_number(accession_number)
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        df = cashflow_stmt.to_dataframe()

        data_cols = [col for col in df.columns
                    if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

        console.print(f"Data columns: {data_cols}")

        # Analyze each column for empty strings vs actual data
        analysis = {}

        for col in data_cols:
            series = df[col]

            # Count different types of "empty"
            null_count = series.isnull().sum()
            empty_string_count = (series == '').sum()
            whitespace_count = series.astype(str).str.strip().eq('').sum() - empty_string_count

            # Count numeric values (actual financial data)
            numeric_values = pd.to_numeric(series, errors='coerce').notna().sum()

            # Total meaningful data
            meaningful_data = numeric_values

            analysis[col] = {
                'null_count': null_count,
                'empty_string_count': empty_string_count,
                'whitespace_count': whitespace_count,
                'numeric_values': numeric_values,
                'meaningful_data': meaningful_data,
                'total_rows': len(series),
                'is_meaningful': meaningful_data > 0
            }

        # Create analysis table
        table = Table(title="Empty String vs Null Analysis")
        table.add_column("Period", style="cyan")
        table.add_column("Null Values", style="blue")
        table.add_column("Empty Strings", style="yellow")
        table.add_column("Numeric Values", style="green")
        table.add_column("Meaningful Data", style="magenta")
        table.add_column("Should Include", style="bold")

        for col, stats in analysis.items():
            should_include = "✅ YES" if stats['is_meaningful'] else "❌ NO"

            table.add_row(
                col,
                str(stats['null_count']),
                str(stats['empty_string_count']),
                str(stats['numeric_values']),
                str(stats['meaningful_data']),
                should_include
            )

        console.print(table)

        # Show the impact of filtering
        meaningful_columns = [col for col, stats in analysis.items()
                            if stats['is_meaningful']]

        console.print(f"\n[bold]Impact Analysis:[/bold]")
        console.print(f"Total periods found: {len(data_cols)}")
        console.print(f"Periods with meaningful data: {len(meaningful_columns)}")
        console.print(f"Empty periods to filter: {len(data_cols) - len(meaningful_columns)}")

        if len(meaningful_columns) < len(data_cols):
            console.print(f"[red]Columns that should be filtered out: {[col for col in data_cols if col not in meaningful_columns]}[/red]")
        else:
            console.print(f"[green]All periods have meaningful data[/green]")

        return {
            'analysis': analysis,
            'meaningful_columns': meaningful_columns,
            'should_filter': len(meaningful_columns) < len(data_cols),
            'total_periods': len(data_cols),
            'meaningful_periods': len(meaningful_columns),
            'success': True
        }

    except Exception as e:
        console.print(f"[red]ERROR: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'success': False}

def propose_solution():
    """Propose solution for the empty string issue"""

    console.print("\n[bold green]PROPOSED SOLUTION[/bold green]")

    console.print("""
[bold]Root Cause:[/bold]
- XBRL parsing includes periods that contain only empty strings ('')
- These empty strings pass .notna() checks but contain no financial data
- User sees empty columns in the rendered cash flow statement

[bold]Solution Strategy:[/bold]
1. Modify period filtering logic to check for meaningful data, not just non-null
2. Filter out periods where all values are empty strings or whitespace
3. Only include periods that have actual numeric financial data

[bold]Implementation Areas:[/bold]
- XBRL statement rendering logic
- Period selection in cash flow statement processing
- Add validation for empty string detection

[bold]Benefits:[/bold]
- Users will only see periods with actual financial data
- Eliminates confusing empty columns in older filings
- Maintains backward compatibility for filings with proper data
    """)

def main():
    """Main analysis comparing working vs problematic filings"""

    console.print("[bold green]Final Root Cause Analysis - Issue #408[/bold green]")

    test_cases = [
        {
            'accession': '0000320193-25-000073',
            'description': 'Recent Apple Q2 2025 - Working baseline'
        },
        {
            'accession': '0000320193-18-000070',
            'description': 'Apple Q1 2018 - Problematic with empty columns'
        },
        {
            'accession': '0000320193-17-000009',
            'description': 'Apple Q3 2017 - Also problematic'
        }
    ]

    results = []
    for case in test_cases:
        result = analyze_empty_string_issue(case['accession'], case['description'])
        result.update(case)
        results.append(result)

    # Summary comparison
    console.print("\n[bold green]FINAL COMPARISON[/bold green]")

    summary_table = Table(title="Root Cause Summary")
    summary_table.add_column("Filing", style="cyan")
    summary_table.add_column("Total Periods", style="blue")
    summary_table.add_column("Meaningful Periods", style="green")
    summary_table.add_column("Empty Periods", style="red")
    summary_table.add_column("Needs Filtering", style="magenta")

    for result in results:
        if result.get('success', False):
            desc = result.get('description', 'Unknown')
            total = result.get('total_periods', 0)
            meaningful = result.get('meaningful_periods', 0)
            empty = total - meaningful
            needs_filter = "YES" if result.get('should_filter', False) else "NO"

            summary_table.add_row(
                desc,
                str(total),
                str(meaningful),
                str(empty),
                needs_filter
            )

    console.print(summary_table)

    propose_solution()

    return results

if __name__ == "__main__":
    main()