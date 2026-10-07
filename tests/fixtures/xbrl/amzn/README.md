# Amazon role-selected balance-sheet fixture

The `10q_2026q2` directory contains the unedited SEC XBRL package for
Amazon.com, Inc. 10-Q `0001018724-26-000026`, filed July 31, 2026 for the period
ended June 30, 2026. The manifest records original URLs, sizes, SHA256 hashes
and the October 7, 2026 capture time. No cassette is involved.

The [primary filing](https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm)
shows Total assets of $1,095,689 million at June 30, 2026 and $818,042 million
at December 31, 2025. The extracted instance files the same USD amounts as
`us-gaap:Assets` in contexts `c-23` and `c-15`, respectively, unit `usd`,
decimals `-6`. Neither context has dimensions.

The regression selects `http://www.amazon.com/role/ConsolidatedBalanceSheets`
through the public URI accessor and asserts both original instant columns and
their filed values. The issuer schema, instance, presentation, labels, definition
and calculation linkbases are kept intact, with the same fixture contract as AAL.
