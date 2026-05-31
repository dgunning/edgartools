# Canonical Parser Fixture Corpus

**Issue:** `edgartools-h44r` · **Design:** `docs/internal/parser-design-sprint-2026-05.md` (Tension 7)

A shared, measured set of real SEC filings used to verify section extraction and
to detect regressions. It replaces the ad-hoc "each PR ships its own filing"
practice that let the GS/Citi catastrophic 10-K failures ship undetected.

## Contents

| File | What it is |
|---|---|
| `manifest.json` | One entry per fixture: ticker, form, date, detected filing agent, per-item text lengths + table counts, and **known-bad markers**. |
| `size_bands.json` | Per `(form, item)` content-size bands derived from the **healthy** filings only. Consumed by the silent-failure guardrail (`edgartools-9hwf`). |
| `build_corpus.py` | Regenerates both artifacts from the fixtures under `tests/fixtures/html/`. |
| `README.md` | This file. |

The fixtures themselves live under `tests/fixtures/html/<ticker>/<form>/` and are
downloaded by `tests/fixtures/download_html_fixtures.py`.

## Known-bad markers

A filing is flagged when its parse exhibits a failure mode. Markers:

- `parse_error` — the parser raised.
- `oversized_section` / `oversized:item_N` — a section exceeds 300KB (boundary
  overshoot; e.g. Citi's raw-HTML leak).
- `oversized_business_section` — documented GS Part-I/II misclassification.
- `undersized:item_N` — a reliably-substantial item (1, 1A, 7, 8 on 10-K) came
  back under its floor — the anchor landed on the heading, not the body.
- `raw_html_leak`, `part_misclassification`, `legacy_fallback_required` —
  documented failures from `edgartools-sldz` (#821).

As of the current corpus, **17 of 54 filings (~31%)** carry a marker — the true
blast radius of the section-extraction bugs is far wider than the four originally
documented filings (GS, Citi, JPM, PPG). Notable: `wfc` 10-K detects only 1
section, `c` (Citi) detects 0, and `gbdc`/`bac`/`ms` over-extract Item 8.

## Size bands

For each `(form, item)` the band records `n`, `min`, `p50`, `max`, recommended
`low_flag` / `high_flag` thresholds (median-relative: `p50 // 5` and `p50 * 8`),
and an `enforce` flag. Only `enforce: true` items — reliably substantial,
well-sampled — should be guarded by `edgartools-9hwf`; items that are commonly a
legitimate "None"/"Not applicable" (1B, 4, 6, 9, 9B, ...) have no meaningful band.

**Caveat — Item 8 is bimodal market-wide.** Every filer in this large-cap corpus
inlines its financial statements, so Item 8 is enforceable here. On a broader
corpus including filers that incorporate Item 8 by reference, the undersize floor
would produce false positives; revisit the floor when the corpus is widened.

## Refresh

Regenerate after adding/rotating fixtures, or **quarterly** (whichever comes
first), and whenever a parser change is expected to move section sizes:

```bash
python tests/fixtures/parser_corpus/build_corpus.py
```

Commit the regenerated `manifest.json` and `size_bands.json` alongside the code
change that moved them, so the diff shows exactly which sections changed size.
When a known-bad filing is fixed, its marker disappears from the regenerated
manifest — update any test that asserted the failure.

To add a filing: add its ticker to `download_html_fixtures.py`, run that, then
rerun `build_corpus.py`.
