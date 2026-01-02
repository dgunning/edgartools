"""
Compare SEC (is.py) and Nasdaq Income Statement Data
Uses nasdaq_api.py for cached API access and saves reports by ticker name.
"""

import json
import subprocess
import sys
import os
import re
from typing import Dict, Any

# Import cached API
from nasdaq_api import get_income_statement

# Map is.py keys to Nasdaq JSON keys
KEY_MAPPING = {
    "revenue": "Total Revenue",
    "costOfGoodsSold": "Cost of Revenue",
    "grossIncome": "Gross Profit",
    "researchDevelopment": "Research and Development",
    "sgaExpense": "Sales, General and Admin.",
    "operatingIncome": "Operating Income",
    "otherIncomeExpense": "Add'l income/expense items",
    "ebit": "Earnings Before Interest and Tax",
    "interestExpense": "Interest Expense",
    "pretaxIncome": "Earnings Before Tax",
    "provisionforIncomeTaxes": "Income Tax",
    "netIncome": "Net Income",
    "netIncomeApplicableToCommon": "Net Income Applicable to Common Shareholders",
    "equityEarnings": "Equity Earnings/Loss Unconsolidated Subsidiary",
    "minorityInterest": "Minority Interest",
    "otherOperatingIncome": "Other Operating Items"
}

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
EXTRACTORS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "extractors"))

def parse_currency_str(curr_str: str) -> float:
    if not isinstance(curr_str, str):
        return 0.0
    if curr_str == "--" or curr_str == "":
        return 0.0
    clean = curr_str.replace("$", "").replace(",", "")
    try:
        return float(clean)
    except ValueError:
        return 0.0

def get_nasdaq_data(ticker: str, frequency: str = "annual") -> Dict[str, str]:
    """Fetches Nasdaq data using cached API."""
    return get_income_statement(ticker, frequency)

def get_sec_data(ticker: str, form: str = "10-K") -> Dict[str, Any]:
    """Runs is.py to get SEC data."""
    script_path = os.path.join(EXTRACTORS_DIR, "is.py")
    cmd = [sys.executable, script_path, "--symbol", ticker, "--form", form]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                raise
        if data.get("financials"):
            return data["financials"][0]
    except subprocess.CalledProcessError as e:
        print(f"Error running is.py: {e.stderr}")
    except Exception as e:
        print(f"Error parsing is.py output: {e}")
    return {}

def compare(ticker: str, frequency: str = "annual"):
    """Compares SEC and Nasdaq Income Statement data."""
    print(f"Comparing {ticker} ({frequency})...")
    
    nasdaq = get_nasdaq_data(ticker, frequency)
    form = "10-K" if frequency == "annual" else "10-Q"
    sec = get_sec_data(ticker, form)

    if not nasdaq:
        print(f"No Nasdaq data for {ticker}")
        return
    if not sec:
        print(f"No SEC data for {ticker}")
        return

    # Determine scaling factor
    scale_factor = 1.0
    nasdaq_rev = parse_currency_str(nasdaq.get("Total Revenue", "0"))
    sec_rev = sec.get("revenue", 0)
    
    if nasdaq_rev > 0 and sec_rev > 0:
        ratio = sec_rev / nasdaq_rev
        if 900 < ratio < 1100:
            scale_factor = 1000.0
            print("Detected NASDAQ data is in Thousands (x1,000).")
        elif 900000 < ratio < 1100000:
            scale_factor = 1000000.0
            print("Detected NASDAQ data is in Millions (x1,000,000).")
    
    matches = []
    deltas = []
    missing_labels = []

    for sec_key, nas_key in KEY_MAPPING.items():
        n_val_raw = nasdaq.get(nas_key, "--")
        n_val = parse_currency_str(n_val_raw) * scale_factor
        
        s_val = sec.get(sec_key)
        s_val = float(s_val) if s_val is not None else 0.0

        # Use absolute values for comparison
        abs_s = abs(s_val)
        abs_n = abs(n_val)
        
        is_magnitude_match = False
        if abs_n != 0:
            diff_pct = abs((abs_s - abs_n) / abs_n)
            if diff_pct < 0.05:
                is_magnitude_match = True
        elif abs_s == 0:
            is_magnitude_match = True

        if is_magnitude_match:
            if (s_val >= 0 and n_val >= 0) or (s_val <= 0 and n_val <= 0):
                matches.append({"SEC Label": sec_key, "Nasdaq Label": nas_key, "Value": s_val})
            else:
                matches.append({"SEC Label": sec_key, "Nasdaq Label": nas_key, "Value": f"{s_val:,.0f} (Sign Diff)"})
        else:
            if abs_n != 0 and abs_s != 0:
                deltas.append({
                    "SEC Label": sec_key, "Nasdaq Label": nas_key,
                    "SEC Value": s_val, "Nasdaq Value": n_val, "Delta": s_val - n_val
                })
            else:
                missing_side = "SEC" if s_val == 0 else "Nasdaq"
                present_value = n_val if s_val == 0 else s_val
                missing_labels.append({
                    "SEC Label": sec_key, "Nasdaq Label": nas_key,
                    "Missing In": missing_side, "Existing Value": present_value
                })

    # Generate Markdown Report
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, f"{ticker}_IS_{frequency}.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Income Statement Comparison: {ticker} ({frequency.capitalize()})\n\n")
        f.write("> **Note:** Comparison uses absolute values. Matches with sign differences are noted.\n\n")
        
        f.write("## MATCH (Absolute Value)\n")
        if matches:
            f.write("| SEC Label | Nasdaq Label | SEC Value |\n|---|---|---|\n")
            for m in matches:
                val_disp = m['Value'] if isinstance(m['Value'], str) else f"{m['Value']:,.0f}"
                f.write(f"| {m['SEC Label']} | {m['Nasdaq Label']} | {val_disp} |\n")
        else:
            f.write("_No matches found._\n")
        f.write("\n")

        f.write("## MISSING LABEL\n")
        if missing_labels:
            f.write("| SEC Label | Nasdaq Label | Missing For | Existing Value |\n|---|---|---|---|\n")
            for m in missing_labels:
                f.write(f"| {m['SEC Label']} | {m['Nasdaq Label']} | {m['Missing In']} | {m['Existing Value']:,.0f} |\n")
        else:
            f.write("_No missing labels._\n")
        f.write("\n")

        f.write("## DELTA\n")
        if deltas:
            f.write("| SEC Label | Nasdaq Label | SEC Value | Nasdaq Value | Delta |\n|---|---|---|---|---|\n")
            for d in deltas:
                f.write(f"| {d['SEC Label']} | {d['Nasdaq Label']} | {d['SEC Value']:,.0f} | {d['Nasdaq Value']:,.0f} | {d['Delta']:,.0f} |\n")
        else:
            f.write("_No value deltas found._\n")
        f.write("\n")

    print(f"Report written to {report_path}")
    return report_path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        freq = sys.argv[2] if len(sys.argv) > 2 else "annual"
        compare(ticker, freq)
    else:
        print("Usage: python compare_financials.py TICKER [annual|quarterly]")
