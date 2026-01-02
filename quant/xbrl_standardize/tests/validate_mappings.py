"""
Label Mapping Validation Script
Compares SEC and Nasdaq labels to validate mapping accuracy.
"""

import json
import os
from typing import Dict, List, Set

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

# Current mappings from compare_all.py
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
    "cashAndCashEquivalents": "Cash and Cash Equivalents",
    "shortTermInvestments": "Short-Term Investments",
    "netReceivables": "Net Receivables",
    "inventory": "Inventory",
    "totalCurrentAssets": "Total Current Assets",
    "longTermInvestments": "Long-Term Investments",
    "fixedAssets": "Fixed Assets",
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
    "depreciation": "Depreciation",
    "netCashFromOperating": "Net Cash Flow-Operating",
    "capitalExpenditures": "Capital Expenditures",
    "netCashFromInvesting": "Net Cash Flows-Investing",
    "netCashFromFinancing": "Net Cash Flows-Financing",
    "netCashFlow": "Net Cash Flow",
}

def load_cached_data(ticker: str) -> tuple:
    sec_path = os.path.join(CACHE_DIR, f"{ticker}_sec.json")
    nas_path = os.path.join(CACHE_DIR, f"{ticker}_nasdaq.json")
    
    sec, nas = None, None
    if os.path.exists(sec_path):
        with open(sec_path) as f:
            sec = json.load(f)
    if os.path.exists(nas_path):
        with open(nas_path) as f:
            nas = json.load(f)
    return sec, nas

def validate_mapping(sec_data: Dict, nas_data: Dict, mapping: Dict, statement_name: str):
    """Validates a single statement mapping."""
    sec_labels = set(sec_data.keys()) if sec_data else set()
    nas_labels = set(nas_data.keys()) if nas_data else set()
    
    mapped_sec = set(mapping.keys())
    mapped_nas = set(mapping.values())
    
    print(f"\n{'='*60}")
    print(f"{statement_name.upper()}")
    print('='*60)
    
    # Check SEC labels
    print(f"\n[SEC Labels] Total: {len(sec_labels)}")
    mapped_sec_found = mapped_sec & sec_labels
    unmapped_sec = sec_labels - mapped_sec
    print(f"  Mapped: {len(mapped_sec_found)}/{len(mapped_sec)}")
    if unmapped_sec:
        print(f"  UNMAPPED SEC Labels ({len(unmapped_sec)}):")
        for lbl in sorted(unmapped_sec)[:10]:
            print(f"    - {lbl}")
        if len(unmapped_sec) > 10:
            print(f"    ... and {len(unmapped_sec)-10} more")
    
    # Check Nasdaq labels
    print(f"\n[Nasdaq Labels] Total: {len(nas_labels)}")
    mapped_nas_found = mapped_nas & nas_labels
    unmapped_nas = nas_labels - mapped_nas
    print(f"  Mapped: {len(mapped_nas_found)}/{len(mapped_nas)}")
    if unmapped_nas:
        print(f"  UNMAPPED Nasdaq Labels ({len(unmapped_nas)}):")
        for lbl in sorted(unmapped_nas)[:10]:
            print(f"    - {lbl}")
        if len(unmapped_nas) > 10:
            print(f"    ... and {len(unmapped_nas)-10} more")
    
    # Check mapping accuracy
    print(f"\n[Mapping Validation]")
    missing_sec = mapped_sec - sec_labels
    missing_nas = mapped_nas - nas_labels
    
    if missing_sec:
        print(f"  SEC keys in mapping but NOT in data ({len(missing_sec)}):")
        for k in missing_sec:
            print(f"    - {k}")
    
    if missing_nas:
        print(f"  Nasdaq keys in mapping but NOT in data ({len(missing_nas)}):")
        for k in missing_nas:
            print(f"    - {k}")
    
    if not missing_sec and not missing_nas:
        print("  ✓ All mapped labels exist in data!")
    
    return {
        "sec_total": len(sec_labels),
        "sec_mapped": len(mapped_sec_found),
        "nas_total": len(nas_labels),
        "nas_mapped": len(mapped_nas_found),
        "missing_sec": list(missing_sec),
        "missing_nas": list(missing_nas),
        "unmapped_sec": list(unmapped_sec),
        "unmapped_nas": list(unmapped_nas),
    }

def main():
    # Get available tickers from cache
    tickers = set()
    for f in os.listdir(CACHE_DIR):
        if f.endswith("_sec.json"):
            tickers.add(f.replace("_sec.json", ""))
    
    print(f"Found {len(tickers)} cached tickers: {sorted(tickers)}")
    
    # Use first ticker for validation
    ticker = "AAPL"
    print(f"\n\nValidating mappings using {ticker} data...\n")
    
    sec, nas = load_cached_data(ticker)
    if not sec or not nas:
        print(f"Missing data for {ticker}")
        return
    
    results = {}
    results["IS"] = validate_mapping(sec.get("income_statement", {}), nas.get("income_statement", {}), IS_MAPPING, "Income Statement")
    results["BS"] = validate_mapping(sec.get("balance_sheet", {}), nas.get("balance_sheet", {}), BS_MAPPING, "Balance Sheet")
    results["CF"] = validate_mapping(sec.get("cash_flow", {}), nas.get("cash_flow", {}), CF_MAPPING, "Cash Flow")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for stmt, r in results.items():
        sec_pct = (r["sec_mapped"] / len(IS_MAPPING if stmt=="IS" else BS_MAPPING if stmt=="BS" else CF_MAPPING)) * 100
        nas_pct = (r["nas_mapped"] / len(IS_MAPPING if stmt=="IS" else BS_MAPPING if stmt=="BS" else CF_MAPPING)) * 100
        print(f"\n{stmt}:")
        print(f"  SEC Coverage: {r['sec_mapped']}/{r['sec_total']} labels mapped ({sec_pct:.0f}% of mapping)")
        print(f"  Nasdaq Coverage: {r['nas_mapped']}/{r['nas_total']} labels mapped ({nas_pct:.0f}% of mapping)")
        if r["missing_sec"]:
            print(f"  ⚠ Missing in SEC data: {r['missing_sec'][:3]}")
        if r["missing_nas"]:
            print(f"  ⚠ Missing in Nasdaq data: {r['missing_nas'][:3]}")

if __name__ == "__main__":
    main()
