# Word-boundary measurement harness

Measures what a change to text extraction does to word boundaries across the fixture
corpus. Written for the delete-vs-collapse bug family (edgartools-tlj1) and kept for what
is still open on **edgartools-jysx**: removing the `ParagraphNode.text()` allowlist
outright still costs 8,109 spaces, and nobody has explained where those boundaries go.

The bug this exists to catch is subtle: whitespace next to a tag boundary gets *deleted*
rather than collapsed, so two words are glued into one (`anon-acceleratedfiler`,
`Washington98052-6399`). Unit tests miss it because it needs real filer markup. Three
separate instances shipped before this harness existed, and it then found a fourth —
lxml's own `remove_blank_text`, which deleted the single space the preprocessor had
deliberately left behind (edgartools-vfwp, fixed in ccb36f70).

## The scripts

| Script | What it does |
|---|---|
| `dump_fixtures.py <fixtures_root> <out_dir>` | Renders `Document.text()` for all 57 HTML fixtures. Run once per branch, then diff the two directories. |
| `variants.py` | Candidate `ParagraphNode.text()` bodies, installed by monkeypatch. `make_text(...)` toggles each heuristic independently. |
| `measure_variants.py` | Renders every document under each variant in `VARIANTS` and classifies each changed line. `--corpus fixtures\|wide\|both`. |
| `joined_tokens.py` | Lists every distinct word a variant joins — a quick read. `--corpus`, `--variant`. |
| `classify_removals.py` | **Decides repair vs loss per removal**, which the two above cannot. `--corpus`, `--variant`. |
| `build_wide_corpus.py` | Downloads the widened corpus from the accessions pinned in `wide_corpus_manifest.json`. |
| `profile_corpus.py` | Counts allowlist-eligible tags per document, so "N of M changed" can be read against how many *could* change. |

Pair these with `../section_map_diff.py`, which checks the same change doesn't move
section detection.

## The two corpora

`--corpus fixtures` is the 57 filings under `tests/fixtures/html`: modern large-cap 10-K
and 10-Q. `--corpus wide` is 129 filings across five markup eras and nine form types,
downloaded by `build_wide_corpus.py` into `tests/fixtures/text_boundary_corpus/`
(gitignored — the manifest is the committed artifact, so the corpus rebuilds exactly from
a clean checkout).

The fixture corpus is not a sample of EDGAR, and the difference matters for anything
keyed on tag names. `profile_corpus.py` on the wide corpus reports a **median `<span>`
count of 0 in nearly every era/form group, including 2020-2026** — filing agents still
emit `<font>` with `<b>`/`<i>`/`<a>` inline. 59 of the 129 documents cannot exercise the
`ParagraphNode.text()` allowlist at all; the pre-2001 ones are `<PRE>`-wrapped plain text
with `<S>`/`<C>` column markers and no inline tags whatsoever.

## Telling a repair from a loss

`measure_variants.py` counts every removed space as "lost", so an intentional word repair
lands in the same column as a destroyed boundary. `classify_removals.py` separates them
with a test the document answers itself: a removal joining `L + R` is a **repair** if
`LR` is spelled whole somewhere else in the same filing (`CONSOLID`+`ATED` against the
CONSOLIDATED that appears throughout), and a **loss** if `LR` appears nowhere while `L`
and `R` both stand alone as their own tokens (`o`+`Yes`). Case-folded matches are
reported separately as `REPAIR-WORD-CI`, because headings are set in caps and
`Item 1A. RI SK FACTORS` has no all-caps `RISK` to match — only the `Risk` in the prose.

Two corrections this test produced, both of which had been read the wrong way for months:

- **The 8,109-lost headline was an artifact.** Deleting the allowlist in favour of the
  CSS-gap rule removes 245 spaces across the fixture corpus, of which **222 are repairs**
  — including the `RI SK`, `UNRESOLV ED`, `PR OPERTIES` and `QUALITAT IVE` corruption of
  Item headings that the allowlist itself introduces.
- **The allowlist invents spaces after opening punctuation.** 92 of those 245, and 48 of
  the 52 on the wide corpus, are `(the " SEC")` → `(the "SEC")` and `( i.e.,` → `(i.e.,`.

