# Section extraction: where the time goes

**Date**: 2026-08-03
**Corpus**: `scripts/perf_baseline/corpus` (11 cached filings)
**Baseline**: `engineering/analysis/perf-baseline/timings.json` (edgartools 5.45.1)

The 6.0 baseline named section extraction as target #1: it costs more than parsing
on every 10-K in the corpus — 6.6s of sections against 1.9s of parse on Morgan
Stanley, 5.2s against 3.1s on Citigroup. This is the profile of that stage.

It is written as **input to the section redesign, not as an optimization list.**
`llmp.6` holds 99 detection defects across 31,691 documents, and tuning code that
is slated for rewrite is waste. The question worth asking of a profile is whether
the hot path and the defect clusters are the same code. On Citigroup they are
exactly the same code, and that is the most useful thing here (finding 4).

## Reproducing

```bash
hatch run python scripts/perf_baseline/bench.py \
    --profile morganstanley_10k_fy2024 --profile-stage sections
```

`--profile-stage` is new. The previous `--profile` parsed with a bare
`ParserConfig()` and never touched `doc.sections`; since `ParserConfig.form`
gates section detection, it profiled a code path the benchmark does not measure —
a flat parse where the baseline records 6.6s of section work.

**Absolute numbers below are inflated by profiler overhead** (Morgan Stanley
profiles at 12.1s against a measured 8.5s). Ratios are the signal; the wall-clock
figures come from `timings.json` and the standalone measurement scripts.

## Finding 1 — anchor resolution rescans the whole document, per anchor

`find_anchor_targets` (`edgar/documents/utils/anchor_targets.py:4`) resolves an
anchor with `tree.xpath('//*[@id=$anchor_id or (self::a and @name=$anchor_id)]')`.
That is a full-document scan for one id, and section extraction calls it from
eleven sites across `toc_analyzer.py`, `toc_section_extractor.py` and
`section_slicer.py`.

On Morgan Stanley: **92 calls resolving 30 distinct ids against 1 tree — 3,854 ms,
60% of the 6.4s stage.** 67% of the calls re-resolve an id already looked up on
the same tree.

Building one `id/name -> elements` map in a single `tree.iter()` pass and serving
every lookup from it was measured across the corpus:

| entry | lookups | distinct | xpath today | index build | all lookups | recoverable |
|---|---|---|---|---|---|---|
| morganstanley_10k_fy2024 | 92 | 30 | 3,646 ms | 31 ms | 0.01 ms | 3,615 ms (99%) |
| ambac_10k_fy2022 | 96 | 28 | 2,412 ms | 20 ms | 0.01 ms | 2,392 ms (99%) |
| regions_10k_fy2021 | 66 | 22 | 2,044 ms | 25 ms | 0.01 ms | 2,019 ms (99%) |
| tesla_10k_fy2023 | 95 | 34 | 997 ms | 8 ms | 0.01 ms | 988 ms (99%) |
| meta_10k_fy2024 | 74 | 26 | 661 ms | 8 ms | 0.01 ms | 653 ms (99%) |
| footlocker_10k_fy2024 | 57 | 26 | 561 ms | 9 ms | 0.01 ms | 552 ms (98%) |
| odp_10k_fy2025 | 26 | 9 | 486 ms | 14 ms | 0.01 ms | 472 ms (97%) |
| footlocker_10k_fy2013 | 60 | 20 | 429 ms | 7 ms | 0.01 ms | 422 ms (98%) |
| jackhenry_10q_fy2025 | 25 | 9 | 89 ms | 3 ms | 0.00 ms | 86 ms (97%) |

The index returned **identical elements in identical document order for all 204
anchor ids across all 9 documents** — the correctness gate ran before the timing,
because a faster lookup that returns a different element is not a faster lookup.

The catch is lifetime, not logic: the index must be keyed to a tree and invalidated
if that tree is mutated. lxml elements do not accept attributes or weak references,
so the index wants to live on the object that already owns the tree
(`SECSectionExtractor._tree`) rather than in a global keyed on `id(tree)`.

Two entries make no anchor calls at all and are excluded: `fanniemae_abs15g_2018`
(0 sections — the form-mismatch case) and `citigroup_10k_fy2024` (finding 4).

## Finding 2 — every section walks the document from the root

`_extract_section_content` (`toc_section_extractor.py:763`) collects a section's
text with `etree.iterwalk(tree, events=('start','end'))`, which always begins at
the document root. A section pays for every element preceding its own start
anchor, discarding each one with `in_range` false.

On Morgan Stanley, across 25 extraction calls: **3,892,226 tree events walked,
771,109 in range — 80% of the traversal is discarded.**

The distribution is worse than the average suggests:

```
part_iii_item_14     190,115 walked          9 used    0.0% useful
part_iii_item_12     190,091 walked          9 used    0.0% useful
part_iii_item_11     190,081 walked          9 used    0.0% useful
part_i_item_1b        37,391 walked          0 used    0.0% useful
```

