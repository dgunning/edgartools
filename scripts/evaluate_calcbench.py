"""
Calcbench Reference Evaluation Script

Evaluates whether Calcbench can serve as a higher-quality reference source
than yfinance for XBRL standardized metrics validation.

Usage:
    pip install calcbench2
    python scripts/evaluate_calcbench.py

Compares our extracted values, yfinance values, and Calcbench values
for 10 diverse companies across all 37 tracked metrics.

NOTE: Calcbench requires a free account. Set environment variables:
    CALCBENCH_USERNAME=your_email
    CALCBENCH_PASSWORD=your_password
"""

import os
import sys
import json
from typing import Dict, Optional, List, Tuple

# Evaluation cohort: diverse companies across sectors
EVAL_COMPANIES = [
    "AAPL",  # Tech
    "JPM",   # Banking
    "XOM",   # Energy
    "WMT",   # Consumer
    "JNJ",   # Healthcare
    "NVDA",  # Semiconductor
    "PLD",   # REIT
    "MS",    # Investment Bank
    "DE",    # Industrial
    "EQIX",  # Data Center REIT
]

# Metric -> Calcbench standardized point mapping
# These are approximate — Calcbench uses its own taxonomy
METRIC_TO_CALCBENCH = {
    "Revenue": "Revenue",
    "COGS": "CostOfRevenue",
    "GrossProfit": "GrossProfit",
    "SGA": "SGAExpense",
    "OperatingIncome": "OperatingIncome",
    "PretaxIncome": "PreTaxIncome",
    "NetIncome": "NetIncome",
    "TotalAssets": "TotalAssets",
    "TotalLiabilities": "TotalLiabilities",
    "StockholdersEquity": "StockholdersEquity",
    "CashAndEquivalents": "CashAndEquivalents",
    "LongTermDebt": "LongTermDebt",
    "ShortTermDebt": "CurrentDebt",
    "OperatingCashFlow": "OperatingCashFlow",
    "Capex": "CapitalExpenditure",
    "AccountsReceivable": "AccountsReceivable",
    "AccountsPayable": "AccountsPayable",
    "Inventory": "Inventory",
    "Goodwill": "Goodwill",
    "IntangibleAssets": "IntangibleAssets",
    "DepreciationAmortization": "DepreciationAndAmortization",
    "InterestExpense": "InterestExpense",
    "IncomeTaxExpense": "IncomeTaxExpense",
    "WeightedAverageSharesDiluted": "DilutedSharesOutstanding",
}


def check_calcbench_available() -> bool:
    """Check if calcbench2 is installed and credentials are set."""
    try:
        import calcbench2 as cb
    except ImportError:
        print("ERROR: calcbench2 not installed. Run: pip install calcbench2")
        return False

    username = os.environ.get("CALCBENCH_USERNAME")
    password = os.environ.get("CALCBENCH_PASSWORD")
    if not username or not password:
        print("ERROR: Set CALCBENCH_USERNAME and CALCBENCH_PASSWORD environment variables")
        print("  Sign up for free at: https://www.calcbench.com/")
        return False

    try:
        cb.set_credentials(username, password)
        return True
    except Exception as e:
        print(f"ERROR: Calcbench authentication failed: {e}")
        return False


def fetch_calcbench_values(ticker: str) -> Dict[str, Optional[float]]:
    """Fetch standardized values from Calcbench for a company."""
    import calcbench2 as cb

    values = {}
    try:
        # Get most recent annual data
        data = cb.standardized(
            company_identifiers=[ticker],
            point_in_time=False,
            period_type="annual",
        )

        if data is not None and not data.empty:
            # Get the most recent year
            latest = data.iloc[-1] if len(data) > 0 else None
            if latest is not None:
                for our_metric, cb_metric in METRIC_TO_CALCBENCH.items():
                    try:
                        val = latest.get(cb_metric)
                        if val is not None and val == val:  # not NaN
                            values[our_metric] = float(val)
                    except (KeyError, TypeError, ValueError):
                        pass
    except Exception as e:
        print(f"  WARNING: Calcbench query failed for {ticker}: {e}")

    return values


def fetch_our_values(ticker: str) -> Dict[str, Optional[float]]:
    """Fetch our extracted values for a company."""
    from edgar import Company
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.config_loader import get_config

    try:
        config = get_config()
        orchestrator = Orchestrator(config=config)
        results = orchestrator.map_company(ticker, use_ai=False)
        return {
            metric: result.value
            for metric, result in results.items()
            if result.value is not None
        }
    except Exception as e:
        print(f"  WARNING: Our extraction failed for {ticker}: {e}")
        return {}


def fetch_yfinance_values(ticker: str) -> Dict[str, Optional[float]]:
    """Fetch yfinance reference values (from snapshot)."""
    from edgar.xbrl.standardization.reference_validator import ReferenceValidator
    from edgar.xbrl.standardization.config_loader import get_config

    try:
        config = get_config()
        validator = ReferenceValidator(config=config, snapshot_mode=True)
        ref_data = validator._get_yfinance_reference(ticker)
        if ref_data:
            return {k: v for k, v in ref_data.items() if v is not None}
    except Exception as e:
        print(f"  WARNING: yfinance snapshot failed for {ticker}: {e}")
    return {}


