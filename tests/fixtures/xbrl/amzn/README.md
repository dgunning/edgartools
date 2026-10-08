# Amazon role-selected balance-sheet fixture

The `10q_2026q2` directory contains a compact, byte-preserved balance-sheet
subset for Amazon.com, Inc. 10-Q `0001018724-26-000026`, filed July 31, 2026 for the period
ended June 30, 2026. The manifest pins the complete original
files at Git commit `6f1f9cd1e446f6f7d84cc3873fe9746a63475d41`, their SEC URLs, sizes,
SHA256 hashes and October 7, 2026 capture time, and the compact files' own sizes
and hashes. No cassette is involved.

The [primary filing](https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm)
shows Total assets of $1,095,689 million at June 30, 2026 and $818,042 million
at December 31, 2025. The extracted instance files the same USD amounts as
`us-gaap:Assets` in contexts `c-23` and `c-15`, respectively, unit `usd`,
decimals `-6`. Neither context has dimensions.

The regression selects `http://www.amazon.com/role/ConsolidatedBalanceSheets`
through the public URI accessor and asserts both original instant columns and
their filed values. The original balance-sheet presentation and calculation role
blocks are retained whole, with exact original facts, contexts, units, labels and
issuer declarations. Container whitespace may change; unrelated roles and facts
are omitted. DEI facts, dimension-free contexts and all original unique reporting
periods retain filing and period controls. The original package has no matching
balance-sheet definition role. Its compact definition file retains the original
AOCI member-hierarchy block from
`StockholdersEquityScheduleofAccumulatedOtherComprehensiveIncomeLossDetails`,
which the parser also uses for balance-sheet dimensional-row indentation.
This is a focused balance-sheet fixture, not a complete filing package.
