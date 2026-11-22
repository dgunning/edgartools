# Viewer-harness fixtures

Offline inputs for `compare_viewer_to_xbrl` tests in
`tests/xbrl/test_viewer_validation.py`. One directory per filing, named by
accession number.

| Accession | Filer | Form | Exercises |
|---|---|---|---|
| 0001628280-20-002543 | Spirit AeroSystems Holdings | 10-K | page in millions, facts at decimals=-5 |
| 0001878848-25-000063 | IREN Ltd | 10-K | balance sheet in thousands, operations in whole dollars (decimals=-3) |
| 0001410578-23-001531 | Quoin Pharmaceuticals | 10-Q | page in whole dollars; duplicate cash facts at decimals 0 and -5 |
| 0001174947-24-000443 | Azure Power Global | 20-F | INR and USD columns; opening/closing cash on the cash flow statement |
| 0001564590-22-016827 | Chindata Group Holdings | 20-F | share counts under class-of-stock member headers; a two-member header |
| 0001299969-24-000010 | Comstock Holding Companies | 10-K | CommonStockValue under Class A / Class B member headers |
| 0001081316-24-000016 | Berkshire Hathaway Energy | 10-Q | combined filing: consolidated rows, then rows under the PacifiCorp member |
| 0001794783-26-000012 | SelectQuote | 10-Q | Goodwill filed twice for one context, at decimals -3 and -5 |
| 0001558370-20-011395 | Trilogy Metals | 10-Q | nine months from 2019-12-01, plus three stray facts from 2019-12-02 |
| 0001581068-21-000012 | Brixmor Property Group | 10-K | cash shown three times on the cash flow statement (start, end, reconciliation total) |
| 0001298946-24-000052 | DiamondRock Hospitality | 10-Q | percent-type dividend rate shown as 8.25% |
| 0001493152-26-037707 | GraniteShares Gold Trust | 10-K | gold in ounces on a page in thousands; percent-type total return |
| 0000950170-23-065631 | Grayscale Stellar Lumens Trust | 10-K | token quantity on a page in thousands; single instant in a duration column |
| 0001713683-20-000163 | Zscaler | 10-K | cash shown three times on the cash flow statement |
| 0001193125-22-052373 | Virgin Group Acquisition Corp. II | 10-K | first period 2021-01-13 to 2021-12-31, headed "12 Months Ended" |
| 0001214659-22-006372 | Good Times Restaurants | 10-Q | the instance binds the srt namespace to the prefix `pf0`; revenue under a ProductOrServiceAxis member header |
| 0001562401-24-000082 | American Homes 4 Rent | 10-Q | L.P. parenthetical: member headers name the legal entity, the unit facts also carry the partner type; R6 statement of equity (whole page): two-line headings (component / share class), NCI, quarterly and year-to-date movements |
| 0001828016-23-000023 | Playtika Holding | 10-Q | statement of stockholders' deficit (whole page): two quarterly movements, a "Total" column |
| 0001562762-22-000397 | DRDGOLD | 20-F | IFRS statement of changes in equity (whole page), amounts printed "R 2,688.6" |
| 0001834376-26-000049 | InnovAge Holding | 10-K | statement of equity (whole page): rows of a movement after its closing balance rows |
| 0001193125-21-361301 | CGI | 40-F | IFRS statement of changes in equity (whole page): opening rows naming a restatement member |

## Provenance

Built on 2026-11-13 from live SEC data with edgartools (`find(accession)`):

- `R*.htm` is the R file from the filing's SGML bundle with every `<tr>` removed
  except the column-header rows, every member-header (`class="rh"`) row, and the
  data rows of the concepts under test. Everything kept is byte-for-byte as filed.
  A statement of equity (`'*'` in the builder's `CASES`) is kept whole, since its
  row order determines each row's period; its `facts.json` then holds the facts
  of every element in the statement's presentation tree.
- `facts.json` is every fact for those concepts from `filing.xbrl().facts.to_dataframe()`
  (columns concept, context_ref, period_key, period_type, value, numeric_value,
  unit_ref, currency, decimals, is_dimensioned), with each fact's context
  dimensions from `xbrl.contexts[context_ref].dimensions`.
- `MetaLinks.json` is the filing's MetaLinks.json reduced to the tag entries of
  those concepts and of the axes and members the kept member headers name
  (without `auth_ref`), and the report entries of the kept R files.
- `facts.json` also keeps, for a few filings (`EXTRA_FACTS` in the builder), the
  facts of concepts no kept row shows, because they carry the periods under test.
- `presentation.json` is, for each kept report's role, the parsed presentation
  tree's roots and every node's children with each child reference's preferred
  label role (`xbrl.presentation_trees[role]`).
- `namespaces.json` is the filing's namespace bindings, URI to prefix
  (`xbrl.parser.namespace_prefixes`), and its typed dimensions
  (`xbrl.parser.typed_dimensions`), so dimension QNames resolve offline.
- For a whole page only: `labels.json` is each presentation-tree element's
  labels by role (`xbrl.element_catalog[id].labels`), and `dimensions.json`
  each of the page's role's axes with its default member and whether it is
  typed (`xbrl.axes_for_role(role)`, and the merged `xbrl.axes` under `merged`).

Do not edit these by hand. `build_fixtures.py` (in this directory) rebuilds them:
`hatch run python tests/fixtures/viewer-harness/build_fixtures.py tests/fixtures/viewer-harness`.
