"""
Investigate missing "Total Stockholders' Equity" values in Apple's equity statement
"""

from edgar import Company

def investigate_missing_totals():
    print("=" * 80)
    print("INVESTIGATING MISSING TOTAL STOCKHOLDERS' EQUITY VALUES")
    print("=" * 80)
    print()

    # Get Apple's 10-Q
    c = Company("AAPL")
    filing = c.get_filings(form="10-Q").latest()
    xb = filing.xbrl()

    print(f"Filing: {filing.form} - {filing.filing_date}")
    print()

    # Check if there are facts for StockholdersEquity concept
    print("1. Checking for StockholdersEquity facts in instance:")
    print("-" * 80)

    stockholders_equity_concept = 'us-gaap_StockholdersEquity'

    # Use the facts query interface
    equity_facts = xb.facts.query().by_concept(stockholders_equity_concept).to_dataframe()

    print(f"Found {len(equity_facts)} facts for {stockholders_equity_concept}")
    print()

    if len(equity_facts) > 0:
        print("Available columns:", equity_facts.columns.tolist())
        print()
        print("Sample facts:")
        print(equity_facts.head(10).to_string())
        print()

    # Check the raw statement data
    print("2. Checking raw statement data:")
    print("-" * 80)

    raw_data = xb.get_statement("StatementOfEquity")
    if raw_data:
        for item in raw_data:
            if 'StockholdersEquity' in item.get('concept', ''):
                print(f"Concept: {item.get('concept')}")
                print(f"Label: {item.get('label')}")
                print(f"Values: {item.get('values', {})}")
                print(f"Has values: {item.get('has_values')}")
                print(f"Is abstract: {item.get('is_abstract')}")
                print()

    # Check the presentation tree
    print("3. Checking presentation tree:")
    print("-" * 80)

    equity_role = None
    for role in xb.presentation_roles.keys():
        if 'EQUITY' in role.upper() or 'SHAREHOLDER' in role.upper():
            equity_role = role
            break

    if equity_role:
        tree = xb.presentation_trees[equity_role]
        for node_id, node in tree.all_nodes.items():
            if 'StockholdersEquity' in node_id:
                print(f"Node: {node_id}")
                print(f"  element_name: {node.element_name}")
                print(f"  depth: {node.depth}")
                print(f"  children: {node.children}")
                print()

    # Check if this is a dimensional statement
    print("4. Checking dimensionality:")
    print("-" * 80)

    stmt = xb.statements.statement_of_equity()
    if stmt:
        raw = stmt.get_raw_data()

        # Check for dimensional metadata
        for item in raw[:10]:
            if 'StockholdersEquity' in item.get('concept', ''):
                print(f"Item: {item.get('label')}")
                print(f"  has_dimension_children: {item.get('has_dimension_children', False)}")
                print(f"  is_dimension: {item.get('is_dimension', False)}")
                print()

    print()
    print("=" * 80)
    print("INVESTIGATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    investigate_missing_totals()
