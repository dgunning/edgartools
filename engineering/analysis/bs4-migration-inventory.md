# BeautifulSoup Migration Inventory

**Bead**: `edgartools-07lk.8` (6.0 epic `edgartools-07lk`, target "bs4-free by 7.0")
**Date**: 2026-07-28 · **Method**: static read-only sweep (grep + structural read); no PoC port executed
**Migration target pattern**: lxml per `edgar/funds/nmfp3.py` with helpers from `edgar/funds/reports.py`

## Bottom line

43 files match bs4/BeautifulSoup, but only **32 need migration**. The rest:
5 in `edgar/files/` (deleted by `07lk.3`), 2 debug scratch scripts, 4 false
positives (comment-only mentions in already-lxml modules). Total effort:
**~33–38 person-days (7–8 weeks for one developer)**. Highest-leverage first
move: **migrate `edgar/xmltools.py`** — 12 of the 32 files route XML field
extraction through its helpers, and rewriting its function bodies against
`lxml.etree` (same names/signatures) requires **zero changes at the ~350+
combined call sites**; each dependent then only swaps its
`BeautifulSoup(xml, 'xml')` construction line plus any local raw bs4 calls.

## Excluded from scope

| File(s) | Why |
|---|---|
| `edgar/files/*.py` (5) | Deleted by `07lk.3` (blocked on 436/3dp/zqjn); `_deprecation.py:1-13` confirms legacy status |
| `edgar/entity/.debug/bug_408/*.py` (2) | Debug scratch, not production |
| `edgar/documents/utils/anchor_cache.py` | Comment only — deliberately regex, avoids bs4 (`anchor_cache.py:124,128`) |
| `edgar/funds/models/derivatives.py` | Comment only — already lxml (`derivatives.py:8`) |
| `edgar/funds/reports.py` | Comment only (`:1227`) — this IS the target pattern module |
| `edgar/thirteenf/parsers/infotable_xml.py` | Already migrated (docstring `:21-25` documents the bs4→lxml speedup) |

## Key architectural finding: `xmltools.py` is a shared bs4 micro-DSL

`edgar/xmltools.py` (153 LOC) exposes `child_text`, `child_value`,
`child_texts`, `find_element`, `optional_decimal`, `value_or_footnote`,
`get_footnote_ids`, `value_with_footnotes` — all typed against `bs4.Tag`.
Imported by 12 files; heaviest helper call-site counts: `schedule13.py` ~99,
`muniadvisors.py` ~99, `form144.py` 53, `formd.py` 50,
`table_containers.py` 38, `primary_xml.py` 32, `filing_summary.py` 30.
Migrating xmltools first is why several heavy files rate M rather than L.

## Inventory (32 files: 14 S · 13 M · 5 L)

Format: file | parses | soup sites (raw / via xmltools) | bs4 in signatures | hot/cold | tests | effort

