from edgar import Company, set_identity, use_local_storage
import pandas as pd

set_identity("Debug Agent e2e@test.local")
use_local_storage(True)

def inspect_gs_custom_tag():
    print("\n=== Inspecting GS Custom Tag (10-K 2024) ===")
    ticker = "GS"
    company = Company(ticker)
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    facts = xbrl.facts.to_dataframe()
    
    tag = "ForeignCurrencyDenominatedDebtDesignatedAsForeignCurrencyHedge"
    
    # Try finding it with and without prefix
    matches = facts[facts['concept'].str.contains(tag, case=False, na=False)]
    if not matches.empty:
        print(f"Found matches for '{tag}':")
        for _, r in matches.iterrows():
            print(f"  - {r['concept']} (Dim: {r.get('full_dimension_label')}): {r['numeric_value']/1e9:.2f}B")
    else:
        print(f"No matches found for '{tag}'")

def inspect_bk_assets():
    print(f"\n=== Inspecting BK Assets (10-K 2024) ===")
    company = Company("BK")
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    facts = xbrl.facts.to_dataframe()
    
    # 1. Look for huge components (e.g. > 20B) to see where the money is
    print("Top 10 Largest (Non-Dim) Asset/Cash Concepts:")
    # Filter for non-dim
    nondim = facts[facts['full_dimension_label'].isna()].copy()
    # Sort by value
    nondim = nondim.sort_values('numeric_value', ascending=False)
    
    unique_concepts = set()
    count = 0
    for _, r in nondim.iterrows():
        if r['concept'] not in unique_concepts and r['numeric_value'] > 1e9:
            print(f"  {r['concept']}: {r['numeric_value']/1e9:.2f}B")
            unique_concepts.add(r['concept'])
            count += 1
            if count >= 15:
                break

def simulate_gs_match():
    print("\n=== Simulating GS Match Logic ===")
    # Replicate _get_fact_value logic
    ticker = "GS"
    company = Company(ticker)
    filing = company.get_filings(form='10-K').latest()
    facts = filing.xbrl().facts.to_dataframe()
    
    target = "gs:ForeignCurrencyDenominatedDebtDesignatedAsForeignCurrencyHedge"
    target_lower = target.lower()
    
    # Logic 1: Strip us-gaap and lower
    facts['match_key_1'] = facts['concept'].str.replace('us-gaap:', '', regex=False).str.lower()
    match1 = facts[facts['match_key_1'] == target_lower]
    print(f"Logic 1 (Strip us-gaap) Match Count: {len(match1)}")
    if not match1.empty:
        print(f"  Sample: {match1.iloc[0]['concept']}")

    # Logic 2: Exact lower match
    facts['match_key_2'] = facts['concept'].str.lower()
    match2 = facts[facts['match_key_2'] == target_lower]
    print(f"Logic 2 (Exact lower) Match Count: {len(match2)}")

def inspect_stt_filing():
    print("\n=== Inspecting STT Filing ===")
    company = Company("STT")
    filing = company.get_filings(form='10-K').latest()
    print(f"Accession: {filing.accession_no}")
    print(f"XML URL: {filing.document.url}")
    # Don't load full XBRL if it failed before, just check metadata

def inspect_stt_debt():
    print("\n=== Inspecting STT ShortTermDebt (10-K 2024) ===")
    ticker = "STT"
    company = Company(ticker)
    filing = company.get_filings(form='10-K').latest()
    xbrl = filing.xbrl()
    facts = xbrl.facts.to_dataframe()
    
    concepts = [
        'ShortTermBorrowings',
        'CommercialPaper',
        'SecuritiesSoldUnderAgreementsToRepurchase',
        'OtherShortTermBorrowings',
        'LongTermDebtCurrent'
    ]
    
    if facts.empty:
        print("STT Facts dataframe is empty")
        return
        
    for c in concepts:
        # Check column existence to avoid KeyError
        if 'concept' not in facts.columns:
            print(f"STT Facts missing 'concept' column. Columns: {facts.columns}")
            break
            
        rows = facts[facts['concept'] == f'us-gaap:{c}']
        nondim = rows[rows['full_dimension_label'].isna()]
        if not nondim.empty:
            val = nondim.sort_values('period_key', ascending=False).iloc[0]['numeric_value']
            print(f"  {c}: {val/1e9:.2f}B")

if __name__ == "__main__":
    inspect_gs_custom_tag()
    simulate_gs_match()
    inspect_bk_assets()
    # inspect_custody_cash("USB") # Replacing with standard inspection if needed, or just skip
    inspect_stt_filing()
    inspect_stt_debt()
