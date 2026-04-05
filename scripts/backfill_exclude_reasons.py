#!/usr/bin/env python3
"""
Backfill exclude_metrics from list format to dict format with classified reasons.

Part of Consensus 018: CQS Scoring Integrity Reform.

Reads companies.yaml, converts each exclude_metrics list entry to dict format
with a classified reason (not_applicable, extraction_failed, semantic_mismatch).

Usage:
    python scripts/backfill_exclude_reasons.py --dry-run    # Preview changes
    python scripts/backfill_exclude_reasons.py --apply       # Apply changes
"""

import argparse
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "edgar" / "xbrl" / "standardization" / "config" / "companies.yaml"

# ─── Classification heuristics ───────────────────────────────────────────────

# Banking companies (from industry config or known GSIBs)
BANKING_TICKERS = {"JPM", "BAC", "GS", "MS", "C", "BLK", "SCHW", "WFC", "USB", "PNC", "TFC", "COF", "BK", "STT", "FITB", "KEY", "HBAN", "RF", "CFG", "MTB"}

# Banking-specific metrics that truly don't apply
BANKING_NA_METRICS = {"COGS", "SGA", "Inventory", "AccountsPayable", "AccountsReceivable", "ResearchAndDevelopment"}

# Pure software/SaaS/services companies where COGS truly doesn't apply
PURE_SERVICES_TICKERS = {"META", "CRM", "ADBE", "SNOW", "NFLX", "V", "MA", "AXP", "PANW", "NOW", "WDAY", "TEAM", "ZS", "CRWD", "DDOG", "NET", "PLTR", "UBER", "ABNB"}

# Companies known to not pay dividends
NON_DIVIDEND_PAYERS = {"AMZN", "TSLA", "SNOW", "ADBE", "NFLX", "PANW", "META", "GOOG", "CRM", "UBER", "ABNB", "PLTR"}

# Hardware/semiconductor companies that DO report CostOfRevenue — COGS exclusion is likely extraction failure
HARDWARE_SEMI_TICKERS = {"CSCO", "INTC", "AMD", "TXN", "AVGO", "IBM", "MU", "QCOM", "AMAT", "LRCX", "KLAC", "ADI", "MCHP", "ON", "NXPI"}

# Companies where OperatingIncome exclusion is likely extraction failure (also in known_divergences)
OPERATING_INCOME_EXTRACTION_FAILED = {"DE", "JNJ", "COP", "SLB", "NKE", "INTC", "LLY", "BRK-B"}

# Companies where ShortTermDebt exclusion is likely extraction failure
SHORT_TERM_DEBT_EXTRACTION_FAILED = {"SNOW", "CAT", "COP", "HD", "MA", "RTX", "KO", "NEE"}

# Insurance / conglomerate companies where COGS doesn't apply
INSURANCE_CONGLOMERATE_TICKERS = {"BRK-B", "ALL", "AIG", "MET", "PRU", "TRV", "CB", "AFL", "AJG", "MMC", "AON"}

