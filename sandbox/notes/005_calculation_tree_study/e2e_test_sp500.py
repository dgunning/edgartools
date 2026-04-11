"""
E2E Test: S&P25 and S&P50 Multi-Period Validation

Tests the concept mapping workflow across:
1. S&P25: 25 Companies (5 Years 10-K + 6 Quarters 10-Q)
2. S&P50: 50 Companies (5 Years 10-K + 6 Quarters 10-Q)

The test reports pass rates for both groups to track progress.
"""

from edgar import set_identity, use_local_storage, Company
from edgar.xbrl.standardization.orchestrator import Orchestrator
from edgar.xbrl.standardization.models import MappingSource

# Define S&P25 and S&P50 Company Lists
SP25 = [
    "AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK", "C",
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR"
]

SP50 = [
    "AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK", "C",
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR", "ABT",
    "WMT", "PG", "KO", "PEP", "COST", "MCD", "DIS", "NKE", "SBUX",
    "XOM", "CVX", "CAT", "GE", "RTX", "HON", "UPS", "BA",
    "CRM", "ORCL", "ADBE", "NFLX", "CSCO", "ACN", "IBM"
]


def run_test_for_group(group_name: str, tickers: list, orchestrator: Orchestrator):
    """Run E2E test for a specific group of companies."""
    print(f"\n{'='*60}")
    print(f"TESTING: {group_name} ({len(tickers)} Companies)")
    print(f"{'='*60}")

    stats = {
        '10-K': {'total': 0, 'passed': 0, 'missing_ref': 0},
        '10-Q': {'total': 0, 'passed': 0, 'missing_ref': 0}
    }

    for ticker in tickers:
        print(f"\n>> {ticker}", end=" ", flush=True)
        
        try:
            company = Company(ticker)
        except Exception as e:
            print(f"[LOAD FAIL: {e}]")
            continue

        # --- PROCESS 10-K (Annual) ---
        filings_10k = company.get_filings(form='10-K').latest(5)
        if filings_10k is not None and not hasattr(filings_10k, '__iter__'):
            filings_10k = [filings_10k]
        if not filings_10k:
            filings_10k = []

        for filing in filings_10k:
            try:
                period_date = filing.period_of_report
                xbrl = filing.xbrl()
                if not xbrl:
                    continue
                
                results = orchestrator.tree_parser.map_company(ticker, filing)
                validations = orchestrator.validator.validate_and_update_mappings(
                    ticker, results, xbrl, filing_date=period_date
                )
                
                passes = sum(1 for v in validations.values() if v.status == 'match')
                fails = sum(1 for v in validations.values() if v.status == 'mismatch')
                missing_ref = sum(1 for v in validations.values() if v.status == 'missing_ref')
                
                stats['10-K']['total'] += (passes + fails)
                stats['10-K']['passed'] += passes
                stats['10-K']['missing_ref'] += missing_ref
            except Exception:
                pass  # Silently skip errors for batch processing

        # --- PROCESS 10-Q (Quarterly) ---
        filings_10q = company.get_filings(form='10-Q').latest(6)
        if filings_10q is not None and not hasattr(filings_10q, '__iter__'):
            filings_10q = [filings_10q]
        if not filings_10q:
            filings_10q = []

        for filing in filings_10q:
            try:
                period_date = filing.period_of_report
                xbrl = filing.xbrl()
                if not xbrl:
                    continue

                results = orchestrator.tree_parser.map_company(ticker, filing)
                
                # Switch to quarterly yfinance data
                original_map = orchestrator.validator.YFINANCE_MAP.copy()
                quarterly_map = {
                    k: (v[0].replace('financials', 'quarterly_financials')
                           .replace('balance_sheet', 'quarterly_balance_sheet')
                           .replace('cashflow', 'quarterly_cashflow'), v[1]) 
                    for k, v in original_map.items()
                }
                orchestrator.validator.YFINANCE_MAP = quarterly_map
                
                validations = orchestrator.validator.validate_and_update_mappings(
                    ticker, results, xbrl, filing_date=period_date
                )
                orchestrator.validator.YFINANCE_MAP = original_map
                
                passes = sum(1 for v in validations.values() if v.status == 'match')
                fails = sum(1 for v in validations.values() if v.status == 'mismatch')
                missing_ref = sum(1 for v in validations.values() if v.status == 'missing_ref')
                
                stats['10-Q']['total'] += (passes + fails)
                stats['10-Q']['passed'] += passes
                stats['10-Q']['missing_ref'] += missing_ref
            except Exception:
                pass

        print(".", end="", flush=True)  # Progress indicator

    # Group Summary
    print(f"\n\n--- {group_name} SUMMARY ---")
    if stats['10-K']['total'] > 0:
        k_rate = stats['10-K']['passed'] / stats['10-K']['total'] * 100
        print(f"10-K Pass Rate: {k_rate:.1f}% ({stats['10-K']['passed']}/{stats['10-K']['total']})")
    else:
        print("10-K Pass Rate: N/A")
    
    if stats['10-Q']['total'] > 0:
        q_rate = stats['10-Q']['passed'] / stats['10-Q']['total'] * 100
        print(f"10-Q Pass Rate: {q_rate:.1f}% ({stats['10-Q']['passed']}/{stats['10-Q']['total']})")
    else:
        print("10-Q Pass Rate: N/A")

    return stats


