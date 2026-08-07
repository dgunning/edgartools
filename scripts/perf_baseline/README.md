# 6.0 performance baseline

The reference point every 6.0 performance change is measured against. It records
three things, and the third one is the reason this is not just a stopwatch:

| | what | asserted how |
|---|---|---|
| **timings** | median / p95 wall-clock per document per stage | compared, not gated — machines differ |
| **memory** | `tracemalloc` peak per parse | compared |
| **schemas** | structural fingerprint of the DataFrame surfaces | **gated** — see below |

## Why schemas are in a performance harness

A downstream consumer reported ([GH #929](https://github.com/dgunning/edgartools/issues/929))
that an upgrade changed the null sentinel of `facts.to_dataframe()`'s `decimals`
column from `None` to `NaN`, silently disabling a filter of theirs. The output
was value-correct, no slower, and no larger — a timing-and-memory harness would
have recorded a clean pass and let it through.

So the rule for 6.0 is: **no optimization merges without a number _and_ a schema
diff.** `schema_snapshot.py` produces the diff.

Its self-check reproduces that exact incident:

```
$ python scripts/perf_baseline/schema_snapshot.py
  facts.to_dataframe():
    BREAKING  decimals: dtype family object -> float
    BREAKING  decimals: null sentinel ['None'] -> ['NaN']
```

Dtype **family** is asserted coarsely (`int64` vs `Int64` vs `float64` differ
legitimately between corpus files) while the **null token** is asserted exactly
— `None`, `NaN`, `pd.NA` and `NaT` are not interchangeable to a caller's filter.

## Usage

```bash
# once: download and cache the corpus (network; ~94 MB)
python scripts/perf_baseline/build_corpus.py

# measure
python scripts/perf_baseline/bench.py --reps 3 --out engineering/analysis/perf-baseline

# after a change: diff your run against the committed baseline
python scripts/perf_baseline/schema_snapshot.py \
    engineering/analysis/perf-baseline/schemas.json \
    scripts/perf_baseline/results/schemas.json
```

`schema_snapshot.py` exits non-zero when there are breaking changes, so it drops
into CI as-is when the gate goes from advisory to blocking after 6.0.

Profiles need the hatch env (`pyinstrument` is a dev dependency, deliberately
not a runtime one):

```bash
hatch run python scripts/perf_baseline/bench.py --profile citigroup_10k_fy2024
```

## The corpus

Named, not sampled. `corpus_manifest.json` pins every accession number and is
committed; the bytes under `corpus/` are gitignored and rebuilt from the
manifest. A number taken today and a number taken in six months describe the
same eleven documents.

Entries were picked for spread, weighted toward the pathological — a filing that
once took 1h12m to render is exactly where an optimization is most likely to
change behaviour:

| entry | size | why it is here |
|---|---|---|
| `fanniemae_abs15g_2018` | 25.2 MB | large-table dimension pass: 1h12m → 24.1s in 5.45.0. An ABS-15G, not a 10-K: one flat 25 MB table, 61,801 rows |
| `citigroup_10k_fy2024` | 16.7 MB | the >10 MB band that took the removed lossy pipeline |
| `regions_10k_fy2021` | 9.5 MB | page-number-only TOC, Item 7/7A anchor collision (#920) |
| `morganstanley_10k_fy2024` | 9.8 MB | ~490 word-gluing sites before 5.45.0 |
| `ambac_10k_fy2022` | 7.7 MB | two-column TOC, Part context scrambling (#924) |
| `odp_10k_fy2025` | 5.6 MB | catastrophic backtracking in `has_index()` (#928) |
| `footlocker_10k_fy2024` | 3.1 MB | nested TOC anchors, off-by-one item map (#923) |
| `tesla_10k_fy2023` | 2.7 MB | Workiva TOC row structure (#915) |
| `meta_10k_fy2024` | 2.4 MB | heading detection: 180 of 296 headings were glyphs |
| `footlocker_10k_fy2013` | 2.3 MB | split TOC cells, phantom item codes (#923) |
| `jackhenry_10q_fy2025` | 0.8 MB | the small end, so tuning does not chase only giants |

Ten of the eleven carry a full XBRL bundle, cached by role so `XBRL.from_files()`
reconstructs them without network.

## Gated surfaces

Only these block a merge. There are around forty `to_dataframe`/`to_pandas`
methods in the library and claiming all of them are frozen would be a promise
we'd quietly break, so the gate covers what downstream filters actually sit on
and what 6.0 work will touch:

- `FactsQuery.to_dataframe()` — `edgar/xbrl/facts.py:859`
- `Filings.to_pandas()` — `edgar/_filings.py:548`
- `EntityFacts.to_dataframe()` — `edgar/entity/entity_facts.py:246`
- `edgar/entity/query.py:641`
- `edgar/xbrl/stitching/query.py:545`

Several are captured under more than one query, because narrowing a query is
what moved the schema in the first place — a single capture per surface would
have missed it.

Surfaces that cannot be built from the cached corpus are recorded as
`unavailable` rather than omitted, since an absent key reads as "no change" on
the next diff. That convention only helps where a builder exists to fail: the
last three surfaces above had none, so they were silently missing from the
capture until the company-facts payload was added to the corpus.
