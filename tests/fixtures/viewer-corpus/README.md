# Viewer Verification Corpus

Tracks: **`edgartools-doup`**
Runner: `tests/issues/regression/test_viewer_corpus.py`

## What this is

A curated set of SEC filings exercising the variation surface of the
`filing.viewer` subsystem (R*.htm rendered files → `FilingViewer`). Each
entry pins (a) a filing, (b) the dimensions of variation it exercises
(header shape, footnote style, scaling, filer type, fiscal-year end),
and (c) ground-truth assertions that distinguish correct from incorrect
viewer behavior.

The corpus exists because we shipped five viewer correctness bugs in the
5.31.x release line (GH #797, #799, #807, #810, #812). Each was found by
a user finding wrong values in production. The corpus turns that
feedback loop into proactive coverage: a viewer fix isn't done until it
has a corpus entry that would have caught the original report.

## Run it

```bash
hatch run test-regression -k viewer_corpus
# or
pytest -m viewer_corpus -v
```

Stays out of `test-fast` because it hits the network.

## Manifest format

`manifest.yaml` lists entries with this shape:

```yaml
- id: gh-NNN-ticker-year      # stable test ID
  company: Full Co. Name
  ticker: XYZ
  cik: 1234567
  accession: "0001234567-25-000001"
  form: 10-K
  filing_date: "2025-02-21"
  dimensions:                 # vocabulary in manifest's `dimensions:` block
    header_shape: comparative_12m
    footnote_style: simple
    scaling: usd_millions
    filer_type: large_us
    fiscal_year_end: dec
  bug_references: [gh-NNN]    # link to motivating bug(s)
  xfail_until_fixed: true     # OPTIONAL — for open bugs
  notes: >
    One-paragraph description of what makes this filing interesting and
    what the bug was (or would be).
  assertions:
    # one or more — keys must be in ASSERTION_RUNNERS
    statement_count_min: 7
    concept_row_check:
      statement_index: 0
      concept: us-gaap_Revenues
      numeric_value: 6202301
```

The dimension vocabulary is closed and validated by
`test_manifest_dimension_tags_match_vocabulary`. Add a new value to the
vocabulary in `manifest.yaml`'s top-level `dimensions:` block before
using it on an entry.

## Available assertion types

| Key | Purpose |
|---|---|
| `statement_count_min` | `len(financial_statements) >= N` |
| `statement_short_name_present` | named statements all appear |
| `levels_min_distinct` | a statement has hierarchical `level` distribution |
| `currency_scaling` | specific scaling on a named statement |
| `currency_scaling_consistent_across_statements` | BS/IS/CF agree |
| `period_headers_contain` | required substrings in `period_headers` |
| `concept_row_check` | per-concept value check (primary period, period-keyed values, value range) |

Adding a new assertion type: add a `_assert_*` function to the runner
and register it in `ASSERTION_RUNNERS`. The schema validator will reject
typos so you'll know if a manifest entry doesn't pick it up.

## When to add a new entry

**Always:** when you fix a viewer bug. Before the fix PR merges, add an
entry whose assertions would have failed on the buggy code. Mark it
`xfail_until_fixed: true` while the fix is in review, then remove that
flag once the fix lands.

**Sometimes:** when you notice a filing shape we don't cover yet. Check
the dimension matrix — if no entry exercises a given (header_shape,
scaling) combination, add one.

**Never:** entries with no ground-truth assertions. The corpus enforces
"data correctness is existential" — see the verification constitution.
`viewer.compare(xbrl)` alone doesn't qualify; the two views could both
be wrong in the same way.

## Finding ground truth

For value assertions:

1. **Read the filing directly.** Open the 10-K/10-Q on SEC EDGAR, find
   the statement, find the concept, copy the value.
2. **Check the XBRL.** `filing.xbrl().facts.query().by_concept(...)`
   gives the structured value. Compare to the rendered HTML.
3. **For multi-period tables**, write the assertion against the period
   key the viewer emits (`stmt.concept_report.period_headers`) so future
   relabeling won't silently invalidate the check.

Stale-tolerance: prefer pinned accession numbers (reproducible) over
`use_latest_filing: true` (rots). Use the latest-filing path only when
you're explicitly testing steady-state behavior.

## Dimension coverage gaps (TODO)

Today's seed corpus covers 5 of 7 `header_shape` values, 2 of 4
`footnote_style` values, and 3 of 6 `filer_type` values. Expansion to
50+ entries should fill out:

- `quarterly_3m_plus_9m` — typical 10-Q comparative
- `segment_dimensional` — dimensional axis headers
- `lettered`, `asterisk` footnotes
- `foreign_20f`, `foreign_40f`, `ifrs`, `investment_company` filers
- `usd_billions`, `non_usd`, `usd_raw` scaling