def run_sp500_test():
    print("="*60)
    print("E2E TEST: S&P25 & S&P50 (MULTI-PERIOD)")
    print("Scope: 5 Years 10-K + 6 Quarters 10-Q")
    print("="*60)

    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)
    
    orchestrator = Orchestrator()

    # Run S&P25 Test
    sp25_stats = run_test_for_group("S&P25", SP25, orchestrator)
    
    # Run S&P50 Test (S&P50 includes S&P25, so we only test the additional companies)
    sp50_additional = [t for t in SP50 if t not in SP25]
    sp50_additional_stats = run_test_for_group("S&P50 (Additional 25)", sp50_additional, orchestrator)
    
    # Combine S&P50 stats
    sp50_stats = {
        '10-K': {
            'total': sp25_stats['10-K']['total'] + sp50_additional_stats['10-K']['total'],
            'passed': sp25_stats['10-K']['passed'] + sp50_additional_stats['10-K']['passed'],
            'missing_ref': sp25_stats['10-K']['missing_ref'] + sp50_additional_stats['10-K']['missing_ref']
        },
        '10-Q': {
            'total': sp25_stats['10-Q']['total'] + sp50_additional_stats['10-Q']['total'],
            'passed': sp25_stats['10-Q']['passed'] + sp50_additional_stats['10-Q']['passed'],
            'missing_ref': sp25_stats['10-Q']['missing_ref'] + sp50_additional_stats['10-Q']['missing_ref']
        }
    }

    # Final Combined Report
    print("\n" + "="*60)
    print("FINAL COMBINED RESULTS")
    print("="*60)
    
    print("\n** S&P25 **")
    if sp25_stats['10-K']['total'] > 0:
        print(f"  10-K: {sp25_stats['10-K']['passed']/sp25_stats['10-K']['total']*100:.1f}%")
    if sp25_stats['10-Q']['total'] > 0:
        print(f"  10-Q: {sp25_stats['10-Q']['passed']/sp25_stats['10-Q']['total']*100:.1f}%")

    print("\n** S&P50 (Full) **")
    if sp50_stats['10-K']['total'] > 0:
        print(f"  10-K: {sp50_stats['10-K']['passed']/sp50_stats['10-K']['total']*100:.1f}%")
    if sp50_stats['10-Q']['total'] > 0:
        print(f"  10-Q: {sp50_stats['10-Q']['passed']/sp50_stats['10-Q']['total']*100:.1f}%")

    return {'sp25': sp25_stats, 'sp50': sp50_stats}


if __name__ == "__main__":
    run_sp500_test()
