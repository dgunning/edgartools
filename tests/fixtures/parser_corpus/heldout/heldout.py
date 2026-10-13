"""Held-out 10-K truth set (edgartools-llmp.11.1).

``boundary_truth.json`` is in-sample: every phase B rule was tuned on its
filings, its labels were proposed from pipeline output (so an item the
pipeline never found never entered the denominator), and some labels moved
with policy. This set is the out-of-sample check. Its filings are a seeded,
era-stratified random draw from the EDGAR full indexes, excluding every filer
and accession in the development corpus; its labels were made from the filing
text without pipeline output in view. It is REPORT-ONLY: nothing in CI pins
it. See README.md for the protocol, including retiring a filing whose failure
drives a fix.

    python tests/fixtures/parser_corpus/heldout/heldout.py sample   # draw (once; seed fixed)
    python tests/fixtures/parser_corpus/heldout/heldout.py fetch    # download into the cache
    python tests/fixtures/parser_corpus/heldout/heldout.py dump DIR # numbered text for labelling
    python tests/fixtures/parser_corpus/heldout/heldout.py cut LABELS.json  # line labels -> windows
    python tests/fixtures/parser_corpus/heldout/heldout.py compare OUT.json  # disagreements, A/B blind
    python tests/fixtures/parser_corpus/heldout/heldout.py resolve VERDICTS.json OUT.key.json
    python tests/fixtures/parser_corpus/heldout/heldout.py report   # recall, precision, exactness

Filings are fetched with ``Filing.html()`` and parsed exactly as
``TenK.document`` parses them, so plain-text filings go through the same
wrapper users get. The cache lives outside the repo (``EDGAR_HELDOUT_CACHE``,
default ``~/.cache/edgartools/heldout``); filings never change once filed, so
a fresh fetch reproduces the measurement.
"""
import json
import os
import random
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[3]))
sys.path.insert(0, str(_HERE.parent))
import scoring  # noqa: E402

TRUTH_PATH = _HERE / "heldout_10k.json"
CACHE = Path(os.environ.get("EDGAR_HELDOUT_CACHE", Path.home() / ".cache" / "edgartools" / "heldout"))

SEED = 20261012
ERAS = {"2001-2006": (2001, 2006), "2007-2012": (2007, 2012),
        "2013-2018": (2013, 2018), "2019-2025": (2019, 2025)}
PER_ERA = 10
# Size strata, per era: public float as the cover page states it. $700M is the
# large-accelerated-filer threshold; "large" filers are what most callers
# parse, "small" ones are most of EDGAR, and each half gets PER_ERA // 2.
LARGE_FLOAT = 700_000_000
ABS_SIC = 6189  # asset-backed issuers file Reg AB 10-Ks without the Item 1-16 layout
_TICKER_ALIASES = {"eaton": "ETN"}
_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


# ---------------------------------------------------------------------------
# sample
# ---------------------------------------------------------------------------

def _dev_corpus_exclusions():
    """(ciks, accessions) of every filing the phase B rules were developed on."""
    from edgar import get_by_accession_number_enriched
    from edgar.reference.tickers import find_cik

    ciks, accessions = set(), set()
    html_root = _HERE.parents[1] / "html"
    for d in sorted(p for p in html_root.iterdir() if p.is_dir()):
        if d.name.isdigit():
            ciks.add(int(d.name))
        else:
            cik = find_cik(_TICKER_ALIASES.get(d.name, d.name.upper()))
            if cik:
                ciks.add(int(cik))
            else:
                print(f"  warning: no CIK for fixture ticker {d.name}")  # noqa: T201
    for e in scoring.consistency_corpus():
        stem = Path(e["path"]).stem
        if _ACCESSION_RE.match(stem):
            accessions.add(stem)
    for root in (_HERE.parents[1] / "parity_gate", _HERE.parents[1] / "text_boundary_corpus"):
        for p in root.rglob("*.html"):
            if _ACCESSION_RE.match(p.stem):
                accessions.add(p.stem)
    for acc in sorted(accessions):
        f = get_by_accession_number_enriched(acc)
        if f is not None:
            ciks.add(int(f.cik))
    return ciks, accessions


_MONEY_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand)?", re.IGNORECASE)
_NO_MARKET_RE = re.compile(r"no (?:established )?public (?:trading )?market|not applicable|"
                           r"no (?:public )?market (?:value|exists)", re.IGNORECASE)


