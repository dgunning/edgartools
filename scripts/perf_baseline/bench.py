"""The 6.0 performance baseline: wall-clock, memory, and output schema.

Runs entirely off the cached corpus, so numbers are comparable across runs and
across machines-with-the-same-corpus. Build it first:

    python scripts/perf_baseline/build_corpus.py
    python scripts/perf_baseline/bench.py --out engineering/analysis/perf-baseline

Three things are recorded, and the third is the one that is easy to leave out:

  timings   median and p95 over N repetitions, per document, per stage. Each
            repetition parses fresh, because sections/tables/markdown are cached
            on the Document and a warm second access measures nothing.
  memory    tracemalloc peak, on a separate pass — tracemalloc has enough
            overhead to distort the timings if left on during them.
  schemas   structural fingerprints of the DataFrame surfaces downstream
            consumers filter on (see schema_snapshot.py and GH #929). A perf
            change that leaves timings alone can still break a caller, so the
            baseline has to carry both or it gives false assurance.

pyinstrument profiles are opt-in via --profile: it is a hatch-env dependency,
not a runtime one, and the baseline itself must run in a plain checkout.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).parent
CORPUS = HERE / "corpus"
MANIFEST = HERE / "corpus_manifest.json"

sys.path.insert(0, str(HERE))
from schema_snapshot import snapshot  # noqa: E402


def _time(fn, reps: int) -> dict | None:
    """Median/p95 wall time in ms. None if the callable raises."""
    samples = []
    for _ in range(reps):
        start = time.perf_counter()
        try:
            fn()
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": round(sorted(samples)[min(int(len(samples) * 0.95), len(samples) - 1)], 2),
        "min_ms": round(min(samples), 2),
        "reps": reps,
    }


def _peak_mb(fn) -> dict:
    """tracemalloc peak for one call, in MB."""
    tracemalloc.start()
    try:
        fn()
    except Exception as exc:
        tracemalloc.stop()
        return {"error": f"{type(exc).__name__}: {exc}"}
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"peak_mb": round(peak / 1e6, 1)}


# --- documents -------------------------------------------------------------

def bench_document(html: str, reps: int, form: str | None = None) -> dict:
    """Parse and then exercise each downstream stage on a freshly parsed doc.

    `form` is not optional in practice: ParserConfig.form gates section
    detection, and without it doc.sections is empty and the sections timing
    measures nothing at all.
    """
    from edgar.documents import HTMLParser
    from edgar.documents.config import ParserConfig

    def parser():
        return HTMLParser(ParserConfig(form=form))

    results = {"parse": _time(lambda: parser().parse(html), reps)}

    # Each stage gets a fresh document: these are cached properties, so timing a
    # second access on the same object measures the cache, not the work.
    stages = {
        "sections": lambda doc: doc.sections,
        "tables": lambda doc: doc.tables,
        "text": lambda doc: doc.text(),
        "markdown": lambda doc: doc.to_markdown(),
        "headings": lambda doc: doc.headings,
    }
    for name, stage in stages.items():
        def run(stage=stage):
            doc = parser().parse(html)
            stage(doc)
        timing = _time(run, reps)
        # Subtract parse so the stage cost is legible on its own.
        if timing and "median_ms" in timing and "median_ms" in results["parse"]:
            timing["net_of_parse_ms"] = round(
                timing["median_ms"] - results["parse"]["median_ms"], 2)
        results[name] = timing

    results["memory"] = _peak_mb(lambda: parser().parse(html))

    # Output sizes alongside the timings. A "faster" parse that quietly produces
    # 40% less text is not faster, and these counts are what make that visible
    # in a diff — the same argument as the schema snapshots, one level up.
    try:
        doc = parser().parse(html)
        results["outputs"] = {
            "sections": len(doc.sections or {}),
            "tables": len(doc.tables or []),
            "headings": len(doc.headings or []),
            "text_chars": len(doc.text()),
            "markdown_chars": len(doc.to_markdown()),
        }
    except Exception as exc:
        results["outputs"] = {"error": f"{type(exc).__name__}: {exc}"}
    return results


# --- xbrl ------------------------------------------------------------------

def _xbrl_from_dir(xbrl_dir: Path):
    from edgar.xbrl.xbrl import XBRL

    def path_for(role: str):
        p = xbrl_dir / f"{role}.xml"
        return str(p) if p.exists() else None

    return XBRL.from_files(
        instance_file=path_for("instance"),
        schema_file=path_for("schema"),
        presentation_file=path_for("presentation"),
        calculation_file=path_for("calculation"),
        definition_file=path_for("definition"),
        label_file=path_for("label"),
    )


def bench_xbrl(xbrl_dir: Path, reps: int) -> dict:
    results = {"parse": _time(lambda: _xbrl_from_dir(xbrl_dir), reps)}

    xbrl = _xbrl_from_dir(xbrl_dir)

    # The query builder caches its DataFrame per column-set, so a fresh query
    # object per repetition is required to measure the conversion.
    results["facts_query_df"] = _time(
        lambda: xbrl.facts.query().to_dataframe(), reps)
    results["income_statement_render"] = _time(
        lambda: xbrl.render_statement("IncomeStatement"), reps)
    results["memory"] = _peak_mb(lambda: _xbrl_from_dir(xbrl_dir))
    return results


# --- schema surfaces -------------------------------------------------------

def capture_schemas(manifest: dict, reps: int) -> dict:
    """Fingerprint the DataFrame surfaces named in the GH #929 commitment.

    Gated surfaces first, then whatever else the corpus makes cheap to reach.
    A surface that cannot be built from the cached corpus is recorded as
    unavailable rather than skipped silently — an absent key in the baseline
    would read as "no change" on the next diff.
    """
    schemas = {}

    def record(name, build):
        try:
            df = build()
        except Exception as exc:
            schemas[name] = {"unavailable": f"{type(exc).__name__}: {exc}"}
            return
        schemas[name] = snapshot(df, label=name)

    # Filings.to_pandas() — arrow schema, rewritten by the planned pyarrow work.
    index = manifest.get("index")
    if index:
        def filings_df():
            import pyarrow.parquet as pq
            from edgar._filings import Filings
            return Filings(pq.read_table(HERE / index["path"])).to_pandas()
        record("Filings.to_pandas()", filings_df)
    else:
        schemas["Filings.to_pandas()"] = {"unavailable": "no cached index in corpus"}

    # FactsQuery.to_dataframe() — the surface the reported incident was on.
    entry = next((e for e in manifest["entries"] if e.get("xbrl_roles")), None)
    if entry:
        xbrl_dir = CORPUS / entry["key"] / "xbrl"
        xbrl = _xbrl_from_dir(xbrl_dir)
        record("FactsQuery.to_dataframe()",
               lambda: xbrl.facts.query().to_dataframe())
        record("FactsQuery.to_dataframe() [IncomeStatement]",
               lambda: xbrl.facts.query().by_statement_type("IncomeStatement").to_dataframe())
        schemas["_source"] = {"xbrl_entry": entry["key"], "accession": entry["accession"]}
    else:
        schemas["FactsQuery.to_dataframe()"] = {"unavailable": "no XBRL in corpus"}

    # EntityFacts surfaces. Company facts come from a different endpoint than the
    # filing bundles, so these need their own cached payload; without it they were
    # not merely unavailable but absent from the capture entirely, which is the
    # silence this file exists to avoid.
    entity_specs = manifest.get("entity_facts") or []
    entity_names = ["EntityFacts.to_dataframe()",
                    "EntityFacts.to_dataframe() [include_metadata]",
                    "entity.FactQuery.to_dataframe()",
                    "entity.FactQuery.to_dataframe() [Revenues]"]
    if entity_specs:
        from edgar.entity.parser import EntityFactsParser

        # Pinned to the first spec: the gate compares one company run over run, so
        # a second company would be a different measurement, not a better one.
        spec = entity_specs[0]
        payload = json.loads((HERE / spec["path"]).read_text())
        entity_facts = EntityFactsParser.parse_company_facts(payload)
        if entity_facts is None:
            for name in entity_names:
                schemas[name] = {"unavailable": f"parse returned None for CIK {spec['cik']}"}
        else:
            record("EntityFacts.to_dataframe()", lambda: entity_facts.to_dataframe())
            record("EntityFacts.to_dataframe() [include_metadata]",
                   lambda: entity_facts.to_dataframe(include_metadata=True))
            record("entity.FactQuery.to_dataframe()",
                   lambda: entity_facts.query().to_dataframe())
            # A narrowing query, because narrowing is what moved the schema on the
            # XBRL side of the house (edgartools-rsyt).
            record("entity.FactQuery.to_dataframe() [Revenues]",
                   lambda: entity_facts.query().by_concept("Revenues").to_dataframe())
            schemas["_entity_source"] = {"key": spec["key"], "cik": spec["cik"]}
    else:
        for name in entity_names:
            schemas[name] = {"unavailable": "no cached company facts in corpus"}

    # StitchedFactQuery — two filings from ONE company, so the stitcher has
    # something coherent to align across periods.
    stitch_keys = sorted(e["key"] for e in manifest["entries"]
                         if e.get("xbrl_roles") and e["key"].startswith("footlocker"))
    if len(stitch_keys) >= 2:
        from edgar.xbrl.stitching import XBRLS

        def stitched_df():
            xbrls = XBRLS([_xbrl_from_dir(CORPUS / key / "xbrl") for key in stitch_keys])
            return xbrls.facts.query().to_dataframe()
        record("StitchedFactQuery.to_dataframe()", stitched_df)
        schemas["_stitch_source"] = {"keys": stitch_keys}
    else:
        schemas["StitchedFactQuery.to_dataframe()"] = {
            "unavailable": f"needs 2 same-company XBRL entries, found {len(stitch_keys)}"}

    # Document.to_dataframe() — INFORMATIONAL, not gated. Its columns are the
    # columns of whatever tables the document happens to contain, so two
    # different filings produce unrelated schemas and a diff across them means
    # nothing. Pinned to one entry so at least the same document is compared
    # run over run.
    doc_entry = next((e for e in manifest["entries"]
                      if e["key"] == "meta_10k_fy2024"), None)
    if doc_entry:
        def document_df():
            from edgar.documents import HTMLParser
            from edgar.documents.config import ParserConfig
            html = (CORPUS / doc_entry["key"] / "primary.html").read_text(encoding="utf-8")
            return HTMLParser(ParserConfig()).parse(html).to_dataframe()
        record("Document.to_dataframe()", document_df)

    return schemas


# --- import time -----------------------------------------------------------

def bench_import(reps: int = 5) -> dict:
    """Cold `import edgar` cost, measured out-of-process.

    In-process timing is meaningless here: the module is already imported, and
    sys.modules manipulation does not undo the C-extension and codegen work.
    """
    samples = []
    code = "import time; t=time.perf_counter(); import edgar; print((time.perf_counter()-t)*1000)"
    for _ in range(reps):
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, cwd=str(HERE.parent.parent))
        if proc.returncode != 0:
            return {"error": proc.stderr.strip()[:300]}
        samples.append(float(proc.stdout.strip().splitlines()[-1]))
    return {
        "median_ms": round(statistics.median(samples), 1),
        "min_ms": round(min(samples), 1),
        "reps": reps,
    }


# --- main ------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(HERE / "results"),
                    help="directory for results JSON (default: scripts/perf_baseline/results)")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--only", help="run a single corpus entry by key")
    ap.add_argument("--skip-documents", action="store_true")
    ap.add_argument("--skip-xbrl", action="store_true")
    ap.add_argument("--skip-schemas", action="store_true")
    ap.add_argument("--profile", metavar="KEY",
                    help="write a pyinstrument profile for one entry (hatch env only)")
    ap.add_argument("--profile-stage", default="sections",
                    choices=["parse", "sections", "tables", "text", "markdown", "headings"],
                    help="which stage to profile (default: sections, the baseline's "
                         "most expensive stage). Every stage but 'parse' profiles the "
                         "parse too, since the stage needs a parsed document.")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print("No corpus. Run: python scripts/perf_baseline/build_corpus.py", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["entries"]
    if args.only:
        entries = [e for e in entries if e["key"] == args.only]
        if not entries:
            print(f"No corpus entry named {args.only}", file=sys.stderr)
            return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from edgar import __version__ as edgar_version

    if args.profile:
        return write_profile(args.profile, out, args.profile_stage, manifest)

    results = {
        "edgar_version": edgar_version,
        "python": sys.version.split()[0],
        "reps": args.reps,
        "import_edgar": bench_import(),
        "documents": {},
        "xbrl": {},
    }
    print(f"edgartools {edgar_version} | python {results['python']} | reps={args.reps}")
    print(f"import edgar: {results['import_edgar'].get('median_ms')} ms\n")

    if not args.skip_documents:
        print(f"{'entry':<28}{'MB':>7}{'parse ms':>11}{'sections':>10}"
              f"{'tables':>10}{'text':>10}{'markdown':>11}{'peak MB':>10}")
        for entry in entries:
            path = CORPUS / entry["key"] / "primary.html"
            if not path.exists():
                print(f"{entry['key']:<28} (not cached)")
                continue
            html = path.read_text(encoding="utf-8")
            res = bench_document(html, args.reps, form=entry.get("form"))
            results["documents"][entry["key"]] = {
                "accession": entry["accession"],
                "form": entry.get("form"),
                "html_mb": round(entry["html_bytes"] / 1e6, 2),
                **res,
            }

            def cell(stage, field="net_of_parse_ms"):
                data = res.get(stage) or {}
                if "error" in data:
                    return "ERR"
                value = data.get(field, data.get("median_ms"))
                return f"{value:,.0f}" if value is not None else "-"

            print(f"{entry['key']:<28}{entry['html_bytes']/1e6:>7.1f}"
                  f"{cell('parse', 'median_ms'):>11}{cell('sections'):>10}"
                  f"{cell('tables'):>10}{cell('text'):>10}{cell('markdown'):>11}"
                  f"{res['memory'].get('peak_mb', '-'):>10}")

    if not args.skip_xbrl:
        print(f"\n{'entry':<28}{'parse ms':>11}{'facts df':>11}{'render ms':>11}{'peak MB':>10}")
        for entry in entries:
            xbrl_dir = CORPUS / entry["key"] / "xbrl"
            if not xbrl_dir.exists() or not any(xbrl_dir.glob("*.xml")):
                continue
            res = bench_xbrl(xbrl_dir, args.reps)
            results["xbrl"][entry["key"]] = {"accession": entry["accession"], **res}

            def xcell(stage):
                data = res.get(stage) or {}
                if "error" in data:
                    return "ERR"
                return f"{data.get('median_ms', 0):,.0f}"

            print(f"{entry['key']:<28}{xcell('parse'):>11}{xcell('facts_query_df'):>11}"
                  f"{xcell('income_statement_render'):>11}"
                  f"{res['memory'].get('peak_mb', '-'):>10}")

    (out / "timings.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nTimings -> {out / 'timings.json'}")

    if not args.skip_schemas:
        schemas = capture_schemas(manifest, args.reps)
        (out / "schemas.json").write_text(json.dumps(schemas, indent=2) + "\n")
        print(f"Schemas -> {out / 'schemas.json'}")
        for name, snap in schemas.items():
            if name.startswith("_"):
                continue
            if "unavailable" in snap:
                print(f"  {name}: UNAVAILABLE — {snap['unavailable']}")
            else:
                print(f"  {name}: {len(snap['columns'])} columns, {snap['row_count']:,} rows")

    return 0


def write_profile(key: str, out: Path, stage: str, manifest: dict) -> int:
    """pyinstrument profile of one entry's stage. Requires the hatch env.

    The entry's form is taken from the manifest, not defaulted away:
    ParserConfig.form gates section detection, so profiling with a bare config
    walks a different code path than the benchmark measures — an empty
    doc.sections and a flat 25ms where the baseline records 6.6s.
    """
    try:
        from pyinstrument import Profiler
    except ImportError:
        print("pyinstrument is a hatch-env dependency. Run under:\n"
              "  hatch run python scripts/perf_baseline/bench.py --profile KEY", file=sys.stderr)
        return 1

    from edgar.documents import HTMLParser
    from edgar.documents.config import ParserConfig

    path = CORPUS / key / "primary.html"
    if not path.exists():
        print(f"No cached entry {key}", file=sys.stderr)
        return 1
    html = path.read_text(encoding="utf-8")

    entry = next((e for e in manifest["entries"] if e["key"] == key), {})
    form = entry.get("form")
    stages = {
        "sections": lambda doc: doc.sections,
        "tables": lambda doc: doc.tables,
        "text": lambda doc: doc.text(),
        "markdown": lambda doc: doc.to_markdown(),
        "headings": lambda doc: doc.headings,
    }

    profiler = Profiler()
    profiler.start()
    doc = HTMLParser(ParserConfig(form=form)).parse(html)
    if stage != "parse":
        result = stages[stage](doc)
    profiler.stop()

    if stage != "parse":
        print(f"{stage}: {len(result or [])} produced (form={form})")
    dest = out / f"profile-{key}-{stage}.html"
    dest.write_text(profiler.output_html())
    print(profiler.output_text(unicode=True, color=True, show_all=False))
    print(f"\nProfile -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
