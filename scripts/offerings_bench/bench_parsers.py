"""Benchmark bs4 (current) vs lxml-native EX-FILING FEES extraction.

Both consume identical raw bytes and produce the identical field set
(verified for equivalence before timing). Reports per-doc latency,
throughput, and a projected full-backfill cost.
"""
from __future__ import annotations

import os
import re
import json
import time
import statistics

CACHE = os.path.join(os.path.dirname(__file__), "corpus")

ROW_CONTEXT_PATTERNS = ['TypedMemberffdOfferingAxis', 'offrl_', 'offt_']
SUMMARY_PREFIXES = ('ffd:Ttl', 'ffd:Net', 'ffd:Nrrtv')


def _get_row_num(ctx):
    m = re.search(r'offrl_(\d+)', ctx)
    if m:
        return int(m.group(1))
    m = re.search(r'_(\d+)TypedMember', ctx)
    if m:
        return int(m.group(1))
    return None


def _row_sort_key(k):
    try:
        return (0, int(k))
    except ValueError:
        return (1, k)


def _assemble(metadata, summary, rows):
    """Shared post-processing — identical for both parsers."""
    offering_rows = []
    for row_key in sorted(rows.keys(), key=_row_sort_key):
        row = rows[row_key]
        offering_rows.append({
            'security_type': row.get('ffd:OfferingSctyTp'),
            'security_title': row.get('ffd:OfferingSctyTitl'),
            'max_aggregate_offering_price': row.get('ffd:MaxAggtOfferingPric'),
            'fee_rate': row.get('ffd:FeeRate'),
            'fee_amount': row.get('ffd:FeeAmt'),
            'fee_rule': row.get('ffd:Rule457rFlg') or row.get('ffd:Rule457oFlg')
                        or row.get('ffd:FeesOthrRuleFlg'),
        })
    is_final = metadata.get('ffd:FnlPrspctsFlg', '').lower() == 'true'
    return {
        'form_type': metadata.get('ffd:FormTp'),
        'registration_file_number': metadata.get('ffd:RegnFileNb'),
        'total_offering_amount': summary.get('ffd:TtlOfferingAmt')
                                 or summary.get('ffd:NrrtvMaxAggtOfferingPric'),
        'total_fee_amount': summary.get('ffd:TtlFeeAmt'),
        'offering_rows': offering_rows,
        'is_final_prospectus': is_final,
    }


