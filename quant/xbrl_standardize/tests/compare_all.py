"""
Full Financial Comparison: SEC vs Nasdaq
Compares Income Statement, Balance Sheet, and Cash Flow.
Generates unified {ticker}_report.md
"""

import os
import sys
from typing import Dict, Any, List, Tuple

from sec_api import fetch_sec_data
from nasdaq_api import fetch_nasdaq_data

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

# Key mappings for each statement
IS_MAPPING = {
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
}

BS_MAPPING = {
    "cash": "Cash and Cash Equivalents",
    "shortTermInvestments": "Short-Term Investments",
    "accountsReceivable": "Net Receivables",
    "inventory": "Inventory",
    "totalCurrentAssets": "Total Current Assets",
    "longTermInvestments": "Long-Term Investments",
    "propertyPlantEquipment": "Fixed Assets",
    "totalAssets": "Total Assets",
    "accountsPayable": "Accounts Payable",
    "shortTermDebt": "Short-Term Debt / Current Portion of Long-Term Debt",
    "totalCurrentLiabilities": "Total Current Liabilities",
    "longTermDebt": "Long-Term Debt",
    "totalLiabilities": "Total Liabilities",
    "totalEquity": "Total Equity",
}

CF_MAPPING = {
    "netIncome": "Net Income",
    "depreciationAndAmortization": "Depreciation",
    "operatingCashFlow": "Net Cash Flow-Operating",
    "capitalExpenditures": "Capital Expenditures",
    "investingCashFlow": "Net Cash Flows-Investing",
    "financingCashFlow": "Net Cash Flows-Financing",
    "netChangeInCash": "Net Cash Flow",
}

def parse_currency(val: str) -> float:
    if not isinstance(val, str) or val in ("--", ""):
        return 0.0
    clean = val.replace("$", "").replace(",", "")
    try:
        return float(clean)
    except ValueError:
        return 0.0

def detect_scale(sec_val: float, nas_val: float) -> float:
    if nas_val == 0 or sec_val == 0:
        return 1.0
    ratio = sec_val / nas_val
    if 900 < ratio < 1100:
        return 1000.0
    elif 900000 < ratio < 1100000:
        return 1000000.0
    return 1.0

def compare_statements(sec_data: Dict, nasdaq_data: Dict, mapping: Dict, scale: float) -> Tuple[List, List, List]:
    """Compares SEC and Nasdaq data for a single statement."""
    matches = []
    deltas = []
    missing = []
    
    for sec_key, nas_key in mapping.items():
        n_val = parse_currency(nasdaq_data.get(nas_key, "--")) * scale
        s_val = float(sec_data.get(sec_key, 0) or 0)
        
        abs_s, abs_n = abs(s_val), abs(n_val)
        
        is_match = False
        if abs_n != 0:
            if abs((abs_s - abs_n) / abs_n) < 0.05:
                is_match = True
        elif abs_s == 0:
            is_match = True
        
        if is_match:
            sign_note = " (Sign Diff)" if (s_val * n_val < 0) else ""
            matches.append({"SEC": sec_key, "Nasdaq": nas_key, "Value": f"{s_val:,.0f}{sign_note}"})
        else:
            if abs_n != 0 and abs_s != 0:
                deltas.append({"SEC": sec_key, "Nasdaq": nas_key, "SEC Val": s_val, "Nasdaq Val": n_val, "Delta": s_val - n_val})
            else:
                side = "SEC" if s_val == 0 else "Nasdaq"
                val = n_val if s_val == 0 else s_val
                missing.append({"SEC": sec_key, "Nasdaq": nas_key, "Missing": side, "Value": val})
    
    return matches, deltas, missing

def write_report(ticker: str, is_result: Tuple, bs_result: Tuple, cf_result: Tuple, scale: float):
    """Writes combined markdown report."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, f"{ticker}_report.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Financial Comparison Report: {ticker}\n\n")
        f.write(f"> Scale factor: x{scale:,.0f}\n\n")
        
        for title, result in [("Income Statement", is_result), ("Balance Sheet", bs_result), ("Cash Flow", cf_result)]:
            matches, deltas, missing = result
            f.write(f"## {title}\n\n")
            
            # Matches
            f.write("### Matches\n")
            if matches:
                f.write("| SEC Label | Nasdaq Label | Value |\n|---|---|---|\n")
                for m in matches:
                    f.write(f"| {m['SEC']} | {m['Nasdaq']} | {m['Value']} |\n")
            else:
                f.write("_None_\n")
            f.write("\n")
            
            # Missing
            if missing:
                f.write("### Missing\n| SEC Label | Nasdaq Label | Missing In | Value |\n|---|---|---|---|\n")
                for m in missing:
                    f.write(f"| {m['SEC']} | {m['Nasdaq']} | {m['Missing']} | {m['Value']:,.0f} |\n")
                f.write("\n")
            
            # Deltas
            if deltas:
                f.write("### Deltas\n| SEC Label | Nasdaq Label | SEC Value | Nasdaq Value | Delta |\n|---|---|---|---|---|\n")
                for d in deltas:
                    f.write(f"| {d['SEC']} | {d['Nasdaq']} | {d['SEC Val']:,.0f} | {d['Nasdaq Val']:,.0f} | {d['Delta']:,.0f} |\n")
                f.write("\n")
            
            f.write("---\n\n")
    
    print(f"Report saved: {report_path}")
    return report_path

def run_comparison(ticker: str):
    """Runs full comparison for a ticker."""
    print(f"\n{'='*50}")
    print(f"Processing: {ticker}")
    print('='*50)
    
    sec = fetch_sec_data(ticker)
    nasdaq = fetch_nasdaq_data(ticker)
    
    if not sec or not nasdaq:
        print(f"[Error] Missing data for {ticker}")
        return None
    
    # Detect scale from revenue
    sec_rev = float(sec["income_statement"].get("revenue", 0) or 0)
    nas_rev = parse_currency(nasdaq["income_statement"].get("Total Revenue", "0"))
    scale = detect_scale(sec_rev, nas_rev)
    print(f"[Scale] Detected: x{scale:,.0f}")
    
    is_result = compare_statements(sec["income_statement"], nasdaq["income_statement"], IS_MAPPING, scale)
    bs_result = compare_statements(sec["balance_sheet"], nasdaq["balance_sheet"], BS_MAPPING, scale)
    cf_result = compare_statements(sec["cash_flow"], nasdaq["cash_flow"], CF_MAPPING, scale)
    
    return write_report(ticker, is_result, bs_result, cf_result, scale)

def run_all_tickers(tickers: List[str]):
    """Runs comparison for all provided tickers."""
    results = {}
    for ticker in tickers:
        try:
            report = run_comparison(ticker)
            results[ticker] = "Success" if report else "Failed"
        except Exception as e:
            print(f"[Error] {ticker}: {e}")
            results[ticker] = f"Error: {e}"
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    for t, status in results.items():
        print(f"  {t}: {status}")
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        # Default tickers from provided JSON files
        tickers = ["AAPL", "BAC", "NVDA", "TSLA", "META", "JPM", "SHOP", "SNAP", "OXY", "URI"]
    
    run_all_tickers(tickers)
