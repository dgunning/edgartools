# SEC source fixtures for issue 1824

These files are unedited SEC document bytes, including the surrounding SGML
`<DOCUMENT>` / `<TEXT>` wrappers. They are not reconstructed tables or VCR
cassettes. Do not remove the wrappers or normalize the HTML.

## TSM earnings exhibit

`a3q26e_withguidancexfinal.htm` was obtained on **2026-11-01**, before the
original implementation, as the EX-99.1 `DOCUMENT` block from the complete
submission:

- Submission: https://www.sec.gov/Archives/edgar/data/1046179/000104617926000726/0001046179-26-000726.txt
- Exhibit for browsing: https://www.sec.gov/Archives/edgar/data/1046179/000104617926000726/a3q26e_withguidancexfinal.htm
- SHA-256: `43d51cc7eba069f9d27e8a4647304d37bdeae90127d5c38e1736d857c240f00d`

The saved bytes are **not** the standalone exhibit's HTML response body.
The wrapper identifies the original filename, type and sequence.

Ground truth: `(Unit: NT$ million, except for EPS)`; net sales 1,494,243;
gross profit 992,379; income from operations 876,445; net income 763,064;
reported EPS 29.43 (raised letter footnote b). Net income comparisons are
452,302 for 3Q25 and 706,562 for 2Q26, with YoY/QoQ percentages interleaved.
The EPS footnote is a smaller font positioned above the baseline, not a plain
magnitude suffix. Footnote a says the 3Q2026 figures have not been approved by
the Board of Directors.

The primary and month-end 6-K fixtures belong to the Company fallback tests in
PR #1825 and are intentionally absent from this standalone parser change.

## Cardlytics currency regression

`cdlx_form8-kx2025q2xex991.htm` was downloaded on **2026-11-04**, before the
review revisions, from this SEC endpoint. The returned bytes include the
EX-99.1 SGML wrapper and are retained unchanged:

- Source: https://www.sec.gov/Archives/edgar/data/1666071/000166607125000124/cdlx_form8-kx2025q2xex991.htm
- Accession: `0001666071-25-000124`, filed 2025-08-06.
- Size: 347,831 bytes.
- SHA-256: `c4531477a11426309dbfda2d669391540033a4b167366c8603ea0ecaa629152c`

Ground truth: Q2 2025 revenue **63,249 thousand USD**, net loss **9,283
thousand USD**, basic and diluted loss per share **USD 0.18**. The income
statement says `(Amounts in thousands, except per share amounts)`: it names
no non-USD currency and must preserve the legacy USD default.