def extract_bs4(content: bytes) -> dict:
    """Mirror of the current edgar/offerings/_424b_xbrl.py path."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'lxml')
    metadata, summary, rows, seen = {}, {}, {}, set()
    for elem in soup.find_all(lambda t: t.name in ('ix:nonnumeric', 'ix:nonfraction')):
        name = elem.get('name', '')
        if not name:
            continue
        ctx = elem.get('contextref') or elem.get('contextRef', '')
        if elem.get('xsi:nil') == 'true':
            continue
        key = (name, ctx)
        if key in seen:
            continue
        seen.add(key)
        value = elem.get_text(strip=True)
        if any(p in ctx for p in ROW_CONTEXT_PATTERNS):
            rk = _get_row_num(ctx)
            rk = str(rk) if rk is not None else ctx
            rows.setdefault(rk, {})[name] = value
        elif name.startswith(SUMMARY_PREFIXES):
            summary[name] = value
        else:
            metadata[name] = value
    return _assemble(metadata, summary, rows)


from lxml import etree

_IX_TAGS = ('nonnumeric', 'nonfraction')


def extract_lxml(content: bytes) -> dict:
    """lxml-native: libxml2 HTML parser + C-level iteration."""
    parser = etree.HTMLParser(recover=True, huge_tree=True)
    root = etree.fromstring(content, parser)
    metadata, summary, rows, seen = {}, {}, {}, set()
    if root is None:
        return _assemble(metadata, summary, rows)
    for elem in root.iter():
        tag = elem.tag
        if not isinstance(tag, str):
            continue
        local = tag.rsplit(':', 1)[-1].rsplit('}', 1)[-1].lower()
        if local not in _IX_TAGS:
            continue
        get = elem.get
        name = get('name', '')
        if not name:
            continue
        ctx = get('contextref') or get('contextref'.replace('ref', 'Ref')) or ''
        if get('xsi:nil') == 'true' or get('nil') == 'true':
            continue
        key = (name, ctx)
        if key in seen:
            continue
        seen.add(key)
        value = ''.join(elem.itertext()).strip()
        if any(p in ctx for p in ROW_CONTEXT_PATTERNS):
            rk = _get_row_num(ctx)
            rk = str(rk) if rk is not None else ctx
            rows.setdefault(rk, {})[name] = value
        elif name.startswith(SUMMARY_PREFIXES):
            summary[name] = value
        else:
            metadata[name] = value
    return _assemble(metadata, summary, rows)


def main():
    manifest = json.load(open(os.path.join(CACHE, "manifest.json")))
    docs = []
    for m in manifest:
        p = os.path.join(CACHE, m["key"] + ".html")
        if os.path.exists(p):
            docs.append((m, open(p, "rb").read()))
    print(f"Loaded {len(docs)} cached exhibits "
          f"({sum(len(d) for _, d in docs)/1e6:.2f} MB)\n")

    # --- correctness: bs4 vs lxml must agree ---
    mismatches = 0
    for m, content in docs:
        a, b = extract_bs4(content), extract_lxml(content)
        if a != b:
            mismatches += 1
            if mismatches <= 5:
                print(f"MISMATCH {m['key']}")
                for k in a:
                    if a[k] != b.get(k):
                        print(f"   {k}: bs4={a[k]!r}  lxml={b.get(k)!r}")
    print(f"Equivalence: {len(docs)-mismatches}/{len(docs)} identical "
          f"({mismatches} mismatches)\n")

    # --- timing ---
    REPS = 5
    results = {}
    for label, fn in (("bs4 (current)", extract_bs4), ("lxml-native", extract_lxml)):
        per_doc = []
        t0 = time.perf_counter()
        for _ in range(REPS):
            for _, content in docs:
                s = time.perf_counter()
                fn(content)
                per_doc.append((time.perf_counter() - s) * 1000)
        total = time.perf_counter() - t0
        results[label] = {
            "total_s": total,
            "docs_per_s": (len(docs) * REPS) / total,
            "mean_ms": statistics.mean(per_doc),
            "median_ms": statistics.median(per_doc),
            "p95_ms": sorted(per_doc)[int(len(per_doc) * 0.95)],
        }

    print(f"{'parser':<16}{'docs/s':>10}{'mean ms':>10}{'median':>10}{'p95 ms':>10}")
    for label, r in results.items():
        print(f"{label:<16}{r['docs_per_s']:>10.1f}{r['mean_ms']:>10.3f}"
              f"{r['median_ms']:>10.3f}{r['p95_ms']:>10.3f}")

    bs4r, lxr = results["bs4 (current)"], results["lxml-native"]
    speedup = bs4r["mean_ms"] / lxr["mean_ms"]
    print(f"\nlxml speedup: {speedup:.2f}x faster per doc")

    # --- backfill projection ---
    # 3yr 424B* (excl 424B2) iXBRL-bearing universe, rough order of magnitude.
    print("\nBackfill projection (parse-only, single core):")
    for n in (50_000, 200_000):
        t_bs4 = n / bs4r["docs_per_s"]
        t_lx = n / lxr["docs_per_s"]
        print(f"  {n:>8,} docs:  bs4 {t_bs4/60:6.1f} min   "
              f"lxml {t_lx/60:6.1f} min   saved {(t_bs4-t_lx)/60:6.1f} min")


if __name__ == "__main__":
    main()
