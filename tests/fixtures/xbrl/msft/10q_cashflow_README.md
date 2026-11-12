# Microsoft 10-Q cash flow fixtures (bead edgartools-k7mi8.3)

Trimmed copies of the XBRL in three Microsoft 10-Qs, kept for
`tests/issues/regression/test_k7mi8_3_msft_derived_quarter.py`. The complete
originals are about 10 MB each, so a cassette of the three was 31 MB.

| Directory | Accession | Quarter ended | Filed |
|---|---|---|---|
| `10q_2025q1` | `0001193125-25-256321` | 2025-09-30 (Q1 FY2026) | 2025-10-29 |
| `10q_2025q2` | `0001193125-26-027207` | 2025-12-31 (Q2 FY2026) | 2026-01-28 |
| `10q_2026q1` | `0001193125-26-436133` | 2026-09-30 (Q1 FY2027) | 2026-10-28 |

Each directory holds the instance (`msft-YYYYMMDD_htm.xml`) and the schema
(`msft-YYYYMMDD.xsd`, which embeds the linkbases), downloaded from SEC on
2026-11-11 by `XBRL.from_filing`. `10q_cashflow_manifest.json` gives each file's
SEC URL and the byte count and SHA-256 of the original and the trimmed copy.

## How they were trimmed

With lxml, keeping original elements unchanged:

- Schema: every element declaration, role type and import. Presentation,
  calculation and definition links only for the cash flow role
  (`.../role/Role_StatementCASHFLOWSSTATEMENTS`). Label links only for the concepts
  that role presents.
- Instance: the `dei:` facts and every fact of a concept the cash flow role
  presents, with the contexts and units they reference. Everything else is dropped.

Check: for both input sets (`[Q2, Q1]` and `[Q1 FY2027, Q2, Q1]`) and six
`cash_flow_statement` configurations (standard on and off, `discrete_quarters`,
`include_quarterly`, `use_optimal_periods=False`, `max_periods=8`), the stitched
periods and every row's values are identical from the trimmed and the complete files.

## Values the test reads

`msft:GainLossOnInvestmentsAndDerivativeInstruments` (net recognized gains on
investments and derivatives): $1,007M for Q1 FY2026 in `10q_2025q1`; $9,931M for the
quarter and $6,024M for the six months ended 2025-12-31 in `10q_2025q2`; $(3,907)M
for Q1 FY2026, recast, as the comparative in `10q_2026q1`. These are not complete
filing packages: only the cash flow statement can be read from them.
