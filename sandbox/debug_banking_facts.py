from edgar import Company, set_identity, use_local_storage
import pandas as pd

set_identity("Debug Agent e2e@test.local")
use_local_storage(True)

def inspect_gs_debt():
    print("\n=== Inspecting GS ShortTermDebt (10-K 2024) ===")
    ticker = "GS"
    company = Company(ticker)
    filing = company.get_filings(form='10-K').latest()
    if not filing:
        print("No 10-K found")
        return

    xbrl = filing.xbrl()
    facts = xbrl.facts.to_dataframe()
    
    # GS: Exploratory search for the missing ~21B
    print("\n[GS] Exploratory Search (Debt/Borrowings ~20B):")
    # Search for concepts containing 'Debt' or 'Borrowings'
    potential_matches = facts[facts['concept'].str.contains('Debt|Borrowings', case=False, na=False)]
    
    # Filter for values in the 15B-25B range (to find the gap) or 90B range (Total)
    for _, row in potential_matches.iterrows():
        val = row['numeric_value']
        # Check non-dimensional only for now
        if pd.isna(row['full_dimension_label']):
            # Gap search (15-25B)
            if 15e9 <= val <= 25e9:
                print(f"  Gap Candidate: {row['concept']} = {val/1e9:.2f}B")
            # Total search (85-95B)
            if 85e9 <= val <= 95e9:
                print(f"  Total Candidate: {row['concept']} = {val/1e9:.2f}B")

def inspect_ms_cash():
    print("\n=== Inspecting MS Cash (10-K 2024) ===")
    ticker = "MS"
    company = Company(ticker)
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    facts = xbrl.facts.to_dataframe()
    
    # MS: Exploratory search for Segregated/Restricted
    print("\n[MS] Exploratory Search (Segregated/Restricted):")
    potential_matches = facts[facts['concept'].str.contains('Segregated|Restricted|Cash', case=False, na=False)]
    
    for _, row in potential_matches.iterrows():
        val = row['numeric_value']
        # Check non-dimensional
        if pd.isna(row['full_dimension_label']):
             # Look for the ~30B difference (25-35B)
            if 25e9 <= val <= 35e9:
                print(f"  Diff Candidate: {row['concept']} = {val/1e9:.2f}B")
            
            # Check for interest bearing deposits
            if 'Interest' in row['concept'] and 'Deposit' in row['concept']:
                 print(f"  Deposit Item: {row['concept']} = {val/1e9:.2f}B")

if __name__ == "__main__":
    inspect_gs_debt()
    inspect_ms_cash()
