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
| `measure_variants.py` | Renders every fixture under each variant in `VARIANTS` and classifies each changed line. |
| `joined_tokens.py` | Lists every distinct word a variant joins or splits — the review artifact. 200 entries you can read in a minute beats 8,000 diff lines you can't. |

Pair these with `../section_map_diff.py`, which checks the same change doesn't move
section detection.

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

`H_wordsplit_same_typeface` is the mid-word-split suppression that shipped in 8041044a,
so on a current tree it now measures the variant against *itself* and reports 0 changed.
It is kept because it is the thing to re-run if that rule is ever revisited; to see what
it does, compare against a worktree at `ccb36f70`. `A_drop_allowlist` still reports
55 of 57 changed and 8,109 spaces lost — that is the open question on edgartools-jysx,
not a broken harness.

Note `measure_variants.py` classifies a *removed* space as "lost", so an intentional word
repair counts in the same column as a destroyed boundary. Read `joined_tokens.py`'s list
to tell them apart: it names every word each removal forms.

## Bar

The four landed commits in this family each held to **0 spaces lost, 0 content changed**.
Table headers may re-wrap when a cell gains a character — verify total content is
unchanged, then say so explicitly rather than waving it through.