# Utility companies where COGS may not apply
UTILITY_TICKERS = {"NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "ED", "WEC", "ES", "PPL", "FE", "CMS", "AES", "ETR", "AWK"}

# REIT companies where certain metrics don't apply
REIT_TICKERS = {"PLD", "AMT", "CCI", "EQIX", "PSA", "SPG", "O", "WELL", "DLR", "AVB", "EQR", "VTR", "ARE", "MAA", "ESS", "UDR"}

# Transportation companies where COGS doesn't apply (expense-by-nature)
TRANSPORT_TICKERS = {"FDX", "UPS"}


def classify_exclusion(ticker: str, metric: str, company_data: dict) -> dict:
    """Classify an exclusion and return {"reason": ..., "notes": ...}."""
    industry = company_data.get("industry", "")
    known_divs = company_data.get("known_divergences", {})

    # Rule 1: Banking + banking-specific metrics → not_applicable
    if ticker in BANKING_TICKERS and metric in BANKING_NA_METRICS:
        return {"reason": "not_applicable", "notes": f"Banking company — {metric} not applicable"}

    # Rule 2: DividendsPaid for known non-dividend payers → not_applicable
    if metric == "DividendsPaid" and ticker in NON_DIVIDEND_PAYERS:
        return {"reason": "not_applicable", "notes": "Company does not pay dividends"}

    # Rule 3: COGS for pure SaaS/services → not_applicable
    if metric == "COGS" and ticker in PURE_SERVICES_TICKERS:
        return {"reason": "not_applicable", "notes": "Pure services/platform company — no cost of goods"}

    # Rule 4: COGS for insurance/conglomerate → not_applicable
    if metric == "COGS" and ticker in INSURANCE_CONGLOMERATE_TICKERS:
        return {"reason": "not_applicable", "notes": "Insurance/conglomerate — COGS not applicable"}

    # Rule 5: COGS for transportation (expense-by-nature) → not_applicable
    if metric == "COGS" and ticker in TRANSPORT_TICKERS:
        return {"reason": "not_applicable", "notes": "Transportation company — expense-by-nature format, no COGS line"}

    # Rule 6: COGS for hardware/semiconductor → extraction_failed
    if metric == "COGS" and ticker in HARDWARE_SEMI_TICKERS:
        return {"reason": "extraction_failed", "notes": "Hardware/semi company reports CostOfRevenue — extraction should work"}

    # Rule 7: OperatingIncome also in known_divergences → extraction_failed
    if metric == "OperatingIncome" and (metric in known_divs or ticker in OPERATING_INCOME_EXTRACTION_FAILED):
        return {"reason": "extraction_failed", "notes": "Dual-listed in exclude + known_divergences — extraction gap"}

    # Rule 8: ShortTermDebt for known extraction failures → extraction_failed
    if metric == "ShortTermDebt" and ticker in SHORT_TERM_DEBT_EXTRACTION_FAILED:
        return {"reason": "extraction_failed", "notes": "ShortTermDebt extraction gap — debt exists but extraction fails"}

    # Rule 9: Inventory for pure services/SaaS → not_applicable
    if metric == "Inventory" and ticker in PURE_SERVICES_TICKERS:
        return {"reason": "not_applicable", "notes": "Services company — no physical inventory"}

    # Rule 10: Goodwill/IntangibleAssets for companies that truly have none → not_applicable
    if metric in ("Goodwill", "IntangibleAssets") and ticker in ("AAPL", "NSC"):
        return {"reason": "not_applicable", "notes": f"{ticker} reports minimal/no {metric}"}

    # Rule 11: IntangibleAssets for TSLA → not_applicable (negligible)
    if metric == "IntangibleAssets" and ticker == "TSLA":
        return {"reason": "not_applicable", "notes": "TSLA has negligible intangible assets"}

    # Rule 12: Capex for insurance companies → not_applicable
    if metric == "Capex" and ticker in INSURANCE_CONGLOMERATE_TICKERS:
        return {"reason": "not_applicable", "notes": "Insurance company — minimal Capex"}

    # Rule 13: ResearchAndDevelopment for retail → not_applicable
    if metric == "ResearchAndDevelopment" and ticker in ("WMT", "COST", "HD", "LOW", "TGT", "KR"):
        return {"reason": "not_applicable", "notes": "Retail company — no R&D spending"}

    # Rule 14: COGS for energy companies → not_applicable (industry structural)
    if metric == "COGS" and industry == "energy":
        return {"reason": "not_applicable", "notes": "Energy company — cost structure differs from COGS"}

    # Rule 15: COGS for REIT companies → not_applicable
    if metric == "COGS" and ticker in REIT_TICKERS:
        return {"reason": "not_applicable", "notes": "REIT — no cost of goods sold"}

    # Rule 16: Inventory for REIT/utility → not_applicable
    if metric == "Inventory" and (ticker in REIT_TICKERS or ticker in UTILITY_TICKERS):
        return {"reason": "not_applicable", "notes": "REIT/Utility — no inventory"}

    # Default: conservative — not_applicable
    return {"reason": "not_applicable", "notes": ""}


def backfill(dry_run: bool = True):
    """Read companies.yaml, classify exclusions, optionally apply."""
    with open(CONFIG_PATH, 'r') as f:
        data = yaml.safe_load(f)

    companies = data.get("companies", {})
    changes = []
    extraction_failed_count = 0
    not_applicable_count = 0
    already_dict_count = 0

    for ticker, company_data in sorted(companies.items()):
        raw_excludes = company_data.get("exclude_metrics")
        if raw_excludes is None:
            continue

        if isinstance(raw_excludes, dict):
            already_dict_count += len(raw_excludes)
            continue

        if not isinstance(raw_excludes, list):
            continue

        new_excludes = {}
        for metric in raw_excludes:
            entry = classify_exclusion(ticker, metric, company_data)
            new_excludes[metric] = entry

            if entry["reason"] == "extraction_failed":
                extraction_failed_count += 1
                changes.append(f"  [EXTRACTION_FAILED] {ticker}:{metric} — {entry['notes']}")
            else:
                not_applicable_count += 1
                changes.append(f"  [not_applicable]    {ticker}:{metric} — {entry['notes']}")

        if not dry_run:
            company_data["exclude_metrics"] = new_excludes

    # Summary
    total = extraction_failed_count + not_applicable_count
    print(f"\n{'DRY RUN' if dry_run else 'APPLIED'}: Backfill exclude_metrics reasons")
    print(f"  Total entries classified: {total}")
    print(f"  Already dict format:     {already_dict_count}")
    print(f"  not_applicable:          {not_applicable_count}")
    print(f"  extraction_failed:       {extraction_failed_count}")
    print()

    if changes:
        print("Classifications:")
        for c in sorted(changes):
            print(c)

    if not dry_run:
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
        print(f"\nWritten to {CONFIG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill exclude_metrics with reasons")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    group.add_argument("--apply", action="store_true", help="Apply changes to companies.yaml")
    args = parser.parse_args()

    backfill(dry_run=args.dry_run)