def public_float(html):
    """Cover-page public float in dollars, 0 when the filer says there is no market, None if unstated."""
    from edgar.documents import HTMLParser, ParserConfig

    text = scoring.collapse(HTMLParser(ParserConfig(form="10-K", detect_sections=False)).parse(html).text() or "")
    head = text[:30_000]
    m = re.search(r"aggregate market value", head, re.IGNORECASE)
    if not m:
        return None
    tail = head[m.end():m.end() + 600]
    # The sentence often quotes the share price first ("based on the closing
    # sale price of $3.20 ... was approximately $81 million"): take the largest.
    amounts = [float(m.group(1).replace(",", "") or 0)
               * {"billion": 1e9, "million": 1e6, "thousand": 1e3}.get((m.group(2) or "").lower(), 1)
               for m in _MONEY_RE.finditer(tail)]
    if not amounts:
        return 0 if _NO_MARKET_RE.search(tail) else None
    return int(max(amounts))


def cmd_sample():
    from edgar import Company, get_by_accession_number_enriched, get_filings

    if TRUTH_PATH.exists():
        sys.exit(f"{TRUTH_PATH.name} exists; the draw is made once. Delete it to redraw.")
    ciks, accessions = _dev_corpus_exclusions()
    print(f"excluding {len(ciks)} dev-corpus CIKs, {len(accessions)} accessions")  # noqa: T201
    CACHE.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)  # noqa: S311 - a reproducible draw, not security
    picked, seen_ciks, indexes = [], set(), {}
    rejected = {"dev_corpus": 0, "abs": 0, "no_html": 0, "float_unstated": 0, "stratum_full": 0}
    for era, (y0, y1) in ERAS.items():
        quota = {"large": PER_ERA // 2, "small": PER_ERA - PER_ERA // 2}
        while any(quota.values()):
            year, quarter = rng.randint(y0, y1), rng.randint(1, 4)
            if (year, quarter) not in indexes:
                fs = get_filings(year=year, quarter=quarter, form="10-K", amendments=False)
                df = fs.to_pandas() if fs is not None else None
                indexes[(year, quarter)] = df[df["form"] == "10-K"].reset_index(drop=True) if df is not None else None
            df = indexes[(year, quarter)]
            if df is None or df.empty:
                continue
            row = df.iloc[rng.randrange(len(df))]
            cik, acc = int(row["cik"]), row["accession_number"]
            if cik in ciks or cik in seen_ciks or acc in accessions:
                rejected["dev_corpus"] += 1
                continue
            seen_ciks.add(cik)
            try:
                sic = int(Company(cik).sic or 0)
            except Exception:  # noqa: BLE001
                sic = 0
            if sic == ABS_SIC:
                rejected["abs"] += 1
                continue
            filing = get_by_accession_number_enriched(acc)
            html = filing.html() if filing is not None else None
            if not html:
                rejected["no_html"] += 1
                continue
            flt = public_float(html)
            if flt is None:
                rejected["float_unstated"] += 1
                continue
            stratum = "large" if flt >= LARGE_FLOAT else "small"
            if not quota[stratum]:
                rejected["stratum_full"] += 1
                continue
            quota[stratum] -= 1
            (CACHE / f"{acc}.html").write_text(html)
            picked.append({"accession": acc, "cik": cik, "company": row["company"],
                           "filing_date": str(row["filing_date"]), "era": era, "size": stratum,
                           "public_float": flt, "sic": sic, "items": {}})
            print(f"  {era} {stratum:5s} {acc} {row['company']} (float {flt:,})")  # noqa: T201
    print(f"rejected: {rejected}")  # noqa: T201
    TRUTH_PATH.write_text(json.dumps({
        "seed": SEED, "per_era": PER_ERA, "eras": ERAS, "large_float": LARGE_FLOAT,
        "chars": scoring.TRUTH_CHARS, "rejected": rejected,
        "excluded_ciks": sorted(ciks), "retired": [], "filings": picked,
    }, indent=1, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# fetch / parse
# ---------------------------------------------------------------------------

def load():
    return json.loads(TRUTH_PATH.read_text())


def save(truth):
    TRUTH_PATH.write_text(json.dumps(truth, indent=1, ensure_ascii=False) + "\n")


def cached_html(accession):
    p = CACHE / f"{accession}.html"
    return p if p.exists() else None


def cmd_fetch():
    from edgar import get_by_accession_number_enriched

    CACHE.mkdir(parents=True, exist_ok=True)
    for f in load()["filings"]:
        if cached_html(f["accession"]):
            continue
        filing = get_by_accession_number_enriched(f["accession"])
        html = filing.html() if filing is not None else None
        if not html:
            print(f"  NO HTML {f['accession']} {f['company']}")  # noqa: T201
            continue
        (CACHE / f"{f['accession']}.html").write_text(html)
        print(f"  fetched {f['accession']} ({len(html):,} chars)")  # noqa: T201


def parse(accession):
    """The parsed Document, exactly as TenK.document builds it."""
    from edgar.documents import HTMLParser, ParserConfig

    p = cached_html(accession)
    if p is None:
        return None
    return HTMLParser(ParserConfig(form="10-K")).parse(p.read_text(errors="ignore"))


# The labeller reads the full-document text; the pipeline's slice is
# ``section.text()``. The two render the same content with different rule
# lines (box-drawing characters) and dash glyphs, so both sides are
# normalised before the 80-character windows are cut and compared.
_RULE_CHARS_RE = re.compile(r"[\u2500-\u257f]+")
_DASHES_RE = re.compile(r"[\u2010-\u2015\u2212]")


def head_tail(text):
    return scoring.head_tail(_DASHES_RE.sub("-", _RULE_CHARS_RE.sub(" ", text or "")))


def document_lines(doc):
    return (doc.text() or "").splitlines()


# ---------------------------------------------------------------------------
# dump (blind labelling input) / cut (line labels -> truth windows)
# ---------------------------------------------------------------------------

def cmd_dump(out_dir):
    """One numbered text file per filing: the full-document text and nothing about sections."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in load()["filings"]:
        doc = parse(f["accession"])
        if doc is None:
            continue
        lines = document_lines(doc)
        with open(out / f"{f['accession']}.txt", "w") as fh:
            for i, line in enumerate(lines, 1):
                fh.write(f"{i:6d}| {line}\n")
        print(f"  {f['accession']}: {len(lines):,} lines")  # noqa: T201


STANDARD_ITEMS = {"1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8",
                  "9", "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16"}
_MATCH_CHARS = 48


def same_boundary(want, got, side):
    """Whether two windows mark the same boundary.

    The truth window is cut from the full-document text and the live one from
    ``section.text()``, which render the same content with different spacing
    and punctuation ("Qualit ative", "Items 10 - 14" vs "Items 10-14"). Compare
    the first (start) or last (end) 48 letters and digits instead of bytes.
    """
    if not want or not got:
        return False
    a, b = re.sub(r"[^0-9a-z]", "", want.lower()), re.sub(r"[^0-9a-z]", "", got.lower())
    n = min(_MATCH_CHARS, len(a), len(b))
    if n < min(_MATCH_CHARS, len(a)):
        return False
    return a[:n] == b[:n] if side == "start" else a[-n:] == b[-n:]


def window(lines, start, end, start_text=None, end_text=None):
    """head/tail windows of lines[start..end] (1-based, inclusive).

    ``start_text`` trims the first line to begin at that text and ``end_text``
    trims the last line to finish after it, for a boundary that falls mid-line
    (a table row rendered as one line, a heading run into its first sentence).
    """
    first, last = lines[start - 1], lines[end - 1]
    if start_text:
        i = scoring.collapse(first).find(scoring.collapse(start_text))
        if i < 0:
            raise ValueError(f"start_text {start_text!r} not on line {start}")
        first = scoring.collapse(first)[i:]
    if end_text:
        lc = scoring.collapse(last) if start != end else scoring.collapse(first)
        j = lc.find(scoring.collapse(end_text))
        if j < 0:
            raise ValueError(f"end_text {end_text!r} not on line {end}")
        last = lc[: j + len(scoring.collapse(end_text))]
    if start == end:
        body = [last if end_text else first]
    else:
        body = [first, *lines[start:end - 1], last]
    return head_tail("\n".join(body))


def cmd_cut(labels_path):
    """Merge a labeller's line labels into the truth file.

    Input: {accession: {"items": {"1": {start, end, start_text?, end_text?, title_only?, note?}},
    "absent": [...], "notes": "..."}} keyed by bare item key ("1", "1A", "7A").
    """
    labels = json.loads(Path(labels_path).read_text())
    truth = load()
    by_acc = {f["accession"]: f for f in truth["filings"]}
    for acc, lab in labels.items():
        f = by_acc[acc]
        lines = document_lines(parse(acc))
        items = {}
        for key, it in lab["items"].items():
            head, tail = window(lines, it["start"], it["end"], it.get("start_text"), it.get("end_text"))
            items[key.upper()] = {"start": head, "end": tail, "lines": [it["start"], it["end"]],
                                  "verified": "blind", **({"note": it["note"]} if it.get("note") else {})}
        f["items"] = items
        f["absent"] = lab.get("absent", [])
        if lab.get("notes"):
            f["notes"] = lab["notes"]
        print(f"  {acc}: {len(items)} items")  # noqa: T201
    save(truth)


# ---------------------------------------------------------------------------
# compare / resolve (blind adjudication of labeller-vs-pipeline disagreements)
# ---------------------------------------------------------------------------

def _line_index(lines):
    """Collapsed full text plus, per character, the 1-based line it came from."""
    parts, owner = [], []
    for i, line in enumerate(lines, 1):
        c = scoring.collapse(_DASHES_RE.sub("-", _RULE_CHARS_RE.sub(" ", line)))
        if not c:
            continue
        if parts:
            parts.append(" ")
            owner.append(i)
        parts.append(c)
        owner.extend([i] * len(c))
    return "".join(parts), owner


def _locate(full, owner, needle, near_line, at_end):
    """Line of the occurrence of ``needle`` nearest ``near_line`` (its last char when at_end)."""
    best, pos = None, full.find(needle)
    while pos >= 0 and needle:
        line = owner[pos + len(needle) - 1] if at_end else owner[pos]
        if best is None or abs(line - near_line) < abs(best - near_line):
            best = line
        pos = full.find(needle, pos + 1)
    return best


def _context(lines, line, radius=6):
    if line is None:
        return None
    lo, hi = max(1, line - radius), min(len(lines), line + radius)
    return [f"{i:6d}| {lines[i - 1]}" for i in range(lo, hi + 1)]


def cmd_compare(out_path):
    """Write every side where the blind label and the pipeline differ, candidates unlabelled.

    The adjudicator sees A and B in random order with the lines around each;
    the key mapping A/B to labeller/pipeline goes to ``<out>.key.json``.
    """
    rng = random.Random(7)  # noqa: S311
    cases, key = [], {}
    for f in load()["filings"]:
        if not f["items"]:
            continue
        lines = document_lines(parse(f["accession"]))
        full, owner = _line_index(lines)
        live = live_items(f["accession"])
        for item, want in f["items"].items():
            got = live.get(item)
            for side, field, at_end in (("start", "head", False), ("end", "tail", True)):
                if got is not None and same_boundary(want[side], got[field], side):
                    continue
                lab_line = want["lines"][0 if side == "start" else 1]
                pipe_line = _locate(full, owner, got[field], lab_line, at_end) if got else None
                cand = {"labeller": {"window": want[side], "line": lab_line,
                                     "context": _context(lines, lab_line)},
                        "pipeline": {"window": got[field] if got else None, "line": pipe_line,
                                     "context": _context(lines, pipe_line)}}
                order = ["labeller", "pipeline"]
                rng.shuffle(order)
                cid = f"{f['accession']}|{item}|{side}"
                key[cid] = {"A": order[0], "B": order[1]}
                cases.append({"id": cid, "company": f["company"], "item": item, "side": side,
                              "A": cand[order[0]], "B": cand[order[1]]})
        # Items the pipeline emits that the labeller did not list: present and
        # missed by the labeller, or spurious? Shown without saying who found it.
        absent = {a["item"] for a in f.get("absent", [])}
        for item in sorted((set(live) & STANDARD_ITEMS) - set(f["items"])):
            got = live[item]
            line = _locate(full, owner, got["head"], 0, False)
            cases.append({"id": f"{f['accession']}|{item}|presence", "company": f["company"],
                          "item": item, "side": "presence", "labeller_listed_absent": item in absent,
                          "candidate": {"window": got["head"], "line": line,
                                        "context": _context(lines, line)}})
    Path(out_path).write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    Path(out_path).with_suffix(".key.json").write_text(json.dumps(key, indent=1))
    print(f"{len(cases)} disagreeing sides -> {out_path}")  # noqa: T201


def cmd_resolve(verdicts_path, key_path):
    """Apply verdicts: {id: {"choice": "A"|"B"|"neither"|"absent", "line": N?, "text": "..."?, "why": "..."}}.

    Presence cases take {"choice": "present", start, end, start_text?, end_text?}
    or {"choice": "absent"}. "absent" on a start/end case drops the item.

    "neither" needs ``line`` (and ``text`` for a mid-line boundary): the
    correct start or end line, re-cut from the document.
    """
    verdicts = json.loads(Path(verdicts_path).read_text())
    key = json.loads(Path(key_path).read_text())
    truth = load()
    by_acc = {f["accession"]: f for f in truth["filings"]}
    tally = {"labeller": 0, "pipeline": 0, "neither": 0}
    for cid, v in verdicts.items():
        acc, item, side = cid.split("|")
        f = by_acc[acc]
        if side == "presence":
            if v["choice"] == "present":
                lines = document_lines(parse(acc))
                head, tail = window(lines, v["start"], v["end"], v.get("start_text"), v.get("end_text"))
                f["items"][item] = {"start": head, "end": tail, "lines": [v["start"], v["end"]],
                                    "verified": "adjudicated", "why": {"presence": v.get("why", "")}}
                f["absent"] = [a for a in f.get("absent", []) if a["item"] != item]
            elif not any(a["item"] == item for a in f.get("absent", [])):
                f.setdefault("absent", []).append({"item": item, "note": v.get("why", "")})
            continue
        want = f["items"].setdefault(item, {"verified": "adjudicated"}) if v["choice"] != "absent" else None
        if v["choice"] == "absent":
            f["items"].pop(item, None)
            f.setdefault("absent", []).append({"item": item, "note": v.get("why", "")})
            continue
        winner = key[cid][v["choice"]] if v["choice"] in ("A", "B") else "neither"
        tally[winner] += 1
        if winner == "pipeline":
            live = live_items(acc)[item]
            want[side] = live["head" if side == "start" else "tail"]
        elif winner == "neither":
            lines = document_lines(parse(acc))
            s, e = want["lines"]
            if side == "start":
                s = v["line"]
                head, _ = window(lines, s, e, start_text=v.get("text"))
                want["start"] = head
            else:
                e = v["line"]
                _, tail = window(lines, s, e, end_text=v.get("text"))
                want["end"] = tail
            want["lines"] = [s, e]
        want["verified"] = "adjudicated"
        want.setdefault("why", {})[side] = f"{winner}: {v.get('why', '')}"
    save(truth)
    print(f"applied {len(verdicts)} verdicts: {tally}")  # noqa: T201


def cmd_finalize():
    """Record how each still-``blind`` label was settled, against the pipeline at labelling time.

    ``agreed``: the pipeline's slice matched the blind label on both sides.
    ``single``: the pipeline emitted no section for the item, so only the
    labeller's boundary exists (it scores as a miss either way; its exact
    boundary has had one reader).
    """
    truth = load()
    tally = {}
    for f in truth["filings"]:
        live = live_items(f["accession"])
        for item, want in f["items"].items():
            if want["verified"] != "blind":
                continue
            got = live.get(item)
            if got is None:
                want["verified"] = "single"
            elif same_boundary(want["start"], got["head"], "start") and same_boundary(want["end"], got["tail"], "end"):
                want["verified"] = "agreed"
            tally[want["verified"]] = tally.get(want["verified"], 0) + 1
    save(truth)
    print(f"finalized: {tally}")  # noqa: T201


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def live_items(accession):
    """{item_key: {head, tail, method}} through the live pipeline, keyed like the truth."""
    doc = parse(accession)
    out = {}
    if doc is None:
        return out
    for name, section in doc.sections.items():
        # Pattern-detected sections carry semantic names ('mda', 'business');
        # their item is on the section, not in the name.
        key = getattr(section, "item", None) or scoring.item_key(name)
        key = key.upper() if key else None
        if key is None or key in out:
            continue
        try:
            text = section.text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        head, tail = head_tail(text)
        out[key] = {"head": head, "tail": tail, "method": getattr(section, "detection_method", None)}
    return out


def score_filing(f):
    live = live_items(f["accession"])
    rows = []
    for key, want in f["items"].items():
        got = live.get(key)
        rows.append({"item": key, "found": got is not None,
                     "start": bool(got) and same_boundary(want["start"], got["head"], "start"),
                     "end": bool(got) and same_boundary(want["end"], got["tail"], "end"),
                     "method": got["method"] if got else None})
    # Non-standard keys the pipeline emits ("4A" for a filer's executive-officer
    # heading, "2P" for a mis-keyed "ITEM 2 - PROPERTIES") are not charged as
    # spurious; a mis-keyed item already scores as a miss on its real key.
    spurious = sorted((set(live) & STANDARD_ITEMS) - set(f["items"]))
    return rows, spurious


def _rate(per_filing, field):
    num = sum(sum(r[field] for r in rows) for rows in per_filing)
    den = sum(len(rows) for rows in per_filing)
    return num, den


def _boot_ci(per_filing, field, n=2000):
    """95% CI resampling FILINGS, since items within a filing fail together."""
    rng = random.Random(0)  # noqa: S311
    vals = []
    for _ in range(n):
        s = [per_filing[rng.randrange(len(per_filing))] for _ in per_filing]
        num, den = _rate(s, field)
        if den:
            vals.append(num / den)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def cmd_report():
    truth = load()
    filings = [f for f in truth["filings"] if f["items"]]
    scored = []
    for f in filings:
        rows, spurious = score_filing(f)
        for r in rows:
            r["both"] = r["start"] and r["end"]
        scored.append((f, rows, spurious))
    print(f"held-out 10-K: {len(scored)} labelled filings, "  # noqa: T201
          f"{sum(len(r) for _, r, _ in scored)} items\n")

    def block(title, group):
        per = [rows for _, rows, _ in group]
        if not per or not sum(len(r) for r in per):
            return
        print(f"{title}")  # noqa: T201
        for field in ("found", "start", "end", "both"):
            num, den = _rate(per, field)
            lo, hi = _boot_ci(per, field)
            label = "recall" if field == "found" else f"{field}-exact"
            print(f"  {label:12s} {num:4d}/{den:<4d} {100 * num / den:5.1f}%  [{100 * lo:.1f}, {100 * hi:.1f}]")  # noqa: T201
        spur = sum(len(s) for _, _, s in group)
        found = sum(r["found"] for _, rows, _ in group for r in rows)
        if found + spur:
            print(f"  precision    {found:4d}/{found + spur:<4d} {100 * found / (found + spur):5.1f}%  "  # noqa: T201
                  f"({spur} emitted items not in the filing)")
        print()  # noqa: T201

    block("ALL", scored)
    for era in truth["eras"]:
        block(f"era {era}", [s for s in scored if s[0]["era"] == era])
    by_method = {}
    for _f, rows, _ in scored:
        for r in rows:
            if r["found"]:
                by_method.setdefault(r["method"], []).append(r)
    print("by detection method (found items only)")  # noqa: T201
    for m, rs in sorted(by_method.items(), key=lambda kv: str(kv[0])):
        both = sum(r["both"] for r in rs)
        print(f"  {str(m):10s} {both:4d}/{len(rs):<4d} both-exact {100 * both / len(rs):5.1f}%")  # noqa: T201
    if "-v" in sys.argv:
        print("\nmisses")  # noqa: T201
        for f, rows, spurious in scored:
            for r in rows:
                if not r["both"]:
                    print(f"  {f['accession']} {f['company'][:30]:30s} item {r['item']:4s} "  # noqa: T201
                          f"found={r['found']} start={r['start']} end={r['end']}")
            if spurious:
                print(f"  {f['accession']} {f['company'][:30]:30s} spurious {spurious}")  # noqa: T201


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"sample": cmd_sample, "fetch": cmd_fetch, "report": cmd_report,
     "dump": lambda: cmd_dump(sys.argv[2]), "cut": lambda: cmd_cut(sys.argv[2]),
     "compare": lambda: cmd_compare(sys.argv[2]), "finalize": cmd_finalize,
     "resolve": lambda: cmd_resolve(sys.argv[2], sys.argv[3])}[cmd]()
