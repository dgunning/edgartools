#!/usr/bin/env python3
"""
Test file to verify SG&A standardization fix.

This tests whether the hierarchical SG&A mapping is working correctly:
- us-gaap_SellingGeneralAndAdministrativeExpense -> "Selling, General and Administrative Expense" 
- us-gaap_GeneralAndAdministrativeExpense -> "General and Administrative Expense"
- us-gaap_SellingAndMarketingExpense -> "Selling Expense"

Expected result: Each concept should get its own distinct label.
"""

from edgar import *
from rich import print
from rich.table import Table
from rich.console import Console

def test_msft_sga_standardization():
    """Test Microsoft SG&A standardization."""
    print("[bold blue]Testing Microsoft SG&A Standardization[/bold blue]\n")
    
    # Load Microsoft 10-K
    f = Filing(
        company='MICROSOFT CORP',
        cik=789019,
        form='10-K',
        filing_date='2024-07-30',
        accession_no='0000950170-24-087843'
    )
    
    xb = f.xbrl()
    
    # Get the rendered income statement 
    inc = xb.statements.income_statement()
    inc_rendered = inc.render()
    
    print("[bold]Rendered Income Statement (showing SG&A lines):[/bold]")
    print(inc_rendered)
    print()
    
    # Query for selling-related concepts
    print("[bold]Selling-related concepts:[/bold]")
    selling_query = xb.query().by_text("Selling").to_dataframe('concept', 'label', 'value', 'statement_type')
    
    table = Table(title="Selling Concepts")
    table.add_column("Concept", style="cyan")
    table.add_column("Label", style="green") 
    table.add_column("Value", style="yellow")
    
    for _, row in selling_query.iterrows():
        if row['statement_type'] == 'IncomeStatement':
            table.add_row(row['concept'], row['label'], str(row['value']))
    
    console = Console()
    console.print(table)
    print()
    
    # Query for the specific G&A value
    print("[bold]General and Administrative concept:[/bold]")
    ga_query = xb.query().by_value(lambda v: v == -7_609_000_000).to_dataframe('concept', 'label', 'value', 'statement_type')
    
    table2 = Table(title="G&A Concept")
    table2.add_column("Concept", style="cyan")
    table2.add_column("Label", style="green")
    table2.add_column("Value", style="yellow")
    
    for _, row in ga_query.iterrows():
        if row['statement_type'] == 'IncomeStatement':
            table2.add_row(row['concept'], row['label'], str(row['value']))
    
    console.print(table2)
    print()
    
    # Check if standardization is working correctly
    print("[bold]Standardization Check:[/bold]")
    
    # Expected mappings based on our concept_mappings.json
    expected_mappings = {
        'us-gaap:SellingAndMarketingExpense': 'Selling Expense',
        'us-gaap:GeneralAndAdministrativeExpense': 'General and Administrative Expense',
        'us-gaap:SellingGeneralAndAdministrativeExpense': 'Selling, General and Administrative Expense'
    }
    
    # Check what we actually got
    all_concepts = {}
    for _, row in selling_query.iterrows():
        if row['statement_type'] == 'IncomeStatement':
            all_concepts[row['concept']] = row['label']
    
    for _, row in ga_query.iterrows():
        if row['statement_type'] == 'IncomeStatement':
            all_concepts[row['concept']] = row['label']
    
    print(f"Found {len(all_concepts)} SG&A-related concepts:")
    for concept, actual_label in all_concepts.items():
        expected_label = expected_mappings.get(concept, "NOT MAPPED")
        status = "✅ CORRECT" if actual_label == expected_label else "❌ INCORRECT"
        print(f"  {concept}")
        print(f"    Expected: {expected_label}")
        print(f"    Actual:   {actual_label}")
        print(f"    Status:   {status}")
        print()

def test_standardization_mappings():
    """Test that our standardization mappings are loaded correctly."""
    print("[bold blue]Testing Standardization Mappings[/bold blue]\n")
    
    from edgar.xbrl.standardization.core import initialize_default_mappings
    
    # Initialize the mapping store
    store = initialize_default_mappings(read_only=True)
    
    # Check key SG&A mappings
    sga_concepts = [
        'us-gaap_SellingGeneralAndAdministrativeExpense',
        'us-gaap_GeneralAndAdministrativeExpense', 
        'us-gaap_SellingAndMarketingExpense'
    ]
    
    print("[bold]SG&A Mapping Check:[/bold]")
    for concept in sga_concepts:
        # Test both underscore and colon formats
        underscore_result = store.get_standard_concept(concept)
        colon_concept = concept.replace('_', ':')
        colon_result = store.get_standard_concept(colon_concept)
        
        print(f"Concept: {concept}")
        print(f"  Underscore format result: {underscore_result}")
        print(f"  Colon format result: {colon_result}")
        print()

if __name__ == '__main__':
    test_msft_sga_standardization()
    print("\n" + "="*80 + "\n")
    test_standardization_mappings()