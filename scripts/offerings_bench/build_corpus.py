"""Sample EX-FILING FEES exhibits across 3 years of 424B* (excluding 424B2).

Caches raw exhibit bytes to disk so the parser benchmark runs network-free
and reproducibly. Spreads sampling across quarters to capture format drift.
"""
from __future__ import annotations

import os
import sys
import json
import random

from edgar import get_filings, set_identity

set_identity(os.environ.get("EDGAR_IDENTITY", "bench dgunning@gmail.com"))

CACHE = os.path.join(os.path.dirname(__file__), "corpus")
os.makedirs(CACHE, exist_ok=True)

# 424B* excluding 424B2. B5/B3 carry most of the iXBRL fee exhibits.
FORMS = ["424B1", "424B3", "424B4", "424B5", "424B7", "424B8"]
YEARS = [2023, 2024, 2025]
QUARTERS = [1, 2, 3, 4]

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 150
PER_QUARTER_SCAN = int(sys.argv[2]) if len(sys.argv) > 2 else 60

random.seed(42)
manifest = []
have = 0

for year in YEARS:
    for q in QUARTERS:
        if have >= TARGET:
            break
        try:
            filings = get_filings(form=FORMS, year=year, quarter=q)
        except Exception as e:
            print(f"  {year}Q{q}: get_filings failed: {e}", file=sys.stderr)
            continue
        if filings is None or len(filings) == 0:
            continue
        n = len(filings)
        idxs = list(range(n))
        random.shuffle(idxs)
        idxs = idxs[:PER_QUARTER_SCAN]
        hits = 0
        for i in idxs:
            if have >= TARGET:
                break
            try:
                filing = filings[i]
                fee_att = None
                for att in filing.attachments:
                    if getattr(att, "document_type", None) == "EX-FILING FEES":
                        fee_att = att
                        break
                if fee_att is None:
                    continue
                content = fee_att.download()
                if isinstance(content, str):
                    content = content.encode("utf-8", "replace")
                key = f"{filing.form}_{filing.accession_no}".replace("/", "_")
                path = os.path.join(CACHE, key + ".html")
                with open(path, "wb") as fh:
                    fh.write(content)
                manifest.append({
                    "key": key,
                    "form": filing.form,
                    "accession": filing.accession_no,
                    "year": year,
                    "quarter": q,
                    "bytes": len(content),
                })
                have += 1
                hits += 1
            except Exception as e:
                print(f"  skip {year}Q{q}[{i}]: {e}", file=sys.stderr)
                continue
        print(f"{year}Q{q}: scanned {len(idxs)} -> {hits} exhibits (total {have})")

with open(os.path.join(CACHE, "manifest.json"), "w") as fh:
    json.dump(manifest, fh, indent=2)

by_form = {}
total_bytes = 0
for m in manifest:
    by_form[m["form"]] = by_form.get(m["form"], 0) + 1
    total_bytes += m["bytes"]
print(f"\nCorpus: {len(manifest)} exhibits, {total_bytes/1e6:.2f} MB")
print("By form:", by_form)
