# EdgarTools 6.0 performance baseline — 5.45.1

**Measured**: 2026-08-03 · edgartools 5.45.1 · Python 3.11.6 · macOS (darwin 25.5.0)
**Harness**: `scripts/perf_baseline/` · **Raw data**: `timings.json`, `schemas.json`

This is the reference point every 6.0 performance change is measured against.
5.45.1 is the right place to take it: 5.45.0 changed extracted text for nearly
every filing, so any baseline recorded before it was stale on arrival.

Numbers are median of 3 repetitions on one machine. They are for **comparison
against a later run on the same machine and corpus**, not for quoting as
absolute performance — and 3 repetitions is thin enough that stage costs under
~100 ms move ±20% between runs. Treat anything in that band as noise.

---

## Headline: section extraction costs more than parsing

| entry | MB | parse | **sections** | tables | text | markdown | peak mem |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fanniemae_abs15g_2018` | 25.2 | 14,230 | 26 | 99 | 4,329 | 200 | 258 MB |
| `citigroup_10k_fy2024` | 16.7 | 3,086 | **5,160** | 399 | 528 | 132 | 99 MB |
| `morganstanley_10k_fy2024` | 9.8 | 1,932 | **6,588** | -16 | 220 | 15 | 59 MB |
| `regions_10k_fy2021` | 9.5 | 1,697 | **3,757** | 55 | 219 | 52 | 56 MB |
| `ambac_10k_fy2022` | 7.7 | 1,396 | **3,471** | 14 | 167 | 25 | 47 MB |
| `odp_10k_fy2025` | 5.6 | 974 | 1,232 | -27 | 65 | 5 | 31 MB |
| `footlocker_10k_fy2024` | 3.0 | 571 | 1,197 | 12 | 75 | 14 | 27 MB |
| `tesla_10k_fy2023` | 2.7 | 563 | 1,554 | 0 | 97 | 13 | 19 MB |
| `meta_10k_fy2024` | 2.4 | 523 | 1,126 | 9 | 79 | 7 | 18 MB |
| `footlocker_10k_fy2013` | 2.3 | 469 | 723 | -3 | 56 | 5 | 21 MB |
| `jackhenry_10q_fy2025` | 0.8 | 161 | 177 | 5 | 29 | 6 | 5 MB |

All figures milliseconds. `parse` is total; every other column is **net of
parse** — each stage runs on a freshly parsed document, because these are
cached properties and a second access measures the cache rather than the work.
Small negatives are that subtraction landing inside the noise band, which is
itself the finding for `tables`: tables are materialized during parse, so
accessing them costs nothing.

**Section extraction is the single largest post-parse cost, and on the largest
documents it exceeds parsing itself** — 6.6 s against a 1.9 s parse on Morgan
Stanley (3.4×), 5.2 s against 3.1 s on Citigroup. Everything downstream of
parse (text, markdown, headings, tables) is comparatively free. If the perf
program optimizes one thing, it is this.

That is worth stating plainly because the candidate hot-spot list this work
started from (`document_builder.py` tree build, `table_matrix.py`, `toc_analyzer.py`)
had section analysis as one item among several. The measurement says it
dominates.

### Section detection burns seconds when it finds nothing

The ABS-15G entry was initially benchmarked with `form="10-K"` (a mislabel in
the corpus spec, since corrected). Section detection spent **6,450 ms** on it
and found zero sections. With the correct `form="ABS-15G"` the same stage costs
**26 ms**.

A 250× swing between "no sections found, fast" and "no sections found, slow" is
a real cost on any document whose structure does not match the form it is
parsed as. Worth understanding before the section work starts.

### Memory tracks input size at roughly 10×

Peak `tracemalloc` during parse: 258 MB for a 25 MB document, 99 MB for 16.7 MB,
5 MB for 0.8 MB. Close to linear, which is the reassuring answer — no size band
falls off a cliff.

---

## XBRL is not the bottleneck

| entry | parse | facts→df | statement render | peak mem |
|---|---:|---:|---:|---:|
| `citigroup_10k_fy2024` | 435 | 114 | 6 | 99 MB |
| `morganstanley_10k_fy2024` | 278 | 81 | 4 | 62 MB |
| `regions_10k_fy2021` | 277 | 50 | 37 | 53 MB |
| `ambac_10k_fy2022` | 252 | 36 | 3 | 43 MB |
| `odp_10k_fy2025` | 179 | 18 | 3 | 34 MB |
| `footlocker_10k_fy2024` | 101 | 15 | 2 | 18 MB |
| `footlocker_10k_fy2013` | 100 | 14 | 1 | 16 MB |
| `tesla_10k_fy2023` | 86 | 15 | 2 | 16 MB |
| `meta_10k_fy2024` | 59 | 12 | 1 | 12 MB |
| `jackhenry_10q_fy2025` | 32 | 6 | 1 | 5 MB |

The entire XBRL path — parse the bundle, query every fact into a DataFrame,
render an income statement — costs less than half a second on the largest
filing in the corpus, against 8+ seconds for the HTML side of the same filing.
Statement rendering is single-digit milliseconds.

This does not mean XBRL work is unwarranted, but it does mean **effort spent
vectorizing XBRL pandas paths buys roughly an order of magnitude less than the
same effort on section extraction.** Sequence accordingly.

---

## Import time: 789 ms

`import edgar`, measured out-of-process over 5 runs (in-process timing is
meaningless once the module is loaded). This is the number the PEP 562 lazy
submodule loading work is against.

---

## Output schemas

The other half of the baseline, per the commitment on
[GH #929](https://github.com/dgunning/edgartools/issues/929): a perf change that
leaves timings alone can still break a caller, so the baseline records the shape
of the DataFrame surfaces downstream code filters on. Full capture in
`schemas.json`.

### `Filings.to_pandas()` — 5 columns, 340,032 rows (2025 Q1 index)

| column | family | exact | nulls |
|---|---|---|---|
| `form` | string | str | — |
| `company` | string | str | — |
| `cik` | integer | int32 | — |
| `filing_date` | object | object | — |
| `accession_number` | string | str | — |

`filing_date` arriving as **object** rather than `datetime64`, and `cik` as
**int32** rather than int64, are both pyarrow→pandas conversion artifacts. The
planned pyarrow-backed index reads are very likely to move both. That is exactly
the change #929 asked to be told about in advance.

### `FactsQuery.to_dataframe()` — the schema moves *within* one version

This is the significant finding. The same XBRL instance, two queries:

| column | `.query()` | `.query().by_statement_type("IncomeStatement")` |
|---|---|---|
| *(column count)* | 24 | **23** |
| `preferred_sign` | float64, nulls=`NaN` | **int64, no nulls** |
| `numeric_value` | float64, nulls=`NaN` | float64, no nulls |
| `decimals` | str, nulls=`pd.NA` | str, no nulls |
| `label` | str, nulls=`pd.NA` | str, no nulls |

`preferred_sign` changes **dtype family** depending on which rows the query
returned, because `to_dataframe()` is `pd.DataFrame(results)` over a list of
dicts (`edgar/xbrl/facts.py:876`) and nothing declares the schema — dtype and
null sentinel are inferred per call from the data that happened to come back.

The incident reported on #929 was an *upgrade* changing a sentinel. This is
worse: a consumer's filter can break by filtering differently, in a single
version, with no release involved. Tracked as a P1 with a design question
attached — whether this method should declare its columns rather than infer
them.

For the record, since #929 asked: `decimals` currently carries **`pd.NA`**, not
`None` and not `NaN`.

### The EntityFacts surfaces — the same defect, a different code path

Wiring these in was meant to close a gap in coverage. It found the same bug
again. Tesla's company facts (CIK 1318605), one `EntityFacts` object, two
queries through `edgar/entity/query.py:641`:

| column | `.query()` | `.query().by_concept("Revenues")` |
|---|---|---|
| *(column count)* | 19 | 19 |
| `value` | float64 | **int64** |
| `period_start` | nulls=`None` | no nulls |
| `statement_type` | nulls=`pd.NA` | no nulls |

The column *count* holds, unlike the XBRL side — but `value`, the column an
EntityFacts consumer actually reads, changes dtype family when the query narrows
to a concept whose values all happen to be integral. That moves its null
sentinel from `NaN` to none-present and changes division semantics for anyone
not explicitly coercing.

This is the parallel implementation of the same idea as `edgar/xbrl/facts.py`,
so it inherited the same design: build a DataFrame from a list of dicts and let
pandas infer. Tracked at P1, to be fixed by applying the same declared-schema
decision rather than inventing a second contract.

### `Document.to_dataframe()` — informational, and currently broken

Not gated: its columns are the columns of whatever tables the document happens
to contain, so two filings produce unrelated schemas and a diff across them
means nothing.

It also fails on 6 of 6 real filings in the corpus — `TypeError: Cannot cast
array data from dtype('float64') to dtype('int64')` on five, `ValueError: Index
data must be 1-dimensional` on Tesla. The one entry where it succeeds is the
ABS-15G, which is a single flat table. Filed separately at P1.

---

## Gated vs. not

Only these block a merge, out of roughly forty `to_dataframe`/`to_pandas`
methods in the library:

| surface | status |
|---|---|
| `FactsQuery.to_dataframe()` — `edgar/xbrl/facts.py:859` | captured |
| `Filings.to_pandas()` — `edgar/_filings.py:548` | captured |
| `EntityFacts.to_dataframe()` — `edgar/entity/entity_facts.py:246` | captured, 2 variants |
| `edgar/entity/query.py:641` | captured, 2 variants |
| `edgar/xbrl/stitching/query.py:545` | captured |

All five are now wired. The last three needed a cached company-facts payload,
which comes from a different endpoint than the filing bundles; `build_corpus.py`
caches the raw JSON for two companies already in the filing corpus and the bench
re-parses it each run, so a change to `EntityFactsParser` shows up rather than
being frozen into a stored object.

Worth recording, since this file previously claimed otherwise: those three were
not being written as `unavailable` — they were **absent from the capture
entirely**, which is exactly the silence the `unavailable` convention exists to
prevent. The convention was real (`Document.to_dataframe()` is recorded that
way) but had never been applied to the surfaces that had no builder at all.

---

## Reproducing

```bash
python scripts/perf_baseline/build_corpus.py       # network, ~94 MB, once
python scripts/perf_baseline/bench.py --reps 3 --out /tmp/after

python scripts/perf_baseline/schema_snapshot.py \
    engineering/analysis/perf-baseline/schemas.json /tmp/after/schemas.json
```

The schema diff exits non-zero on breaking changes, so it drops into CI as-is
when the gate moves from advisory to blocking after 6.0.

The corpus is named rather than sampled — `corpus_manifest.json` pins all
eleven accession numbers and is committed, while the bytes are gitignored and
rebuilt from it. A number taken today and a number taken in six months describe
the same documents.
