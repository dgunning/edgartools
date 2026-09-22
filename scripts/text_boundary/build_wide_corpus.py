"""Build the widened text-boundary corpus.

The 57 fixtures under tests/fixtures/html are all modern large-cap 10-K/10-Q. That is the
wrong shape for the one question left open on edgartools-jysx — whether the
ParagraphNode.text() tag allowlist can be deleted — because the allowlist keys on
`original_tag in span/a/em/strong/i/b`, and which tags a filing uses is decided by its
markup generation and its filing agent, neither of which the current corpus varies.

So sample along the two axes that actually move tag choice:

  era   1996-2001 pure <font>, tables for layout   (much of it is plain text, not HTML)
        2002-2008 <font> plus early inline CSS
        2009-2014 <span> plus inline CSS, pre-inline-XBRL
        2015-2019 <span>, EDGAR modernization
        2020-2026 inline XBRL (ix:) throughout
  form  10-K 10-Q   core prose
        DEF 14A     proxy layout idioms, heavy tables
        S-1 424B    dense offering prose
        N-CSR N-PX  fund reports, a different agent population
        20-F        foreign filers
        8-K         short documents

Documents are size-capped: the allowlist question is about markup shape, and the existing
corpus already covers large documents. Filings are deduped by CIK so one prolific filer
cannot dominate a cell.

The HTML is cached under a gitignored directory and is NOT committed — the committed
artifact is manifest.json, which pins every accession number, so the corpus rebuilds
byte-identically from a clean checkout.

Usage:
    PYTHONPATH=$REPO python scripts/text_boundary/build_wide_corpus.py [--per-cell 3]
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from edgar import get_filings, set_identity  # noqa: E402

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/text_boundary_corpus"
MANIFEST = Path(__file__).resolve().parent / "wide_corpus_manifest.json"

MIN_BYTES = 20_000       # below this there is no prose to measure
MAX_BYTES = 4_000_000    # keep the measurement run bounded

# (label, years, quarters to sample)
ERAS = [
    ("e1_1996_2001", [1997, 1999, 2001], [1, 3]),
    ("e2_2002_2008", [2003, 2005, 2007], [1, 3]),
    ("e3_2009_2014", [2010, 2012, 2014], [1, 3]),
    ("e4_2015_2019", [2016, 2018], [1, 3]),
    ("e5_2020_2026", [2021, 2023, 2025], [1, 3]),
]

FORMS = ["10-K", "10-Q", "DEF 14A", "S-1", "424B2", "N-CSR", "N-PX", "20-F", "8-K"]


def looks_like_html(text: str) -> bool:
    """EDGAR filings before ~2001 are frequently plain text wrapped in <DOCUMENT>."""
    if not text:
        return False
    head = text[:20000].lower()
    return ("<font" in head or "<span" in head or "<p" in head
            or "<div" in head or "<table" in head)


def sample(filings, n, seen_ciks):
    """Take up to n filings spread across the list, one per CIK."""
    out = []
    total = len(filings)
    if total == 0:
        return out
    # Stride through rather than taking the head: the index is ordered by CIK/company,
    # so the first N are all one corner of the alphabet.
    stride = max(1, total // (n * 12))
    for i in range(0, total, stride):
        if len(out) >= n * 12:
            break
        try:
            f = filings[i]
        except Exception:
            continue
        if f.cik in seen_ciks:
            continue
        out.append(f)
    return out


def fetch(filing):
    """Return (html, note). Skips anything that is not real HTML or is out of band."""
    try:
        html = filing.html()
    except Exception as e:
        return None, f"error:{type(e).__name__}"
    if not html:
        return None, "no-html"
    n = len(html.encode("utf-8", errors="replace"))
    if n < MIN_BYTES:
        return None, f"too-small:{n}"
    if n > MAX_BYTES:
        return None, f"too-big:{n}"
    if not looks_like_html(html):
        return None, "plain-text"
    return html, f"ok:{n}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=3)
    ap.add_argument("--identity", default="Dwight Gunning dgunning@gmail.com")
    args = ap.parse_args()
    set_identity(args.identity)

    CORPUS.mkdir(parents=True, exist_ok=True)
    entries = []
    if MANIFEST.exists():
        entries = json.loads(MANIFEST.read_text())["filings"]
    have = {e["accession"] for e in entries}
    seen_ciks = {e["cik"] for e in entries}

    for era, years, quarters in ERAS:
        for form in FORMS:
            kept = sum(1 for e in entries if e["era"] == era and e["form"] == form)
            if kept >= args.per_cell:
                continue
            for year in years:
                if kept >= args.per_cell:
                    break
                for q in quarters:
                    if kept >= args.per_cell:
                        break
                    try:
                        fl = get_filings(year=year, quarter=q, form=form)
                    except Exception as e:
                        print(f"  {era} {form} {year}Q{q}: index error {e}", flush=True)
                        continue
                    if fl is None or len(fl) == 0:
                        continue
                    for filing in sample(fl, args.per_cell, seen_ciks):
                        if kept >= args.per_cell:
                            break
                        if filing.accession_no in have:
                            continue
                        html, note = fetch(filing)
                        if html is None:
                            continue
                        dest = CORPUS / era / form.replace(" ", "").replace("/", "")
                        dest.mkdir(parents=True, exist_ok=True)
                        path = dest / f"{filing.accession_no}.html"
                        path.write_text(html, errors="replace")
                        entries.append({
                            "era": era, "form": form, "year": year, "quarter": q,
                            "accession": filing.accession_no, "cik": filing.cik,
                            "company": str(filing.company)[:60],
                            "filing_date": str(filing.filing_date),
                            "bytes": int(note.split(":")[1]),
                            "path": str(path.relative_to(CORPUS)),
                        })
                        have.add(filing.accession_no)
                        seen_ciks.add(filing.cik)
                        kept += 1
                        print(f"  {era} {form:8} {filing.filing_date} "
                              f"{str(filing.company)[:34]:34} {note}", flush=True)
                        MANIFEST.write_text(json.dumps(
                            {"corpus_root": "tests/fixtures/text_boundary_corpus",
                             "n_filings": len(entries), "filings": entries}, indent=2))

    MANIFEST.write_text(json.dumps(
        {"corpus_root": "tests/fixtures/text_boundary_corpus",
         "n_filings": len(entries), "filings": entries}, indent=2))
    print(f"\n{len(entries)} filings in corpus -> {MANIFEST}")
    by_era = {}
    for e in entries:
        by_era.setdefault(e["era"], []).append(e["form"])
    for era in sorted(by_era):
        forms = {}
        for f in by_era[era]:
            forms[f] = forms.get(f, 0) + 1
        print(f"  {era}: {sum(forms.values()):3}  {forms}")


if __name__ == "__main__":
    main()