def compare_values(
    our_val: Optional[float],
    yf_val: Optional[float],
    cb_val: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Compute pairwise variance percentages."""
    def pct_var(a, b):
        if a is None or b is None or b == 0:
            return None
        return abs(a - b) / abs(b) * 100

    return (
        pct_var(our_val, yf_val),    # us vs yfinance
        pct_var(our_val, cb_val),    # us vs calcbench
        pct_var(yf_val, cb_val),     # yfinance vs calcbench
    )


def run_evaluation():
    """Run the full Calcbench evaluation."""
    from edgar import set_identity, use_local_storage
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    if not check_calcbench_available():
        print("\nTo evaluate without Calcbench, this script needs calcbench2 installed.")
        print("Alternatively, review Calcbench coverage at https://www.calcbench.com/")
        sys.exit(1)

    print("=" * 80)
    print("CALCBENCH REFERENCE EVALUATION")
    print("=" * 80)

    all_results = []

    for ticker in EVAL_COMPANIES:
        print(f"\n--- {ticker} ---")

        our = fetch_our_values(ticker)
        yf = fetch_yfinance_values(ticker)
        cb = fetch_calcbench_values(ticker)

        print(f"  Our metrics: {len(our)}, yfinance: {len(yf)}, Calcbench: {len(cb)}")

        for metric in sorted(set(list(our.keys()) + list(yf.keys()) + list(cb.keys()))):
            our_v = our.get(metric)
            yf_v = yf.get(metric)
            cb_v = cb.get(metric)

            us_yf, us_cb, yf_cb = compare_values(our_v, yf_v, cb_v)

            all_results.append({
                "ticker": ticker,
                "metric": metric,
                "our_value": our_v,
                "yfinance_value": yf_v,
                "calcbench_value": cb_v,
                "us_vs_yf_pct": us_yf,
                "us_vs_cb_pct": us_cb,
                "yf_vs_cb_pct": yf_cb,
            })

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    us_yf_matches = [r for r in all_results if r["us_vs_yf_pct"] is not None and r["us_vs_yf_pct"] <= 5]
    us_cb_matches = [r for r in all_results if r["us_vs_cb_pct"] is not None and r["us_vs_cb_pct"] <= 5]
    yf_cb_matches = [r for r in all_results if r["yf_vs_cb_pct"] is not None and r["yf_vs_cb_pct"] <= 5]

    us_yf_total = len([r for r in all_results if r["us_vs_yf_pct"] is not None])
    us_cb_total = len([r for r in all_results if r["us_vs_cb_pct"] is not None])
    yf_cb_total = len([r for r in all_results if r["yf_vs_cb_pct"] is not None])

    print(f"\nAgreement rates (within 5% tolerance):")
    print(f"  Us vs yfinance:  {len(us_yf_matches)}/{us_yf_total} ({len(us_yf_matches)/max(us_yf_total,1)*100:.0f}%)")
    print(f"  Us vs Calcbench: {len(us_cb_matches)}/{us_cb_total} ({len(us_cb_matches)/max(us_cb_total,1)*100:.0f}%)")
    print(f"  yfinance vs CB:  {len(yf_cb_matches)}/{yf_cb_total} ({len(yf_cb_matches)/max(yf_cb_total,1)*100:.0f}%)")

    # Coverage comparison
    cb_coverage = len([r for r in all_results if r["calcbench_value"] is not None])
    yf_coverage = len([r for r in all_results if r["yfinance_value"] is not None])
    print(f"\nCoverage:")
    print(f"  Calcbench: {cb_coverage}/{len(all_results)} metrics have values")
    print(f"  yfinance:  {yf_coverage}/{len(all_results)} metrics have values")

    # Where Calcbench agrees with us but yfinance doesn't
    cb_wins = [r for r in all_results
               if r["us_vs_cb_pct"] is not None and r["us_vs_cb_pct"] <= 5
               and (r["us_vs_yf_pct"] is None or r["us_vs_yf_pct"] > 5)]
    if cb_wins:
        print(f"\nCalcbench agrees with us where yfinance doesn't ({len(cb_wins)}):")
        for r in cb_wins[:10]:
            print(f"  {r['ticker']}:{r['metric']} — us_vs_cb={r['us_vs_cb_pct']:.1f}%, us_vs_yf={r['us_vs_yf_pct']:.1f}%" if r['us_vs_yf_pct'] else f"  {r['ticker']}:{r['metric']} — us_vs_cb={r['us_vs_cb_pct']:.1f}%, yfinance=N/A")

    # Save raw results
    output_file = "calcbench_evaluation_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nRaw results saved to: {output_file}")


if __name__ == "__main__":
    run_evaluation()
