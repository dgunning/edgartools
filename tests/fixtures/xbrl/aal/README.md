# American Airlines combined-filing role fixtures

These are original, unedited SEC XBRL attachments captured October 7, 2026.
The per-directory `manifest.json` files record original URLs, byte counts,
SHA256 hashes, capture times and exact filing accessions. No cassette is involved.

| Directory | Filing | Report date | Filing date |
|---|---|---|---|
| `10k_2025` | `0000006201-26-000014`, 10-K | 2025-12-31 | 2026-02-18 |
| `10q_2026q2` | `0000006201-26-000052`, 10-Q | 2026-06-30 | 2026-07-23 |

The filings contain separate balance-sheet presentation roles for American
Airlines Group Inc. and American Airlines, Inc. The original issuer schema,
extracted instance, presentation, label, definition and calculation linkbases
are retained. A numeric role-selection reproduction needs the instance and
presentation; the regression contract also retains schema, labels and definition
for classified processing, filed display and dimension behavior. Calculation is
retained to keep the complete parsed metadata.

Independent primary-HTML sources:

- [Annual filing](https://www.sec.gov/Archives/edgar/data/4515/000000620126000014/aal-20251231.htm)
- [Quarterly filing](https://www.sec.gov/Archives/edgar/data/4515/000000620126000052/aal-20260630.htm)

The annual subsidiary balance sheet files receivables from related parties, net
(`us-gaap:OtherReceivablesNetCurrent`) of $9,896 million and $8,187 million.
The quarterly subsidiary balance sheet, Item 1B, files $10,203 million and
$9,896 million. The parent balance-sheet role has no corresponding receivable
row. The regression asserts USD amounts, not the displayed million-dollar scale.

These fixtures establish role fidelity, comparative-period selection and
processing preservation. They do not establish complete subsidiary financial
correctness: the independently reported parent-fact contamination of the plain
`us-gaap:Assets` row remains unresolved by this correction.
