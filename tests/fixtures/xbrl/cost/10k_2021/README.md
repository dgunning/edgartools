# Costco FY2021 10-K XBRL (GH #1947)

Verbatim files from SEC filing `0000909832-21-000014` (Costco Wholesale Corp,
CIK 909832, 10-K for the fiscal year ended 2021-08-29), downloaded 2026-11-13
and not edited: the inline-XBRL instance, its schema and linkbases, and the
filing's `FilingSummary.xml`.

Why this filing: its lease detail roles are titled without the "(Details)"
suffix, so SEC's renderer filed them under the wrong menu categories in
`FilingSummary.xml` ("Leases, Components of Lease Expense" under Cover,
"Leases, Future Minimum Payments" under Notes, "Leases, Supplemental Balance
Sheet Information" under Uncategorized). Used by
`tests/issues/regression/test_issue_1947.py`.
