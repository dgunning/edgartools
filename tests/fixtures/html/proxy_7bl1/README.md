# Proxy statement fixtures for bead edgartools-7bl1

These are verbatim primary documents from SEC EDGAR, retrieved on 2026-11-17 and left unedited.
`tests/issues/regression/test_7bl1_proxy_html_tables.py` uses them.

| File | Company | Form | Accession | Source URL | SHA-256 |
|---|---|---|---|---|---|
| `amzn_tm261382-1_def14a.htm` | Amazon.com, Inc. (CIK 1018724) | DEF 14A | 0001104659-26-041026 | https://www.sec.gov/Archives/edgar/data/1018724/000110465926041026/tm261382-1_def14a.htm | 327bebc45b3908f83823a8a9bdb3dd4ddec51ac67edc4be5322f26fa3a308f31 |
| `ko_ko-20260429xdef14a.htm` | The Coca-Cola Company (CIK 21344) | DEF 14A | 0001104659-26-028215 | https://www.sec.gov/Archives/edgar/data/21344/000110465926028215/ko-20260429xdef14a.htm | 061a7d5b4a5cde01af7bcc7d98a34aa39ed9c121b15b56d3f544c31346e4de58 |
| `shak_tm261375-1_def14a.htm` | Shake Shack Inc. (CIK 1620533) | DEF 14A | 0001104659-26-051572 | https://www.sec.gov/Archives/edgar/data/1620533/000110465926051572/tm261375-1_def14a.htm | 6d395caab151a96cc3cc4ffeab84ff867a96f6d12cd48416566dda91d865d20e |

The three show the table shapes the bead covers:

- AMZN puts each executive's name in a cell spanning three rows, and its directors are paid only in stock.
- KO stacks its director-compensation labels over six rows and states its audit fees in thousands.
- SHAK has a dual-class ownership table under stacked headers, and the heading for its SCT sits inside the table's title row.
