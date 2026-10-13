# Held-out 10-K truth set (edgartools-llmp.11.1)

`../boundary_truth.json` measures the section detector on the filings it was
developed on. Its 10-K rate is a regression ruler, not an accuracy figure:
every phase B rule was tuned on those 37 filings, its labels were proposed
from pipeline output (an item the pipeline never emitted never entered the
denominator), and some labels moved when a boundary policy was decided.

This set answers the question that one cannot: **on 10-Ks the rules have
never seen, how many items does the pipeline find, and how many of those have
exactly the right text?**

## How it was built

- **Draw.** `heldout.py sample`, seed `20261012`: random quarters per era
  (2001-06, 2007-12, 2013-18, 2019-25), a random `10-K` (no amendments) from
  each quarter's full index, 10 per era, half with a cover-page public float of
  at least $700M ("large") and half below. Rejected: any filer or accession in
  the development corpus (`html/`, `parity_gate/`, the era corpus),
  asset-backed issuers (SIC 6189, Reg AB 10-Ks without the Item 1-16 layout),
  filings with no HTML or text document, and filings whose cover states no
  float (a small bias against filers that phrase the cover differently).
  Rejection counts are in the JSON. A first uniform draw (same seed, no
  ABS exclusion or size strata) was discarded before any filing was labelled
  or scored: a fifth of it was ABS trusts.
- **Labels.** Made blind from the full-document text, following
  `LABELING.md` (the same policies as the development set): one Sonnet
  labeller per two filings, with no pipeline output in view. The labeller
  records lines; `heldout.py cut` cuts the 80-character windows, so no window
  was copied by hand. Every disagreement with the pipeline was then
  adjudicated by an Opus reader against the filing, with the two candidates
  shown as an unlabelled A and B (`compare` writes the key to a separate
  file). `verified` says how each item was settled:
  `agreed` (labeller and pipeline matched), `adjudicated` (a disagreement
  settled against the text; `why` records the winner and the reason), or
  `single` (the pipeline emitted no section for the item, so its boundary has
  one reader; it scores as a miss whatever the boundary).
  Two verdicts were overridden to the never-orphan policy (an exhibit index
  after back-of-book statements stays with Item 8), and `LABELING.md` was
  corrected to say so; both are marked "override" in `why`.
- **Matching.** Truth windows are cut from the full-document text; the live
  ones from `section.text()`, which renders the same content with different
  rule lines, dashes and spacing. Two windows mark the same boundary when
  their first (start) or last (end) 48 letters and digits agree
  (`same_boundary`). This measures boundaries, not rendering, so it is not
  byte-comparable with `boundary_truth.json`'s exact-match rates.
  Non-standard keys the pipeline emits (a filer's "Item 4A") are neither
  credited nor charged.
- **Storage.** Accessions and labels only; `heldout.py fetch` downloads each
  filing with `Filing.html()` into `EDGAR_HELDOUT_CACHE` (default
  `~/.cache/edgartools/heldout`). Filings do not change once filed.

## How to use it

```bash
python tests/fixtures/parser_corpus/heldout/heldout.py fetch
python tests/fixtures/parser_corpus/heldout/heldout.py report      # -v lists misses
```

The report gives item recall (labelled items the pipeline emits), precision
(emitted items the filing has), and start-, end- and both-exact rates, with
95% intervals from resampling filings (items in one filing fail together, so
items are not independent draws).

## Rules that keep it held out

1. **Nothing in CI pins it.** A ratchet invites tuning until it is green.
2. **Do not develop against it.** Read the report; do not open a held-out
   filing to design a rule.
3. **Retire what you use.** When a held-out failure leads to a fix, move that
   filing to the development corpus (as a tracked fixture and
   `boundary_truth.json` entries), list it under `retired` with the PR, and
   draw a replacement from the same era and stratum. A number reported after
   a retirement names the set's version.

## Results

**v1, 2026-10-12** (main at a07cf674, after #1526): 40 filings, 770 items.

| | all | 2001-06 | 2007-12 | 2013-18 | 2019-25 |
|---|---|---|---|---|---|
| recall | 87.8% [77.6, 95.8] | 44.8% | 99.0% | 99.5% | 100% |
| start-exact | 84.9% | 43.6% | 95.9% | 95.9% | 96.7% |
| end-exact | 81.0% | 37.6% | 90.9% | 92.7% | 94.9% |
| both-exact | 79.1% [69.1, 87.3] | 36.4% | 89.3% | 90.7% | 92.1% |
| precision | 100% | | | | |

Of the 94 items the pipeline does not emit, 91 are in six 2001-2006 filings
where it emits nothing or almost nothing. On the 676 items it does emit, 90.1%
are exact on both sides (TOC path 91.5%, pattern path 80.2%). Labels:
586 agreed, 90 adjudicated, 94 single.

**Label change, 2026-10-13.** The Item 16 exception in `LABELING.md` was
decided after v1 was labelled. Two Item 16 labels that ran through a schedule
and exhibit index printed after Item 16 were cut back to Item 16's own text
from the recorded lines (Calavo 0001558370-17-009444, Madison Square Garden
Sports 0001636519-24-000015; `verified: "relabelled"`). This applies a policy;
it is not a fix built from those filings, so neither is retired.
