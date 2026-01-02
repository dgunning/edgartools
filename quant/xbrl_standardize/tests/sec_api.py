"""
SEC Data Fetcher with Caching
Runs is.py, bs.py, cf.py and caches combined output as {ticker}_sec.json
"""

import subprocess
import sys
import os
import json
import time
import re
from typing import Dict, Any, Optional

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
CACHE_TTL_HOURS = 24
EXTRACTORS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "extractors"))

def _get_cache_path(ticker: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{ticker}_sec.json")

def _is_cache_valid(cache_path: str) -> bool:
    if not os.path.exists(cache_path):
        return False
    mtime = os.path.getmtime(cache_path)
    age_hours = (time.time() - mtime) / 3600
    return age_hours < CACHE_TTL_HOURS

def _run_extractor(script_name: str, ticker: str, form: str = "10-K") -> Dict[str, Any]:
    """Runs a single extractor script and returns parsed output."""
    script_path = os.path.join(EXTRACTORS_DIR, script_name)
    cmd = [sys.executable, script_path, "--symbol", ticker, "--form", form]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                return {}
        
        if data.get("financials"):
            return data["financials"][0]
    except subprocess.TimeoutExpired:
        print(f"[Timeout] {script_name} for {ticker}")
    except subprocess.CalledProcessError as e:
        print(f"[Error] {script_name}: {e.stderr[:200] if e.stderr else 'No stderr'}")
    except Exception as e:
        print(f"[Error] {script_name}: {e}")
    return {}

def fetch_sec_data(ticker: str, form: str = "10-K", force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Fetches all SEC financial data (IS, BS, CF) for a ticker with caching.
    
    Returns:
        Dictionary with keys: income_statement, balance_sheet, cash_flow, meta
    """
    cache_path = _get_cache_path(ticker)
    
    if not force_refresh and _is_cache_valid(cache_path):
        print(f"[SEC Cache Hit] {ticker}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    print(f"[SEC Fetch] Running extractors for {ticker}...")
    
    income_statement = _run_extractor("is.py", ticker, form)
    balance_sheet = _run_extractor("bs.py", ticker, form)
    cash_flow = _run_extractor("cf.py", ticker, form)
    
    data = {
        "ticker": ticker,
        "form": form,
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "meta": {
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_available": bool(income_statement),
            "bs_available": bool(balance_sheet),
            "cf_available": bool(cash_flow)
        }
    }
    
    # Save to cache
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"[SEC Cache] Saved to {cache_path}")
    
    return data

def clear_sec_cache(ticker: Optional[str] = None):
    """Clears SEC cache for a specific ticker or all."""
    if ticker:
        path = _get_cache_path(ticker)
        if os.path.exists(path):
            os.remove(path)
            print(f"Cleared SEC cache: {ticker}")
    else:
        for f in os.listdir(CACHE_DIR):
            if f.endswith("_sec.json"):
                os.remove(os.path.join(CACHE_DIR, f))
        print("All SEC cache cleared.")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Testing SEC fetch for {ticker}...")
    data = fetch_sec_data(ticker)
    print(f"IS fields: {list(data['income_statement'].keys())[:5]}...")
    print(f"BS fields: {list(data['balance_sheet'].keys())[:5]}...")
    print(f"CF fields: {list(data['cash_flow'].keys())[:5]}...")
