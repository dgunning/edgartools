# SEC quarterly full-index fixtures

Verbatim quarterly form indexes from SEC EDGAR, laid out under the same path SEC serves
them from: `<year>/QTR<n>/form.gz` here is
`https://www.sec.gov/Archives/edgar/full-index/<year>/QTR<n>/form.gz`. Each file was
downloaded on 2026-11-23, decompressed, and recompressed at level 9 with mtime 0 (`gzip.compress(data, 9, mtime=0)`), so
the bytes are reproducible. Gzip is lossless: decompressing a file gives back exactly the
index SEC served. Never edit a file here. To replace one, download it again from SEC and
recompress it, then check its SHA-256 against the table.

These quarters predate 1994 Q3, the old hardcoded start of `available_quarters()`. EFTS
only indexes 2001 onward, so `get_by_accession_number()` resolves a filing from these
quarters by scanning the quarterly index, and the tests serve that scan from here.

Used by `tests/issues/regression/test_issue_g00j_pre_1994q3_quarters.py`.

| Index | Gzipped bytes | Decompressed bytes | SHA-256 of decompressed content |
|---|---|---|---|
| `1993/QTR1/form.gz` | 436 | 1,081 | `6f1734583bf47d6da38bc6f56061b1aaef901c678530875cd46c2cd085128059` |
| `1993/QTR2/form.gz` | 398 | 1,080 | `7dc68eea3b80ebdf064f7d32293ce87b0ba0fd81b72406edf114d4bfb51969c6` |
| `1993/QTR3/form.gz` | 585 | 1,553 | `52cfb80882b14158189d43b119fdffede003642046940d51bcdf074582de1ade` |
| `1994/QTR1/form.gz` | 361,376 | 3,257,581 | `0b943c3539aa949a50be422d705b1d1f7ffe3bb01303fdb0ae8b9dd5f6fe28cb` |
| `1994/QTR2/form.gz` | 310,801 | 2,574,456 | `09ebf81661a775a9eafd8766ea91835537a6780683d21fb4ade3c28400398388` |

The filings the tests resolve:

| Accession | Company | Form | Filed | Index |
|---|---|---|---|---|
| `0000003673-94-000052` | ALLEGHENY POWER SYSTEM INC | 35-CERT | 1994-06-30 | `1994/QTR2` |
| `0000873611-93-000002` | MERRILL LYNCH FL MUN BOND FD OF MERRILL LYNCH MUL ST MUN SER | 24F-2NT | 1993-09-28 | `1993/QTR3` |
