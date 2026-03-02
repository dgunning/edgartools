"""
yfinance Reference Snapshot System

Pins yfinance reference data to deterministic JSON snapshots so E2E pass rates
only change when extraction code changes, not when Yahoo revises their data.

Usage:
    from edgar.xbrl.standardization.yf_snapshot import (
        fetch_and_save_snapshot,
        load_snapshot,
        get_snapshot_value,
    )

    # Generate snapshot
    fetch_and_save_snapshot("AAPL")

    # Load and query
    snapshot = load_snapshot("AAPL")
    value = get_snapshot_value(snapshot, "financials", "Total Revenue", target_date, max_periods=4)
"""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

# Directory for per-company JSON snapshot files
SNAPSHOT_DIR = Path(__file__).parent / "config" / "yf_snapshots"

# All 6 yfinance sheet types to capture
SHEET_NAMES = [
    "financials",
    "quarterly_financials",
    "balance_sheet",
    "quarterly_balance_sheet",
    "cashflow",
    "quarterly_cashflow",
]

SCHEMA_VERSION = "1.0.0"


def fetch_and_save_snapshot(ticker: str, output_dir: Optional[Path] = None) -> Path:
    """Download all 6 yfinance sheets for a ticker and save as JSON.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL")
        output_dir: Directory to write JSON file (defaults to SNAPSHOT_DIR)

    Returns:
        Path to the written JSON file

    Raises:
        ImportError: If yfinance is not installed
        RuntimeError: If yfinance returns no data for any sheet
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance required: pip install yfinance")

    output_dir = output_dir or SNAPSHOT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    stock = yf.Ticker(ticker)

    snapshot: Dict = {
        "_metadata": {
            "ticker": ticker.upper(),
            "fetched_at": datetime.utcnow().isoformat(),
            "yfinance_version": getattr(yf, "__version__", "unknown"),
            "schema_version": SCHEMA_VERSION,
        }
    }

    for sheet_name in SHEET_NAMES:
        df = getattr(stock, sheet_name, None)
        if df is None or df.empty:
            snapshot[sheet_name] = {}
            continue

        sheet_data: Dict[str, Dict[str, float]] = {}
        for col in df.columns:
            # Convert column (date) to ISO string
            col_key = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col).split(" ")[0]

            row_data: Dict[str, float] = {}
            for field_name in df.index:
                val = df.loc[field_name, col]
                # Skip NaN / None values — omission = no data
                if val is None:
                    continue
                try:
                    fval = float(val)
                except (ValueError, TypeError):
                    continue
                if math.isnan(fval) or math.isinf(fval):
                    continue
                row_data[str(field_name)] = fval

            if row_data:
                sheet_data[col_key] = row_data

        snapshot[sheet_name] = sheet_data

    out_path = output_dir / f"{ticker.upper()}.json"
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    return out_path


def load_snapshot(ticker: str, snapshot_dir: Optional[Path] = None) -> Optional[Dict]:
    """Load a snapshot JSON file from disk.

    Args:
        ticker: Stock ticker symbol
        snapshot_dir: Directory containing snapshots (defaults to SNAPSHOT_DIR)

    Returns:
        Parsed dict or None if file does not exist
    """
    snapshot_dir = snapshot_dir or SNAPSHOT_DIR
    path = snapshot_dir / f"{ticker.upper()}.json"

    if not path.exists():
        return None

    with open(path, "r") as f:
        return json.load(f)


def get_snapshot_value(
    snapshot: Dict,
    sheet_name: str,
    field_name: str,
    target_date: Optional[Union[str, datetime]] = None,
    max_periods: int = 4,
) -> Optional[float]:
    """Look up a value from a snapshot dict, mirroring _get_yfinance_value date-matching logic.

    Args:
        snapshot: Loaded snapshot dict (from load_snapshot)
        sheet_name: One of the 6 yfinance sheet names (e.g. "financials")
        field_name: Row label in the sheet (e.g. "Total Revenue")
        target_date: Optional specific date to match (within 7 days)
        max_periods: Max periods to try when no target_date

    Returns:
        Float value or None
    """
    if snapshot is None:
        return None

    sheet_data = snapshot.get(sheet_name)
    if not sheet_data or not isinstance(sheet_data, dict):
        return None

    # DATE MATCHING LOGIC (mirrors ReferenceValidator._get_yfinance_value)
    if target_date:
        # Normalize target_date to datetime
        if isinstance(target_date, str):
            try:
                if "T" in target_date:
                    target_date = target_date.split("T")[0]
                t_date = datetime.strptime(target_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                t_date = None
        else:
            t_date = target_date

        if t_date:
            best_col = None
            min_diff = 365

            for col_key in sheet_data:
                try:
                    col_date = datetime.strptime(col_key, "%Y-%m-%d")
                    diff = abs((col_date - t_date).days)
                    if diff <= 7 and diff < min_diff:
                        min_diff = diff
                        best_col = col_key
                except (ValueError, TypeError):
                    continue

            if best_col is not None:
                val = sheet_data[best_col].get(field_name)
                if val is not None:
                    return float(val)

            # No date match — return None (don't fallback to random date)
            return None

    # DEFAULT LOGIC: no target_date — try first N periods (sorted newest-first)
    sorted_cols = sorted(sheet_data.keys(), reverse=True)
    for col_key in sorted_cols[:max_periods]:
        val = sheet_data[col_key].get(field_name)
        if val is not None:
            return float(val)

    return None
