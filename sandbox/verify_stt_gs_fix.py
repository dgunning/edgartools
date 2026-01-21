from edgar import Company, set_identity, use_local_storage
from edgar.xbrl.standardization.orchestrator import Orchestrator
import pandas as pd

set_identity("Verification Agent e2e@test.local")
use_local_storage(True)

def verify_company(ticker, form='10-K'):
    print(f"\n=== Verifying {ticker} ({form}) ===")
    c = Company(ticker)
    filings = c.get_filings(form=form).latest(2)
    
    # Handle single result
    if not isinstance(filings, list) and not hasattr(filings, '__iter__'):
        filings = [filings]
        
    filing = filings[0]
    print(f"Filing: {filing.accession_no} ({filing.period_of_report})")
    
    # Initialize Orchestrator
    orchestrator = Orchestrator()
    xbrl = filing.xbrl()
    
    # 1. Run Tree Mapper
    results = orchestrator.tree_parser.map_company(ticker, filing)
    
    # 2. Run Validator (which triggers Banking Extractor)
    # We cheat yfinance validation by mocking it or just observing the extraction flow
    # Since we can't easily mock yf inside the Orchestrator without extensive patching,
    # we will inspect the Validator's _try_industry_extraction output directly
    
    # Verify ShortTermDebt specifically
    metric = "ShortTermDebt"
    print(f"\n[Metric: {metric}]")
    
    # A. Check Tree Result
    tree_res = results.get(metric)
    if tree_res:
        print(f"Tree Concept: {tree_res.concept}")
        print(f"Tree Source: {tree_res.source}")
    else:
        print("Tree Result: Not Mapped")
        
    # B. Run Industry Extraction directly
    print("Running Industry Extraction...")
    val = orchestrator.validator._try_industry_extraction(ticker, metric, xbrl)
    if val:
        print(f"Industry Extracted Value: {val/1e9:.3f}B")
    else:
        print("Industry Extraction returned None")
        
    # C. Run Validate Company Logic (simulated) for Guardrail check
    print("Running Guardrail Logic...")
    if tree_res and tree_res.is_mapped:
        if orchestrator.validator._is_balance_sheet_metric(metric):
            if orchestrator.validator._is_flow_concept(tree_res.concept):
                print(f"GUARDRAIL TRIGGERED: Rejected {tree_res.concept}")
            else:
                print("Guardrail Check: Passed")

    # D. Check GS Extra Logic (if applicable)
    if ticker == 'GS':
        print("\nChecking GS Dealer Logic...")
        # Check if internal banking logic picked up 'OtherSecuredBorrowings'
        from edgar.xbrl.standardization.industry_logic import BankingExtractor
        be = BankingExtractor()
        facts = xbrl.facts.to_dataframe()
        extracted = be.extract_street_debt(xbrl, facts)
        print(f"BankingExtractor Final Value: {extracted.value/1e9:.3f}B")
        print(f"Notes: {extracted.notes}")

if __name__ == "__main__":
    # STT 2023 10-K (Accession 0000093751-24-000498)
    print("Verifying STT 2023 (Guardrail Test)...")
    from edgar import Company
    c = Company("STT")
    filings = c.get_filings(form="10-K")
    target_filing = [f for f in filings if "0000093751-24-000498" in f.accession_no]
    
    if target_filing:
        # Mocking the Orchestrator usage but focusing on that specific filing object
        # We need to use the Orchestrator instance to run map_company on THIS filing object
        orchestrator = Orchestrator()
        filing = target_filing[0]
        print(f"Target Filing: {filing.accession_no}")
        
        # 1. Map
        results = orchestrator.tree_parser.map_company("STT", filing)
        metric = "ShortTermDebt"
        res = results.get(metric)
        print(f"Tree Output: {res.concept if res else 'None'}")
        
        # 2. Check Guardrail
        if res and res.is_mapped:
            if orchestrator.validator._is_balance_sheet_metric(metric) and orchestrator.validator._is_flow_concept(res.concept):
                print(f"GUARDRAIL: Flows tag '{res.concept}' detected!")
                # Simulate Validator behavior
                res.concept = None
                res.confidence = 0.0
                print("GUARDRAIL: Mapping invalidated.")
        
        # 3. Check Industry Logic via Fallback
        print("Checking Industry Fallback...")
        val = orchestrator.validator._try_industry_extraction("STT", metric, filing.xbrl())
        print(f"Industry Logic Value: {val/1e9 if val else 'None'}B")
        
    else:
        print("Target STT filing not found")


    print("\n" + "="*50 + "\n")
    verify_company("GS", "10-Q")
    
    print("\n" + "="*50 + "\n")
    verify_company("USB", "10-K")
