# browse-edgar filing pages for fund series, one form per query

Saved verbatim on 2026-11-22 with `edgar.httprequests.download_text` from:

- `{SERIES}-{FORM}-start{N}.html`: https://www.sec.gov/cgi-bin/browse-edgar?CIK={SERIES}&type={FORM}&start={N}&count=100
  for N = 0 and 100 (a space in the form is an underscore in the file name)

| Series | Fund | Registrant | Forms | Newest NPORT-P |
|---|---|---|---|---|
| S000002841 | VEXMX | VANGUARD INDEX FUNDS, CIK 36405 | NPORT-P (29 rows) | 0000036405-26-000478 |
| S000026864 | VCLT | VANGUARD SCOTTSDALE FUNDS, CIK 1021882 | NPORT-P (28), N-PORT (0), SC 13D (0) | 0001021882-26-000851 |
| S000013499 | PFF | iSHARES TRUST, CIK 1100663 | NPORT-P (28), N-PORT (0) | 0000940400-26-034998 |

The SEC header of each newest NPORT-P lists exactly one series, the one in its row. Every
start=100 page, and every page with 0 rows, is SEC's empty listing for that query.

`tests/issues/regression/test_issue_888_series_only_filtering.py` and
`test_issue_1143_followup_series_scoping.py` read them through `tests/_browse_edgar_pages.py`.
Do not edit them; re-fetch instead.
