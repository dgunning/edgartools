# Industry breakdown fixtures (GH #1784)

These are real fact rows from three BDC 10-K filings. `tests/issues/regression/test_issue_1784.py`
uses them to check `PortfolioInvestments.reported_industry_breakdown()` without downloading
the full XBRL. They replace three cassettes of about 62 MB.

| File | Filing | Fact rows |
|---|---|---|
| `arcc_10k_0001287750-26-000006.json` | Ares Capital 10-K, filed 2026-02-04, period 2025-12-31 | 102 |
| `fsk_10k_0001628280-26-011734.json` | FS KKR Capital 10-K, filed 2026-02-25, period 2025-12-31 | 60 |
| `main_10k_0001396440-26-000016.json` | Main Street Capital 10-K, filed 2026-02-27, period 2025-12-31 | 8 |

The rows were fetched from SEC on 2026-11-11 with `filing.xbrl().facts.get_facts()`. Each row
is a fact dict as edgartools parses it, with the values unchanged and the unused keys dropped.

A row is kept when all of these hold:

- its concept is `us-gaap:InvestmentOwnedAtFairValue` or `us-gaap:InvestmentOwnedPercentOfNetAssets`
- it is an instant
- it has no dimension (the reported totals), or it is dimensioned by
  `us-gaap:EquitySecuritiesByIndustryAxis`, alone or with other axes, at any period

Rows for the prior period (2024-12-31) are kept on purpose, so the tests can check that the
extraction leaves them out. Rows with more than one axis would be kept too, but none of these
three filings has any. Do not edit the values by hand. To change a fixture,
re-run the script below from the repo root:
`hatch run python extract.py tests/fixtures/bdc/industry_breakdown_1784`.

```python
"""Extract the fact rows reported_industry_breakdown() reads, verbatim from live SEC XBRL."""
import json
import sys
from datetime import date
from pathlib import Path

from edgar import Filing

OUT = Path(sys.argv[1])
AXIS = 'dim_us-gaap_EquitySecuritiesByIndustryAxis'
CONCEPTS = ('us-gaap:InvestmentOwnedAtFairValue', 'us-gaap:InvestmentOwnedPercentOfNetAssets')
KEEP = ('concept', 'context_ref', 'value', 'numeric_value', 'unit_ref', 'currency', 'decimals',
        'period_instant', 'dimension_member_label')
CASES = [
    ('arcc', 1287750, 'ARES CAPITAL CORP', '2026-02-04', '0001287750-26-000006'),
    ('fsk', 1422183, 'FS KKR Capital Corp', '2026-02-25', '0001628280-26-011734'),
    ('main', 1396440, 'Main Street Capital CORP', '2026-02-27', '0001396440-26-000016'),
]

for slug, cik, name, filed, acc in CASES:
    xbrl = Filing(cik=cik, company=name, form='10-K', filing_date=filed, accession_no=acc).xbrl()
    rows = []
    for fact in xbrl.facts.get_facts():
        if fact.get('concept') not in CONCEPTS or fact.get('period_type') != 'instant':
            continue
        dims = {k: fact[k] for k in fact if k.startswith('dim_') and fact.get(k)}
        # Undimensioned totals, and every fact on the industry axis (alone or with other axes)
        if dims and AXIS not in dims:
            continue
        row = {k: fact.get(k) for k in KEEP if fact.get(k) is not None}
        row.update(dims)
        rows.append(row)
    payload = {
        'accession_no': acc, 'cik': cik, 'company': name, 'form': '10-K', 'filing_date': filed,
        'period_of_report': xbrl.period_of_report, 'fetched': date.today().isoformat(),
        'extracted_by': 'see README.md in this directory', 'facts': rows,
    }
    path = OUT / f'{slug}_10k_{acc}.json'
    path.write_text(json.dumps(payload, indent=1, sort_keys=False) + '\n')
    print(path, len(rows), path.stat().st_size)
```
