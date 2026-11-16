---
description: How closely edgartools' financial statements match the SEC's own rendering, measured on a random sample of 10-K, 10-Q, 20-F and 40-F filings and regenerated each release.
---

# As-Filed Fidelity Scorecard

The SEC renders every XBRL filing as a set of statement pages, the `R*.htm` files behind the Interactive Data Viewer. This scorecard measures how closely edgartools reproduces those pages, on a random sample of filings the library's developers had not looked at before. It is regenerated each release with `scripts/fidelity_scorecard.py`.

Two checks run on every filing (see [SEC Viewer: Cross-Validate Against the XBRL Parser](../guides/sec-viewer-guide.md#cross-validate-against-the-xbrl-parser)):

- **Facts check**, `viewer.compare(xbrl)`: does each numeric cell on a statement page have the XBRL fact the library parsed, with the same value?
- **Statement check**, `viewer.compare_statements(xbrl)`: does the statement a user gets, both `to_dataframe()` and the rendered table, show that cell in the page's row, under the page's period, with the page's value and sign?

## Latest result

edgartools `main` at commit `1f3c6cd6` (6.2.0 plus the fix for single-period statement requests, #1981), measured 2026-11-15.

**Sample**: seed 20261115; 120 original 10-K, 10-Q, 20-F and 40-F filings filed from 2020-01-01 to 2026-09-30, drawn at random by form and era, plus 1 filing added so every industry group has a minimum share. 756 filings used while building the checks were excluded. Of the 121 filings, 98 have SEC statement pages and were compared, and 23 have none. No filing raised an error.

| Check | Cells compared | Matched | Rate | Coverage of page cells |
|---|---|---|---|---|
| Facts check | 33,075 | 33,074 | 100.00% | 96.84% |
| Statement check, `to_dataframe()` | 23,397 | 23,390 | 99.97% | 68.51% |
| Statement check, rendered table | 23,397 | 23,390 | 99.97% | 68.51% |

Per filing, each filing weighed the same:

| Surface | Filings | Median | At 100% | Lowest |
|---|---|---|---|---|
| `to_dataframe()` | 98 | 100% | 98.0% | 98.87% |
| Rendered table | 98 | 100% | 98.0% | 98.87% |

Read the rate together with coverage. The rate counts only the cells the check could compare. Coverage says how many of the page's numeric cells that is.

### What the 31% of uncompared cells are

The statement pages hold 34,153 numeric cells. 10,756 of them were not compared:

- **9,561 (28%) are on statement-of-equity pages.** The check does not read the equity layout yet (member columns, with period blocks in the rows), so `statement_of_equity()` is not covered by this scorecard.
- **1,082** are cells the check could not tie to one fact or one library row. Most are fund and segment pages whose column header names several members at once.
- **113** are in a convenience-currency column (a 20-F's USD translation beside its home-currency figures), which the library shows in the filing's own currency.

### Disagreements found

These are reported next to the rate and don't count against it. Each one is something the SEC page and the library show differently. Whether it is a library defect is for the reader to decide.

| What differs | `to_dataframe()` | Rendered |
|---|---|---|
| A page row the library does not show | 13 rows in 10 filings | 13 rows in 10 filings |
| A library row with a different label from the page | 591 rows in 24 filings | 601 rows in 26 filings |
| A library row on an axis the page's statement does not present | 4,281 rows in 97 filings | 4 rows in 2 filings |
| A cell value different from the page | 6 cells in 1 filing | 6 cells in 1 filing |
| A cell sign different from the page, as rendered text | none | 5 cells in 4 filings |

The default DataFrame includes dimensional rows that the SEC page leaves out. That accounts for the large count of rows on axes the statement does not present. The rendered table hides them.

## Earlier results

A scorecard's sample is drawn fresh for each release, so its numbers come from filings the library was not tuned on. Results from before this page existed were not drawn that way.

| Version | Seed | Filings compared | `to_dataframe()` rate | Filings at 100% | Coverage |
|---|---|---|---|---|---|
| 6.2.0 + #1981 (`1f3c6cd6`) | 20261115 | 98 | 99.97% | 98.0% | 68.51% |

## Limits

- Only statement pages are compared, parentheticals included. Notes, policies, tables and details are not.
- Statement-of-equity pages are not compared yet, and their cells count in the coverage denominator.
- A cell matches within half a unit of its last displayed digit, so a page in millions cannot show an error under $0.5 million.
- The facts check reads the SEC's rendering of the same filing. It does not check the filer's own numbers or calculation arithmetic (see `viewer.validate()`).
- The pooled rate weighs filings by how many cells they have. A fund's schedule of investments runs to thousands of cells, so one filing can move the pooled rate by several points. The per-filing table is not affected that way.

The full list of limits and every rate definition is written into each run's `scorecard.md`, read from the modules' own documentation.

## Reproduce it

```bash
export EDGAR_IDENTITY="Your Name you@example.com"
python scripts/fidelity_scorecard.py --seed 20261115 --size 120 --end 2026-09-30 \
    --exclude scripts/fidelity_scorecard_excluded.txt --out scorecard-run
```

The same seed, size, dates and exclusion list draw the same sample; use `scripts/fidelity_scorecard_excluded.txt` as it was at the run's commit, since each later release adds the previous sample to it. The run writes the sample, every cell and every outcome as CSV files, plus `scorecard.md` and `scorecard.json`. The SEC can re-render a filing's pages, so a later run of the same sample can differ slightly.
