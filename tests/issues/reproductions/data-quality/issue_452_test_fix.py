"""
Test the fix for issue #452
"""

from edgar import Company
from rich import print as rprint
import pandas as pd

company = Company("DNUT")

rprint("\n[bold]Testing Fixed DNUT Income Statement[/bold]\n")

# Clear any caches
import os
cache_dir = os.path.expanduser("~/.edgar/company_facts")
dnut_cache = os.path.join(cache_dir, "CIK0001857154.json")
if os.path.exists(dnut_cache):
    rprint(f"[yellow]Removing cache: {dnut_cache}[/yellow]")
    os.remove(dnut_cache)

# Get fresh data
income_stmt = company.income_statement(periods=5, annual=True)
income_df = income_stmt.to_dataframe()

rprint("[yellow]Income Statement Columns:[/yellow]")
rprint(income_df.columns.tolist())

# Get revenue row
revenue_row = income_df[income_df['label'].str.contains('Total Revenue', case=False, na=False)]

if not revenue_row.empty:
    rprint("\n[yellow]Revenue by Fiscal Year:[/yellow]")
    for col in income_df.columns:
        if col.startswith('FY'):
            val = revenue_row[col].values[0]
            if pd.notna(val):
                val_float = float(val)
                rprint(f"{col}: ${val_float:,.0f} ({val_float/1e9:.3f}B)")

                # Check expected values
                if col == "FY 2023":
                    if abs(val_float - 1686104000) < 1000000:
                        rprint("  [green]✓ CORRECT - Shows $1.686B for FY 2023![/green]")
                    elif abs(val_float - 1529898000) < 1000000:
                        rprint("  [red]✗ STILL WRONG - Shows $1.530B (FY 2022 value)[/red]")
                    else:
                        rprint(f"  [yellow]? Unexpected value[/yellow]")

                if col == "FY 2022":
                    if abs(val_float - 1529898000) < 1000000:
                        rprint("  [green]✓ Correct - This should be FY 2022's value[/green]")
