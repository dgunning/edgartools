# EdgarTools

Python library for SEC Edgar filings analysis.

## Philosophy

- **Simple API, complex data**: Hide SEC complexity behind intuitive Python objects
- **Progressive disclosure**: Basic usage is easy; advanced features available when needed
- **Read before write**: Understand existing patterns before modifying code

## Quick Navigation

| Need | Location | Key Classes |
|------|----------|-------------|
| Filing access | `edgar/_filings.py` | `Filing`, `Filings` |
| Company data | `edgar/entity/core.py` | `Company`, `Entity` |
| XBRL parsing | `edgar/xbrl/xbrl.py` | `XBRL` |
| Statements | `edgar/xbrl/statements.py` | `Statement` |
| Documents | `edgar/documents/` | `Document`, `HTMLParser` |
| Reports (10-K/Q/8-K) | `edgar/company_reports.py` | `TenK`, `TenQ`, `EightK` |
| Reference data | `edgar/reference/` | Tickers, forms |

## Entry Points

```python
from edgar import Filing, Filings, Company, find, obj
```

- `Company("AAPL")` - Get company by ticker or CIK
- `find(form="10-K", ticker="AAPL")` - Search filings
- `filing.xbrl()` - Parse XBRL financials
- `filing.obj()` - Get typed report object (TenK, TenQ, etc.)

## Data Flow

```
Filing → filing.obj() → TenK/TenQ/EightK
Filing → filing.xbrl() → XBRL → statements
Company → company.get_facts() → EntityFacts → Statement
Filing → filing.document() → Document → extractors
```

## Large Files (>30KB)

When modifying these, read in chunks:
- `_filings.py` (72KB), `xbrl/rendering.py` (72KB), `xbrl/xbrl.py` (66KB)
- `entity/entity_facts.py` (63KB), `xbrl/facts.py` (55KB), `xbrl/statements.py` (46KB)

## Development

| Task | Reference |
|------|-----------|
| Testing | `docs/testing-guide.md` |
| Issue tracking (Beads) | `docs/beads-workflow.md` |
| API examples | `edgar/ai/skills/core/quickstart-by-task.md` |
| Data objects | `edgar/ai/skills/core/data-objects.md` |
| Workflows | `edgar/ai/skills/core/workflows.md` |

## Test Commands

```bash
hatch run test-fast          # Fast tests (no network)
hatch run test-network       # Network tests
hatch run test-regression    # Regression tests
hatch run cov                # With coverage
```

Only parallelize fast tests to avoid SEC rate limits.

## Version

Check `edgar/__about__.py`
