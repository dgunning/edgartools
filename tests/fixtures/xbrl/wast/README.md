# Waste Energy Corp. 10-K for 2025 (GH #1452)

`10k_2025/` holds the XBRL instance and the schema, calculation, label and
presentation linkbases of Waste Energy Corp. (CIK 1515139), 10-K for the year
ended 2025-12-31, accession `0001493152-26-033196`. The files are byte-for-byte
the attachments SEC serves for that filing, fetched 2026-11-13 with
`Filing(cik=1515139, accession_no="0001493152-26-033196").attachments`. The
definition linkbase and `FilingSummary.xml` were left out; nothing else was
changed. No cassette is involved.

The cash flow statement reports operating cash of continuing operations for
both years (-$390,107 for 2025, -$402,563 for 2024) and no total. Discontinued
operating cash
(`us-gaap:CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations`) is
reported only for 2024 (-$1,554,250); its 2025 cell is empty. So the continuing
figure is the whole for 2025 and not for 2024.

Used by `tests/issues/regression/test_issue_1452.py`.
