"""Cache a fixed corpus of filings so the 6.0 perf baseline runs network-free.

The corpus is *named, not sampled*. Every entry is a specific accession number
pinned in corpus_manifest.json, which is committed; the bytes under corpus/ are
gitignored and rebuilt by running this script. That way a baseline number taken
today and a number taken six months from now describe the same documents, and
anyone can reproduce the corpus from the manifest alone.

Entries were chosen for spread rather than typicality — the pathological cases
(the 1h12m table, the 5.6MB backtracking case, the >10MB parse) are exactly the
ones an optimization is most likely to change, so they belong in the baseline.

Usage:
    python scripts/perf_baseline/build_corpus.py            # build missing entries
    python scripts/perf_baseline/build_corpus.py --refresh  # re-download everything
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
CORPUS = HERE / "corpus"
MANIFEST = HERE / "corpus_manifest.json"

# The six roles XBRL.from_files() accepts, in the order XBRL.from_filing() parses them.
XBRL_ROLES = ("schema", "label", "presentation", "calculation", "definition", "instance")

# key -> how to find it. `accession` is authoritative when present; ticker/year is
# only used to resolve an accession the first time, and the result is pinned into
# the manifest so later runs never re-resolve (and never drift onto a new filing).
CORPUS_SPEC = [
    # --- pathological: these drove specific fixes and are the regression surface ---
    # Not a 10-K — an ABS-15G, "File 08 of 98": one 25MB table, 61,801 rows,
    # 1.48M cells, one <div>. It is in the corpus as the extreme table workload
    # (the 1h12m -> 24.1s fix), not as a representative annual report.
    dict(key="fanniemae_abs15g_2018", accession="0000310522-18-000010", form="ABS-15G",
         note="large-table dimension pass: 1h12m -> 24.1s in 5.45.0"),
    dict(key="footlocker_10k_fy2024", accession="0001437749-25-009620", form="10-K",
         note="nested TOC anchors; off-by-one item map (GH #923)"),
    dict(key="footlocker_10k_fy2013", accession="0001144204-14-019510", form="10-K",
         note="split TOC cells; phantom item codes (GH #923)"),
    dict(key="ambac_10k_fy2022", accession="0000874501-23-000040", form="10-K",
         note="two-column TOC; Part context scrambling (GH #924)"),
    dict(key="regions_10k_fy2021", accession="0001281761-22-000016", form="10-K",
         note="page-number-only TOC; Item 7/7A anchor collision (GH #920)"),
    # --- large: the >10MB band that took the removed streaming pipeline ---
    dict(key="citigroup_10k_fy2024", ticker="C", form="10-K", year=2025,
         note=">10MB; 830K vs 1.81M chars under the removed lossy pipeline"),
    dict(key="morganstanley_10k_fy2024", ticker="MS", form="10-K", year=2025,
         note="~490 word-gluing sites before 5.45.0"),
    # CIK, not ticker: ODP is absent from the SEC ticker file.
    dict(key="odp_10k_fy2025", cik=800240, form="10-K", year=2025,
         note="5.6MB; catastrophic backtracking in has_index() (GH #928)"),
    # --- ordinary: the common case the pathological entries would otherwise crowd out ---
    dict(key="tesla_10k_fy2023", ticker="TSLA", form="10-K", year=2024,
         note="Workiva TOC row structure (GH #915)"),
    dict(key="meta_10k_fy2024", ticker="META", form="10-K", year=2025,
         note="heading detection: 180 of 296 headings were glyphs pre-5.45.0"),
    # --- small: keeps the low end of the size band represented ---
    dict(key="jackhenry_10q_fy2025", ticker="JKHY", form="10-Q", year=2025,
         note="small-to-mid 10-Q; guards against tuning only for giants"),
]


def resolve_accession(entry: dict) -> str | None:
    """Find the accession for a ticker-or-cik/form/year entry. Network.

    One unresolvable entry must not sink the build — a corpus short one filing
    is still a usable baseline, and the manifest records what was skipped.
    """
    from edgar import Company

    ident = entry.get("cik") or entry.get("ticker")
    try:
        company = Company(ident)
        filings = company.get_filings(form=entry["form"], year=entry["year"])
    except Exception as exc:
        print(f"  ! {entry['key']}: cannot resolve {ident} "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        return None
    if filings is None or len(filings) == 0:
        print(f"  ! {entry['key']}: no {entry['form']} for {ident} in {entry['year']}",
              file=sys.stderr)
        return None
    # Oldest-first would drift as amendments land; take the first of the year.
    return filings[0].accession_no


def fetch_entry(entry: dict, refresh: bool) -> dict | None:
    """Download primary HTML + XBRL attachments for one entry. Network."""
    from edgar import find
    from edgar.xbrl.xbrl import XBRLAttachments

    key = entry["key"]
    out = CORPUS / key
    primary = out / "primary.html"

    if primary.exists() and not refresh:
        record = dict(entry)
        record["html_bytes"] = primary.stat().st_size
        record["xbrl_roles"] = sorted(p.stem for p in (out / "xbrl").glob("*.xml"))
        return record

    filing = find(entry["accession"])
    if filing is None:
        print(f"  ! {key}: accession {entry['accession']} not found", file=sys.stderr)
        return None

    out.mkdir(parents=True, exist_ok=True)
    # filing.html() routes through the homepage, which occasionally comes back
    # empty under sustained fetching; the primary attachment is the same bytes
    # by a shorter path, so fall back to it rather than dropping the entry.
    html = None
    for source in ("html", "attachment"):
        try:
            html = filing.html() if source == "html" else filing.document.download()
        except Exception as exc:
            print(f"  ~ {key}: {source} source failed "
                  f"({type(exc).__name__}: {exc})", file=sys.stderr)
            continue
        if html:
            break
    if not html:
        print(f"  ! {key}: no primary HTML from either source", file=sys.stderr)
        return None
    primary.write_text(html, encoding="utf-8")

    roles = []
    try:
        attachments = XBRLAttachments(filing.attachments)
        if not attachments.empty:
            (out / "xbrl").mkdir(exist_ok=True)
            for role in XBRL_ROLES:
                att = attachments.get(role)
                if att is None:
                    continue
                content = att.content
                if isinstance(content, str):
                    content = content.encode("utf-8", "replace")
                (out / "xbrl" / f"{role}.xml").write_bytes(content)
                roles.append(role)
    except Exception as exc:  # a missing XBRL bundle must not sink the HTML entry
        print(f"  ~ {key}: XBRL unavailable ({type(exc).__name__}: {exc})", file=sys.stderr)

    record = dict(entry)
    record.update(
        company=filing.company,
        form=filing.form,
        filing_date=str(filing.filing_date),
        html_bytes=primary.stat().st_size,
        xbrl_roles=sorted(roles),
    )
    return record


# Companies whose SEC company-facts payload is cached, so the EntityFacts
# surfaces named in the GH #929 commitment can be snapshotted without network.
# Both are already in the filing corpus, which keeps the manifest coherent — and
# they are deliberately unalike: one reports in a single currency with a short
# history, the other has a decade of restatements behind it.
ENTITY_FACTS_SPEC = [
    dict(key="tesla", cik=1318605, note="matches tesla_10k_fy2023"),
    dict(key="footlocker", cik=850209, note="matches the two footlocker entries"),
]


def fetch_entity_facts(refresh: bool) -> list[dict]:
    """Cache each company's raw company-facts JSON. Network.

    The raw payload rather than a parsed object: EntityFactsParser is exactly
    what a 6.0 change might alter, so the baseline has to re-parse it on every
    run rather than snapshot a pickle of last year's parse.
    """
    from edgar.entity.entity_facts import download_company_facts_from_sec

    out = CORPUS / "_entity_facts"
    records = []
    for spec in ENTITY_FACTS_SPEC:
        path = out / f"CIK{spec['cik']:010}.json"
        if not path.exists() or refresh:
            out.mkdir(parents=True, exist_ok=True)
            try:
                payload = download_company_facts_from_sec(spec["cik"])
            except Exception as exc:
                print(f"  ! entity facts {spec['key']}: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
                continue
            if not payload:
                print(f"  ! entity facts {spec['key']}: empty payload", file=sys.stderr)
                continue
            path.write_text(json.dumps(payload))
        record = dict(spec)
        record["path"] = str(path.relative_to(HERE))
        record["bytes"] = path.stat().st_size
        records.append(record)
        print(f"{'facts ' + spec['key']:<28} {record['bytes']/1e6:>7.2f} MB  CIK {spec['cik']}")
    return records


INDEX_QUARTER = (2025, 1)  # pinned; a moving quarter would make the snapshot drift


def fetch_index(refresh: bool) -> dict | None:
    """Cache one quarter's filing index as parquet.

    `Filings.to_pandas()` is one of the two surfaces named in the GH #929
    schema-stability commitment, and it is `pyarrow.Table.to_pandas()` under the
    hood — so its schema is the arrow schema that the planned pyarrow-backed
    index reads will rewrite. Snapshotting it needs a real index, cached here so
    the bench stays network-free.
    """
    import pyarrow.parquet as pq
    from edgar import get_filings

    year, quarter = INDEX_QUARTER
    out = CORPUS / "_index"
    path = out / f"{year}Q{quarter}.parquet"
    if path.exists() and not refresh:
        return {"path": str(path.relative_to(HERE)), "rows": pq.read_metadata(path).num_rows,
                "year": year, "quarter": quarter}

    out.mkdir(parents=True, exist_ok=True)
    filings = get_filings(year=year, quarter=quarter)
    if filings is None or len(filings) == 0:
        print(f"  ! index {year}Q{quarter} unavailable", file=sys.stderr)
        return None
    filings.save_parquet(str(path))
    print(f"{'index ' + str(year) + 'Q' + str(quarter):<28} {len(filings):>7,} rows")
    return {"path": str(path.relative_to(HERE)), "rows": len(filings),
            "year": year, "quarter": quarter}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true", help="re-download entries already cached")
    args = ap.parse_args()

    from edgar import set_identity
    set_identity(os.environ.get("EDGAR_IDENTITY", "perf-baseline dgunning@gmail.com"))

    CORPUS.mkdir(exist_ok=True)
    pinned = {}
    if MANIFEST.exists():
        pinned = {e["key"]: e for e in json.loads(MANIFEST.read_text())["entries"]}

    manifest = []
    for entry in CORPUS_SPEC:
        key = entry["key"]
        entry = dict(entry)

        # Accession precedence: the spec, then whatever a previous run pinned,
        # then a fresh resolve. Once pinned it never moves.
        if "accession" not in entry:
            if key in pinned and pinned[key].get("accession"):
                entry["accession"] = pinned[key]["accession"]
            else:
                resolved = resolve_accession(entry)
                if resolved is None:
                    continue
                entry["accession"] = resolved
                print(f"  resolved {key} -> {resolved}")

        record = fetch_entry(entry, args.refresh)
        if record is None:
            continue
        manifest.append(record)
        print(f"{key:<28} {record['html_bytes']/1e6:>7.2f} MB  "
              f"xbrl:{len(record.get('xbrl_roles', []))}/6  {record['accession']}")

    index = fetch_index(args.refresh)
    entity_facts = fetch_entity_facts(args.refresh)

    MANIFEST.write_text(json.dumps(
        {"entries": manifest, "index": index, "entity_facts": entity_facts}, indent=2) + "\n")
    total = sum(e["html_bytes"] for e in manifest)
    with_xbrl = sum(1 for e in manifest if e.get("xbrl_roles"))
    print(f"\nCorpus: {len(manifest)} filings, {total/1e6:.1f} MB HTML, {with_xbrl} with XBRL")
    print(f"Manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
