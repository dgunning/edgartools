"""Trim SEC company facts to the cash-change elements tested in test_issue_1448.py.

Usage: python trim_companyfacts.py CIK0000023217.json conagra_cash_change_companyfacts.json

The input is https://data.sec.gov/api/xbrl/companyfacts/CIK0000023217.json as served.
Every kept fact is copied verbatim; only whole concepts are dropped.
"""
import json
import sys

KEEP = {
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffectContinuingOperations",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations",
    "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations",
    # EntityFacts builds no cash flow statement without the three activity totals.
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
}

source, target = sys.argv[1], sys.argv[2]
with open(source, encoding="utf-8") as f:
    raw = json.load(f)
raw["facts"] = {
    "dei": raw["facts"].get("dei", {}),
    "us-gaap": {name: body for name, body in raw["facts"]["us-gaap"].items() if name in KEEP},
}
assert set(raw["facts"]["us-gaap"]) == KEEP, sorted(KEEP - set(raw["facts"]["us-gaap"]))
with open(target, "w", encoding="utf-8") as f:
    json.dump(raw, f, indent=1)
    f.write("\n")