Sections that resolve to almost no content still walk the entire document to
discover that. The start element is already known from finding 1's lookup, so the
walk could begin there instead of at the root.

## Finding 3 — the navigation-pattern cache re-hashes the whole filing per section

`_clean_section_text` calls `filter_with_cached_patterns(text, html_content)` with
the document's full original HTML, and `AnchorCache._get_html_hash`
(`anchor_cache.py:29`) md5s all 9.8 MB of it to build the cache key — once per
section, ~340 ms per document on Morgan Stanley. The cache is keyed on content
that cannot change during a run, so the key is recomputed to prove it is the same
key. Small next to findings 1 and 2, and correspondingly cheap to fix: hash once
per document, or key on the document rather than its bytes.

## Finding 4 — the slowest document is slow *because* detection failed

Citigroup is the case where the hot path and the defect cluster are the same code.

TOC detection produces nothing (it makes zero anchor lookups, which is why it drops
out of finding 1's table), so `HybridSectionDetector` falls back to
`_try_pattern_detection`. That fallback costs **16.4s of an 18.0s stage**, and
**10.5s of it is `ParagraphNode.__eq__`**.

The source is `pattern_section_extractor.py:959`:

```python
nodes_in_range = []          # a list
...
for n in nodes_in_range:
    if n.parent not in nodes_in_range:
        section_node.add_child(n)
```

`Node` is a `@dataclass` (`nodes.py:94`), so `__eq__` is generated field-by-field
and recurses through `children`. Membership against a list therefore runs a deep
structural comparison for every candidate, O(n²) in the nodes in range.

The test means *is this same node object also in the range* — identity — while `in`
asks whether any in-range node is structurally **equal**. That reads like a
correctness bug on top of the cost, and it was written up as one here. It is not:
`Node.id` is a per-instance uuid and dataclass `__eq__` compares fields in
declaration order, so `id` is compared first and two distinct nodes are never equal.
Equality already coincided with identity, which is why fixing it changed no output.

**Verified rather than assumed**: section names and per-section character counts are
byte-identical across all 11 corpus filings before and after the change. The defect
was cost, not correctness.

Fixed — `{id(n) for n in nodes_in_range}` snapshotted before the loop (`add_child()`
reassigns `child.parent` as it goes), `id(n.parent)` tested against it:

| entry | before | after |
|---|---|---|
| citigroup_10k_fy2024 | 5,215 ms | 816 ms |
| odp_10k_fy2025 | 1,197 ms | 966 ms |

Every other entry moved within run-to-run noise, since they never reach this path.

Citigroup still returns 4 sections where comparable 10-Ks yield 20–24. **That is
unchanged and is the real defect** — this fix only stops it costing 18 seconds to
arrive at the same wrong answer. The detection failure that routes it here is the
`llmp.6` problem proper.

### The same pattern, one file over

Attributing the `__eq__` calls that remained after the fix found a second site:
`postprocessor.py:280` ran `if node != document.root` — a generated field-by-field
comparison, once per node in the document, to answer a question about object
identity. 2,415 calls on a small synthetic 10-K. Fixed to `is not`.

Both are the same latent hazard: `Node` is a `@dataclass` with `eq=True` by default,
so any `==`, `!=`, `in`, `.index()` or `.remove()` on nodes silently buys a deep
comparison. It is worth considering `eq=False` on the node dataclasses so identity
is the only thing available — the comparison is never what callers want, and it has
a sharper failure mode than slowness: `Node.__eq__` recurses through `parent` and
`children`, so comparing two nodes that share an `id` (a `deepcopy`, say) raises
`RecursionError` rather than returning a wrong answer.

## What this says for the redesign

The first three findings are one shape: **work proportional to the whole document,
repeated once per section**, where the document is fixed for the duration. An
index-once-reuse-per-section pass addresses all three, and findings 1 and 3 are
contained enough to fix ahead of the rewrite without betting on its design.

Finding 4 is the one that matters, and not for the 6.4× it recovered. The quadratic
fallback runs precisely when detection has already failed — so the documents that
get the worst answers also cost the most to produce them. Citigroup is now fast and
still wrong. That coincidence is the argument for treating detection quality and
section-extraction performance as one piece of work rather than two.

It is also a caution about reading profiles. The quadratic membership test looked
like it must be dropping content, and that inference was written down as a finding
before it was checked. It was wrong — a uuid field in a dataclass meant equality had
collapsed to identity all along. Both halves of a "slow *and* wrong" claim need
their own evidence; the profile only ever proved the first.

## Artifacts

- `scripts/perf_baseline/bench.py --profile-stage` — profiles the real stage
- Measurement scripts used for findings 1, 2 and 4 are one-off and not committed;
  the numbers above are reproducible from the profiles plus the corpus.
