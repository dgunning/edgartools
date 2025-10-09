"""
Test that Statement of Equity shows "Beginning balance" and "Ending balance" labels
for concepts that appear multiple times (like Total Stockholders' Equity).
"""

from edgar import Company

def test_beginning_ending_labels():
    print("Testing Beginning/Ending Balance Labels")
    print("=" * 80)

    # Get Apple's 10-Q
    company = Company("AAPL")
    tenq = company.get_filings(form="10-Q").latest(1)
    xbrl = tenq.xbrl()

    # Get the equity statement
    equity_stmt = xbrl.statements.statement_of_equity()
    df = equity_stmt.to_dataframe()

    print("\nAll labels in Statement of Equity:")
    print("-" * 80)
    for idx, row in df.iterrows():
        label = row['label']
        concept = row['concept']
        if 'StockholdersEquity' in concept:
            print(f"  [{idx}] {label}")
            print(f"      Concept: {concept}")

    # Check for Total Stockholders' Equity rows
    equity_concept = 'us-gaap_StockholdersEquity'
    equity_rows = df[df['concept'] == equity_concept]

    print(f"\nTotal Stockholders' Equity rows: {len(equity_rows)}")
    print("-" * 80)

    for idx, row in equity_rows.iterrows():
        print(f"  [{idx}] {row['label']}")
        value_cols = [col for col in df.columns if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]
        for col in value_cols:
            if row[col] not in ('', None):
                print(f"      {col}: {row[col]}")

    # Verify the labels
    print("\nVerification:")
    print("-" * 80)

    labels = equity_rows['label'].tolist()

    if len(labels) >= 2:
        first_label = labels[0]
        last_label = labels[-1]

        has_beginning = 'Beginning balance' in first_label
        has_ending = 'Ending balance' in last_label

        print(f"  First row label: {first_label}")
        print(f"  Has 'Beginning balance': {has_beginning}")
        print()
        print(f"  Last row label: {last_label}")
        print(f"  Has 'Ending balance': {has_ending}")
        print()

        if has_beginning and has_ending:
            print("✅ SUCCESS: Labels correctly distinguish beginning and ending balances")
        else:
            print("❌ FAILURE: Labels do not distinguish beginning and ending balances")
    else:
        print(f"❌ FAILURE: Expected at least 2 rows, found {len(labels)}")

if __name__ == "__main__":
    test_beginning_ending_labels()
