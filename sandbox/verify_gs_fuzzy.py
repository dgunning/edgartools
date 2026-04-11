from edgar import Company, set_identity, use_local_storage
from edgar.xbrl.standardization.industry_logic import BankingExtractor
import pandas as pd
import sys

# Ensure local code is used
sys.path.insert(0, "/mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools")

set_identity("Debug Agent e2e@test.local")
use_local_storage(True)

def verify_gs():
    print(f"Testing GS Fuzzy Match")
    c = Company("GS")
    # Q1 2025
    filing = next((f for f in c.get_filings(form='10-Q') if '0000886982-25-000009' in f.accession_no), None)
    if not filing:
        print("Filing not found")
        return

    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()
    extractor = BankingExtractor()
    
    # Check strict match
    print("--- Strict Match Check ---")
    val = extractor._get_fact_value(facts_df, 'UnsecuredShortTermBorrowings')
    print(f"Strict Value: {val}")
    
    # Check fuzzy match
    print("--- Broker Payables Check ---")
    val_bp = extractor._get_fact_value_fuzzy(facts_df, 'PayablesToBrokerDealersAndClearingOrganizations')
    print(f"Broker Payables Value: {val_bp}")
    
    # Check manual search
    print("--- Manual Search ---")
    matches = facts_df[facts_df['concept'].str.contains('PayablesToBrokerDealers', case=False, na=False)]
    for idx, row in matches.head().iterrows():
        print(f"Match: {row['concept']} = {row['numeric_value']}")
        print(f"  Dims: full={row.get('full_dimension_label')}")

if __name__ == "__main__":
    verify_gs()
