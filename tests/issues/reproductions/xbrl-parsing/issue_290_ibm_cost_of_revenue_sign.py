"""
Issue #290: IBM Cost of Revenue Sign Inconsistency Reproduction

Reproduces the issue where Cost of Revenue shows as:
- Positive 27,201 in HTML rendering on SEC website
- Negative -27201000000 in EdgarTools XBRL parsing

IBM 10-K filing:
- Accession: 0000051143-25-000015
- Report date: 2024-12-31
- Filing date: 2025-02-25
"""

from edgar import Company, set_identity
from edgar.xbrl.xbrl import XBRL
import pandas as pd

def reproduce_ibm_cost_of_revenue_sign_issue():
    """Reproduce the IBM Cost of Revenue sign inconsistency issue."""

    # Set proper identity for SEC API
    set_identity("Research Team research@edgartools.dev")

    print("=== IBM Cost of Revenue Sign Inconsistency Reproduction ===\n")

    # Get the specific IBM filing
    print("1. Fetching IBM filing...")
    c = Company("IBM")
    filings = c.get_filings(accession_number="0000051143-25-000015")
    filing = filings[0]

    print(f"   Filing: {filing.form} for {filing.period_of_report}")
    print(f"   Accession: {filing.accession_number}")
    print(f"   Company: {filing.company}")
    print()

    # Parse XBRL and get income statement
    print("2. Parsing XBRL and extracting Income Statement...")
    xbrl = XBRL.from_filing(filing)
    stmt = xbrl.statements.income_statement()

    print(f"   Statement type: {stmt.role_or_type}")
    print(f"   Canonical type: {stmt.canonical_type}")
    print()

    # Convert to DataFrame and examine Cost of Revenue
    df = stmt.to_dataframe()

    print("3. Examining Income Statement DataFrame structure...")
    print(f"   DataFrame shape: {df.shape}")
    print(f"   DataFrame columns: {list(df.columns)}")
    print()

    print("4. Full Income Statement DataFrame:")
    print(df)
    print()

    # Look for Cost of Revenue in the DataFrame using appropriate column
    print("5. Searching for Cost of Revenue entries...")
    if 'concept' in df.columns:
        search_column = 'concept'
    elif 'fact' in df.columns:
        search_column = 'fact'
    elif df.index.name:
        # Sometimes the fact names are in the index
        cost_of_revenue_rows = df[df.index.str.contains('Cost.*Revenue|Revenue.*Cost', case=False, na=False)]
        print(f"   Searching in index for Cost of Revenue...")
    else:
        # Try to find a label or description column
        search_column = None
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['label', 'description', 'name', 'fact']):
                search_column = col
                break

    if search_column:
        cost_of_revenue_rows = df[df[search_column].str.contains('Cost.*Revenue|Revenue.*Cost', case=False, na=False)]
        print(f"   Searching in column '{search_column}' for Cost of Revenue...")
    elif 'cost_of_revenue_rows' not in locals():
        cost_of_revenue_rows = pd.DataFrame()  # Empty DataFrame if no search was done

    if not cost_of_revenue_rows.empty:
        print("   Found Cost of Revenue entries:")
        for idx, row in cost_of_revenue_rows.iterrows():
            print(f"   - Index: {idx}")
            print(f"     Row data: {row.to_dict()}")
            print()
    else:
        print("   No Cost of Revenue entries found.")
        print("   Showing sample rows:")
        print(df.head())
        print()

    # Let's also examine the raw facts to understand the underlying data
    print("6. Examining raw XBRL facts related to Cost of Revenue...")

    # Use the facts query interface to get Cost of Revenue facts
    cost_revenue_facts_df = xbrl.facts.query().by_concept("CostOfRevenue").to_dataframe()

    if not cost_revenue_facts_df.empty:
        print(f"   Found {len(cost_revenue_facts_df)} Cost of Revenue facts:")
        print(f"   Facts DataFrame columns: {list(cost_revenue_facts_df.columns)}")
        print("   Sample facts:")
        for idx, row in cost_revenue_facts_df.head(3).iterrows():
            print(f"   - Concept: {row['concept']}")
            print(f"     Value: {row['value']}")
            print(f"     Available columns: {list(row.keys())}")
            print()
    else:
        print("   No CostOfRevenue facts found in raw data")

    # Let's also look at the key fact that shows as -27201000000
    print("7. Examining the specific Cost of Revenue fact for 2024...")
    key_fact_df = xbrl.facts.query().by_concept("CostOfRevenue").by_fiscal_year(2024).to_dataframe()

    if not key_fact_df.empty:
        print("   2024 Cost of Revenue facts:")
        for idx, row in key_fact_df.head(3).iterrows():
            print(f"   - Value: {row['value']}")
            print(f"     Row data: {row.to_dict()}")
            print()

    return filing, xbrl, stmt, df

if __name__ == "__main__":
    try:
        filing, xbrl, stmt, df = reproduce_ibm_cost_of_revenue_sign_issue()
        print("✓ Reproduction completed successfully")
    except Exception as e:
        print(f"✗ Error during reproduction: {e}")
        import traceback
        traceback.print_exc()