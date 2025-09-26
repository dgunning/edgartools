#!/usr/bin/env python3

"""
Investigation script for GitHub issue #449: Support of units and point_in_time flag

This script investigates how unit and context information is currently stored
in EdgarTools XBRL data structures to determine the best way to expose:
- unit information (usd, shares, usdPerShare, etc.)
- point_in_time flag for instant vs accumulated metrics

GitHub issue: https://github.com/dgunning/edgartools/issues/449
"""

import pandas as pd
from edgar import Filing
from edgar.xbrl import XBRL
from rich import print

pd.options.display.max_columns = None
pd.options.display.width = None


def investigate_apple_10k():
    """Investigate Apple's 10-K to understand unit and context structure."""
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01',
                   accession_no='0000320193-24-000123')
    xbrl = filing.xbrl()

    print("=== APPLE 10-K XBRL INVESTIGATION ===")
    print(f"Entity: {xbrl.entity_name}")
    print(f"Period: {xbrl.period_of_report}")
    print(f"Total facts: {len(xbrl._facts)}")
    print(f"Total contexts: {len(xbrl.contexts)}")
    print(f"Total units: {len(xbrl.units)}")
    print()

    # 1. Examine units structure
    print("=== UNIT INFORMATION ===")
    print("Available units:")
    for unit_id, unit in list(xbrl.units.items())[:5]:
        print(f"  {unit_id}: {unit}")
        if hasattr(unit, '__dict__'):
            print(f"    Attributes: {vars(unit)}")
    print()

    # 2. Examine context structure
    print("=== CONTEXT INFORMATION ===")
    print("Sample contexts:")
    for context_id, context in list(xbrl.contexts.items())[:3]:
        print(f"  {context_id}: {context}")
        if hasattr(context, '__dict__'):
            print(f"    Attributes: {vars(context)}")
        if hasattr(context, 'period'):
            print(f"    Period type: {getattr(context.period, 'type', None)}")
            if hasattr(context.period, 'instant'):
                print(f"    Period instant: {context.period.instant}")
            if hasattr(context.period, 'startDate'):
                print(f"    Period start: {context.period.startDate}")
            if hasattr(context.period, 'endDate'):
                print(f"    Period end: {context.period.endDate}")
        print()

    # 3. Examine facts structure with unit/context info
    print("=== FACT STRUCTURE ===")
    facts = xbrl.facts.get_facts()
    sample_facts = facts[:5]

    print("Sample fact fields:")
    for i, fact in enumerate(sample_facts):
        print(f"Fact {i+1}: {fact.get('concept', 'NO_CONCEPT')}")
        print(f"  Available keys: {list(fact.keys())}")
        print(f"  unit_ref: {fact.get('unit_ref', 'NO_UNIT')}")
        print(f"  period_type: {fact.get('period_type', 'NO_PERIOD_TYPE')}")
        print(f"  period_instant: {fact.get('period_instant', 'NO_INSTANT')}")
        print(f"  period_start: {fact.get('period_start', 'NO_START')}")
        print(f"  period_end: {fact.get('period_end', 'NO_END')}")
        print(f"  value: {fact.get('value', 'NO_VALUE')}")
        print()

    # 4. Focus on different types of facts (monetary, shares, per-share)
    print("=== FACT TYPE ANALYSIS ===")

    # Revenue facts (monetary)
    revenue_facts = xbrl.facts.query().by_concept('Revenue').to_dataframe()
    if not revenue_facts.empty:
        print("Revenue facts:")
        print(revenue_facts[['concept', 'unit_ref', 'period_type', 'value', 'period_end']].head())
        print()

    # Shares outstanding (shares)
    shares_facts = xbrl.facts.query().by_concept('SharesOutstanding').to_dataframe()
    if not shares_facts.empty:
        print("Shares Outstanding facts:")
        print(shares_facts[['concept', 'unit_ref', 'period_type', 'value', 'period_end']].head())
        print()

    # EPS facts (per-share)
    eps_facts = xbrl.facts.query().by_concept('EarningsPerShare').to_dataframe()
    if not eps_facts.empty:
        print("EPS facts:")
        print(eps_facts[['concept', 'unit_ref', 'period_type', 'value', 'period_end']].head())
        print()

    # 5. Check statement data structure
    print("=== STATEMENT DATAFRAME ANALYSIS ===")
    income_statement = xbrl.statements.income_statement()
    if income_statement:
        df = income_statement.to_dataframe()
        print("Income statement DataFrame columns:")
        print(list(df.columns))
        print()
        print("Sample rows:")
        print(df[['concept', 'label'] + [col for col in df.columns if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]].head())
        print()

    return xbrl


