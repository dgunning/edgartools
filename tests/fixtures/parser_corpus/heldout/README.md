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

Retiring filings (rule 3 below): `retire "WHY" ACC...` copies each filing to
`heldout_retired/10-K/` and moves its entry, labels included, to `retired`;
`replace` draws successors from the same era and size stratum with the seed
`20261012:v<version>`, excluding every filer already in or retired from the
set. The new filings then go through the same `dump`, blind labelling, `cut`,
`compare`, adjudication, `resolve` and `finalize` steps; `dump` and `compare`
touch only filings that are unlabelled or still blind.

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

**v2, 2026-10-14** (main at bdcdb7d5): 40 filings, 776 items. Eight v1
filings were retired to the development corpus for edgartools-llmp.12.1:
the six its findings name (Landec 0001144204-08-044977, Plum Creek
0000849213-13-000007, Vasomedical 0001201800-13-000006, Tetra Tech
0001047469-15-008864, Bright Green 0001493152-23-012561, TechPrecision
0001410578-25-001537) and two last-item Item 15 end misses (Intuit
0000950134-07-020001, Sanmina 0000897723-17-000029). They are tracked under
`heldout_retired/10-K/`, and their labels seeded 157 `boundary_truth.json` items
(131 eye, 26 wrong, the same misses this set recorded). Their successors were
drawn by `replace` (2 in 2007-12, 4 in 2013-18, 2 in 2019-25; strata kept),
labelled blind by four Sonnet labellers, and 24 disagreeing sides were
adjudicated blind by an Opus reader (22 for the labeller, 2 for the pipeline;
143 items agreed).

| | all | 2001-06 | 2007-12 | 2013-18 | 2019-25 |
|---|---|---|---|---|---|
| recall | 98.1% [96.5, 99.4] | 93.3% | 99.0% | 99.0% | 100% |
| start-exact | 94.8% | 90.9% | 96.0% | 95.0% | 96.7% |
| end-exact | 89.7% | 73.3% | 93.9% | 91.5% | 96.7% |
| both-exact | 87.9% [83.9, 91.3] | 72.1% | 92.4% | 90.0% | 93.9% |
| precision | 100% | | | | |

v1 on the same code measured 86.8% both-exact. The eight new filings score
87.3% (145 of 166 items), against 83.4% for the eight they replace, so the
rise is the draw, not a fix. Their misses repeat the two shapes the retired
filings carry: a Part divider kept at an item's start (Dorian LPG, National
Security Group, South State) and a last Item 15 that stops short of the
schedule or exhibit index after its signatures (Interstate Power & Light,
Hormel, South State, Woodward). Global Cornerstone prints its Unresolved
Staff Comments heading as a second "Item 1A"; it is labelled 1B.

**Label change, 2026-10-14.** A second last-item exception (`LABELING.md`):
when the TOC lists SIGNATURES, the last item ends before them, and an index
or schedule after the signature block is the `exhibit_index` section. Three
v2 Item 15 labels that ran through the signatures were cut back from the
recorded lines (Interstate Power & Light 0001193125-12-081622, Hormel
0001104659-14-087276, Woodward 0000108312-14-000037; `verified:
"relabelled"`). South State's TOC lists no SIGNATURES, so its label stands.
This applies a policy; it is not a fix built from those filings, so none is
retired. The same policy relabelled three retired filings' Item 15 in
`boundary_truth.json` (Intuit, Sanmina, Tetra Tech). Six v1 labels
(Schlumberger, Marvell, Quad/Graphics, Donaldson, Allied World, Aegion) were
relabelled the same way; three plain-text v1 filings whose document text has
changed since labelling were left, since their recorded lines no longer sit on
the text.

| v2, 2026-10-14 | both-exact | recall |
|---|---|---|
| main at 6565466c, labels as drawn | 87.9% | 98.1% |
| same code, labels after the policy | 88.9% | 98.1% |
| with #1551 (page furniture) and the Signatures split | 91.5% [87.5, 94.8] | 98.1% |

The page-furniture fixes were built on the eight retired filings; the 20
items they gain here are on filings no rule was developed against.
