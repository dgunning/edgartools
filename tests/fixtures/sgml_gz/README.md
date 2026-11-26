# Gzipped full submission text files

Each file is a filing's full submission text (`<accession>.txt`, the SGML that
`Filing.sgml()` parses) exactly as SEC EDGAR served it, compressed at level 9 with
mtime 0 (`gzip.compress(data, 9, mtime=0)`) so the bytes are reproducible. Gzip is
lossless: decompressing a file gives back exactly what SEC served. Never edit a file
here. To replace one, download it again from SEC, recompress it, and check its SHA-256
against the table.

Tests decompress a file into a temporary directory, load it with
`FilingSGML.from_source()`, and set it as the filing's `_sgml`, so the filing's documents
come from here and nothing reaches the network. The four index fields of each filing
are in `tests/_offline_filings.py`.

Downloaded 2026-11-23. Used by `tests/issues/regression/test_issue_844_sixk_binary_artifacts.py`.

| Accession | Company | Form | Filed | Gzipped bytes | Decompressed bytes | SHA-256 of decompressed content |
|---|---|---|---|---|---|---|
| `0001104659-22-129316` | Futu Holdings Ltd | 6-K | 2022-12-22 | 2,141,656 | 20,810,074 | `057e645968fe9549e26ba2a35be70becf8fb6694018e321380df374389111114` |
| `0001654954-18-006914` | CRESUD INC | 6-K | 2018-06-25 | 3,097 | 37,689 | `36b92af65e7f40faff9d13116f0a74b31fddc45afce09e154537464660b44eb2` |
