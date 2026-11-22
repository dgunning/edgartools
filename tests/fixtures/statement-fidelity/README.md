# Statement-fidelity fixtures

Offline inputs for `compare_statements_to_viewer` tests in
`tests/xbrl/test_statement_fidelity.py`. One directory per filing, named by
accession number, each holding one statement page and the XBRL that page's
library `Statement` is built from.

| Accession | Filer | Form | Page | Exercises |
|---|---|---|---|---|
| 0000065984-24-000112 | Entergy | 10-Q | R3 Consolidated Statements of Cash Flows | a concept shown twice per entity; -0.0; zero rendered blank; a balance period outside the default view |
| 0001081316-24-000016 | Berkshire Hathaway Energy | 10-Q | R25 Comprehensive Income (Parenthetical) | a negated label's sign under `comprehensive_income(parenthetical=True)` |
| 0001562762-22-000397 | DRDGOLD | 20-F | R2 Statement of Profit or Loss and OCI | `income_statement()` and the statement by role sign cost of sales differently |
| 0001493152-26-037707 | GraniteShares Gold Trust | 10-K | R2 Statements of Assets and Liabilities | library labels that are not the filing's |
| 0001581068-21-000012 | Brixmor Property Group | 10-K | R8 Consolidated Statements of Cash Flows | the operating partnership's beginning-balance row |
| 0001564590-22-016827 | Chindata Group Holdings | 20-F | R2 Consolidated Balance Sheets | a USD convenience column beside RMB columns |
| 0001214659-22-006372 | Good Times Restaurants | 10-Q | R6 Condensed Consolidated Statements of Cash Flows | a statement where every cell matches |
| 0001298946-24-000052 | DiamondRock Hospitality | 10-Q | R3 Consolidated Balance Sheets (Parenthetical) | instant facts under a "3 Months Ended" column: judged under the column's period, the fact's own period reported beside |

## What each directory holds

- `R<n>.htm`: the SEC viewer page, verbatim.
- `xbrl/`: the filing's schema, linkbases and XBRL instance, trimmed to what
  the role's `Statement` reads, and parsed in the tests with
  `XBRL.from_directory`:
  - the schema keeps the role's `roleType` and the element declarations of
    the role's presentation-tree concepts;
  - the presentation, calculation and definition linkbases keep the role's
    extended links;
  - the label linkbase keeps the labels of the role's concepts and of every
    axis and member the kept contexts name (so member row labels read as live);
  - the instance keeps the facts of the role's concepts and every `dei` fact,
    with the contexts and units they reference; footnote links are dropped;
  - `MetaLinks.json` keeps the page's report entry and the tag entries of the
    same concepts, axes and members, verbatim except that `auth_ref` is dropped.

  Elements are removed with lxml; every kept element is serialized unchanged.
  BHE also keeps its Comprehensive Income role, and DiamondRock its Balance
  Sheet role (without their pages): without them `comprehensive_income()` and
  `balance_sheet()` would claim the parenthetical roles.
- `manifest.json`: filer, form, role and page, and what `XBRL.from_filing`
  adds from the filing itself (the header's SIC code and period of report, and
  each kept role's FilingSummary menu category), with the access path
  (typed getter or `statements[role]`) the live filing gives the page.

## Provenance

Built on 2026-11-14 from live SEC filings with

```bash
hatch run python tests/fixtures/statement-fidelity/build_fixtures.py tests/fixtures/statement-fidelity
hatch run python tests/fixtures/statement-fidelity/compare_live.py
```

`compare_live.py` runs `compare_statements_to_viewer` on each live filing and
on its fixture and compares the outcomes for the fixture's page as multisets
of every field of `StatementFidelityResults.to_dataframe()`, labels and
reasons included, and the page's access path. On 2026-11-14 all 4,015 outcomes over the eight pages were
identical. `test_fixture_reaches_the_page_statement_as_live` checks each
page's access path against the manifest. The values pinned in the tests were
read from the R pages in this directory.

Total size: 3.1 MB.
