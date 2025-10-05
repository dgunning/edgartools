"""
Issue #452: Debug period selection for DNUT income statement

The issue: Company.income_statement() is returning the wrong revenue value.
We found $1.686B exists in XBRL but EdgarTools is showing something different.

This script debugs the period selection logic to understand which period is being selected.
"""

from edgar import Company
from rich import print as rprint
import pandas as pd

company = Company("DNUT")
latest_10k = company.get_filings(form="10-K").latest(1)

rprint(f"[bold]Filing:[/bold] {latest_10k.filing_date} for period ending {latest_10k.period_of_report}")
rprint(f"[bold]Accession:[/bold] {latest_10k.accession_no}\n")

# Get XBRL
xbrl = latest_10k.xbrl()

# Step 1: Check available reporting periods
rprint("[bold blue]Available Reporting Periods:[/bold blue]")
for i, period in enumerate(xbrl.reporting_periods[:15]):
    rprint(f"{i+1}. {period.get('label', 'Unknown')}: {period.get('key', 'Unknown')}")

# Step 2: Get the income statement using the high-level API
rprint("\n[bold blue]Income Statement from Company API:[/bold blue]")
income_stmt = company.income_statement(periods=5, annual=True)
income_df = income_stmt.to_dataframe()

# Show column names (periods)
rprint(f"\n[yellow]Columns (periods):[/yellow] {list(income_df.columns)}")

# Get revenue value
rprint("\n[yellow]Revenue Row:[/yellow]")
revenue_row = income_df[income_df['label'].str.contains('Total Revenue', case=False, na=False)]
if not revenue_row.empty:
    rprint(revenue_row)
    # Show all period values
    for col in income_df.columns:
        if col != 'label':
            val = revenue_row[col].values[0] if len(revenue_row[col].values) > 0 else None
            if val and pd.notna(val):
                rprint(f"\n{col}: ${float(val):,.0f} ({float(val)/1e9:.3f}B)")

# Step 3: Examine all revenue facts for period ending 2023-12-31
rprint("\n[bold blue]All Revenue Facts for Period 2023-01-02 to 2023-12-31:[/bold blue]")

target_period = "duration_2023-01-02_2023-12-31"
all_revenue = xbrl.facts.query().by_concept("RevenueFromContractWithCustomerExcludingAssessedTax").by_period_key(target_period).to_dataframe()

if not all_revenue.empty:
    rprint(f"\nFound {len(all_revenue)} revenue facts for this period")

    # Group by unique values to see what we have
    unique_values = all_revenue['value'].apply(lambda x: float(x) if pd.notna(x) and x != '' else 0).unique()

    rprint("\n[yellow]Unique revenue values for FY 2023:[/yellow]")
    for val in sorted(unique_values, reverse=True):
        if val > 0:
            count = len(all_revenue[all_revenue['value'].apply(lambda x: float(x) if pd.notna(x) and x != '' else 0) == val])
            rprint(f"  ${val:,.0f} ({val/1e9:.3f}B) - appears {count} times")

            if abs(val - 1686104000) < 1000:
                rprint("    [green]✓ This is the expected value![/green]")
            elif abs(val - 1529898000) < 1000:
                rprint("    [red]✗ This is the incorrect value being shown![/red]")

    # Let's see if there are dimensions/segments involved
    rprint("\n[yellow]Checking for dimensions/segments:[/yellow]")
    if 'dimensions' in all_revenue.columns:
        rprint(f"  Dimensions column exists: {all_revenue['dimensions'].unique()}")
    else:
        rprint("  No dimensions column found")

    # Show some context about these facts
    rprint("\n[yellow]Sample facts (showing value, label, dimensions if any):[/yellow]")
    for idx, row in all_revenue.head(10).iterrows():
        value = float(row['value']) if pd.notna(row['value']) and row['value'] != '' else 0
        if value > 1e9:  # Only show large values
            label = row.get('label', 'N/A')
            dims = row.get('dimensions', 'None')
            rprint(f"  ${value:,.0f} - Label: {label} - Dims: {dims}")

# Step 4: Look specifically at the period ending 2023-12-31
rprint("\n[bold blue]Checking Specific Period: 2023-12-31[/bold blue]")
target_period_key = "duration_2023-01-02_2023-12-31"

target_revenue = xbrl.facts.query().by_concept("RevenueFromContractWithCustomerExcludingAssessedTax").by_period_key(target_period_key).to_dataframe()

if not target_revenue.empty:
    rprint(f"\n[yellow]Found {len(target_revenue)} revenue facts for period {target_period_key}[/yellow]")

    # These might be segmented, let's see all of them
    rprint("\n[yellow]Revenue values for this period:[/yellow]")
    for idx, row in target_revenue.iterrows():
        value = float(row['value']) if pd.notna(row['value']) and row['value'] != '' else 0
        rprint(f"  ${value:,.0f}")

    total = target_revenue['value'].apply(lambda x: float(x) if pd.notna(x) and x != '' else 0).sum()
    rprint(f"\n[bold]Total revenue for 2023-12-31 period: ${total:,.0f} ({total/1e9:.3f}B)[/bold]")
else:
    rprint("[red]No revenue facts found for this period![/red]")