## Harness gotchas

Four now, each of which produced a wrong answer before it was understood:

1. `variants.py` is a **separate copy** of `ParagraphNode.text()`. Any change to the
   shipped method must be mirrored here or the variants measure the wrong thing.
2. `measure_variants.py` scores a removed space as "lost" — see above. Never quote its
   "lost" column as a loss count without running `classify_removals.py`.
3. The source locator in the `allowlist_*` scripts finds the FIRST word pair separated
   only by tags, so short fragments can land on a different instance of the same shape.
   Shape percentages are sound; individual site attributions are not.
4. `classify_removals.py` walks two lines character by character. A variant that **adds**
   a space desynchronizes the walk unless the insertion is consumed from the new line
   alone — the unfixed version reported 50,741 removals for a variant that changes 18
   documents. If a run reports a huge `UNEXPECTED` bucket, that is the symptom.
5. **`classify_removals.py` cannot judge a space a variant ADDS.** It buckets those as
   `GAINED` and assumes they are good. They are not always: the first cut of the
   marker-glyph rule scored as strictly better on the wide corpus (342 gained, 2 lost)
   while quietly turning A-Power's `our wind turbine business` into `o ur` — the filer
   splits `our` as `o`+`ur`, and the marker branch is reached before any mid-word-split
   test. Only the glyph audit caught it, by attributing each insertion to the glyph that
   triggered it and showing the context. **Any change to this branch needs that audit as
   well as the classifier**; the script is in the session scratchpad rather than here
   because it wants rewriting per signal, but the technique is the point: group the new
   spaces by what caused them and read the contexts.

`PYTHONPATH=$REPO` is mandatory throughout: the hatch env has a non-editable edgartools
installed, so a script run without it silently measures the released version.

## The classification that matters

A changed line whose `.replace(" ", "")` is unchanged differs **only in spacing**. Split
those into gained-a-space and lost-a-space, and count anything else as a content change.
A clean whitespace fix is `gained > 0, lost == 0, content == 0`.

Whole-document check, stricter and cheaper: `"".join(before.split()) ==
"".join(after.split())` — true means nothing but whitespace moved anywhere in the file.

## Running

These import `edgar`, so put the tree you're measuring on `PYTHONPATH` — and note the
hatch env has a **non-editable** edgartools installed, so a script run from outside the
repo silently measures the wrong version:

```bash
REPO=/Users/dwight/PycharmProjects/edgartools
PYTHONPATH=$REPO hatch run python scripts/text_boundary/measure_variants.py
```

To compare against another commit, `git worktree add` it and point `PYTHONPATH` there.

## The variants

| Variant | What it is |
|---|---|
| `G_css_gap_plus_marker` | **Shipped behaviour.** Expect **0 changed** on both corpora — the harness self-check. |
| `D_union_allowlist_or_css_gap` | The *previous* shipped behaviour, allowlist included. Its diff is what deleting the allowlist did. |
| `E_shallow_tailws` | Shipped minus the rightmost-spine tail-whitespace walk; its "lost" count is what `996f5998` restores. |
| `F_css_gap_only` | Allowlist deleted with no marker rule — `G` minus the glyph signal. |
| `A_drop_allowlist` | Pure deletion, no replacement at all. The upper bound the others are measured against. |

`A_drop_allowlist` is genuinely unsafe and the wide corpus is where that shows: it
destroys 63 real boundaries, nearly all of them a bullet or footnote marker against its
text (`• Proposal No. 1` → `•Proposal No. 1`, 43 lines in one small-cap 2021 proxy). The
CSS-gap rule in `F` recovers all but two of them, on a filer using `<font>`-era markup —
which is the evidence the large-cap corpus could never have produced.

## Bar

The five landed commits in this family each held to **0 spaces lost, 0 content changed**,
verified with `"".join(text.split())` equality per document plus `../section_map_diff.py`
reporting 0 sections lost. Table headers may re-wrap when a cell gains a character —
verify total content is unchanged, then say so explicitly rather than waving it through.

Deleting the allowlist cannot meet that bar as stated, because it removes spaces by
design. State it instead as **0 losses that `classify_removals.py` confirms**, and list
the residual losses by name.
