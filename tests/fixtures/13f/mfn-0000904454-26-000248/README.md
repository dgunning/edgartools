# MFN Partners Management LP, 13F-HR/A for Q4 2025

CIK: 1732811. Accession: 0000904454-26-000248. Filed: 2026-05-01. Period: 2025-12-31.

These are the original primary and information-table XML returned by EdgarTools
from the public SEC filing on 2026-09-26. They have not been edited or reduced.
Only their local filenames differ.

Source: https://www.sec.gov/Archives/edgar/data/1732811/0000904454-26-000248-index.html

SHA-256:

- `primary.xml`: `573632a89d5c338c888c5757b57231154def236a0a7992b76c21cc4243b2b19c`
- `holdings.xml`: `0c3da56178a746dca63a6664b1a06236556ecfbd022cfc90ba7158492feb4ef3`

A "NEW HOLDINGS" amendment with two rows, both RICE ACQUISITION CORP 3:

- warrants (`*W EXP 99/99/999`), value 320,000 for 400,000 units, or $0.80 each
- ordinary shares (`ORD SHS CL A`), value 24,600,000 for 2,400,000 shares, or $10.25 each

The cover declares `schemaVersion` X0202 (values in dollars) and
`tableValueTotal` 24,920,000, which equals the two rows' sum. One warrant under a
dollar makes half of the priceable rows sub-dollar, which the implied-price
heuristic used to read as values in thousands (GH #1336).
