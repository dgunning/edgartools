"""
Debug the period_info dict to see what fiscal_year values are available
"""

from edgar import Company
from edgar.entity.enhanced_statement import EnhancedStatementBuilder
from rich import print as rprint

company = Company("DNUT")
facts = company.facts

rprint("\n[bold]Debugging DNUT Period Info[/bold]\n")

# Get the raw facts
from collections import defaultdict
from datetime import date

stmt_facts = [f for f in facts._facts if f.statement_type == "IncomeStatement"]

# Replicate the period_info building logic
period_info = {}
period_facts = defaultdict(list)

for fact in stmt_facts:
    period_key = (fact.fiscal_year, fact.fiscal_period, fact.period_end)
    period_label = f"{fact.fiscal_period} {fact.fiscal_year}"

    if period_key not in period_info:
        period_info[period_key] = {
            'label': period_label,
            'end_date': fact.period_end or date.max,
            'is_annual': fact.fiscal_period == 'FY',
            'filing_date': fact.filing_date or date.min,
            'fiscal_year': fact.fiscal_year,
            'fiscal_period': fact.fiscal_period
        }

    period_facts[period_key].append(fact)

# Show annual periods
rprint("[yellow]Annual Periods (FY) with their info:[/yellow]\n")
annual_periods = [(pk, info) for pk, info in period_info.items() if info['is_annual']]

# Sort by end_date
annual_periods.sort(key=lambda x: x[1]['end_date'], reverse=True)

for pk, info in annual_periods[:10]:
    fiscal_year_in_key, fiscal_period, period_end = pk

    rprint(f"Period Key: fiscal_year={fiscal_year_in_key}, fiscal_period={fiscal_period}, period_end={period_end}")
    rprint(f"  Info dict fiscal_year: {info['fiscal_year']}")
    rprint(f"  Period end date: {info['end_date']}")
    rprint(f"  Label: {info['label']}")

    # What would our fix generate?
    if info.get('fiscal_year'):
        generated_label = f"FY {info['fiscal_year']}"
    else:
        if period_end and period_end.month == 1 and period_end.day <= 7:
            generated_label = f"FY {period_end.year - 1}"
        else:
            generated_label = f"FY {period_end.year if period_end else 'N/A'}"

    rprint(f"  Generated label: {generated_label}")

    # Find a revenue fact for this period
    revenue_facts = [f for f in period_facts[pk] if 'Revenue' in f.concept and f.concept.endswith('ExcludingAssessedTax')]
    if revenue_facts:
        # Get the max (likely total)
        max_revenue = max(revenue_facts, key=lambda f: f.numeric_value or 0)
        rprint(f"  Revenue: ${max_revenue.numeric_value:,.0f}")

    rprint()
