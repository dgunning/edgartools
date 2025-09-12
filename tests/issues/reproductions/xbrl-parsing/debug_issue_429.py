#!/usr/bin/env python3
"""
Debug script for GitHub issue #429 - deeper investigation
"""

import edgar
from rich.console import Console
from rich.table import Table

console = Console()

def debug_period_detection():
    """Debug the current period detection and fact filtering"""
    console.print(f"\n[bold blue]Deep debugging AAPL XBRL structure[/bold blue]")
    
    # Get AAPL data
    aapl = edgar.Company("AAPL")
    filing = aapl.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()
    
    console.print(f"Filing: {filing.accession_no} ({filing.filing_date})")
    console.print(f"Entity: {getattr(xbrl, 'entity_name', 'Unknown')}")
    
    # Debug reporting periods
    console.print(f"\n[bold green]Reporting periods:[/bold green]")
    if hasattr(xbrl, 'reporting_periods'):
        for i, period in enumerate(xbrl.reporting_periods):
            console.print(f"  {i}: {period}")
    else:
        console.print("  No reporting_periods attribute found")
    
    # Check current period detection
    current = xbrl.current_period
    console.print(f"\n[bold green]Current period detection:[/bold green]")
    console.print(f"  Period key: {current.period_key}")
    console.print(f"  Period label: {current.period_label}")
    
    # Debug statement finding
    console.print(f"\n[bold green]Statement availability:[/bold green]")
    statement_types = ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement']
    
    for stmt_type in statement_types:
        console.print(f"\n--- {stmt_type} ---")
        
        # Try to find the statement
        try:
            matching_statements, found_role, actual_type = xbrl.find_statement(stmt_type)
            console.print(f"  Found role: {found_role}")
            console.print(f"  Actual type: {actual_type}")
            console.print(f"  Matching statements: {len(matching_statements) if matching_statements else 0}")
            
            if matching_statements:
                for stmt in matching_statements[:2]:  # Show first 2
                    console.print(f"    - {stmt.get('definition', 'No definition')}")
            
        except Exception as e:
            console.print(f"  Error finding statement: {e}")
        
        # Try to get raw statement data without period filter
        try:
            raw_data = xbrl.get_statement(stmt_type)
            console.print(f"  Raw data items (no period filter): {len(raw_data)}")
        except Exception as e:
            console.print(f"  Error getting raw data: {e}")
        
        # Try to get with period filter
        try:
            filtered_data = xbrl.get_statement(stmt_type, period_filter=current.period_key)
            console.print(f"  Filtered data items (period={current.period_key}): {len(filtered_data)}")
            
            # Show first few items
            if filtered_data:
                console.print("  First few items:")
                for i, item in enumerate(filtered_data[:3]):
                    values = item.get('values', {})
                    current_value = values.get(current.period_key)
                    console.print(f"    {i}: {item.get('label', 'No label')} = {current_value}")
            
        except Exception as e:
            console.print(f"  Error getting filtered data: {e}")
    
    # Debug the context_period_map
    console.print(f"\n[bold green]Context period mapping:[/bold green]")
    if hasattr(xbrl, 'context_period_map'):
        console.print(f"  Total contexts: {len(xbrl.context_period_map)}")
        
        # Group by period
        from collections import defaultdict
        periods_count = defaultdict(int)
        for context_id, period_key in xbrl.context_period_map.items():
            periods_count[period_key] += 1
        
        console.print("  Periods with context counts:")
        for period_key, count in sorted(periods_count.items()):
            console.print(f"    {period_key}: {count} contexts")
            
        # Check if current period exists in the map
        current_period_contexts = [ctx for ctx, period in xbrl.context_period_map.items() 
                                  if period == current.period_key]
        console.print(f"  Current period contexts: {len(current_period_contexts)}")
        
    else:
        console.print("  No context_period_map attribute found")

def test_fact_finding():
    """Test fact finding for specific elements"""
    console.print(f"\n[bold blue]Testing fact finding for specific elements[/bold blue]")
    
    aapl = edgar.Company("AAPL")
    filing = aapl.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()
    current = xbrl.current_period
    
    # Test some common concepts
    test_concepts = [
        'Assets',
        'us-gaap_Assets',
        'Revenues',
        'us-gaap_Revenues',
        'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax',
        'CashAndCashEquivalentsAtCarryingValue',
        'us-gaap_CashAndCashEquivalentsAtCarryingValue'
    ]
    
    console.print(f"Testing concepts with period filter: {current.period_key}")
    
    for concept in test_concepts:
        console.print(f"\n--- {concept} ---")
        
        try:
            # Test without period filter
            all_facts = xbrl._find_facts_for_element(concept)
            console.print(f"  Without period filter: {len(all_facts)} facts found")
            
            # Test with period filter
            filtered_facts = xbrl._find_facts_for_element(concept, period_filter=current.period_key)
            console.print(f"  With period filter: {len(filtered_facts)} facts found")
            
            if filtered_facts:
                for context_id, wrapped_fact in list(filtered_facts.items())[:2]:
                    fact = wrapped_fact['fact']
                    value = fact.numeric_value if fact.numeric_value is not None else fact.value
                    console.print(f"    Context {context_id}: {value}")
            
        except Exception as e:
            console.print(f"  Error: {e}")

if __name__ == "__main__":
    debug_period_detection()
    test_fact_finding()