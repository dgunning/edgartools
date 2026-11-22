# Non-accrual fixtures (GH #1959)

These are real fact rows and footnotes from two BDC filings. `tests/issues/regression/test_issue_1959.py`
uses them to check `extract_nonaccrual` without downloading the full XBRL. Trinity Capital's
instance and schema alone are 20.8 MB.

| File | Filing | Period | Facts | Footnotes |
|---|---|---|---|---|
| `trin_10q_0000950170-25-065028.json` | Trinity Capital 10-Q, accession 0000950170-25-065028 | 2025-03-31 | 1,563 | 2 |
| `bxsl_10k_0001736035-26-000004.json` | Blackstone Secured Lending 10-K, accession 0001736035-26-000004 | 2025-12-31 | 1,596 | 2 |

The rows were fetched from SEC on 2026-11-15 with `filing.xbrl().facts.get_facts()` and
`filing.xbrl().footnotes`. Each fact is a dict as edgartools parses it, with the values unchanged
and the keys `extract_nonaccrual` does not read dropped.

A fact is kept when any of these hold:

- a footnote that mentions non-accrual links to it, at any period
- its concept is `us-gaap:InvestmentOwnedAtFairValue` or `us-gaap:InvestmentOwnedAtCost` and it is
  an instant at the period (the schedule, which the subtotal rule reads, and the portfolio total)
- its concept names non-accrual (`trin:NonAccrualCost`, `bxsl:InvestmentOwnedNonaccrualNumberOfLoans`)

A footnote is kept when it mentions non-accrual; its links are cut to the facts kept.

What to check them against, in each filing's printed pages:

- Trinity, notes: "loans to three portfolio companies and equipment financings to two portfolio
  company were on non-accrual status, with a total cost of approximately $49.7 million".
  Schedule: "Total: Debt Securities- United States ... $1,637,052" and the Transportation Technology
  total, $64,811 at cost (thousands). Both are printed total rows.
- Blackstone tags `InvestmentOwnedNonaccrualNumberOfLoans` = 8 and `...NumberOfBorrowers` = 5.

Do not edit the files by hand. To change one, re-run the script from the repo root:

```bash
hatch run python tests/fixtures/bdc/nonaccrual_1959/extract.py 0000950170-25-065028 2025-03-31 \
    tests/fixtures/bdc/nonaccrual_1959/trin_10q_0000950170-25-065028.json
hatch run python tests/fixtures/bdc/nonaccrual_1959/extract.py 0001736035-26-000004 2025-12-31 \
    tests/fixtures/bdc/nonaccrual_1959/bxsl_10k_0001736035-26-000004.json
```
