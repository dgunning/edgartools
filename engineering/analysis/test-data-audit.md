# Test Data Audit — cassettes, fixtures, root data/

**Bead**: `edgartools-07lk.12.3` · **Date**: 2026-07-30 · **Method**: AST index of
every test def/class cross-referenced against cassette basenames (both
pytest-vcr auto-naming and explicit `my_vcr.use_cassette` patterns); grep of
every fixture/data path fragment across `tests/`, `edgar/`, `scripts/`.

Footprint audited: `tests/cassettes/` 1.6 GB (176 files, 154 tracked) ·
`tests/fixtures/` 577 MB (424 files) · root `data/` 384 MB (405 on disk, 360
tracked) · `tests/data/` 64 KB. `.git` is 829 MB.

## Status (2026-08-05)

**(b) is done** — 117 MiB of zero-reference fixtures deleted after the sanity
check this document asked for. Every candidate was re-verified against the whole
working tree, not just tracked files, and the aapl fallback in
`xbrl2_fixtures.py:37` was read to confirm it globs only top-level `*.xsd` and so
cannot reach the deleted subdirectories. `-m fast` passes at 4,339 with the same
seven skips as before, none of them fixture-related — worth checking, because a
missing xbrl fixture makes its test *skip*, not fail.

**Also settled since this audit**, though not by this document's plan: the
recorded-quarterly-index problem in `tests/cassettes/` was found and fixed
independently (beads zuuu, 07lk.21), taking cassettes from 1.6 GB to 899 MiB and
tracked from ~1,054 MB to 530 MiB. That retires a large part of what row (d)
below was aiming at, and **corrects it**: gzip serialization does *not* reduce
clone download, because git already zlib-compresses blobs and base64-of-gzip
re-compresses in the pack. Measured on a 33.8 MB cassette: pack 8.0 MB today
versus 8.1 MB pre-compressed, while the working tree drops 33.8 MB to 10.7 MB.
Row (d) is a checkout/IO win, not a transfer win.

Two things this audit did not catch, both worth knowing:

- A cassette existing is not evidence a test replays from it.
  `test_issue_880`'s cassette held an index and nothing else while its docstring
  claimed it recorded the whole filing; the document had always been fetched
  live past vcr.
- `test_section_detection_comparison.py:161` wants
  `fixtures/html/msft/10k/msft-10-k-2024-07-30.html`, but the fixture on disk is
  `...-2025-07-30.html`. The test has been skipping silently since the fixture
  was re-dated. Dead coverage, not dead data.

## Headline numbers

| Action | Tracked clone savings | Effort |
|---|---|---|
| (a) Delete confirmed orphans | **~34 MB** (+149 MB local-only disk) | Zero risk, minutes |
| (b) Delete zero-reference fixtures (sanity-check first) | **~121 MB** | Low |
| (c) Relocate schema/example files to docs | size-neutral (4.8 MB moved) | Low |
| (d) Gzip cassette serialization | **~500–700 MB** | Moderate: custom serializer + one-time re-encode |
| (e) LFS/external-fetch for `fixtures/{html,xbrl}` | checkout unchanged, clone/history relief | Decision + migration |

Whales dominate: the top 5 files are 415 MB (26% of the 4.15 GB combined
footprint).

## (a) Confirmed orphans — delete now

- `data/cik_lookup_data.txt` (**33 MB**, tracked) — the one plausible consumer,
  `edgar/entity/tickers.py:38-46`, downloads this live from SEC and never reads
  the file. Single largest orphan in the audit.
- `data/index_files/company.20221003.idx` (tracked) — all its siblings are used
  by `test_read_filing_indexes.py`/`test_filing.py`; this one isn't.
- 2 tracked orphan cassettes (72 KB):
  `test_problem2_full_footnote_fallback_on_real_pre_checkbox_filing.yaml`
  (test renamed — see `test_issue_863...py:137`) and
  `TestEdgeCases.test_date_range_no_results.yaml` (no such test in any of the 8
  `TestEdgeCases` classes).
- Local-only cruft (no clone impact): 7 untracked `[aapl_company]`/`[msft_company]`
  parametrize-era cassettes (140 MB) from the rename to `..._aapl`/`..._msft`
  (`test_entity_facts_revenue_fixes.py:197-213`), plus untracked
  `data/Schedule13{D,G}.xml`, `data/20-F/pdd.htm`, `data/10-D/*` (~9.3 MB).

