#!/usr/bin/env python3
"""
Test Tesla Net Income hierarchy fix.

This verifies that us-gaap:NetIncomeLossAttributableToNoncontrollingInterest
gets a distinct label from us-gaap:NetIncomeLoss.
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def test_tesla_net_income_fix():
    """Test that Tesla Net Income concepts have distinct labels."""
    print("[bold green]Tesla Net Income Hierarchy Fix Verification[/bold green]\n")
    
    # Reinitialize to pick up changes
    store = initialize_default_mappings(read_only=True)
    
    # Test the specific concepts from Tesla's issue
    tesla_net_income_test_cases = [
        ("us-gaap_NetIncomeLoss", "Net Income"),
        ("us-gaap_NetIncomeLossAttributableToNoncontrollingInterest", "Net Income Attributable to Noncontrolling Interest"),
        # Test colon format as well since that's what Tesla uses
        ("us-gaap:NetIncomeLoss", None),  # Should not be mapped in colon format yet
        ("us-gaap:NetIncomeLossAttributableToNoncontrollingInterest", None)  # Should not be mapped in colon format yet
    ]
    
    table = Table(title="Tesla Net Income Concept Mapping After Fix")
    table.add_column("Concept", style="cyan", width=50)
    table.add_column("Expected Label", style="yellow")
    table.add_column("Actual Label", style="green") 
    table.add_column("Status", style="red")
    
    all_correct = True
    
    for concept, expected_label in tesla_net_income_test_cases:
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
    
    return all_correct

def explain_noncontrolling_interest():
    """Explain what noncontrolling interest means."""
    print("\n[bold blue]Understanding Noncontrolling Interest[/bold blue]\n")
    
    print("When a company owns a subsidiary but not 100% of it:")
    print("  • The parent company consolidates 100% of subsidiary's income")
    print("  • But some of that income belongs to other shareholders") 
    print("  • That portion is 'attributable to noncontrolling interest'")
    print()
    
    print("Example for Tesla:")
    print("  • Tesla might own 85% of a subsidiary")
    print("  • Subsidiary earns $100M in net income")
    print("  • Tesla reports full $100M in consolidated income")
    print("  • But $15M is 'attributable to noncontrolling interest'")
    print("  • Tesla's actual share is $85M")
    print()
    
    print("Why separate labels matter:")
    print("  ✅ 'Net Income' = Total consolidated income")
    print("  ✅ 'Net Income Attributable to Noncontrolling Interest' = Minority shareholders' portion")
    print("  ❌ Both labeled as 'Net Income' = Confusing!")

def demonstrate_tesla_impact():
    """Show how this affects Tesla's financial statements."""
    print("\n[bold magenta]Impact on Tesla's Financial Statements[/bold magenta]\n")
    
    print("Before the fix:")
    print("  Line 1: 'Net Income' (us-gaap:NetIncomeLoss)")
    print("  Line 2: 'Net Income' (us-gaap:NetIncomeLossAttributableToNoncontrollingInterest)")
    print("  ❌ Both have same label - confusing for analysts!")
    print()
    
    print("After the fix:")
    print("  Line 1: 'Net Income' (us-gaap:NetIncomeLoss)")
    print("  Line 2: 'Net Income Attributable to Noncontrolling Interest'")
    print("  ✅ Clear distinction between total and minority interest portions!")
    print()
    
    print("This helps:")
    print("  📊 Investors understand true Tesla shareholder income")
    print("  🔍 Analysts separate parent vs subsidiary performance")
    print("  📈 Better comparability across companies")
    print("  ⚖️ Proper financial statement presentation")

def check_extended_net_income_hierarchy():
    """Check our complete Net Income hierarchy."""
    print("\n[bold yellow]Complete Net Income Hierarchy[/bold yellow]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    net_income_categories = [
        "Net Income",
        "Net Income from Continuing Operations", 
        "Net Income Attributable to Noncontrolling Interest",
        "Profit or Loss"
    ]
    
    table = Table(title="Complete Net Income Hierarchy")
    table.add_column("Category", style="cyan")
    table.add_column("Mapped Concepts", style="green")
    table.add_column("Count", style="yellow")
    
    for category in net_income_categories:
        concepts = store.get_company_concepts(category)
        concept_list = "\n".join(sorted(concepts)) if concepts else "None"
        count = len(concepts)
        
        table.add_row(category, concept_list, str(count))
    
    console = Console()
    console.print(table)

if __name__ == '__main__':
    success = test_tesla_net_income_fix()
    explain_noncontrolling_interest()
    demonstrate_tesla_impact() 
    check_extended_net_income_hierarchy()
    
    if success:
        print(f"\n[bold green]🎉 Tesla Net Income hierarchy fix is working correctly![/bold green]")
    else:
        print(f"\n[bold red]⚠️ Tesla Net Income hierarchy fix needs debugging[/bold red]")