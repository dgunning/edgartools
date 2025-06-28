#!/usr/bin/env python3
"""
Test the Net Income hierarchy fix.

This verifies that Net Income concepts now get distinct, appropriate labels
instead of all mapping to generic "Net Income".
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def test_net_income_hierarchy_fix():
    """Test that Net Income concepts now have distinct labels."""
    print("[bold green]Net Income Hierarchy Fix Verification[/bold green]\n")
    
    # Reinitialize to pick up changes
    store = initialize_default_mappings(read_only=True)
    
    # Test specific Net Income concepts
    net_income_test_cases = [
        ("us-gaap_NetIncome", "Net Income"),
        ("us-gaap_NetIncomeLoss", "Net Income"),
        ("us-gaap_IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest", "Net Income from Continuing Operations"),
        ("us-gaap_ProfitLoss", "Profit or Loss"),
        # Test that missing concepts don't break
        ("us-gaap_SomeOtherIncome", None)
    ]
    
    table = Table(title="Net Income Concept Mapping After Fix")
    table.add_column("Concept", style="cyan", width=50)
    table.add_column("Expected Label", style="yellow")
    table.add_column("Actual Label", style="green")
    table.add_column("Status", style="red")
    
    all_correct = True
    
    for concept, expected_label in net_income_test_cases:
        actual_label = store.get_standard_concept(concept)
        
        if expected_label is None:
            status = "✅ Correct (Not Mapped)" if actual_label is None else "❌ Unexpected Mapping"
            if actual_label is not None:
                all_correct = False
        else:
            status = "✅ Correct" if actual_label == expected_label else "❌ Incorrect"
            if actual_label != expected_label:
                all_correct = False
        
        table.add_row(
            concept,
            expected_label or "Not Mapped",
            actual_label or "Not Found",
            status
        )
    
    console = Console()
    console.print(table)
    
    if all_correct:
        print("\n[bold green]✅ All Net Income mappings are correct![/bold green]")
    else:
        print("\n[bold red]❌ Some Net Income mappings need attention[/bold red]")
    
    return all_correct

def test_income_hierarchy_separation():
    """Test that we've properly separated the Net Income hierarchy."""
    print("\n[bold blue]Net Income Hierarchy Separation[/bold blue]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Check what concepts map to each income type
    income_categories = [
        "Net Income",
        "Net Income from Continuing Operations",
        "Profit or Loss"
    ]
    
    table = Table(title="Net Income Category Breakdown")
    table.add_column("Category", style="cyan")
    table.add_column("Mapped Concepts", style="green")
    table.add_column("Count", style="yellow")
    
    for category in income_categories:
        concepts = store.get_company_concepts(category)
        concept_list = "\n".join(sorted(concepts)) if concepts else "None"
        count = len(concepts)
        
        table.add_row(category, concept_list, str(count))
    
    console = Console()
    console.print(table)

def simulate_company_impact_net_income():
    """Simulate how this affects company financial statements."""
    print("\n[bold magenta]Impact on Company Financial Statements - Net Income[/bold magenta]\n")
    
    print("Before the fix:")
    print("  Company Income Line 1: 'Net Income' (us-gaap_NetIncome)")
    print("  Company Income Line 2: 'Net Income' (us-gaap_IncomeLossFromContinuing...) ← CONFUSING!")
    print("  Company Income Line 3: 'Net Income' (us-gaap_ProfitLoss) ← MORE CONFUSION!")
    print()
    
    print("After the fix:")
    print("  Company Income Line 1: 'Net Income' (us-gaap_NetIncome)")
    print("  Company Income Line 2: 'Net Income from Continuing Operations' ← CLEAR!")
    print("  Company Income Line 3: 'Profit or Loss' ← DISTINCT!")
    print()
    
    print("This provides better clarity for:")
    print("  ✓ Distinguishing total vs component income")
    print("  ✓ Understanding continuing vs discontinued operations")
    print("  ✓ International vs US accounting standards (Profit/Loss)")
    print("  ✓ Complex corporate structures with subsidiaries")

def check_other_income_categories():
    """Check other income categories that might need similar fixes."""
    print("\n[bold yellow]Other Income Categories Analysis[/bold yellow]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Check Income Before Tax which also had 4+ concepts
    income_before_tax_concepts = store.get_company_concepts("Income Before Tax")
    
    print(f"[bold]Income Before Tax concepts ({len(income_before_tax_concepts)}):[/bold]")
    for concept in sorted(income_before_tax_concepts):
        print(f"  • {concept}")
    
    if len(income_before_tax_concepts) > 2:
        print("\n[bold red]⚠️ Income Before Tax may also need hierarchy review[/bold red]")
    
    print(f"\n[bold]Operating Income concepts:[/bold]")
    operating_income_concepts = store.get_company_concepts("Operating Income")
    for concept in sorted(operating_income_concepts):
        print(f"  • {concept}")

if __name__ == '__main__':
    success = test_net_income_hierarchy_fix()
    test_income_hierarchy_separation()
    simulate_company_impact_net_income()
    check_other_income_categories()
    
    if success:
        print(f"\n[bold green]🎉 Net Income hierarchy fix is working correctly![/bold green]")
    else:
        print(f"\n[bold red]⚠️ Net Income hierarchy fix needs debugging[/bold red]")