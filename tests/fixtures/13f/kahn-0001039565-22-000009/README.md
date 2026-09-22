# Kahn Brothers Group, Q1 2022

CIK: 1039565. Accession: 0001039565-22-000009. Filed: 2022-05-02.

These are the original primary and information-table XML returned by EdgarTools
from the public SEC filing on 2026-09-11, before the unit-diagnostics change.
They have not been edited or reduced. Only their local filenames differ.

Source: https://www.sec.gov/Archives/edgar/data/1039565/000103956522000009/0001039565-22-000009-index.html

SHA-256:

- `primary.xml`: `faef7bb48b5740e21faa72f6f47bf48d34be8138f3f8141a6e321475f7203c64`
- `holdings.xml`: `b57f19d6f857cb53f00bf4fc0e1a14297a6731f696ad5d185392381d9c708ea5`

The 46 raw holding values sum to 787,553,692. The cover summary contains
787,553,693, a difference of one dollar that must not be silently reconciled.
ALCON has raw value 254,000 and 3,175 shares, implying $80 per share when
interpreted as dollars, versus $80,000 after a thousands conversion.

Independent corroboration of dollar interpretation:

- https://13f.info/13f/000103956522000009-kahn-brothers-group-inc-q1-2022
  shows a portfolio value of $787,554 thousand (rounded).
- https://www.dataroma.com/m/hist/p_hist.php?f=KB
  shows $788 million for Q1 2022.

The primary document has no `schemaVersion`. A pre-transition date fallback
therefore selects thousands even though these amounts already represent dollars.
The fixture supports an ambiguity warning and a caller-verified dollar override;
it does not justify a universal maximum-share-price heuristic.
