# Parser & Section-Extraction Design Sprint — May 2026

**Status:** Draft for maintainer review
**Owner:** dwight
**Tracking:** `edgartools-0kcx` (epic) · blocks `edgartools-sldz` (#821, P0)
**Scope:** `edgar/documents/` and `edgar/files/` only. Not XBRL, not statement rendering.
**This is a design document, not an implementation.** Implementation happens after sign-off.

---

## 0. Why this sprint exists

Four PRs in a six-week window (#827, #830, #833, and the `sldz` umbrella) each shipped a
*correct* fix and each surfaced the *same* structural tensions. The signal is in the review cost,
not the fixes: Codex caught 5 rounds of regressions on #827 and 11 on #833; #830 has an
unexplained 25–67% size divergence between the streaming and non-streaming text paths. When
correct fixes are this expensive to land, the architecture is harder to reason about than it
should be.

The section-extraction stack is in its **heuristic-accretion phase**. Every fix adds a guard
(`_content_depth`, `_table_depth`, a form-aware cap table, an escaped-period regex branch) that is
right in isolation and adds surface area to maintain. Two of the recent PRs explicitly call their
own fixes interim ("proper rewrite scheduled" in #827, "TOC structural rendering follow-up" in
#833). The team already knows the patches are interim. This sprint decides what to keep, what to
replace, and in what order.

The output is: this document, a canonical fixture corpus, an unblocked `sldz`, and new issues for
the follow-on work.

---

## 1. The system as it stands today

### 1.1 Pipeline

```
Filing.sections() / Document.sections          document.py:694
  └─ HybridSectionDetector.detect_sections()    extractors/hybrid_section_detector.py:73
       ├─ 1. TOCSectionDetector.detect()         extractors/toc_section_detector.py:55   conf 0.95
       │       └─ SECSectionExtractor            extractors/toc_section_extractor.py:36
       │             └─ TOCAnalyzer              utils/toc_analyzer.py:57
       │                   └─ find_anchor_targets utils/anchor_targets.py:4
       ├─ 2. heading detection                   hybrid_section_detector.py:139           conf 0.7–0.9
       └─ 3. SectionExtractor (regex)            extractors/pattern_section_extractor.py   conf 0.6
```

`TOCAnalyzer` maps *normalized section name → anchor ID*. `SECSectionExtractor` turns each anchor
into a `SectionBoundary` (start anchor → next section's anchor). The `Section` object extracts
text / tables / markdown **lazily** by re-walking the original HTML between those anchors.

### 1.2 The defining architectural fact

**TOC-detected sections carry no node tree.** `node.children` is empty; content is fetched on
demand from `metadata.original_html` (`toc_section_extractor.py:237` for text; `document.py:299`
for HTML/tables). Every fragility in §3 traces back to this: we are slicing a flat HTML string
between two anchors and hoping the slice is well-formed.

### 1.3 Agent-aware dispatch

Filing agent is detected from the first 3000 chars (`agents.py:29`). Four hand-tuned parsers model
vendor TOC quirks; unknown agents fall through to `_analyze_generic_toc`:

| Agent | Share | Anchor style | Quirk the parser exists for |
|---|---|---|---|
| Workiva | ~35% | opaque UUID | item # only in *combined cell text* |
| Donnelley/DFIN | ~26% | semantic `#item_1_business` | text-only `PART I` rows set context |
| Toppan Merrill | ~11% | `#ITEM1BUSINESS_392371` | zero-width spaces, split cells |
| Novaworks | ~9% | `#item1a` / `#Item1C` | inconsistent casing, Item 1 shares `#part1` |
| *generic* | ~14% | anything | last-resort link scan |

This dispatch model **works** — agent-aware beats generic on the 20-filing eval — and is not what
this sprint proposes to tear down. The problem is everything *below* the dispatch.

---

## 2. The design tensions (current state → target state → recommendation)

### Tension 1 — Form-shape leakage into "universal" heuristics

**Current state.** `TOCAnalyzer` carries 10-K-shaped assumptions baked into supposedly
form-agnostic code: the bare-item cap of 15 (`_MAX_BARE_ITEM_BY_FORM`, line 47), the text fallback
"Financial Statements → Item 8" (`_normalize_section_name`, lines 1065–1078), and the matching
sort-order table (`_get_section_type_and_order`, lines 1135–1148). #827 added a `form` kwarg and
form-aware bounds. Every fix in this space is the same move: "add `form` kwarg, make heuristic
form-aware," now scattered across the analyzer as `if self.form in ("10-Q", "10-Q/A"): ... elif
self.form not in ("10-K", ...)` branches.

**Why it's wrong.** 10-Q, 20-F, 40-F, S-1, DEF 14A all want different item vocabularies and
different part structures. The current model forces them through a 10-K-shaped pipe and patches the
leaks one form at a time. The branch count only grows.

**Target state.** A declarative **per-form schema** — the canonical item vocabulary, part
structure, and bare-item ceiling for each supported form — consulted by the analyzer instead of
hard-coded keyword tables. The analyzer becomes form-agnostic mechanism; the schema is the only
form-aware data.

**Recommendation.** Introduce `edgar/documents/forms/` (or a `FormSchema` dataclass keyed by form).
Migrate the three leaky heuristics to read from it. **Decision needed:** does form-awareness live
in the extractor (schema lookup) or also in the renderer? Recommendation below in the decision log:
extractor owns *what* sections exist; renderer stays form-agnostic.

---

### Tension 2 — Two text paths diverging (streaming vs non-streaming)

**Current state.** #830 fixed a real streaming bug (span-wrapped text silently dropped, 20–67%
data loss). Post-fix, streaming output now *exceeds* non-streaming by 25–67% on the same filings —
unexplained. Tests assert content *presence* in both paths, never content *equivalence*.

**Why it's wrong.** Same library, two extraction paths, two truths, no equivalence test. We do not
know which is correct on large filings — only that they disagree.

**Target state.** A written parser contract: `filing.text()` produces equivalent output on both
paths, with "equivalent" defined (byte-identical after whitespace normalization, or a bounded
token-level diff). One source of truth.

**Recommendation.** Add a cross-path equivalence test harness over the canonical corpus (§4). Track
divergence as a metric, not a pass/fail at first, then ratchet down. File the equivalence-testing
issue as a sprint deliverable.

---

### Tension 3 — TOC-anchor HTML slicing is fragile and unsolved

**Current state.** "Extract HTML between anchor N and anchor N+1" (`_extract_section_html`,
`document.py:299`) breaks on every real-world variation:
1. next-section heading leaks via nested anchors,
2. shared-wrapper LCA computation,
3. same-anchor boundaries (Novaworks Item 1 == `#part1`),
4. inline anchor wrappers,
5. last-section-in-wrapper leaks,
6. table-row-bounded anchors losing `<table>`/`<tbody>` wrappers,
7. (and the #826 case) nested-table re-serialization producing N copies.

This is why `Section.markdown()` punts to `.text()` for **all** TOC sections (`document.py:137`),
why #826 needed a top-level-only serialization fix, and why Citi 10-K returned 1.78MB of raw HTML.
Three tickets independently need this primitive: `sldz` (correctness), `4j6f` (markdown), `8zqq`
(40-F).

**Why it's wrong.** A primitive three features depend on has no robust implementation. Each feature
re-derives a partial version and hits a different subset of the seven cases.

**Target state.** One concrete, tested slicing algorithm that handles all seven cases — **or** an
explicit decision that anchor-slicing is the wrong primitive and TOC should be navigation-only,
with content extracted by heading-walk instead.

**Recommendation.** Build the slicing primitive (prototype landed alongside this sprint — see
`edgar/documents/utils/section_slicer.py` and §6). The algorithm: collect elements in document
order between anchors, compute the set of *top-level* collected elements (parent not also
collected), wrap them in a synthetic container preserving table ancestry, and serialize the
container once. This subsumes #826 and gives `markdown()` a clean subtree. Keep TOC for both
navigation *and* content, because heading-walk has its own failure modes on filings with weak
heading markup (small-cap Novaworks filings).

---

### Tension 4 — Boundary artifacts fought downstream with regex

**Current state.** `_clean_boundary_artifacts` (`document.py:152–239`) grew through 11 rounds of
review to strip "page number + PART + Item" bleed-in across plain, markdown-escaped,
heading-decorated, bold-decorated, and combined variants.

**Why it's wrong.** The cleanup regex is fighting the renderer. The renderer *knows* where the
section ends; it should not emit bleed-in that downstream regex then strips. Each review round
caught a new shape because the regex chases output instead of fixing the cause.

**Target state.** Renderer-aware boundaries: the extractor hands the renderer a precise element
range and the renderer never emits past it. `_clean_boundary_artifacts` shrinks to a safety net
with a *bounded* contract, or disappears.

**Recommendation.** Tie this to Tension 3's slicing primitive — a clean subtree has no bleed-in to
strip. Keep `_clean_boundary_artifacts` only for the legacy heading/pattern paths until they're
retired, and freeze its growth (no new variants without a corpus fixture proving the need).

---

### Tension 5 — Heuristic accretion vs principled rewrite

**Current state.** Every recent PR adds a guard. Each is correct alone. The cumulative stack has no
stated invariants.

**Target state.** A short list of written invariants the extractor must preserve, e.g.:
- every emitted section maps to a verified anchor target,
- section boundaries are non-overlapping and document-ordered,
- a section's extracted text length is within a form/item expected band or it is flagged,
- no section is emitted at 0.95 confidence whose anchor lands on a PART header rather than item
  content.

**Recommendation.** Write the invariants into this doc's §5, assert them in the validation pipeline
(`hybrid_section_detector.py:_validate_pipeline`), and reject the next guard-style PR that can't be
expressed as preserving an invariant.

---

### Tension 6 — Silent data-correctness failures

**Current state.** The worst class of bug for a data library, and the reason this sprint is P0-
adjacent:
- Goldman Sachs 10-K `.business` silently returned 669KB of MD&A (`sldz`).
- Citigroup 10-K returned 1.78MB of raw HTML markup.
- PPG 10-Q produced a phantom `Item 8` with 96KB of mis-classified content (#827/#821).
- StreamingParser silently dropped cover-page content (#830).

No exception, no warning — just wrong content at 0.95 confidence. Users build pipelines on wrong
values. This is exactly what Verification Constitution #2 ("Data correctness is existential")
exists to prevent, and it leaked through anyway. The analyzer's pervasive `except Exception: pass`
(lines 209, 492, 574, 670, 757, 854, 918) converts every internal failure into a silent empty
mapping.

**Target state.** A stated **silent-failure budget**: under what conditions may the parser return
reduced content vs. raise vs. flag-and-return? Today the fallbacks are informal.

**Recommendation.**
- Add an **expected-size band** per (form, item). Content outside the band (Citi 1.78MB high, GS
  669KB-in-`.business` high, anchor-to-PART-header <200 chars low) gets `confidence` lowered and a
  `Section.warnings` field the caller can introspect — not silently returned at 0.95.
- Replace blanket `except Exception: pass` with logged, typed catches so #6-class failures are
  diagnosable.
- **Decision needed:** fail-loud (raise) vs. flag-and-return. Recommendation: flag-and-return with
  introspectable confidence + warnings, because raising breaks bulk pipelines on one bad filing;
  but `.business`-style typed accessors should consult the flag and raise/return None rather than
  hand back 669KB.

---

### Tension 7 — No canonical fixture corpus

**Current state.** Each PR ships its own representative filing. The `edgartools-dt1f` benchmark (53
10-Ks + 24 10-Qs + 19 20-Fs) is 5 months stale: the Jan benchmark says "new parser wins +0.8%";
May evidence shows GS/Citi catastrophic failures the benchmark never included. The eval suite
(`tests/evaluation/_test_toc_evaluation.py`) is real but `@pytest.mark.manual` and underscore-
prefixed (not collected).

**Target state.** A shared, rotating corpus spanning known-bad cases (GS, Citi, JPM, PPG) and
representative typical cases, refreshed on a cadence, used by every parser PR's verification step.

**Recommendation.** `tests/fixtures/parser_corpus/` with a manifest (form, accession, agent,
known-bad markers, expected per-item size bands), a refresh script, and a cadence rule. Wire into a
de-`manual`-ized benchmark replacing the stale Jan one. Promote `_test_toc_evaluation.py` to CI.

---

### Tension 8 — Fallbacks mask the gaps they should expose

**Current state.** JPM 10-K works only via the legacy-parser fallback (warning-only, slated for
v6.0 removal). `Section.markdown()` silently downgrades to `.text()` on TOC sections. #827's
conservative gates emit empty strings rather than raise.

**Why it's wrong.** "It works" — until v6.0 removes the fallback, or until a user upgrades and
quietly loses `markdown()` structure on certain filings. The fallback hides the real coverage gap.

**Target state.** Either the fallback is unnecessary (the primary path handles the case) or the
reduced functionality is *introspectable* (`detection_method`, a `degraded` flag).

**Recommendation.** Lock a v6.0 date for legacy-parser removal *or* defer it with an explicit
reason in this doc. Make `markdown()`'s text-fallback set a flag callers can read. Unblock JPM via
the Tension-3 slicing primitive so it no longer needs the legacy path.

---

## 3. Sprint goals (the questions we must answer in writing)

1. **What is the parser's contract?** Streaming/non-streaming equivalence definition; single source
   of truth for the section index.
2. **What are the form-shape invariants?** Per-form needs; where form-awareness belongs and where
   it explicitly does not.
3. **How does TOC-anchor extraction actually work?** A concrete algorithm for the seven edge cases,
   or an explicit replacement.
4. **Where do boundary artifacts go?** Renderer-clean (preferred) vs. bounded cleanup regex.
5. **What is the canonical corpus?** Rotating N-per-form including known-bad, with a refresh
   cadence.
6. **What is the silent-failure budget?** Concrete reduced-content-vs-raise-vs-flag rule.

---

## 4. Invariants (proposed — to be asserted in the validation pipeline)

1. Every emitted section maps to an anchor target that exists in the tree.
2. Section boundaries are non-overlapping and strictly document-ordered.
3. No 0.95-confidence section's start anchor lands on a PART header instead of item content.
4. A section's extracted text length falls within the (form, item) expected band, or its
   confidence is reduced and a warning is attached.
5. `Section.text()` and `Section.markdown()` cover the same byte range (markdown adds syntax, not
   content).
6. Streaming and non-streaming `filing.text()` are equivalent under the agreed definition.

---

## 5. Sequenced rollout

Current shipped version: **5.33.0**. (The epic's original v5.32/v5.33 targets have already shipped:
form-aware TOC analyzer #827, the #826 nested-table fix.)

| Release | Contents | Tension |
|---|---|---|
| **v5.34.0** | TOC-anchor slicing primitive (`section_slicer`); unlock `Section.markdown()` for TOC sections; canonical corpus + de-`manual`-ized benchmark | 3, 4, 7 |
| **v5.35.0** | Per-form schema replacing scattered `if self.form` branches; expected-size bands + `Section.warnings` introspection; streaming/non-streaming equivalence harness | 1, 2, 6 |
| **v6.0** | Remove legacy-parser fallback (JPM now on primary path); replace blanket `except: pass`; freeze `_clean_boundary_artifacts` growth | 5, 8 |

---

## 6. Implementation note — slicing primitive prototype

A prototype of the Tension-3 primitive ships alongside this doc: `edgar/documents/utils/
section_slicer.py`, with `_extract_section_html` (`document.py:299`) refactored to call it. The
algorithm and the seven cases it covers are documented in that module. It subsumes the #826
top-level-only serialization fix and is the precondition for unlocking `Section.markdown()` on TOC
sections (`edgartools-4j6f`) and for 40-F section extraction (`edgartools-8zqq`).

---

## 7. Decision log

**Signed off by maintainer (dwight), 2026-05-31.** All recommendations accepted as the
agreed direction.

| # | Decision | Accepted resolution | Status |
|---|---|---|---|
| D1 | Form-awareness location | Extractor owns *what sections exist* via a declarative per-form schema; renderer stays form-agnostic. Implemented under `edgartools-fhno`. | **accepted** |
| D2 | TOC primitive: slice vs heading-walk | Keep slicing, harden it; TOC for nav *and* content. Shipped (`section_slicer`, `edgartools-4j6f`). | **accepted** |
| D3 | Boundary artifacts | Renderer-clean for new path; freeze `_clean_boundary_artifacts` regex on the legacy path. Tracked `edgartools-yr1z`. | **accepted** |
| D4 | Silent-failure policy | Flag-and-return with introspectable confidence/`warnings`; typed accessors (`.business`) consult the flag. Guardrail shipped (`edgartools-9hwf`); accessor wiring is the residual. | **accepted** |
| D5 | Legacy fallback sunset | Lock v6.0 once JPM is on the primary path. | **accepted** |
| D6 | Equivalence definition | Byte-identical after whitespace normalization. Tracked `edgartools-z5pu`. | **accepted** |

---

## 8. Out of scope

- The rewrite itself (this is the design; implementation follows sign-off).
- XBRL extraction, financial-statement rendering, anything outside `edgar/documents/` and
  `edgar/files/`.
- New form types beyond the existing roster. Getting the existing forms right comes first.

## 9. Acceptance criteria

- [x] This document reviewed by maintainer. *(Signed off 2026-05-31.)*
- [x] Cross-form fixture corpus exists and is wired into the benchmark. *(`edgartools-h44r` — `tests/fixtures/parser_corpus/` + `tests/test_parser_corpus.py`.)*
- [x] `edgartools-sldz` updated with the agreed TOC-analyzer rewrite design and unblocked. *(Fix path = `fhno` per-form schema + `9hwf` guardrail, recorded on the issue.)*
- [x] Decisions recorded (D1–D6) with chosen options. *(§7, accepted.)*
- [x] v5.34 / v5.35 / v6.0 sequencing confirmed.
- [x] New issues filed: streaming/non-streaming equivalence (`z5pu`); renderer-aware boundaries (`yr1z`).
