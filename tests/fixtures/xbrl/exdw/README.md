# Exceed World 10-K for fiscal 2025 (GH #1452)

`10k_2025/` holds the XBRL instance and the schema, calculation, label and
presentation linkbases of Exceed World, Inc. (CIK 1634293), 10-K for the year
ended 2025-09-30, accession `0001634293-26-000002`. The files are byte-for-byte
the attachments SEC serves for that filing, fetched 2026-11-13 with
`Filing(cik=1634293, accession_no="0001634293-26-000002").attachments`. The
definition linkbase and `FilingSummary.xml` were left out; nothing else was
changed. No cassette is involved.

The cash flow statement reports operating cash only as
`us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`
(-$8,147,821 for 2025, $2,724,235 for 2024), with no total and no discontinued
operations, so the continuing figure is the whole.

Used by `tests/issues/regression/test_issue_1452.py`.