| File | Parses | Sites | Sig leaks | Path | Tests | Effort | Notes |
|---|---|---|---|---|---|---|---|
| `xmltools.py` | XML | 11 / — | 9 (by design) | shared foundation | test_xml.py | **M** | Do first |
| `_party.py` | XML | 6 / 13 | 1 | hot (Filer info) | **NONE** | S | Add tests first |
| `current_filings.py` | Atom XML | 2 / 3 | 0 | warm | yes + regression | S | |
| `effect.py` | XML | 12 / 4 | 0 | cold | yes | S | |
| `ownership/core.py` | Tag | 3 / — | 2 | hot (Form 3/4/5) | yes | S | |
| `ownership/forms.py` | XML | 7 / 10 | 0 | hot | via public_api | S | |
| `ownership/models.py` | Tag typing | 2 / — | 0 | hot | yes | S | |
| `ownership/owners.py` | XML | 3 / 13 | 0 | hot | yes | S | |
| `company_reports/forty_f.py` | HTML (lazy) | 4 | 0 | cold | yes | S | Has regex fallback (`:540`) — template for bs4-optional |
| `company_reports/subsidiaries.py` | HTML (lazy) | 5 | 0 | warm (Ex-21) | yes | S | |
| `offerings/prospectus/drs.py` | HTML (lazy) | 2 | 0 | warm | yes | S | |
| `storage/_local.py` | HTML | 4 | 0 | cold | yes | S | |
| `forms.py` (list_forms) | HTML | 6 | 0 | cold, cached | **NONE** | S | Add tests first |
| `funds/reference.py` | HTML | 7 | 0 | cold | yes | S | |
| `datatools.py` | Tag | 3 | 1 | **DEAD — no callers** | partial | S | **Delete `table_tag_to_dataframe` (:165-179), don't migrate** |
| `attachments.py` | HTML (filing index) | 13 | 1 | **HOT** (every filing) | yes | M | |
| `headers.py` | HTML (SEC-HEADER) | 7 | 1 | **HOT** (every filing) | yes | M | Also fix unpinned parser at `:483` |
| `abs/ten_d.py` | HTML | 8 | 5 | cold | yes | M | |
| `abs/distribution.py` | HTML | 6 | 1 | cold | yes | M | |
| `funds/_497k_tables.py` | HTML | 11 | 2 | warm (GH #912 active) | yes + regression | M | |
| `offerings/prospectus/_fee_table/parsing.py` | HTML (lazy) | 11 | 0 | warm/growing | regression | M | |
| `sgml/filing_summary.py` | HTML+XML | 19 / 30 | 0 | **HOT** (attachments, xbrl, MCP) | yes | M | |
| `thirteenf/parsers/primary_xml.py` | XML | 12 / 32 | 0 | **HOT** (13F) | cassettes | M | |
| `xbrl/notes.py` | HTML | 8 (2 lazy) | 0 | **HOT** (Notes core feature) | 3 test files | M | |
| `ownership/table_containers.py` | XML | 16 / 38 | 4 | hot | yes + regression | M | |
| `form144.py` | XML | 20 / 53 | 4 | warm | yes | M | |
| `sgml/concept_extractor.py` | HTML (R*.htm, CSS-class) | 21 | 7 | warm (viewer) | yes | M | |
| `beneficial_ownership/schedule13.py` | XML + legacy HTML | 43 / 99 | 0 | warm (13D/G; HTML path pre-Dec-2024 only, `:107-111`) | 3 regressions | **L** | Heaviest file |
| `muniadvisors.py` | XML | 39 / 99 | 0 | cold (Form MA) | yes | **L** | |
| `offerings/exempt/formd.py` | XML | 37 / 50 | 1 | warm (Form D) | yes + regression | **L** | |
| `markdown.py` | HTML (DOM-heavy) | 41 | 0 | **HOT** (`filing.markdown()`, RAG-facing) | 4 test files | **L** | Needs careful parity testing |
| `funds/data.py` | HTML (multiple scrapers) | 38 | 1 | hot (fund users) | many | **L** | Split into separate PRs |

## Migration order

1. `xmltools.py` — unlocks 12 dependents cheaply.
2. Hot-path S/M: `headers.py`, `attachments.py`, `sgml/filing_summary.py`,
   `xbrl/notes.py`, `thirteenf/parsers/primary_xml.py`, ownership S-tier
   (`core.py`, `forms.py`, `models.py`, `owners.py`, `table_containers.py`).
3. Remaining M: `form144.py`, `concept_extractor.py`, `_497k_tables.py`,
   `_fee_table/parsing.py`, `abs/*`.
4. Cold S opportunistically.
5. Delete dead `datatools.py:165-179` instead of migrating.
6. L items last with real time budgeted: `schedule13.py`, `muniadvisors.py`,
   `formd.py`, `markdown.py`, `funds/data.py`.

## Effort

S ≈ 0.3–0.5d · M ≈ 0.75–1.5d · L ≈ 2.5–4d (developer familiar with the
nmfp3.py pattern): 14×S ≈ 5.5d + 13×M ≈ 14d + 5×L ≈ 16d ≈ **33–38
person-days**. Excludes the optional "bs4-optional wrapper" work —
`forty_f.py:517-540` already demonstrates that exact pattern.

## Leniency check — no bs4-load-bearing files

No file relies on bs4's lenient parsing in a way lxml can't handle: the
already-migrated reference modules handle malformed XML with lxml recovery in
production, and `edgar/documents/` handles broken SEC HTML on lxml.html today.
A sweep for leniency-related comments near bs4 call sites found none.

## Gaps / caveats

- `_party.py` and top-level `forms.py` have **no direct tests** — add coverage
  before migrating or regressions will be silent.
- Static inventory only; no PoC port was executed. Effort figures assume the
  nmfp3.py pattern transfers, which the xmltools-first strategy makes likely
  but unproven until the first M-tier port lands.
