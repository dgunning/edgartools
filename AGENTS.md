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
| Statements | `edgar/xbrl/statements.py` | `Statement`, `StatementLineItem` |
| Notes & disclosures | `edgar/xbrl/notes.py` | `Note`, `Notes` |
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

```text
Company -> company.get_financials() -> Financials -> income/balance/cashflow
Filing -> filing.obj() -> TenK/TenQ -> .notes -> Notes -> Note -> .tables/.text/.expands
Filing -> filing.obj() -> TenK/TenQ/EightK -> .reports -> Reports
Filing -> filing.xbrl() -> XBRL -> statements
Statement -> stmt['line item'] -> StatementLineItem -> .note -> Note (drill-down)
Company -> company.get_facts() -> EntityFacts -> Statement
Filing -> filing.document() -> Document -> extractors
```

## Large Files (>30KB)

When modifying these, read in chunks:
- `_filings.py` (72KB), `xbrl/rendering.py` (72KB), `xbrl/xbrl.py` (66KB)
- `entity/entity_facts.py` (63KB), `xbrl/facts.py` (55KB), `xbrl/statements.py` (46KB)

## Issue Tracking (Beads)

We use `bd` (beads) for issue tracking. Full docs: `docs/beads-workflow.md`

```bash
bd list --status open
bd list --status in_progress
bd list --status open -p 0
bd list -t bug
bd show ISSUE_ID
bd update ISSUE_ID --status in_progress
bd create --title "..." --type bug --priority P1
```

Statuses: `open`, `in_progress`, `blocked`, `closed`

## Development

| Task | Reference |
|------|-----------|
| Verification | `docs/verification-guide.md` |
| Constitution | `docs/verification-constitution.md` |
| Roadmap | `docs/verification-roadmap.md` |
| API examples | `edgar/ai/skills/core/quickstart-by-task.md` |
| Data objects | `edgar/ai/skills/core/data-objects.md` |
| Workflows | `edgar/ai/skills/core/workflows.md` |

Execution rules:

- Use Git Bash for all verification, testing, build, Docker, and Terraform commands
- Do not use PowerShell for testing, building, or deployment commands unless the user explicitly requires it

## Warehouse Work

When working on the SEC warehouse or hosting design, treat these as the authoritative docs:

1. `specification.md`
2. `docs/sec-company-filings-data-model.md`
3. `docs/sec-hosting-verification-plan.md`
4. `docs/guides/aws-warehouse-deployment.md`

Core warehouse rules:

- Flow is `bronze -> stg_* -> silver.sec_* -> gold.dim_* / fact_*`
- Silver is normalized; gold is the only star-schema layer
- `dim_party` is the actor dimension for people and non-issuer entities
- `dim_company` is issuer and business specific
- Compatibility `gold.sec_*` objects are views only, not canonical storage

Canonical warehouse load interfaces:

- `bootstrap_full`
- `bootstrap_recent_10`
- `daily_incremental`
- `load_daily_form_index_for_date`
- `catch_up_daily_form_index`
- `targeted_resync`
- `full_reconcile`
- `submissions_orchestrator`

Daily incremental rules:

- Use SEC daily `form.YYYYMMDD.idx` as the authoritative daily discovery source
- Current Atom feed is optional acceleration only
- Do not guess changed CIKs or accessions
- Daily-index catch-up is checkpoint-driven and gap-aware

Submissions staging rules:

- One orchestrator handles one `CIK##########.json` at a time
- Stage all company-scope rowsets before any silver merge
- Use idempotent sub-loaders for company, address, former names, manifest, and recent filings

Storage and authoring rules:

- Silver is stored as Parquet on filesystem or object storage, not inside DuckDB
- Generated partition keys like `cik_bucket` are storage helpers only, never business join keys
- All repo-authored warehouse code, tests, SQL, comments, and docs must remain ASCII-only
- AWS Terraform lives under `infra/terraform/` with separate `bootstrap-state`, `accounts/dev`, and `accounts/prod` roots

## Verification

We use "verification" not "testing". Verification is outward-facing - does this library deliver what we promised?

Governing principle: the [Verification Constitution](docs/verification-constitution.md) defines 11 principles. The three most important for daily work:

1. **Documentation is the specification** - every documented example must be verifiable
2. **Data correctness is existential** - assert specific values, not just `is not None`
3. **The API must be solvable** - users and agents can navigate to answers

### Definition of Done for New Features

Every new user-facing feature must include:
- **One ground-truth assertion** - a specific value from a real SEC filing, verified by hand
- **One verified documented example** - a code example that is itself a runnable test
- **One silence check** - verify that bad or missing input produces a useful error, not `None`
- **Solvability** - update skill YAML files so agents can discover and use the feature

### Verification Commands

```bash
hatch run test-fast
hatch run test-network
hatch run test-regression
hatch run cov
```

Only parallelize fast tests to avoid SEC rate limits.

### Writing Verification

- **Assert values, not existence**: `assert revenue == 394328000000` not `assert revenue is not None`
- **Use VCR cassettes** for network tests to enable speed and determinism
- **Diversify companies**: Do not default to AAPL; use companies from different industries
- **Test error paths**: Verify that failures produce useful messages, not silent `None`
- **Place regression tests** in `tests/issues/regression/test_issue_NNN.py`

## Version

Check `edgar/__about__.py`
