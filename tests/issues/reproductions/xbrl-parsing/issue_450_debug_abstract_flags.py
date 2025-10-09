"""
Debug script to investigate abstract flag propagation for issue #450

This script will:
1. Load Apple's 10-Q
2. Access the raw statement data
3. Check the presentation nodes
4. Compare abstract flags in schema vs. presentation tree vs. rendered statement
"""

from edgar import Company

def debug_abstract_flags():
    print("=" * 80)
    print("ISSUE #450 DEBUG: Abstract Flag Propagation")
    print("=" * 80)
    print()

    # Get Apple's latest 10-Q
    company = Company("AAPL")
    tenq = company.get_filings(form="10-Q").latest(1)
    xbrl = tenq.xbrl()

    print(f"Filing: {tenq.form} - {tenq.filing_date}")
    print()

    # Find the equity statement role
    print("Finding StatementOfEquity role...")
    print()

    # Check presentation trees
    print("Available presentation roles:")
    for role in list(xbrl.presentation_roles.keys())[:10]:
        print(f"  {role}")
    print()

    # Find equity statement
    equity_role = None
    for role in xbrl.presentation_roles.keys():
        if 'equity' in role.lower() or 'stockholder' in role.lower():
            print(f"Found equity role: {role}")
            equity_role = role
            break

    if not equity_role:
        print("ERROR: Could not find equity statement role")
        return

    print()

    # Get the presentation tree
    print("=" * 80)
    print("PRESENTATION TREE ANALYSIS")
    print("=" * 80)
    print()

    tree = xbrl.presentation_trees.get(equity_role)
    if not tree:
        print("ERROR: Could not get presentation tree")
        return

    print(f"Tree has {len(tree.all_nodes)} nodes")
    print()

    # Check abstract flags in presentation nodes
    print("Checking abstract flags in presentation nodes:")
    print("-" * 80)

    for node_id, node in list(tree.all_nodes.items())[:20]:
        print(f"Node: {node_id}")
        print(f"  element_name: {node.element_name}")
        print(f"  standard_label: {node.standard_label}")
        print(f"  is_abstract: {node.is_abstract}")
        print(f"  depth: {node.depth}")

        # Check if this concept is in element catalog
        if node.element_name in xbrl.element_catalog:
            elem = xbrl.element_catalog[node.element_name]
            print(f"  Element catalog abstract: {elem.abstract}")
        else:
            print(f"  Element NOT in catalog")
        print()

    print()

    # Get raw statement data
    print("=" * 80)
    print("RAW STATEMENT DATA ANALYSIS")
    print("=" * 80)
    print()

    raw_data = xbrl.get_statement("StatementOfEquity")
    if not raw_data:
        print("ERROR: Could not get raw statement data")
        return

    print(f"Statement has {len(raw_data)} line items")
    print()

    print("Checking is_abstract flags in statement data:")
    print("-" * 80)

    for idx, item in enumerate(raw_data[:15]):
        label = item.get('label', '')
        is_abstract = item.get('is_abstract', False)
        concept = item.get('concept', '')
        element_name = item.get('name', '')
        has_values = item.get('has_values', False)

        print(f"{idx}. {label}")
        print(f"   concept: {concept}")
        print(f"   name: {element_name}")
        print(f"   is_abstract: {is_abstract}")
        print(f"   has_values: {has_values}")

        # Check element catalog
        if element_name and element_name in xbrl.element_catalog:
            elem = xbrl.element_catalog[element_name]
            print(f"   catalog.abstract: {elem.abstract}")

            # Flag mismatch
            if elem.abstract != is_abstract:
                print(f"   ⚠️  MISMATCH: catalog says {elem.abstract}, statement data says {is_abstract}")
        print()

    print()
    print("=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    debug_abstract_flags()
