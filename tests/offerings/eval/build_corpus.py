"""
Build / refresh the offerings extraction eval corpus.

Writes corpus.json: a stratified list of real SEC filings the eval harness runs
extraction over. Combines hand-curated anchor cases (known-good values and the
filings behind edgartools-fu3x/2w5y/2h4c/zxnj) with a live-sampled breadth set so
no failure mode hides in a tail.

Usage:
    python tests/offerings/eval/build_corpus.py            # refresh from SEC
    python tests/offerings/eval/build_corpus.py --no-live  # curated anchors only

The curated anchors carry `expected`/`note` metadata so the harness can assert
ground truth, not just coverage. The live set is breadth only (no expectations).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CORPUS_PATH = Path(__file__).with_name("corpus.json")

# Hand-curated anchors: known values verified against SEC EDGAR by hand.
# strata: form / issuer_class / vintage. facet: which extractor this exercises.
ANCHORS = [
    # --- fee capacity: ok (regression guards for known-good values) ---
    {"accession": "0001193125-25-067122", "form": "S-3", "issuer": "biotech",
     "facet": "fee_capacity", "expected": 300000000.0, "note": "Nektar"},
    {"accession": "0001140361-25-024210", "form": "S-3", "issuer": "bank",
     "facet": "fee_capacity", "expected": 300000000.0, "note": "Central Pacific universal shelf"},
    {"accession": "0000950103-25-008153", "form": "S-3", "issuer": "biotech",
     "facet": "fee_capacity", "expected": 79157878.46, "note": "ADC Therapeutics"},
    {"accession": "0001213900-25-058997", "form": "S-3", "issuer": "asset_mgr",
     "facet": "fee_capacity", "expected": 350000000.0, "note": "GCM Grosvenor carry-forward"},
    {"accession": "0001193125-22-186192", "form": "S-3", "issuer": "telecom", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": 21730000.0, "note": "Anterix pre-inline-XBRL"},
    # --- fee capacity: recovered by zxnj (were null before the fix) ---
    {"accession": "0001193125-25-068942", "form": "S-3", "issuer": "biotech",
     "facet": "fee_capacity", "expected": 79170150.0, "note": "Whitehawk split-tag header (zxnj)"},
    {"accession": "0001193125-25-067858", "form": "S-3", "issuer": "biotech",
     "facet": "fee_capacity", "expected": 9704293.70, "note": "Vigil footnote-table avoidance (zxnj)"},
    {"accession": "0001193125-25-067182", "form": "S-3", "issuer": "biotech",
     "facet": "fee_capacity", "expected": 300000000.0, "note": "Forte (zxnj)"},
    # --- fee capacity: legitimately indeterminate (deferred ASR) ---
    {"accession": "0001193125-25-066253", "form": "S-3ASR", "issuer": "reit",
     "facet": "fee_capacity", "expected": None, "deferred": True, "note": "Welltower indeterminate ASR (zxnj)"},
    {"accession": "0001104659-25-064107", "form": "S-3ASR", "issuer": "industrial",
     "facet": "fee_capacity", "expected": None, "deferred": True, "note": "AeroVironment deferred 457(r)"},
    # --- lead_bookrunner: 424B2 structured notes must NOT return garbage (2h4c) ---
    {"accession": "0001918704-25-005479", "form": "424B2", "issuer": "structured_note",
     "facet": "lead_bookrunner", "note": "BofA note title leak (2h4c)"},
    {"accession": "0001918704-25-005486", "form": "424B2", "issuer": "structured_note",
     "facet": "lead_bookrunner", "note": "BofA TOC blob (2h4c)"},
]

# Live breadth: N most-recent per form, tagged by stratum. No expectations.
LIVE_FORMS = [
    ("S-3", "mixed", "fee_capacity", 6),
    ("F-3", "foreign", "fee_capacity", 4),
    ("S-3ASR", "wksi", "fee_capacity", 4),
    ("424B5", "firm_commitment", "lead_bookrunner", 6),
    ("424B2", "structured_note", "lead_bookrunner", 6),
    ("424B3", "shelf_takedown", "shelf_status", 4),
]


def _live(year: int, quarter: int) -> list[dict]:
    from edgar import get_filings
    rows = []
    seen = set()
    for form, issuer, facet, n in LIVE_FORMS:
        for f in get_filings(form=form, year=year, quarter=quarter).head(n):
            if f.accession_no in seen:
                continue
            seen.add(f.accession_no)
            rows.append({"accession": f.accession_no, "form": form, "issuer": issuer,
                         "facet": facet, "note": f.company[:30]})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-live", action="store_true", help="curated anchors only")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--quarter", type=int, default=1)
    args = ap.parse_args()

    corpus = list(ANCHORS)
    anchor_accessions = {a["accession"] for a in ANCHORS}
    if not args.no_live:
        corpus += [r for r in _live(args.year, args.quarter)
                   if r["accession"] not in anchor_accessions]

    CORPUS_PATH.write_text(json.dumps(corpus, indent=2) + "\n")
    by_facet: dict[str, int] = {}
    for r in corpus:
        by_facet[r["facet"]] = by_facet.get(r["facet"], 0) + 1
    print(f"Wrote {len(corpus)} entries to {CORPUS_PATH}")
    print("  by facet:", by_facet)
    print(f"  anchors: {len(ANCHORS)} | live: {len(corpus) - len(ANCHORS)}")


if __name__ == "__main__":
    main()
