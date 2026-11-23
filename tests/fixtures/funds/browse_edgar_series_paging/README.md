# browse-edgar filing pages for one fund series, every offset

Saved verbatim on 2026-11-22 with `edgar.httprequests.download_text` from:

- `S000002841-start{N}.html`: https://www.sec.gov/cgi-bin/browse-edgar?CIK=S000002841&start={N}&count=100
  for N = 0, 100, 200, 300, 400, 500, 600

S000002841 is the series behind VEXMX (VANGUARD INDEX FUNDS, CIK 0000036405). The seven
pages hold 540 filing rows and 486 unique accession numbers; the page at 600 is empty and
ends the walk. The page at 100 begins with 0001104659-23-037487, the filing the old
`start=101` offset skipped.

`tests/issues/regression/test_89483_fund_series_paging.py` reads them. Do not edit them;
re-fetch instead.
