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

# Frontier: documented coverage gaps with hand-verified ground truth, kept OUT of
# the ratcheted denominator (see run_eval.summarize). These are the pre-2022
# "Calculation of Registration Fee" filings: before the EX-FILING FEES (Exhibit
# 107) regime the fee table lived inline in the S-3/S-1 body, with no exhibit to
# parse — so extract_registration_fee_table returns None for every one of them
# today. Each total below was read from the inline cover table and cross-checked
# against the stated fee (offering amount x SEC rate = fee). When an inline-table
# extractor lands, the concrete entries must return `expected` and the
# indeterminate 457(r) shelves must return `deferred`. Diverse by sector so the
# extractor isn't tuned to one issuer's table layout.
FRONTIER = [
    # concrete fixed-dollar shelves — value must be recovered exactly
    {"accession": "0001104659-20-040593", "form": "S-3", "issuer": "consumer", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": 30000000.0, "frontier": True,
     "note": "Kingold Jewelry inline fee table (gap)"},
    {"accession": "0001654954-21-007440", "form": "S-3/A", "issuer": "medical_device", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": 50000000.0, "frontier": True,
     "note": "Dynatronics inline fee table (gap)"},
    {"accession": "0001193125-21-204768", "form": "S-3", "issuer": "biotech_foreign", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": 250000000.0, "frontier": True,
     "note": "DBV Technologies inline fee table (gap)"},
    {"accession": "0001104659-21-067046", "form": "S-3", "issuer": "energy", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": 200000000.0, "frontier": True,
     "note": "Uranium Energy inline fee table (gap)"},
    {"accession": "0001047469-18-007293", "form": "S-3", "issuer": "clean_energy", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": 38606063.86, "frontier": True,
     "note": "Plug Power inline fee table (gap)"},
    # indeterminate WKSI shelves (Rule 457(r), pay-as-you-go) — inline equivalent
    # of the deferred ASR; correct answer is `deferred`, currently null
    {"accession": "0001193125-20-310765", "form": "S-3ASR", "issuer": "financial", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": None, "deferred": True, "frontier": True,
     "note": "Charles Schwab indeterminate 457(r) inline (gap)"},
    {"accession": "0001104659-20-121185", "form": "S-3ASR", "issuer": "tech", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": None, "deferred": True, "frontier": True,
     "note": "Micron indeterminate 457(r) inline (gap)"},
    {"accession": "0001104659-21-086851", "form": "S-3ASR", "issuer": "reit", "vintage": "pre-2022",
     "facet": "fee_capacity", "expected": None, "deferred": True, "frontier": True,
     "note": "Realty Income indeterminate 457(r) inline (gap)"},
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

    corpus = list(ANCHORS) + list(FRONTIER)
    known = {a["accession"] for a in corpus}
    if not args.no_live:
        corpus += [r for r in _live(args.year, args.quarter)
                   if r["accession"] not in known]

    CORPUS_PATH.write_text(json.dumps(corpus, indent=2) + "\n")
    by_facet: dict[str, int] = {}
    for r in corpus:
        by_facet[r["facet"]] = by_facet.get(r["facet"], 0) + 1
    n_live = len(corpus) - len(ANCHORS) - len(FRONTIER)
    print(f"Wrote {len(corpus)} entries to {CORPUS_PATH}")
    print("  by facet:", by_facet)
    print(f"  anchors: {len(ANCHORS)} | frontier: {len(FRONTIER)} | live: {n_live}")


if __name__ == "__main__":
    main()
