"""
Debug script to check if presentation nodes have parent information
"""
from edgar import Company

company = Company("NFLX")
filing = company.get_filings(form="10-Q", accession_number="0001065280-25-000406").latest()
xbrl = filing.xbrl()

# Find income statement role
matching_statements, found_role, actual_statement_type = xbrl.find_statement("IncomeStatement")

print(f"Found role: {found_role}")
print(f"Statement type: {actual_statement_type}")

# Get presentation tree
if found_role in xbrl.presentation_trees:
    tree = xbrl.presentation_trees[found_role]
    print(f"\nRoot element: {tree.root_element_id}")
    print(f"\nTotal nodes: {len(tree.all_nodes)}")

    # Check first few nodes
    print("\nFirst 10 nodes:")
    for i, (element_id, node) in enumerate(list(tree.all_nodes.items())[:10]):
        print(f"\n{i}. Element: {element_id}")
        print(f"   Parent: {node.parent}")
        print(f"   Children: {node.children[:3] if node.children else []}")
        print(f"   Depth: {node.depth}")
        print(f"   Label: {node.display_label}")