def examine_unit_mapping():
    """Examine how units map to human-readable names."""
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01',
                   accession_no='0000320193-24-000123')
    xbrl = filing.xbrl()

    print("=== UNIT MAPPING ANALYSIS ===")

    # Get all unique unit references used in facts
    all_facts = xbrl.facts.get_facts()
    unique_units = set()
    unit_fact_counts = {}

    for fact in all_facts:
        unit_ref = fact.get('unit_ref')
        if unit_ref:
            unique_units.add(unit_ref)
            unit_fact_counts[unit_ref] = unit_fact_counts.get(unit_ref, 0) + 1

    print(f"Total unique units referenced: {len(unique_units)}")
    print("Unit usage counts:")
    for unit_ref, count in sorted(unit_fact_counts.items(), key=lambda x: x[1], reverse=True):
        if unit_ref in xbrl.units:
            unit_obj = xbrl.units[unit_ref]
            print(f"  {unit_ref}: {count} facts, unit object: {unit_obj}")
        else:
            print(f"  {unit_ref}: {count} facts, unit object: NOT_FOUND")
    print()


def analyze_period_context_distinction():
    """Analyze how to distinguish point-in-time vs accumulated metrics."""
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01',
                   accession_no='0000320193-24-000123')
    xbrl = filing.xbrl()

    print("=== POINT-IN-TIME ANALYSIS ===")

    # Get balance sheet (instant) vs income statement (duration) facts
    balance_sheet_facts = xbrl.facts.query().by_statement_type('BalanceSheet').to_dataframe()
    income_facts = xbrl.facts.query().by_statement_type('IncomeStatement').to_dataframe()

    print("Balance Sheet facts (should be point-in-time/instant):")
    if not balance_sheet_facts.empty:
        print(balance_sheet_facts['period_type'].value_counts())
        print("Sample balance sheet facts:")
        available_cols = ['concept', 'label', 'period_type']
        if 'period_instant' in balance_sheet_facts.columns:
            available_cols.append('period_instant')
        if 'period_start' in balance_sheet_facts.columns:
            available_cols.append('period_start')
        if 'period_end' in balance_sheet_facts.columns:
            available_cols.append('period_end')
        print(balance_sheet_facts[available_cols].head())
    print()

    print("Income Statement facts (should be accumulated/duration):")
    if not income_facts.empty:
        print(income_facts['period_type'].value_counts())
        print("Sample income statement facts:")
        available_cols = ['concept', 'label', 'period_type']
        if 'period_instant' in income_facts.columns:
            available_cols.append('period_instant')
        if 'period_start' in income_facts.columns:
            available_cols.append('period_start')
        if 'period_end' in income_facts.columns:
            available_cols.append('period_end')
        print(income_facts[available_cols].head())
    print()

    # Show mixed cases - some income statement items might be instant (like shares outstanding)
    income_instant_facts = income_facts[income_facts['period_type'] == 'instant']
    if not income_instant_facts.empty:
        print("Income Statement facts with instant periods (likely shares outstanding, etc.):")
        print(income_instant_facts[['concept', 'label', 'period_type']].head(10))
    print()


if __name__ == "__main__":
    print("Starting XBRL unit and point-in-time investigation...")
    print("=" * 80)

    xbrl = investigate_apple_10k()
    print("\n" + "=" * 80)

    examine_unit_mapping()
    print("=" * 80)

    analyze_period_context_distinction()
    print("=" * 80)

    print("Investigation complete.")