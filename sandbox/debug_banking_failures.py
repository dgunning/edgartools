import sys
import os
sys.path.insert(0, "/mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools")

from edgar import Company, set_identity, use_local_storage
print(f"EDGAR FILE: {Company.__module__}")
try:
    from edgar.xbrl.standardization.orchestrator import Orchestrator
except ImportError as e:
    print(f"ImportError: {e}")
    import edgar.xbrl.standardization
    print(f"Standardization dir: {edgar.xbrl.standardization.__file__}")

from edgar.xbrl.standardization.industry_logic import BankingExtractor
print(f"BankingExtractor File: {sys.modules['edgar.xbrl.standardization.industry_logic'].__file__}")
import pandas as pd

set_identity("Debug Agent e2e@test.local")
use_local_storage(True)

def debug_company(ticker, accession_no=None, form='10-K'):
    print(f"\n{'='*50}")
    print(f"DEBUGGING {ticker} ({form}) - Accession: {accession_no}")
    print(f"{'='*50}")
    
    c = Company(ticker)
    filings = c.get_filings(form=form)
    if accession_no:
        filing = next((f for f in filings if accession_no in f.accession_no), None)
        if not filing:
            print(f"Filing {accession_no} not found")
            return
    else:
        filing = filings[0]
        
    print(f"Filing: {filing.accession_no} ({filing.period_of_report})")
    
    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()
    try:
        extractor = BankingExtractor()
    except Exception as e:
        print(f"Error creating extractor: {e}")
        return

    orchestrator = Orchestrator()
    results = orchestrator.tree_parser.map_company(ticker, filing)
    
    # helper to print concept name
    def get_val_and_concept(df, concept, fuzzy=False):
        if fuzzy:
            matches = df[df['concept'].str.lower().str.contains(concept.lower(), regex=False, na=False)]
        else:
             matches = df[df['concept'] == f"us-gaap:{concept}"]
        
        if matches.empty:
            return None, None
            
        # Filter non-dim
        non_dim = matches.copy()
        if 'full_dimension_label' in non_dim.columns:
            non_dim = non_dim[non_dim['full_dimension_label'].isna() | (non_dim['full_dimension_label'] == '')]
        
        if non_dim.empty:
            return None, None
            
        val = non_dim['numeric_value'].iloc[0] # simplified
        name = non_dim['concept'].iloc[0]
        return val, name

    # 1. Archetype
    archetype = extractor._detect_bank_archetype(facts_df)
    print(f"\nDetected Archetype: {archetype}")
    
    # 2. ShortTermDebt Analysis
    print(f"\n--- ShortTermDebt Analysis ---")
    stb_agg = extractor._get_fact_value(facts_df, 'ShortTermBorrowings')
    print(f"us-gaap:ShortTermBorrowings (Aggregate): {stb_agg/1e9 if stb_agg else 'None'} B")
    
    concepts_to_check = [
        'CommercialPaper',
        'OtherShortTermBorrowings',
        'FederalHomeLoanBankAdvancesCurrent',
        'FederalHomeLoanBankAdvances', 
        'LongTermDebtCurrent',
        'SecuritiesSoldUnderAgreementsToRepurchase', 
        'SecuritiesPurchasedUnderAgreementsToResell',
        'OtherSecuredBorrowings',
        'SecuredBorrowings',
        'OtherBorrowings'
    ]
    
    print("\n[Components Check]")
    for c in concepts_to_check:
        val, name = get_val_and_concept(facts_df, c, fuzzy=False)
        fuzzy_val, fuzzy_name = get_val_and_concept(facts_df, c, fuzzy=True)
        print(f"{c}:")
        if val: print(f"  Direct: {name} = {val/1e9:.3f} B")
        if fuzzy_val: print(f"  Fuzzy:  {fuzzy_name} = {fuzzy_val/1e9:.3f} B")

    print(f"\n[Validation of extraction logic]")
    extracted_debt = extractor.extract_street_debt(xbrl, facts_df)
    print(f"ShortTermDebt Value: {extracted_debt.value/1e9 if extracted_debt.value else 'None'} B")
    print(f"ShortTermDebt Notes: {extracted_debt.notes}")

    extracted_cash = extractor.extract_street_cash(xbrl, facts_df)
    print(f"CashAndEquivalents Value: {extracted_cash.value/1e9 if extracted_cash.value else 'None'} B")
    print(f"CashAndEquivalents Notes: {extracted_cash.notes}")

    # DISCOVERY: List all large liability concepts to find the missing pieces
    print(f"\n[Discovery: Top Liability Concepts > $1B]")
    if not facts_df.empty:
        # Check specific GS gap candidate
        gap_concept = 'ForeignCurrencyDenominatedDebtDesignatedAsForeignCurrencyHedge'
        gap_val = extractor._get_fact_value_fuzzy(facts_df, gap_concept)
        if gap_val:
            print(f"  *** GAP CANDIDATE *** {gap_concept}: {gap_val/1e9:.3f} B")
            
        # Filter likely liability patterns
        potential = facts_df[facts_df['concept'].str.contains('Debt|Borrow|Payable|Liabilit', case=False, regex=True)]
        potential = potential[potential['numeric_value'] > 1e9]
        # Unique concepts with values
        for concept in potential['concept'].unique():
            val = extractor._get_fact_value(facts_df, concept)
            if val and val > 1e9:
                print(f"  {concept}: {val/1e9:.3f} B")

    # 3. Cash Analysis
    print(f"\n--- Cash Analysis ---")
    cash_concepts = [
        'CashAndDueFromBanks',
        'InterestBearingDepositsInBanks',
        'InterestBearingDepositsInFederalReserve',
        'DepositsInFederalReserve',
        'RestrictedCash', 
        'RestrictedCashAndCashEquivalents'
    ]
    
    for c in cash_concepts:
        val, name = get_val_and_concept(facts_df, c, fuzzy=False)
        fuzzy_val, fuzzy_name = get_val_and_concept(facts_df, c, fuzzy=True)
        print(f"{c}:")
        if val: print(f"  Direct: {name} = {val/1e9:.3f} B")
        if fuzzy_val: print(f"  Fuzzy:  {fuzzy_name} = {fuzzy_val/1e9:.3f} B")



if __name__ == "__main__":
    # GS (Dealer) - 10-K 2024 (Accession 0000886982-25-000005)
    debug_company("GS", accession_no="0000886982-25-000005", form="10-K")
