#!/usr/bin/env python3
"""
Refresh yfinance reference snapshots.

Downloads current yfinance data for each company and saves it as a JSON snapshot
in config/yf_snapshots/. These snapshots are used by the E2E test runner so that
pass rates are deterministic and only change when extraction code changes.

Usage:
    # Refresh all companies from companies.yaml
    python -m edgar.xbrl.standardization.tools.refresh_yf_snapshots

    # Refresh specific tickers
    python -m edgar.xbrl.standardization.tools.refresh_yf_snapshots --tickers AAPL,MSFT,GOOG

    # Dry run — show what would be refreshed
    python -m edgar.xbrl.standardization.tools.refresh_yf_snapshots --dry-run
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from edgar.xbrl.standardization.config_loader import get_config
from edgar.xbrl.standardization.yf_snapshot import (
    SNAPSHOT_DIR,
    fetch_and_save_snapshot,
    load_snapshot,
)


def get_all_tickers() -> list:
    """Get all company tickers from companies.yaml."""
    config = get_config()
    return sorted(config.companies.keys())


def main():
    parser = argparse.ArgumentParser(description="Refresh yfinance reference snapshots")
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers to refresh (default: all from companies.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be refreshed without downloading",
    )
    args = parser.parse_args()

    # Determine tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        tickers = get_all_tickers()

    print(f"yfinance Snapshot Refresh")
    print(f"{'=' * 50}")
    print(f"Tickers: {len(tickers)}")
    print(f"Snapshot dir: {SNAPSHOT_DIR}")
    print()

    if args.dry_run:
        print("DRY RUN — no downloads will be performed\n")
        for ticker in tickers:
            snapshot = load_snapshot(ticker)
            if snapshot:
                meta = snapshot.get("_metadata", {})
                fetched = meta.get("fetched_at", "unknown")
                version = meta.get("yfinance_version", "unknown")
                print(f"  {ticker}: last fetched {fetched} (yfinance {version})")
            else:
                print(f"  {ticker}: NO SNAPSHOT — would be created")
        return

    # Download snapshots
    succeeded = 0
    failed = []

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        try:
            path = fetch_and_save_snapshot(ticker)
            snapshot = load_snapshot(ticker)
            sheet_count = sum(
                1
                for k in snapshot
                if k != "_metadata" and snapshot[k]
            )
            print(f"OK ({sheet_count}/6 sheets with data) -> {path.name}")
            succeeded += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append((ticker, str(e)))

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Results: {succeeded}/{len(tickers)} succeeded")
    if failed:
        print(f"Failed ({len(failed)}):")
        for ticker, err in failed:
            print(f"  {ticker}: {err}")


if __name__ == "__main__":
    main()
