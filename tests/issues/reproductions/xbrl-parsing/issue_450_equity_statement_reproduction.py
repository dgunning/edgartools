"""
Reproduction script for issue #450: Statement of Equity rendering problems

GitHub Issue: #450
https://github.com/dgunning/edgartools/issues/450

Three problems to reproduce:
1. Missing values for "Total Stockholders' Equity" (appears twice but both empty)
2. Wrong abstract positioning (abstracts appear AFTER their children instead of before)
3. Incorrect abstract flagging (`abstract` column shows `False` for all rows, even abstracts)

Expected behavior:
- Total Stockholders' Equity should show values
- Abstract rows should appear BEFORE their children
- Abstract column should show True for abstract concepts

Test filing: Apple Q3 2025 10-Q
"""

from edgar import Company

def reproduce_issue_450():
    """Reproduce all three equity statement rendering issues"""

    print("=" * 80)
    print("ISSUE #450 REPRODUCTION: Statement of Equity Rendering Problems")
    print("=" * 80)
    print()

    # Get Apple's latest 10-Q
    print("Fetching Apple's latest 10-Q...")
    company = Company("AAPL")
    tenq = company.get_filings(form="10-Q").latest(1)

    print(f"Filing: {tenq.form} - {tenq.filing_date}")
    print(f"Accession: {tenq.accession_no}")
    print()

    # Get XBRL instance
    print("Loading XBRL instance...")
    xbrl = tenq.xbrl()

    if not xbrl:
        print("ERROR: Could not load XBRL instance")
        return

    print("XBRL loaded successfully")
    print()

    # Get statement of equity
    print("=" * 80)
    print("STATEMENT OF EQUITY")
    print("=" * 80)
    print()

    equity_statement = xbrl.statements.statement_of_equity()

    if equity_statement is None:
        print("ERROR: statement_of_equity() returned None")
        return

    print(f"Statement type: {type(equity_statement)}")
    print()

    # Display the statement
    print("RENDERED STATEMENT:")
    print("-" * 80)
    print(equity_statement)
    print("-" * 80)
    print()

    # Check for the three issues
    print("=" * 80)
    print("ISSUE VERIFICATION")
    print("=" * 80)
    print()

    # Convert to DataFrame
    import pandas as pd

    # Statement objects have a to_dataframe() method
    df = equity_statement.to_dataframe()

    print(f"DataFrame columns: {df.columns.tolist()}")
    print(f"DataFrame shape: {df.shape}")
    print()

    # Issue 1: Check for missing totals
    print("ISSUE 1: Missing Total Stockholders' Equity Values")
    print("-" * 80)

    # Find rows containing "Total" and "Stockholders" in the label
    if 'label' in df.columns:
        total_equity_rows = df[df['label'].str.contains('Total.*Stockholders', case=False, regex=True, na=False)]

        if len(total_equity_rows) > 0:
            print(f"Found {len(total_equity_rows)} rows with 'Total Stockholders' in label:")
            for idx, row in total_equity_rows.iterrows():
                print(f"  Row {idx}: {row.get('label', 'N/A')}")
                # Check if values are present
                value_cols = [col for col in df.columns if col not in ['label', 'concept', 'abstract']]
                values = {col: row.get(col) for col in value_cols}
                print(f"    Values: {values}")

                # Check if all values are empty/None/NaN
                all_empty = all(pd.isna(v) or v == '' or v is None for v in values.values())
                if all_empty:
                    print(f"    ❌ ISSUE CONFIRMED: All values are empty!")
                else:
                    print(f"    ✅ Values present")
        else:
            print("  ⚠️  No rows found with 'Total Stockholders' in label")
    else:
        print("  ⚠️  No 'label' column in DataFrame")

    print()

    # Issue 2: Check for abstract ordering
    print("ISSUE 2: Abstract Positioning (Should appear BEFORE children)")
    print("-" * 80)

    if 'abstract' in df.columns and 'label' in df.columns:
        # Look for abstract rows
        abstract_rows = df[df['abstract'] == True]

        if len(abstract_rows) > 0:
            print(f"Found {len(abstract_rows)} abstract rows")

            # Check if abstracts appear before their children
            # Simple heuristic: abstract rows should have lower indices than their children
            for idx, row in abstract_rows.iterrows():
                label = row.get('label', '')
                print(f"  Abstract row {idx}: {label}")

                # Check if there are rows before this that could be children
                # (This is a simplified check - real check would need hierarchy info)
        else:
            print("  ⚠️  No abstract rows found (this might be Issue 3!)")
    else:
        print("  ⚠️  Missing 'abstract' or 'label' column")

    print()

    # Issue 3: Check abstract column values
    print("ISSUE 3: Incorrect Abstract Flags")
    print("-" * 80)

    if 'abstract' in df.columns:
        abstract_counts = df['abstract'].value_counts()
        print(f"Abstract column value counts:")
        print(f"  {abstract_counts.to_dict()}")

        # Check if ALL values are False
        if len(abstract_counts) == 1 and False in abstract_counts.index:
            print("  ❌ ISSUE CONFIRMED: All rows show abstract=False!")
        elif True not in abstract_counts.index:
            print("  ❌ ISSUE CONFIRMED: No rows marked as abstract=True!")
        else:
            print(f"  ✅ Some rows marked as abstract=True")

        # Look for rows that SHOULD be abstract based on label patterns
        if 'label' in df.columns:
            print()
            print("  Checking labels that should likely be abstract:")

            abstract_patterns = [
                r'^Total\s+Stockholders',
                r'^Total\s+Equity',
                r'^Stockholders.*Equity\s*$',
                r'^Common\s+Stock\s*$',
                r'^Additional\s+Paid',
                r'^Retained\s+Earnings\s*$',
            ]

            for pattern in abstract_patterns:
                matching = df[df['label'].str.contains(pattern, case=False, regex=True, na=False)]
                if len(matching) > 0:
                    for idx, row in matching.iterrows():
                        is_abstract = row.get('abstract', False)
                        label = row.get('label', '')
                        status = "✅" if is_abstract else "❌"
                        print(f"    {status} Row {idx}: {label} - abstract={is_abstract}")
    else:
        print("  ⚠️  No 'abstract' column in DataFrame")

    print()

    # Additional debugging information
    print("=" * 80)
    print("DEBUGGING INFORMATION")
    print("=" * 80)
    print()

    print("First 10 rows of statement:")
    print(df.head(10).to_string())
    print()

    if hasattr(xbrl, 'get_presentation_linkbase'):
        print("Checking presentation linkbase...")
        # This might not exist, but worth checking

    print()
    print("=" * 80)
    print("REPRODUCTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    reproduce_issue_450()
