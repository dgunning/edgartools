"""
Nasdaq API Client with File Caching
Fetches all statements (IS, BS, CF) and caches as {ticker}_nasdaq.json
"""

import requests
import json
import os
import time
from typing import Dict, Any, Optional

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
CACHE_TTL_HOURS = 240

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'application/json, text/plain, */*'
}

def _get_cache_path(ticker: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{ticker}_nasdaq.json")

def _is_cache_valid(cache_path: str) -> bool:
    if not os.path.exists(cache_path):
        return False
    mtime = os.path.getmtime(cache_path)
    age_hours = (time.time() - mtime) / 3600
    return age_hours < CACHE_TTL_HOURS

def _parse_table(table_data: Dict) -> Dict[str, str]:
    """Parses Nasdaq table format into {label: value} dict (most recent period)."""
    result = {}
    for row in table_data.get("rows", []):
        label = row.get("value1", "")
        value = row.get("value2", "")  # Most recent period
        if label and label.strip():
            result[label] = value
    return result

def fetch_nasdaq_data(ticker: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Fetches all Nasdaq financial data (IS, BS, CF) for a ticker with caching.
    
    Returns:
        Dictionary with keys: income_statement, balance_sheet, cash_flow, meta
    """
    cache_path = _get_cache_path(ticker)
    
    if not force_refresh and _is_cache_valid(cache_path):
        print(f"[Nasdaq Cache Hit] {ticker}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Fetch from API (annual data)
    url = f"https://api.nasdaq.com/api/company/{ticker}/financials?frequency=1"
    print(f"[Nasdaq Fetch] {ticker} from API...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            api_data = response.json()
            if 'data' not in api_data or not api_data['data']:
                print(f"[Warning] No data for {ticker}")
                return None
            
            raw = api_data['data']
            
            # Parse each table
            income_statement = _parse_table(raw.get("incomeStatementTable", {}))
            balance_sheet = _parse_table(raw.get("balanceSheetTable", {}))
            cash_flow = _parse_table(raw.get("cashFlowTable", {}))
            
            data = {
                "ticker": ticker,
                "income_statement": income_statement,
                "balance_sheet": balance_sheet,
                "cash_flow": cash_flow,
                "meta": {
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_labels": len(income_statement),
                    "bs_labels": len(balance_sheet),
                    "cf_labels": len(cash_flow)
                }
            }
            
            # Save to cache
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"[Nasdaq Cache] Saved to {cache_path}")
            
            return data
        else:
            print(f"[Error] API returned {response.status_code}")
            return None
    except Exception as e:
        print(f"[Error] Failed to fetch {ticker}: {e}")
        return None

def clear_nasdaq_cache(ticker: Optional[str] = None):
    """Clears Nasdaq cache for a specific ticker or all."""
    if ticker:
        path = _get_cache_path(ticker)
        if os.path.exists(path):
            os.remove(path)
            print(f"Cleared Nasdaq cache: {ticker}")
    else:
        for f in os.listdir(CACHE_DIR):
            if f.endswith("_nasdaq.json"):
                os.remove(os.path.join(CACHE_DIR, f))
        print("All Nasdaq cache cleared.")

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Testing Nasdaq fetch for {ticker}...")
    data = fetch_nasdaq_data(ticker)
    if data:
        print(f"IS labels: {list(data['income_statement'].keys())[:5]}...")
        print(f"BS labels: {list(data['balance_sheet'].keys())[:5]}...")
        print(f"CF labels: {list(data['cash_flow'].keys())[:5]}...")
