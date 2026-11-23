# Zimmer Biomet 10-K for 2018 (GH #1995)

The six EX-101 files of accession 0001564590-19-004283, downloaded verbatim from SEC on
2026-11-17 with `Attachment.download()`. Do not edit them.

The income statement presents two extensible-enumeration facts on its face,
`us-gaap:TypeOfRevenueExtensibleList` and `us-gaap:TypeOfCostGoodOrServiceExtensibleList`,
each with the value `us-gaap:ProductMember`. `tests/issues/regression/test_issue_1995.py` uses
them to check that a primary statement's value columns stay numeric.

Check against the printed income statement: Net sales $7,932.9 million (2018) and $7,803.3
million (2017).
