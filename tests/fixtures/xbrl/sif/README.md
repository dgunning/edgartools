# SIFCO Industries 10-K for fiscal 2025 (GH #1452)

`10k_2025/` holds the XBRL instance and the schema, calculation, label and
presentation linkbases of SIFCO Industries, Inc. (CIK 90168), 10-K for the year
ended 2025-09-30, accession `0001628280-25-058405`. The files are byte-for-byte
the attachments SEC serves for that filing, fetched 2026-11-13 with
`Filing(cik=90168, accession_no="0001628280-25-058405").attachments`. The
definition linkbase and `FilingSummary.xml` were left out; nothing else was
changed. No cassette is involved.

The cash flow statement reports operating cash of continuing operations
(`us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`,
$127,000 for 2025) and of discontinued operations
(`us-gaap:CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations`,
$5,000 for 2025) and no total, so the continuing figure is not the company's
operating cash flow. SEC's CY2025 frames carry the same two values.

Used by `tests/issues/regression/test_issue_1452.py`.
