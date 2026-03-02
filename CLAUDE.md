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
| Reports (10-K/Q/8-K) | `edgar/company_reports/` | `TenK`, `TenQ`, `EightK`, `AuditorInfo`, `SubsidiaryList` |
| Reference data | `edgar/reference/` | Tickers, forms |

## Entry Points

```python
from edgar import Filing, Filings, Company, find, obj
```

- `Company("AAPL")` - Get company by ticker or CIK
- `company.get_financials()` - Financial statements from latest 10-K (recommended)
- `company.get_quarterly_financials()` - Financial statements from latest 10-Q
- `find(form="10-K", ticker="AAPL")` - Search filings
- `filing.xbrl()` - Parse XBRL financials
- `filing.obj()` - Get typed report object (TenK, TenQ, etc.)

## Data Flow

```
Company → company.get_financials() → Financials → income/balance/cashflow
Filing → filing.obj() → TenK/TenQ/EightK → .reports → Reports
Filing → filing.xbrl() → XBRL → statements
Company → company.get_facts() → EntityFacts → Statement
Filing → filing.document() → Document → extractors
```

## Large Files (>30KB)

When modifying these, read in chunks:
- `_filings.py` (72KB), `xbrl/rendering.py` (72KB), `xbrl/xbrl.py` (66KB)
- `entity/entity_facts.py` (63KB), `xbrl/facts.py` (55KB), `xbrl/statements.py` (46KB)

## Issue Tracking (Beads)

We use `bd` (beads) for issue tracking. Full docs: `docs/beads-workflow.md`

```bash
bd list --status open              # Ready/open issues
bd list --status in_progress       # Currently active
bd list --status open -p 0         # Critical priority (0=critical, 4=backlog)
bd list -t bug                     # Filter by type (bug/feature/task)
bd show ISSUE_ID                   # View details
bd update ISSUE_ID --status in_progress  # Change status
bd create --title "..." --type bug --priority P1  # Create issue
```

**Statuses**: `open`, `in_progress`, `blocked`, `closed`

## Development

| Task | Reference |
|------|-----------|
| Verification | `docs/verification-guide.md` |
| Constitution | `docs/verification-constitution.md` |
| Roadmap | `docs/verification-roadmap.md` |
| API examples | `edgar/ai/skills/core/quickstart-by-task.md` |
| Data objects | `edgar/ai/skills/core/data-objects.md` |
| Workflows | `edgar/ai/skills/core/workflows.md` |

## Verification

We use "verification" not "testing". Verification is outward-facing — does this library deliver what we promised?

**Governing principle**: The [Verification Constitution](docs/verification-constitution.md) defines 11 principles. The three most important for daily work:

1. **Documentation is the specification** — every documented example must be verifiable
2. **Data correctness is existential** — assert specific values, not just `is not None`
3. **The API must be solvable** — users and agents can navigate to answers

### Definition of Done for New Features

Every new user-facing feature must include:
- **One ground-truth assertion** — a specific value from a real SEC filing, verified by hand
- **One verified documented example** — a code example that is itself a runnable test
- **One silence check** — verify that bad/missing input produces a useful error, not `None`
- **Solvability** — update skill YAML files so agents can discover and use the feature

### Verification Commands

```bash
hatch run test-fast          # Fast tests (no network) — run often
hatch run test-network       # Network tests (sequential, rate-limited)
hatch run test-regression    # Regression tests
hatch run cov                # With coverage
```

Only parallelize fast tests to avoid SEC rate limits.

### Writing Verification

- **Assert values, not existence**: `assert revenue == 394328000000` not `assert revenue is not None`
- **Use VCR cassettes** for network tests to enable speed and determinism
- **Diversify companies**: Don't default to AAPL — use companies from different industries
- **Test error paths**: Verify that failures produce useful messages, not silent `None`
- **Place regression tests** in `tests/issues/regression/test_issue_NNN.py`

## Version

Check `edgar/__about__.py`
