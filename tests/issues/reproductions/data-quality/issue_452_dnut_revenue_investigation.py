"""
Issue #452: DNUT revenue value discrepancy investigation
GitHub Issue: https://github.com/dgunning/edgartools/issues/452
Reporter: staplestack

Issue Summary:
- Company: Krispy Kreme (DNUT)
- Form: 10-K FY2023
- Expected Revenue: $1.686B
- Actual Revenue: $1.530B
- User hypothesis: "Latest 10-K filing has both dec 1 2023 and jan 1 2023"

Investigation Plan:
1. Reproduce the issue
2. Examine the filing's XBRL structure
3. Understand the dual-date period issue
4. Determine why EdgarTools selects the wrong value
"""

from edgar import Company
from rich import print as rprint
from rich.table import Table
from rich.console import Console
import pandas as pd

console = Console()

# Step 1: Reproduce the issue
rprint("\n[bold blue]Step 1: Reproducing the Issue[/bold blue]")
rprint("=" * 80)

company = Company("DNUT")
rprint(f"Company: {company.name}")

# Get income statement
income_stmt = company.income_statement(periods=5, annual=True)
income_df = income_stmt.to_dataframe()

rprint("\n[yellow]Income Statement DataFrame:[/yellow]")
rprint(income_df)

# Look at the most recent period specifically
rprint("\n[yellow]Most Recent Period Revenue:[/yellow]")
revenue_row = income_df[income_df.index.str.contains('RevenueFromContractWithCustomer', case=False, na=False)]
if not revenue_row.empty:
    # Get the first non-label column (should be most recent period)
    recent_period_col = [col for col in income_df.columns if col != 'label'][0]
    recent_revenue = revenue_row[recent_period_col].values[0]
    rprint(f"EdgarTools shows: ${recent_revenue:,.0f} ({recent_revenue/1e9:.3f}B)")
    rprint(f"Expected: $1,686,000,000 (1.686B)")
    rprint(f"Difference: ${abs(recent_revenue - 1686000000):,.0f}")

# Step 2: Get the latest 10-K filing details
rprint("\n[bold blue]Step 2: Examining Latest 10-K Filing[/bold blue]")
rprint("=" * 80)

latest_10k = company.get_filings(form="10-K").latest(1)

if latest_10k:
    rprint(f"Filing Date: {latest_10k.filing_date}")
    rprint(f"Period of Report: {latest_10k.period_of_report}")
    rprint(f"Accession: {latest_10k.accession_no}")

    # Step 3: Examine XBRL data for revenue facts
    rprint("\n[bold blue]Step 3: Examining XBRL Revenue Facts[/bold blue]")
    rprint("=" * 80)

    xbrl = latest_10k.xbrl()

    if xbrl:
        # Get all facts to inspect
        facts = xbrl.facts

        # Look for revenue concept
        revenue_concept = "RevenueFromContractWithCustomerExcludingAssessedTax"

        rprint(f"\n[yellow]Searching for revenue facts with concept: {revenue_concept}[/yellow]")

        # Query for revenue facts
        revenue_facts = facts.query().by_concept(revenue_concept).to_dataframe()

        if not revenue_facts.empty:
            rprint(f"\nFound {len(revenue_facts)} revenue facts")

            # Filter for duration periods (annual data)
            duration_facts = revenue_facts[revenue_facts['period_type'] == 'duration']

            # Create a detailed table of revenue facts
            table = Table(title="Revenue Facts by Period")
            table.add_column("Period Start", style="cyan")
            table.add_column("Period End", style="cyan")
            table.add_column("Value", style="green", justify="right")
            table.add_column("Duration (days)", style="yellow", justify="right")
            table.add_column("Period Type", style="magenta")

            for _, fact in duration_facts.iterrows():
                start = fact.get('period_start', 'N/A')
                end = fact.get('period_end', 'N/A')
                value = fact.get('value', 0)

                # Calculate duration
                if start != 'N/A' and end != 'N/A':
                    from datetime import datetime
                    duration = (pd.to_datetime(end) - pd.to_datetime(start)).days
                else:
                    duration = 0

                # Format value properly
                try:
                    value_str = f"${float(value):,.0f}" if value and value != 'N/A' else "N/A"
                except (ValueError, TypeError):
                    value_str = str(value)

                table.add_row(
                    str(start),
                    str(end),
                    value_str,
                    str(duration),
                    fact.get('period_type', 'N/A')
                )

            console.print(table)

            # Step 4: Identify the dual-date issue
            rprint("\n[bold blue]Step 4: Analyzing Period End Dates[/bold blue]")
            rprint("=" * 80)

            # Look for periods ending in late 2023/early 2024
            recent_periods = duration_facts[
                (pd.to_datetime(duration_facts['period_end']) >= '2023-11-01') &
                (pd.to_datetime(duration_facts['period_end']) <= '2024-02-01')
            ].sort_values('period_end', ascending=False)

            if not recent_periods.empty:
                rprint("\n[yellow]Periods ending around Dec 2023 / Jan 2024:[/yellow]")
                for _, period in recent_periods.iterrows():
                    end_date = period['period_end']
                    value_raw = period['value']
                    start_date = period['period_start']
                    duration = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days

                    try:
                        value = float(value_raw)
                        rprint(f"\nPeriod: {start_date} to {end_date} ({duration} days)")
                        rprint(f"  Revenue: ${value:,.0f} ({value/1e9:.3f}B)")

                        if abs(value - 1686000000) < 1000000:
                            rprint("  [green]✓ This matches expected value (1.686B)![/green]")
                        elif abs(value - 1530000000) < 1000000:
                            rprint("  [red]✗ This is the incorrect value EdgarTools is showing (1.530B)[/red]")
                    except (ValueError, TypeError):
                        rprint(f"\nPeriod: {start_date} to {end_date} ({duration} days)")
                        rprint(f"  Revenue: {value_raw}")

            # Step 5: Check available periods in xbrl
            rprint("\n[bold blue]Step 5: Available Reporting Periods[/bold blue]")
            rprint("=" * 80)

            rprint("\n[yellow]All reporting periods in XBRL:[/yellow]")
            periods = xbrl.reporting_periods
            for period in periods[:10]:  # Show first 10
                rprint(f"  {period.get('label', 'Unknown')}: {period.get('key', 'Unknown')}")

rprint("\n[bold green]Investigation Complete[/bold green]")
rprint("\n[bold yellow]Summary:[/bold yellow]")
rprint("1. EdgarTools returns $1.530B for Total Revenue")
rprint("2. Expected value is $1.686B")
rprint("3. The filing appears to have multiple period end dates in late 2023/early 2024")
rprint("4. This suggests a fiscal year-end change or 52/53-week calendar issue")
