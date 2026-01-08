"""
Investigation: JPM Balance Sheet Analysis

Find all current liabilities to identify the missing $11.58B
"""

from edgar import Company, set_identity, use_local_storage

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

print("="*80)
print("JPM BALANCE SHEET ANALYSIS")
print("="*80)

# Get JPM data
company = Company('JPM')
filing = list(company.get_filings(form='10-K'))[0]
xbrl = filing.xbrl()

# Try to get balance sheet
print("\nSearching for balance sheet statement...")
try:
    balance_sheet = xbrl.statements.balance_sheet
    print(f"Balance sheet found!")
    print(f"\nStatements available: {xbrl.statements}")
except Exception as e:
    print(f"Could not get balance sheet: {e}")

# Get all presentation roles that might contain balance sheet
print("\nChecking presentation roles:")
for role_name in list(xbrl.presentation_trees.keys())[:20]:
    if 'balance' in role_name.lower() or 'financial' in role_name.lower() or 'position' in role_name.lower():
        print(f"  - {role_name}")

# Look at calculation trees for liabilities
print("\nChecking calculation trees for liabilities:")
for role_name, tree in xbrl.calculation_trees.items():
    if 'balance' in role_name.lower() or 'financial' in role_name.lower() or 'position' in role_name.lower():
        print(f"\nRole: {role_name[:80]}...")

        # Look for current liabilities node
        for node_id in tree.all_nodes.keys():
            if 'liabilitiescurrent' in node_id.lower():
                node = tree.all_nodes[node_id]
                print(f"  Found: {node_id}")

                # Get children (components of current liabilities)
                if node.children:
                    print(f"  Components ({len(node.children)}):")
                    for child_id in node.children[:15]:  # Show first 15
                        child = tree.all_nodes[child_id]
                        print(f"    - {child_id} (weight: {child.weight})")

                        # Check if this is debt-related
                        if 'debt' in child_id.lower() or 'borrow' in child_id.lower():
                            # Try to get value
                            try:
                                concept_name = child_id.replace('us-gaap:', '').replace('us-gaap_', '')
                                df = xbrl.facts.get_facts_by_concept(concept_name)

                                if df is not None and len(df) > 0:
                                    expected = [f'us-gaap:{concept_name}', f'us-gaap_{concept_name}', concept_name]
                                    exact = df[df['concept'].isin(expected)]

                                    if len(exact) > 0:
                                        if 'full_dimension_label' in exact.columns:
                                            no_dim = exact[exact['full_dimension_label'].isna()]
                                        else:
                                            no_dim = exact

                                        numeric = no_dim[no_dim['numeric_value'].notna()]

                                        if len(numeric) > 0:
                                            latest = numeric.sort_values('period_key', ascending=False).iloc[0]
                                            val = latest['numeric_value'] / 1e9
                                            print(f"      VALUE: ${val:.2f}B")
                            except Exception as e:
                                pass

print("\n" + "="*80)
