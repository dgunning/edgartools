# Zymeworks 10-Q for the quarter ended 2026-06-30

These are the filing's XBRL files, downloaded unedited from SEC EDGAR on 2026-11-17 for GitHub issue #1234
(https://github.com/dgunning/edgartools/issues/1234). `tests/issues/regression/test_issue_1234.py` uses them.

- Accession: 0001937653-26-000047
- Source: https://www.sec.gov/Archives/edgar/data/1937653/000193765326000047/

`zyme-20260630_htm.xml` is the instance SEC extracts from the Inline XBRL document. It is the file
`XBRL.from_filing()` reads. The 1.8 MB inline HTML is left out.

The filing imports the 2026 US-GAAP taxonomy. Eight contexts put a `xbrldi:typedMember` on
`us-gaap:StatementOfIncomeLocationBalanceAxis`, with the values
`us-gaap:ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost` and
`us-gaap:GeneralAndAdministrativeExpense`. The 2026 schema declares that axis with
`xbrldt:typedDomainRef="#us-gaap_QName.domain"`.

| File | SHA-256 |
|---|---|
| zyme-20260630.xsd | 2e8674ebb67c3ef844648c21da32a4becfe8613816cdd137c7305f52d45fd78d |
| zyme-20260630_cal.xml | 5bc5fc66f52e34a0788fbe4b8d955bad4cf28f191b0942cb01ff27105dce14a8 |
| zyme-20260630_def.xml | 6353383211f14f50417afd61eccbf4648796dfd50db402c1998398e10ad1c408 |
| zyme-20260630_htm.xml | d38049dff3da800d2ec7062fc14cb53099c569e1a816fccdc475e315ea30075b |
| zyme-20260630_lab.xml | 5164266f3480a92d89102866e8215372ae2835748a1663a6e5b65761d4501390 |
| zyme-20260630_pre.xml | 31991c9810e0f2132d94a867674bc53303464643b06d126dc1c318b112f65ed5 |
