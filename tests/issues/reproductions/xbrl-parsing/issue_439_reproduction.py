"""
Reproduction script for Issue #439: `order` and `balance_type` values not properly parsed in calculation trees

The issue reports that:
1. CalculationNode.order shows 0.0 instead of actual order values
2. CalculationNode.balance_type shows None instead of actual balance types
3. Presentation trees also have incorrect order values

Test case: AAPL 10-K filed 2024-11-01 (accession: 000032019324000123)
Order properties should be in aapl-20240928_cal.xml (calculation linkbase)
Balance type properties should be in us-gaap-2024.xsd (schema document)
"""

from edgar import find, Filing

def reproduce_issue():
    print("=== Issue #439 Reproduction ===")
    print("Testing order and balance_type parsing in calculation trees")
    print()

    # Get the AAPL filing mentioned in the issue
    print("Fetching AAPL 10-K filing (accession: 000032019324000123)...")
    filing: Filing = find('000032019324000123')
    print(f"Found filing: {filing.form} for {filing.company} filed {filing.filing_date}")
    print()

    # Get XBRL data
    print("Loading XBRL data...")
    xbrl = filing.xbrl()
    print(f"XBRL loaded successfully")
    print()

    # Check calculation trees
    print("=== CALCULATION TREES ANALYSIS ===")
    calc_trees = xbrl.calculation_trees
    print(f"Number of calculation trees: {len(calc_trees)}")
    print(f"Type of calc_trees: {type(calc_trees)}")

    # Convert to list if it's a dict-like structure
    if hasattr(calc_trees, 'values'):
        calc_trees_list = list(calc_trees.values())
    elif hasattr(calc_trees, 'items'):
        calc_trees_list = [tree for _, tree in list(calc_trees.items())[:3]]
    else:
        calc_trees_list = list(calc_trees)[:3]

    for i, tree in enumerate(calc_trees_list[:3]):  # Check first 3 trees
        print(f"\nCalculation Tree {i+1}:")
        print(f"  Type: {type(tree)}")
        print(f"  Attributes: {[attr for attr in dir(tree) if not attr.startswith('_')]}")

        # Get available attributes
        if hasattr(tree, 'role'):
            print(f"  Role: {tree.role}")
        if hasattr(tree, 'concept'):
            print(f"  Root concept: {tree.concept}")

        # Check root node
        root_node = tree
        if hasattr(root_node, 'order'):
            print(f"  Root node order: {root_node.order} (expected: not 0.0)")
        if hasattr(root_node, 'balance_type'):
            print(f"  Root node balance_type: {root_node.balance_type} (expected: not None)")

        # Check all_nodes attribute which contains the calculation nodes
        if hasattr(root_node, 'all_nodes') and root_node.all_nodes:
            print(f"  Number of all_nodes: {len(root_node.all_nodes)}")
            print(f"  Type of all_nodes: {type(root_node.all_nodes)}")

            # Convert to list to examine nodes
            all_nodes_list = list(root_node.all_nodes.values()) if hasattr(root_node.all_nodes, 'values') else list(root_node.all_nodes)

            for j, node in enumerate(all_nodes_list[:5]):  # First 5 nodes
                print(f"    Node {j+1}:")
                print(f"      Type: {type(node)}")
                if hasattr(node, 'element_id'):
                    print(f"      Element ID: {node.element_id}")
                if hasattr(node, 'parent'):
                    print(f"      Parent: {node.parent}")
                if hasattr(node, 'children'):
                    print(f"      Children: {node.children}")
                if hasattr(node, 'order'):
                    print(f"      Order: {node.order} (expected: not 0.0 for child nodes)")
                if hasattr(node, 'balance_type'):
                    print(f"      Balance type: {node.balance_type} (expected: not None)")
                if hasattr(node, 'weight'):
                    print(f"      Weight: {node.weight}")
                print()

    print("\n=== PRESENTATION TREES ANALYSIS ===")
    pres_trees = xbrl.presentation_trees
    print(f"Number of presentation trees: {len(pres_trees)}")
    print(f"Type of pres_trees: {type(pres_trees)}")

    # Convert to list if it's a dict-like structure
    if hasattr(pres_trees, 'values'):
        pres_trees_list = list(pres_trees.values())
    elif hasattr(pres_trees, 'items'):
        pres_trees_list = [tree for _, tree in list(pres_trees.items())[:2]]
    else:
        pres_trees_list = list(pres_trees)[:2]

    for i, tree in enumerate(pres_trees_list[:2]):  # Check first 2 trees
        print(f"\nPresentation Tree {i+1}:")
        print(f"  Type: {type(tree)}")
        print(f"  Attributes: {[attr for attr in dir(tree) if not attr.startswith('_')]}")

        # Get available attributes
        if hasattr(tree, 'role'):
            print(f"  Role: {tree.role}")
        if hasattr(tree, 'concept'):
            print(f"  Root concept: {tree.concept}")

        # Check root node
        root_node = tree
        if hasattr(root_node, 'order'):
            print(f"  Root node order: {root_node.order} (expected: not 0.0)")

        # Check all_nodes attribute which contains the presentation nodes
        if hasattr(root_node, 'all_nodes') and root_node.all_nodes:
            print(f"  Number of all_nodes: {len(root_node.all_nodes)}")
            print(f"  Type of all_nodes: {type(root_node.all_nodes)}")

            # Convert to list to examine nodes
            all_nodes_list = list(root_node.all_nodes.values()) if hasattr(root_node.all_nodes, 'values') else list(root_node.all_nodes)

            for j, node in enumerate(all_nodes_list[:5]):  # First 5 nodes
                print(f"    Node {j+1}:")
                print(f"      Type: {type(node)}")
                if hasattr(node, 'element_id'):
                    print(f"      Element ID: {node.element_id}")
                if hasattr(node, 'parent'):
                    print(f"      Parent: {node.parent}")
                if hasattr(node, 'children'):
                    print(f"      Children: {node.children}")
                if hasattr(node, 'order'):
                    print(f"      Order: {node.order} (expected: not 0.0 for child nodes)")
                print()

    # Summary of issues found
    print("\n=== ISSUE SUMMARY ===")

    # Count nodes with incorrect values
    calc_nodes_with_zero_order = 0
    calc_nodes_with_none_balance_type = 0
    pres_nodes_with_zero_order = 0

    def count_calc_issues(tree):
        nonlocal calc_nodes_with_zero_order, calc_nodes_with_none_balance_type
        if hasattr(tree, 'all_nodes') and tree.all_nodes:
            all_nodes_list = list(tree.all_nodes.values()) if hasattr(tree.all_nodes, 'values') else list(tree.all_nodes)
            for node in all_nodes_list:
                if hasattr(node, 'order') and node.order == 0.0:
                    calc_nodes_with_zero_order += 1
                if hasattr(node, 'balance_type') and node.balance_type is None:
                    calc_nodes_with_none_balance_type += 1

    def count_pres_issues(tree):
        nonlocal pres_nodes_with_zero_order
        if hasattr(tree, 'all_nodes') and tree.all_nodes:
            all_nodes_list = list(tree.all_nodes.values()) if hasattr(tree.all_nodes, 'values') else list(tree.all_nodes)
            for node in all_nodes_list:
                if hasattr(node, 'order') and node.order == 0.0:
                    pres_nodes_with_zero_order += 1

    for tree in calc_trees_list:
        count_calc_issues(tree)

    for tree in pres_trees_list:
        count_pres_issues(tree)

    print(f"Calculation nodes with order = 0.0: {calc_nodes_with_zero_order}")
    print(f"Calculation nodes with balance_type = None: {calc_nodes_with_none_balance_type}")
    print(f"Presentation nodes with order = 0.0: {pres_nodes_with_zero_order}")

    if calc_nodes_with_zero_order > 0 or calc_nodes_with_none_balance_type > 0 or pres_nodes_with_zero_order > 0:
        print("\n❌ ISSUE CONFIRMED: order and/or balance_type values are not properly parsed")
    else:
        print("\n✅ No issues found - order and balance_type values appear correct")

if __name__ == "__main__":
    reproduce_issue()