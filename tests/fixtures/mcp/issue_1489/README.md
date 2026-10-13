# Missing note-table metadata

This fixture supports [issue #1489](https://github.com/dgunning/edgartools/issues/1489).
It contains the first table-record object from received MCP `TextContent.text`,
captured on 2026-10-08 using upstream commit
`7a2a157e34e0329b1a8428127dd6ab1b985813fe`, plus one final LF outside the object.
The object was extracted byte for byte, without reserializing cells or replacing
its two bare `NaN` constants. Its `.txt` extension reflects that it is not strict
JSON. It is a received record fragment, not a SEC-response cassette, raw JSON-RPC
frame or complete filing replay.

The record comes from Apple's 10-Q `0000320193-26-000020`, filed 2026-07-31 for
the period ended 2026-06-27: Note 6, Debt, [R24.htm](https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/R24.htm),
role `http://www.apple.com/role/DebtTables`, concept
`aapl_CommercialPaperCashFlowSummaryTableTextBlock`. The missing `balance` and
`weight` are metadata fields 16 and 17 in its twenty-field record, beyond the ten
displayed column names. The captured source-schema evidence has no balance
attribute for this text-block concept and no calculation locator for it.

The fixture is 2,669 bytes, with SHA-256
`b46ab38069b2b6a04043d028eb668dff726a1bcfe66dfb77d18d56b24b3fb946`.
The regression reconstructs a DataFrame from these recorded values, supplies
scoped Company, filing and Notes stubs, and invokes the registered `edgar_notes`
handler. It tests exported-record conversion and preservation of the other
eighteen fields; it does not reparse the complete filing or verify financial
accuracy. Other frames in that module are explicitly synthetic controls.
