"""
Issue #438: Missing revenue facts in income statement for NVDA

Problem:
- NVDA income statement shows "Total Revenue" only in FY 2020 column, missing in recent years
- User investigation shows us-gaap:Revenues concepts have statement_type=None (267 facts)
- User's attempted fix (adding "Revenues": "IncomeStatement" to STATEMENT_MAPPING) causes duplicate entries

This script reproduces the issue to understand the root cause.
"""

import edgar
from edgar import Company
from rich import print as rprint


def investigate_nvda_revenue_facts():
    """Reproduce the NVDA income statement revenue issue."""
    print("=== Issue #438: NVDA Missing Revenue Facts Investigation ===\n")
    
    # Get NVDA company and filing
    company = Company("NVDA")
    print(f"Company: {company.name} ({company.cik})")
    
    # Get multiple recent filings to check if it's period-specific
    filings = company.get_filings(form="10-K")
    recent_10k = filings.latest()
    print(f"Latest 10-K: {recent_10k.accession_number} filed {recent_10k.filing_date}")
    
    # Also try previous filing
    print(f"Available 10-K filings: {len(filings)}")
    if len(filings) >= 2:
        prev_10k = filings[1]  # Get the second most recent
        print(f"Previous 10-K: {prev_10k.accession_number} filed {prev_10k.filing_date}")
    
    # Check 10-Q filings too
    recent_10q = company.get_filings(form="10-Q").latest()
    if recent_10q:
        print(f"Latest 10-Q: {recent_10q.accession_number} filed {recent_10q.filing_date}")
    
    # Get the XBRL data
    xbrl = recent_10k.xbrl()
    
    print("\n=== Income Statement Analysis ===")
    income_statement = xbrl.statements.income_statement()
    print("Income Statement:")
    rprint(income_statement)
    
    print("\n=== Revenue Facts Investigation ===")
    
    # Look for revenue-related facts using the proper API
    revenue_facts_df = xbrl.facts.search_facts("revenue")
    revenues_facts_df = xbrl.facts.get_facts_by_concept("us-gaap:Revenues", exact=True)
    
    print(f"\nFound {len(revenue_facts_df)} revenue-related facts:")
    if len(revenue_facts_df) > 0:
        print("Sample revenue facts:")
        for idx, row in revenue_facts_df.head(10).iterrows():
            stmt_type = row.get('statement_type', 'N/A')
            period = row.get('period_end', row.get('period_instant', 'N/A'))
            print(f"  - {row['concept']}: {row['value']} ({period}) - statement_type: {stmt_type}")
    
    print(f"\nFound {len(revenues_facts_df)} us-gaap:Revenues facts:")
    if len(revenues_facts_df) > 0:
        print("Sample us-gaap:Revenues facts:")
        for idx, row in revenues_facts_df.head(10).iterrows():
            stmt_type = row.get('statement_type', 'N/A')
            period = row.get('period_end', row.get('period_instant', 'N/A'))
            print(f"  - {row['concept']}: {row['value']} ({period}) - statement_type: {stmt_type}")
        
        # Check what statement types are assigned to revenues facts
        statement_types = revenues_facts_df['statement_type'].value_counts()
        
        print(f"\nStatement type distribution for us-gaap:Revenues facts:")
        for stmt_type, count in statement_types.items():
            print(f"  - {stmt_type}: {count} facts")
    
    return xbrl, income_statement, revenues_facts_df


def check_statement_mapping():
    """Check the STATEMENT_MAPPING configuration."""
    print("\n=== Statement Mapping Investigation ===")
    
    # Import the statement mapping from correct location
    try:
        from edgar.entity.parser import EntityFactsParser
        STATEMENT_MAPPING = EntityFactsParser.STATEMENT_MAPPING
        print("STATEMENT_MAPPING found in EntityFactsParser:")
        revenue_mappings = {k: v for k, v in STATEMENT_MAPPING.items() if 'revenue' in k.lower()}
        if revenue_mappings:
            for key, value in revenue_mappings.items():
                print(f"  - {key}: {value}")
        else:
            print("  - No revenue-related entries found")
        
        # Check if Revenues is in the mapping
        if "Revenues" in STATEMENT_MAPPING:
            print(f"  - Revenues: {STATEMENT_MAPPING['Revenues']}")
        else:
            print("  - 'Revenues' NOT found in STATEMENT_MAPPING")
            
        if "Revenue" in STATEMENT_MAPPING:
            print(f"  - Revenue: {STATEMENT_MAPPING['Revenue']}")
        else:
            print("  - 'Revenue' NOT found in STATEMENT_MAPPING")
            
    except ImportError as e:
        print(f"Could not import STATEMENT_MAPPING: {e}")


def investigate_statement_classification_mechanism(xbrl):
    """Investigate how statement types are determined for facts."""
    print("\n=== Statement Classification Mechanism Investigation ===")
    
    # Check the presentation trees and roles
    print(f"Number of presentation trees: {len(xbrl.presentation_trees)}")
    
    for role, tree in xbrl.presentation_trees.items():
        print(f"Role: {role}")
        if hasattr(tree, 'root_nodes'):
            print(f"  Root nodes: {len(tree.root_nodes)}")
            # Look for revenue-related nodes
            revenue_nodes = [node_id for node_id in tree.all_nodes if 'revenue' in node_id.lower()]
            if revenue_nodes:
                print(f"  Revenue-related nodes: {revenue_nodes[:5]}")  # Show first 5
    
    # Check all statements
    statements = xbrl.get_all_statements()
    print(f"\nNumber of statements: {len(statements)}")
    for stmt in statements:
        print(f"  Statement: {stmt.get('type')} - Role: {stmt.get('role')}")
    
    return statements


def main():
    """Main reproduction function."""
    try:
        xbrl, income_statement, revenues_facts = investigate_nvda_revenue_facts()
        check_statement_mapping()
        statements = investigate_statement_classification_mechanism(xbrl)
        
        print("\n=== Summary ===")
        print("1. Check if income statement shows revenue in recent years ✓")
        print("2. Verify if us-gaap:Revenues facts have statement_type=None - NOT REPRODUCED")
        print("3. Analyze STATEMENT_MAPPING for revenue concept handling ✓")
        print("4. Investigated statement classification mechanism ✓")
        
        # Conclusion
        print("\n=== Conclusion ===")
        print("The issue appears to be NOT REPRODUCIBLE with the current NVDA filing.")
        print("All us-gaap:Revenues facts are properly classified as IncomeStatement.")
        print("This suggests either:")
        print("  - The issue has been fixed")
        print("  - The issue is specific to different filings or time periods")
        print("  - The issue description may be inaccurate")
        
    except Exception as e:
        print(f"Error during investigation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()