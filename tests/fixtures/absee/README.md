# ABS-EE EX-102 fixtures

Verbatim SEC files for `tests/abs/test_asset_data.py` and
`tests/issues/regression/test_pjlj5_3_absee_asset_columns.py` (bead edgartools-pjlj5.3).
Fetched 2026-11-17 from sec.gov.

| File | Filing | Schema | Content |
|---|---|---|---|
| `woart_2022c_0001104659-26-111517_first25.xml` | World Omni Auto Receivables Trust 2022-C, ABS-EE 0001104659-26-111517, filed 2026-09-29 | autoloan | first 25 of 17,425 assets of `woart2022cex102aug26.xml` (63 MB) |
| `bmwlt_2023-2_0000929638-25-004537_first25.xml` | BMW Vehicle Lease Trust 2023-2, ABS-EE 0000929638-25-004537, filed 2025-12-09 | autolease | first 25 of 31,924 assets of `bmwlt2023-2_exhibit102.xml` (121 MB) |
| `bank_2025-bnk49_0001888524-26-019640_ex102.xml` | BANK 2025-BNK49, ABS-EE 0001888524-26-019640, filed 2026-10-28 | cmbs | whole `exh_102.xml` (37 loans, 65 properties) |
| `gnmag_2020-1_0001213900-21-000188.txt` | GNMAG Asset Backed Securitizations Trust 2020-1, ABS-EE/A 0001213900-21-000188, filed 2021-01-04 | debtsecurities | whole submission `.txt` (SGML, with the EX-102 inside) |

The two trimmed files were cut with `scripts/abs/trim_ex102.py <full file> 25`,
which copies the document byte for byte through the 25th `</assets>` and then
closes the root element, so every asset in them is exactly as filed.

SHA-256 of the full downloads the fixtures came from:

```
4a7c26c2a75e565ffbc3bca387c62dbbcdae6c9b85cd6da02e6f985edf29f388  woart2022cex102aug26.xml
51c1f864982e9219449c7819d7610c92a52f3ef319da726f82a33016b4ab97cc  bmwlt2023-2_exhibit102.xml
43d90448fc350d821de23a697f1a1e788c80f835633b07e8c3b198d87da3dd46  exh_102.xml (BANK 2025-BNK49)
91eb55b4f89173b1152963c673ffe00cd9fcef0f300c90a760d14508356cbc98  0001213900-21-000188.txt
```
