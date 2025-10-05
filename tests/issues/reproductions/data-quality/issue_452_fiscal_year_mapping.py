"""
Issue #452: Check fiscal year mapping

HYPOTHESIS: The fiscal year labels might be misaligned with the actual period dates.

From earlier output:
- FY 2023 shows: $1,529,898,000
- Period 2023-01-02 to 2023-12-31 has: $1,686,104,000 (expected)
- Period 2022-01-03 to 2023-01-01 has: $1,529,898,000 (the value being shown!)

This suggests EdgarTools might be mapping "FY 2023" to the wrong period.
"""

from edgar import Company
from rich import print as rprint
import pandas as pd

company = Company("DNUT")
latest_10k = company.get_filings(form="10-K").latest(1)

rprint(f"[bold]Filing Period: {latest_10k.period_of_report}[/bold]")
rprint(f"[bold]Filing Date: {latest_10k.filing_date}[/bold]\n")

xbrl = latest_10k.xbrl()

# Get all annual revenue periods
rprint("[bold blue]All Annual Revenue Periods in XBRL:[/bold blue]\n")

revenue_facts = xbrl.facts.query().by_concept("RevenueFromContractWithCustomerExcludingAssessedTax").to_dataframe()

# Filter for duration periods >300 days
if not revenue_facts.empty:
    revenue_facts['duration'] = (pd.to_datetime(revenue_facts['period_end']) -
                                pd.to_datetime(revenue_facts['period_start'])).dt.days

    annual_revenue = revenue_facts[revenue_facts['duration'] > 300].copy()

    # Get unique period combinations
    period_groups = annual_revenue.groupby(['period_start', 'period_end']).agg({
        'value': lambda x: sorted([float(v) for v in x if pd.notna(v) and v != ''], reverse=True)
    }).reset_index()

    rprint("[yellow]Period-end to Revenue mapping:[/yellow]\n")

    for _, row in period_groups.iterrows():
        start = row['period_start']
        end = row['period_end']
        values = row['value']

        # Get the maximum value (likely the consolidated total)
        max_val = max(values) if values else 0

        rprint(f"Period: {start} to {end}")
        rprint(f"  Max Revenue: ${max_val:,.0f} ({max_val/1e9:.3f}B)")

        # Identify fiscal year from period end
        end_date = pd.to_datetime(end)
        fiscal_year = end_date.year

        # Check if this is a 52/53 week calendar ending in early January
        if end_date.month == 1 and end_date.day <= 7:
            rprint(f"  [yellow]Period ends in early January {fiscal_year}[/yellow]")
            rprint(f"  [yellow]This is likely fiscal year {fiscal_year - 1} (prior calendar year)[/yellow]")
            fiscal_year_label = f"FY {fiscal_year - 1}"
        else:
            fiscal_year_label = f"FY {fiscal_year}"

        rprint(f"  Fiscal Year: {fiscal_year_label}")

        # Check against what we expect
        if abs(max_val - 1686104000) < 1000:
            rprint("  [green]✓ This is the expected value for FY 2023 (1.686B)![/green]")
        elif abs(max_val - 1529898000) < 1000:
            rprint("  [red]✗ This value ($1.530B) is being shown for FY 2023 but shouldn't be![/red]")

        rprint()

# Now check what the income_statement API returns
rprint("\n[bold blue]What income_statement() Returns:[/bold blue]\n")

income_stmt = company.income_statement(periods=5, annual=True)
income_df = income_stmt.to_dataframe()

# Get revenue row
revenue_row = income_df[income_df['label'].str.contains('Total Revenue', case=False, na=False)]

if not revenue_row.empty:
    rprint("[yellow]Revenue values by fiscal year label:[/yellow]\n")
    for col in income_df.columns:
        if col.startswith('FY'):
            val = revenue_row[col].values[0]
            if pd.notna(val):
                val_float = float(val)
                rprint(f"{col}: ${val_float:,.0f} ({val_float/1e9:.3f}B)")

                if abs(val_float - 1686104000) < 1000:
                    rprint("  [green]✓ Correct value for most recent completed fiscal year[/green]")
                elif abs(val_float - 1529898000) < 1000:
                    rprint("  [red]✗ This is from the PRIOR fiscal year period![/red]")

rprint("\n[bold green]FINDING:[/bold green]")
rprint("EdgarTools appears to be mapping fiscal year labels to the wrong calendar periods.")
rprint("The period ending Jan 1, 2023 is labeled as 'FY 2023' but should be 'FY 2022'.")
rprint("The period ending Dec 31, 2023 is the actual FY 2023 and has the correct $1.686B value.")
