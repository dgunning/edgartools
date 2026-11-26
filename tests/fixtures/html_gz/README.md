# Gzipped primary documents of real SEC filings

Each `.gz` file is one filing's primary HTML document, exactly as
`Filing.html()` returned it, compressed with gzip level 9 and no name or
timestamp in the header (`gzip -n -9` equivalent), so recompressing the same
text always produces the same bytes. Decompress with `gzip.decompress(...)`;
the SHA-256 below is of the decompressed text.

Do not edit these files; re-fetch instead.

## hsic/10k: Henry Schein, Inc. (CIK 1000228), saved 2026-11-23

| File | Accession | Filed | Raw size | SHA-256 (decompressed) |
|---|---|---|---|---|
| `hsicform10k20201226.htm.gz` | 0001000228-21-000019 | 2021-02-17 | 3.89 MB | `ec5ef613c76802ae01a148893c4dbfe9277ebb840477ef7524e6370ba9971a28` |
| `hsic-20221231.htm.gz` | 0001000228-23-000011 | 2023-02-21 | 3.55 MB | `8d540cfea91ebcd6cecc2d126f073c3f7ddb88b023d032f360ba8355f6cb9f07` |
| `form10k20231230.htm.gz` | 0001000228-24-000011 | 2024-02-28 | 3.58 MB | `c3bd12fbd12c9b38135651c251be18f5616b0d03d114d56bd404e6c2a77dd83e` |

Read by `tests/issues/regression/test_issue_107.py`.
