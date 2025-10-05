"""
Issue #452: Analyze the actual statement rendering to understand the discrepancy

We know:
- XBRL has $1.686B as revenue for FY 2023
- EdgarTools income_statement() shows $1.530B for FY 2023
- The value $1.530B doesn't appear in the revenue facts for that period

This suggests the issue is in how the statement is being rendered or which facts are being selected.
"""

from edgar import Company
from rich import print as rprint
from rich.table import Table
from rich.console import Console
import pandas as pd

console = Console()

company = Company("DNUT")
latest_10k = company.get_filings(form="10-K").latest(1)

rprint(f"[bold]Investigating Filing: {latest_10k.accession_no}[/bold]\n")

xbrl = latest_10k.xbrl()

# Get the statement directly from XBRL
rprint("[bold blue]Step 1: Get Statement from XBRL[/bold blue]")

try:
    # Get the income statement statement object
    from edgar.xbrl.statements import Statement

    # Find the income statement
    income_stmt = None
    for role, stmt_data in xbrl.get_all_statements().items():
        if 'income' in role.lower() or 'operations' in role.lower():
            rprint(f"\nFound statement role: {role}")
            try:
                income_stmt = Statement(xbrl, role, canonical_type="IncomeStatement")
                break
            except Exception as e:
                rprint(f"  Error creating statement: {e}")
                continue

    if income_stmt:
        rprint("\n[green]Successfully created income statement[/green]")

        # Get the dataframe
        stmt_df = income_stmt.to_dataframe()

        rprint(f"\nStatement columns: {list(stmt_df.columns)}")
        rprint(f"Statement shape: {stmt_df.shape}")

        # Find revenue rows
        rprint("\n[yellow]Revenue-related rows:[/yellow]")
        revenue_rows = stmt_df[stmt_df['label'].str.contains('revenue', case=False, na=False)]

        for idx, row in revenue_rows.iterrows():
            rprint(f"\n  Concept: {idx}")
            rprint(f"  Label: {row['label']}")

            # Show all period values
            for col in stmt_df.columns:
                if col not in ['label', 'depth', 'is_abstract', 'is_total', 'section', 'confidence']:
                    val = row[col]
                    if pd.notna(val) and val != '':
                        try:
                            val_float = float(val)
                            if val_float > 1e6:  # Only show significant values
                                rprint(f"    {col}: ${val_float:,.0f} ({val_float/1e9:.3f}B)")
                        except (ValueError, TypeError):
                            pass

except Exception as e:
    rprint(f"[red]Error getting statement: {e}[/red]")
    import traceback
    traceback.print_exc()

# Step 2: Check what revenue concept is being used in the statement
rprint("\n[bold blue]Step 2: Check All Revenue Concepts in XBRL[/bold blue]")

# Get all facts and filter for anything with "revenue" in the concept name
all_facts = xbrl.facts.query().to_dataframe()

revenue_concepts = all_facts[all_facts['concept'].str.contains('revenue', case=False, na=False)]['concept'].unique()

rprint(f"\n[yellow]Found {len(revenue_concepts)} revenue-related concepts:[/yellow]")
for concept in sorted(revenue_concepts)[:20]:  # Show first 20
    rprint(f"  {concept}")

# Step 3: Check for the specific period and see what revenue is reported
rprint("\n[bold blue]Step 3: Check FY 2023 Revenue by Different Concepts[/bold blue]")

target_period = "duration_2023-01-02_2023-12-31"

# Try different revenue concepts
revenue_concept_candidates = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]

for concept in revenue_concept_candidates:
    facts = xbrl.facts.query().by_concept(concept).by_period_key(target_period).to_dataframe()

    if not facts.empty:
        # Get unique values (filtering out segments)
        # The non-segmented value usually has no dimensions
        facts_df = facts.copy()

        rprint(f"\n[yellow]{concept}:[/yellow]")
        rprint(f"  Found {len(facts)} facts")

        # Show unique values
        unique_vals = facts_df['value'].apply(lambda x: float(x) if pd.notna(x) and x != '' else 0).unique()
        for val in sorted(unique_vals, reverse=True):
            if val > 1e9:  # Only show values over 1B
                count = len(facts_df[facts_df['value'].apply(lambda x: float(x) if pd.notna(x) and x != '' else 0) == val])
                rprint(f"    ${val:,.0f} ({val/1e9:.3f}B) - {count} facts")

# Step 4: Look at the raw XBRL to see if $1.530B appears anywhere
rprint("\n[bold blue]Step 4: Search for $1,529,898,000 in All Facts[/bold blue]")

all_facts_df = xbrl.facts.query().to_dataframe()

# Search for the value 1529898000
matching_facts = all_facts_df[all_facts_df['value'].apply(lambda x: abs(float(x) - 1529898000) < 1000 if pd.notna(x) and x != '' else False)]

if not matching_facts.empty:
    rprint(f"\n[yellow]Found {len(matching_facts)} facts with value ~$1,529,898,000:[/yellow]")

    for idx, fact in matching_facts.iterrows():
        rprint(f"\n  Concept: {fact['concept']}")
        rprint(f"  Label: {fact.get('label', 'N/A')}")
        rprint(f"  Period: {fact.get('period_start', 'N/A')} to {fact.get('period_end', 'N/A')}")
        rprint(f"  Value: ${float(fact['value']):,.0f}")
else:
    rprint("\n[red]No facts found with value $1,529,898,000![/red]")
    rprint("[yellow]This suggests the value is calculated or aggregated from segments.[/yellow]")
