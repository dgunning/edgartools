
import sys
import os

# Add the project root to python path
sys.path.append('/mnt/c/Users/Sangicook/LAB_FHI/Project/Side_project/edgartools')

from edgar import set_identity, use_local_storage
from edgar.xbrl.standardization.orchestrator import Orchestrator
from edgar.xbrl.standardization.tools import (
    discover_concepts,
    check_fallback_quality,
    verify_mapping,
    learn_mappings
)
from edgar import Company
from edgar.xbrl.standardization.tools.resolve_gaps import resolve_all_gaps, calculate_coverage

def run_test():
    print("Step 1: Run the Orchestrator")
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True) # Ensure consistent data access method

    orchestrator = Orchestrator()
    # Using a subset for speed/testing as per plan, but user asked for MAG7 example. 
    # Let's use AAPL, GOOG, AMZN first as they represent different challenges.
    tickers = ['AAPL', 'GOOG', 'AMZN'] 
    
    print(f"Mapping companies: {tickers}")
    results = orchestrator.map_companies(
        tickers=tickers,
        # use_ai=False to simulate gaps that tools need to fill
        use_ai=False, 
        validate=True
    )

    print("\nStep 2: Identify Gaps and Invalid Mappings")
    issues = {}
    for ticker, metrics in results.items():
        for metric, result in metrics.items():
            if not result.is_mapped:
                issues.setdefault(ticker, []).append(f"UNMAPPED: {metric}")
            elif result.validation_status == "invalid":
                issues.setdefault(ticker, []).append(f"INVALID: {metric}")

    print("Issues found:")
    for ticker, problems in issues.items():
        print(f"\n{ticker}:")
        for p in problems:
            print(f"  - {p}")

    print("\nStep 3: Use AI Tools to Resolve ONE Issue (IntangibleAssets for AMZN if available)")
    ticker = "AMZN"
    metric = "IntangibleAssets"
    
    # Check if AMZN IntangibleAssets is actually an issue
    if ticker in issues and any(metric in p for p in issues[ticker]):
        print(f"Resolving {metric} for {ticker}...")
        try:
            company = Company(ticker)
            filing = list(company.get_filings(form='10-K'))[0]
            xbrl = filing.xbrl()
            facts = company.get_facts().to_dataframe()

            print("  3a: Discovering concepts...")
            candidates = discover_concepts(metric, xbrl, facts)
            print(f"  Top 3 candidates for {metric}:")
            for c in candidates[:3]:
                print(f"    {c.concept} (confidence: {c.confidence:.2f})")

            if candidates:
                best = candidates[0]
                print(f"  3b: Checking fallback quality for {best.concept}...")
                quality = check_fallback_quality(metric, best.concept)
                print(f"    Quality check: is_valid={quality.is_valid}")
                if quality.issues:
                    print(f"    Issues: {quality.issues}")

                if quality.is_valid:
                    print(f"  3c: Verifying mapping...")
                    verification = verify_mapping(metric, best.concept, xbrl, ticker)
                    print(f"    Verification: {verification.status}")
                    if verification.xbrl_value and verification.reference_value:
                        print(f"    XBRL: {verification.xbrl_value/1e9:.2f}B")
                        print(f"    Reference: {verification.reference_value/1e9:.2f}B")
        except Exception as e:
            print(f"Error in Step 3: {e}")
    else:
        print(f"Skipping Step 3: {metric} for {ticker} was not identified as an issue.")

    print("\nStep 4: Use learn_mappings for Cross-Company Patterns")
    try:
        result = learn_mappings("IntangibleAssets", ["AAPL", "GOOG", "AMZN", "MSFT"])
        print(f"summary: {result.summary}")
        print(f"New concept variants to add: {result.new_concept_variants}")
    except Exception as e:
        print(f"Error in Step 4: {e}")

    print("\nStep 5: Run Full Resolution Workflow (resolve_all_gaps)")
    try:
        before = calculate_coverage(results)
        print(f"BEFORE coverage: {before}")
        
        resolutions, updated_results = resolve_all_gaps(results)
        
        after = calculate_coverage(updated_results)
        print(f"AFTER coverage: {after}")
        
        print(f"Resolved {sum(1 for r in resolutions if r.resolved)} gaps.")
    except Exception as e:
        print(f"Error in Step 5: {e}")


if __name__ == "__main__":
    run_test()
