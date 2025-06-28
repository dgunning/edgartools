#!/usr/bin/env python3
"""
Test Net Income hierarchy mapping issue.

This demonstrates the same problem we had with revenue - different 
Net Income concepts all map to the same "Net Income" label, causing 
confusion when companies report both total and component income items.
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def analyze_net_income_hierarchy_issue():
    """Analyze the Net Income mapping issue."""
    print("[bold red]Net Income Hierarchy Mapping Issue[/bold red]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Get all concepts that map to "Net Income"
    net_income_concepts = store.get_company_concepts("Net Income")
    
    print(f"[bold]Concepts currently mapping to 'Net Income' ({len(net_income_concepts)}):[/bold]")
    
    table = Table(title="Net Income Concept Mappings")
    table.add_column("Concept", style="cyan", width=50)
    table.add_column("Mapped Label", style="green")
    table.add_column("Hierarchy Analysis", style="yellow")
    
    # Analyze each concept to understand the hierarchy issue
    concept_analysis = {
        "us-gaap_NetIncome": "Net Income (Simple/Total)",
        "us-gaap_NetIncomeLoss": "Net Income or Loss (Total)", 
        "us-gaap_ProfitLoss": "Profit or Loss (Total/International)",
        "us-gaap_IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest": "Continuing Operations Income (Component)"
    }
    
    for concept in sorted(net_income_concepts):
        standard_label = store.get_standard_concept(concept)
        hierarchy_analysis = concept_analysis.get(concept, "Detailed/Component Income")
        
        table.add_row(concept, standard_label, hierarchy_analysis)
    
    console = Console()
    console.print(table)

def demonstrate_problem_companies():
    """Show which companies this affects."""
    print("\n[bold blue]Companies Affected by Net Income Confusion[/bold blue]\n")
    
    print("Companies that report multiple income concepts:")
    print("  • Complex corporations with subsidiaries")
    print("  • Companies with discontinued operations") 
    print("  • International companies (using ProfitLoss)")
    print("  • Companies with noncontrolling interests")
    print()
    
    print("Example confusion:")
    print("  Line 1: 'Net Income' (us-gaap_NetIncome)")
    print("  Line 2: 'Net Income' (us-gaap_IncomeLossFromContinuingOperations...) ← DUPLICATE LABEL!")
    print()
    print("This makes it impossible to distinguish between:")
    print("  ✓ Total net income")
    print("  ✓ Income from continuing operations")
    print("  ✓ Income attributable to parent company")

def propose_net_income_solution():
    """Propose a solution for Net Income hierarchy."""
    print("\n[bold green]Proposed Net Income Hierarchy Solution[/bold green]\n")
    
    solution = '''
"Net Income": [
  "us-gaap_NetIncome",
  "us-gaap_NetIncomeLoss"
],

"Net Income from Continuing Operations": [
  "us-gaap_IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
  "us-gaap_IncomeLossFromContinuingOperations"
],

"Profit or Loss": [
  "us-gaap_ProfitLoss"
],

"Net Income Attributable to Parent": [
  "us-gaap_NetIncomeLossAttributableToParent",
  "us-gaap_NetIncomeLossAvailableToCommonStockholdersBasic"
]'''
    
    print(solution)
    print()
    print("This creates proper hierarchy:")
    print("  • Net Income (simple/total)")
    print("  • Net Income from Continuing Operations (component)")
    print("  • Profit or Loss (international standard)")
    print("  • Net Income Attributable to Parent (ownership specific)")

def check_additional_income_concepts():
    """Check if there are other income concepts with similar issues."""
    print("\n[bold yellow]Other Income Concepts to Review[/bold yellow]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Check other income-related mappings
    income_categories = [
        "Operating Income",
        "Income Before Tax", 
        "Gross Profit"
    ]
    
    table = Table(title="Other Income Categories")
    table.add_column("Category", style="cyan")
    table.add_column("Concept Count", style="yellow")
    table.add_column("Potential Issues", style="red")
    
    for category in income_categories:
        concepts = store.get_company_concepts(category)
        count = len(concepts)
        
        # Check for potential hierarchy issues
        potential_issues = "None"
        if count > 3:
            potential_issues = "Multiple concepts - review needed"
        elif count > 1:
            potential_issues = "Check for hierarchy"
            
        table.add_row(category, str(count), potential_issues)
    
    console = Console()
    console.print(table)

if __name__ == '__main__':
    analyze_net_income_hierarchy_issue()
    demonstrate_problem_companies()
    propose_net_income_solution()
    check_additional_income_concepts()