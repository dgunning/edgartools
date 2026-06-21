"""Calibrate _MIN_PLAUSIBLE_DEAL_SIZE (edgartools-s9uo #2).

Samples real 424B* filings (excl 424B2), computes the RAW cover-derived deal
size (pre-floor) and the authoritative XBRL total, and buckets the result. The
question the floor must answer: in the sub-$100k tail, which values are
denomination artifacts (corroborated/superseded by a different XBRL total, or
suspiciously round) versus legitimate small offerings the floor would wrongly
null.
"""
from __future__ import annotations

import os
import sys
import random
from collections import Counter

from edgar import get_filings, set_identity
from edgar.offerings._424b_cover import extract_cover_page_fields
from edgar.offerings._424b_xbrl import extract_filing_fees_xbrl
from edgar.offerings.prospectus import CoverPageData, _parse_sec_number

set_identity(os.environ.get("EDGAR_IDENTITY", "bench dgunning@gmail.com"))

FORMS = ["424B1", "424B3", "424B4", "424B5", "424B7", "424B8"]
YEARS = [2024, 2025]
QUARTERS = [1, 2, 3, 4]
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 250
PER_Q = int(sys.argv[2]) if len(sys.argv) > 2 else 40

random.seed(7)


def bucket(v):
    if v is None:
        return "none"
    if v <= 0:
        return "<=0"
    if v <= 1_000:
        return "(0, 1k]"
    if v <= 10_000:
        return "(1k, 10k]"
    if v <= 100_000:
        return "(10k, 100k]"
    if v <= 1_000_000:
        return "(100k, 1M]"
    if v <= 10_000_000:
        return "(1M, 10M]"
    return "(10M+)"


cover_buckets = Counter()
scanned = 0
have = 0
sub100k = []  # (raw_cover, xbrl_total, form, accession)

for year in YEARS:
    for q in QUARTERS:
        if have >= TARGET:
            break
        try:
            filings = get_filings(form=FORMS, year=year, quarter=q)
        except Exception:
            continue
        if not filings:
            continue
        idxs = list(range(len(filings)))
        random.shuffle(idxs)
        for i in idxs[:PER_Q]:
            if have >= TARGET:
                break
            f = filings[i]
            try:
                doc = f.parse()
                cover = CoverPageData(**extract_cover_page_fields(f, document=doc))
                raw = cover.offering_amount_float
            except Exception:
                continue
            scanned += 1
            have += 1
            cover_buckets[bucket(raw)] += 1
            if raw is not None and 0 < raw <= 100_000:
                try:
                    fees = extract_filing_fees_xbrl(f)
                    xbrl = _parse_sec_number(fees.get("total_offering_amount")) \
                        if fees.get("has_exhibit") else None
                except Exception:
                    xbrl = None
                sub100k.append((raw, xbrl, f.form, f.accession_no))
        print(f"{year}Q{q}: have={have}", file=sys.stderr)

print(f"\nSampled {have} filings with a cover offering amount field.\n")
print("RAW cover-derived deal size distribution (pre-floor):")
order = ["none", "<=0", "(0, 1k]", "(1k, 10k]", "(10k, 100k]",
         "(100k, 1M]", "(1M, 10M]", "(10M+)"]
nonnull = sum(v for k, v in cover_buckets.items() if k not in ("none",))
for k in order:
    n = cover_buckets.get(k, 0)
    pct = 100 * n / have if have else 0
    print(f"  {k:14s} {n:5d}  ({pct:4.1f}%)")

print(f"\nSub-$100k tail ({len(sub100k)} filings) — the floor's blast radius:")
print(f"  {'raw_cover':>14} {'xbrl_total':>16}  verdict")
artifact = legit = 0
for raw, xbrl, form, acc in sorted(sub100k):
    if xbrl is not None and xbrl > 100_000:
        verdict = "ARTIFACT (XBRL supersedes)"
        artifact += 1
    elif raw in (1000.0, 2000.0, 5000.0, 10000.0, 25000.0, 50000.0, 100000.0):
        verdict = "likely-artifact (round denom)"
        artifact += 1
    else:
        verdict = "maybe-legit (no XBRL, non-round)"
        legit += 1
    print(f"  {raw:>14,.0f} {str(xbrl):>16}  {verdict}  {form} {acc}")

print(f"\n  artifact-ish: {artifact}   maybe-legit: {legit}")