## (b) Zero-reference fixtures — delete after sanity check (~121 MB tracked)

- `tests/fixtures/xbrl/{ba,gs,hubs,jnj,nvda,pg}/10k_202x` — zero references
  (53.2 MB, 45 tracked files across this bullet and the next).
- `tests/fixtures/xbrl/aapl/{10k_2015,10q_2010,10q_2015}`,
  `msft/{10q_2015,10q_2024}`, `nflx/10q_2010` — not among the fixtures defined
  by `tests/fixtures/xbrl2_fixtures.py` (21.6 MB).
- `tests/fixtures/entity/tsla_facts.json` (2.9 MB) — `test_entity_facts.py:941-946`
  loads only `lpa_facts.json`/`snow_facts.json`.
- `data/xbrl/datafiles/{aes,att,crsr,gd,hubspot,mtpi,orcl,radcq,spire}` (43 MB) —
  zero references; siblings (aapl, msft, nflx, tsla, unp, gahc) are used.
- Borderline, keep-or-relocate: `tests/fixtures/xbrl/ibm/10k_2024` (20 MB) is
  used only by `scripts/manual/test_statement_fidelity.py:34` (never runs in CI).

## (c) Schema/example files misfiled as test data — relocate (4.8 MB, all tracked)

None are read by any test or library code; they are format documentation.
Suggested home: `docs/reference/sec-form-schemas/` (or wiki).

- `data/xbrl/xsd/` — iXBRL 1.1 XSD schemas
- `data/xbrl/srt/SRT Taxonomy 2024.xlsx` (3.0 MB)
- `data/13f/EDGAR Form 13F Schema Files/` + `XML Samples/`
- `data/144/EDGAR Form 144 XML Schema Files/`
- `data/NPX/EDGAR Form N-PX XML Samples/`
- `data/nport/schema/`
- `data/formc/formc.pdf`
- `data/xbrl/docs/FAIR_VALUE_DIMENSIONS.md` — actual prose docs; move to `docs/`
  regardless.

## (d) Cassette compression — the biggest and only *scaling* lever

`decode_compressed_response: True` (`tests/conftest.py:37`) stores response
bodies as plain decompressed text in YAML. Samples:

| Cassette | Raw | Gzipped | Reduction |
|---|---|---|---|
| `test_xbrl_periods_msft.yaml` | 65.5 MB | 6.3 MB | 90% |
| `test_allstate_2026_10k_item_1_present.yaml` | 64 MB | 11 MB | 83% |
| `TestIssue868...` (binary body, already gitignored) | 135 MB | 76.8 MB | 43% |

Text-bodied cassettes (the majority of ~1.0 GB tracked) compress 80–90% →
estimated 500–700 MB reduction. Options: custom vcrpy serializer, or
`.yaml.gz` + thin load wrapper. Do this BEFORE the `iz7d` cassette-expansion
campaign (~50 new cassettes) so every future cassette benefits automatically.

## Other findings

- **Root `data/` sits under a blanket `.gitignore` rule** (`data/`); the 360
  tracked files were historically force-added. New files there are invisible to
  git — explains the 405-vs-360 drift; tracked orphans are legacy debt, not
  ongoing risk.
- `tests/fixtures/html/` (278 MB) is essentially fully used (parser corpus
  manifest covers all 38 tickers + 2 direct refs) — size is inherent to full
  10-K HTML. Best LFS candidate along with `fixtures/xbrl/` post-pruning;
  cassettes benefit more from compression than LFS.
- `tests/data/` (64 KB) fully used; no duplication with root `data/`
  (different fixture generations, differing sizes).
- Harness storage (`scripts/harness/storage.py:13-40`) uses
  `~/.edgar_test/harness.db` — no repo data footprint.

## Suggested execution order

1. (a) deletions + local cruft `rm` — minutes, ~34 MB tracked.
2. (b) after one sanity grep per path — ~121 MB tracked.
3. (c) relocation PR with redirect note in `data/` README.
4. (d) gzip serializer spike, then one-time re-encode migration; land before
   `iz7d` recording campaign.
5. (e) LFS vs fetch-step decision for `fixtures/{html,xbrl}` — the remaining
   ~550 MB that is legitimately used and will keep growing.

Note: deletions shrink the working tree and future clones' checkout; history
still carries the blobs. Any history rewrite is a separate, explicit owner
decision (out of scope).
