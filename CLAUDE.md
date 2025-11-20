# EdgarTools - Agent Navigation Guide

**edgartools** is a Python library for SEC Edgar filings analysis.

## Quick Links to Documentation

**User Documentation** (detailed guides in `edgar/ai/skills/core/`):
- `readme.md` - Library overview and getting started
- `quickstart-by-task.md` - Common tasks and code examples
- `data-objects.md` - Core data models (Filing, Company, XBRL, etc.)
- `workflows.md` - Common workflows and patterns
- `advanced-guide.md` - Advanced features and techniques
- `common-questions.md` - FAQ and troubleshooting
- `form-types-reference.md` - SEC form types catalog

---

## Issue Tracking & Task Management

**Hybrid approach**: Beads for tracking, Markdown for planning.

### Beads Commands

**Common Commands:**
```bash
# List and filter issues
bd list --status open                    # View open work items
bd list --status open --priority 0       # Critical items (0-4 or P0-P4)
bd list --status open -l bug             # Filter by label (use -l or --label, singular)
bd list --status in_progress             # Currently active work
bd list -t bug -p 1                      # High priority bugs

# Create issues
bd create --title "Bug: Description" \
          --type bug \
          --priority P1 \
          --label bug,xbrl-parsing \
          --external-ref 'gh:123' \
          --description "Detailed description"

# Update issues
bd update ISSUE_ID --status in_progress  # Valid: open, in_progress, blocked, closed
bd update ISSUE_ID --priority P0         # Change priority (0-4 or P0-P4)
bd update ISSUE_ID --notes "Progress note"  # Add notes (NOT --add-comment)
bd update ISSUE_ID --assignee "username"

# Show details
```

**Valid Status Values**: `open`, `in_progress`, `blocked`, `closed` (NOT "done")

**Valid Priority Values**: 0-4 or P0-P4 (0/P0 = critical, 1/P1 = high, 2/P2 = medium, 3/P3 = low, 4/P4 = backlog)

**Valid Types**: `bug`, `feature`, `task`, `epic`, `chore`

**Use Beads for**: Active work tracking, GitHub issue linking, status updates, priority filtering.

**Use Markdown for**: ROADMAP.md (version planning), VELOCITY-TRACKING.md (velocity analysis), architecture docs.

### Agent Integration

- **product-manager**: Uses `bd list` for work queue, creates issues with `bd create`, updates ROADMAP.md
- **issue-handler**: Creates `bd create --external-ref 'gh:XXX'`, tracks progress with status updates
- **Slash commands**: `/task` and `/triage` wrap `bd` commands

---

## Package Structure

### Core Entry Points

**Top Level** (`__init__.py`): `Filing`, `Filings`, `Company`, `find()`, `obj()`

**Filings** (`_filings.py` 72KB): `Filing` model, `Filings` collection, `get_filings()`

**Current Filings** (`current_filings.py`): `CurrentFilings`, `get_current_filings()`

### Functional Domains

**Entity & Company** (`entity/`):
- `core.py` - `Company`, `Entity`, `SecFiler` classes
- `entity_facts.py` - Company Facts API (63KB)
- `statement_builder.py` - Build statements from facts
- `filings.py` - Company-specific filings
- `tickers.py` - Ticker/CIK lookup

**XBRL** (`xbrl/`):
- `xbrl.py` - Main parser (66KB)
- `statements.py` - Statement classes (46KB)
- `facts.py` - Fact queries (55KB)
- `rendering.py` - Table rendering (72KB)
- `parsers/` - Linkbase parsers
- `stitching/` - Multi-period stitching
- `analysis/` - Metrics, ratios, fraud detection

**Documents** (`documents/`):
- `document.py` - Node tree structure (33KB)
- `parser.py` - HTML parser (13KB)
- `search.py` - BM25 search (27KB)
- `extractors/` - Section detection
- `renderers/` - Markdown, text, table output

**Specialized Forms**:
- `company_reports.py` (37KB) - 10-K/Q/8-K reports
- `funds/` - Investment companies (N-CSR, NPORT)
- `ownership/` - Insider trading (Forms 3/4/5)
- `form144.py` - Insider sales
- `thirteenf.py` - Institutional holdings (13F)
- `offerings/` - Form C, Form D

**Infrastructure**:
- `httpclient.py` - SEC API client
- `storage.py` - Filing cache
- `reference/` - Tickers, company subsets, form types
- `richtools.py` - Terminal display

### Navigation by Task

| Task | Start Here |
|------|------------|
| Get company filings | `entity/core.py` → `Company` |
| Parse financials | `xbrl/xbrl.py` → `XBRL.from_filing()` |
| Extract text | `documents/parser.py` → `HTMLParser` |
| Specific forms | `company_reports.py` or specialized packages |
| Reference data | `reference/` package |

**Details**: See `edgar/ai/skills/core/quickstart-by-task.md` for code examples.

---

## Tests

**Location**: `tests/` (sibling to `edgar/`)

### Structure

```
tests/
├── conftest.py           # Fixtures, hooks, config
├── fixtures/             # Test data
├── issues/
│   ├── regression/       # Auto-marked regression tests
│   └── reproductions/    # Issue reproductions by category
├── batch/                # Batch integration tests
├── perf/                 # Performance benchmarks
└── test_*.py             # Main test suite
```

### Key Configuration

**conftest.py** provides:
- Auto-marking: Tests in `regression/` auto-get `@pytest.mark.regression`
- Fixtures: `aapl_company`, `tsla_company`, etc. (session-scoped)
- HTTP caching disabled for tests (use `--enable-cache` to override)

### Markers

| Marker | When |
|--------|------|
| `fast` | Pure logic, no network |
| `network` | Uses `Company()`, `get_filings()` |
| `slow` | Heavy processing |
| `regression` | Auto-applied in `regression/` folders |
| `reproduction` | Issue reproduction tests |
| `batch` | Multi-company/filing tests |

### Commands

```bash
hatch run test-fast              # Fast tests only
hatch run test-network           # Network tests
hatch run test-fast-parallel     # Parallelized (safe)
hatch run test-regression        # Regression only
hatch run test-full              # All tests
hatch run cov                    # With coverage
```

**Note**: Only parallelize fast tests (`-n auto`) to avoid SEC rate limits.

### Writing Tests

**Best Practices**:
1. Use appropriate markers (`fast`, `network`, etc.)
2. Use fixtures (`aapl_company`) instead of creating objects
3. Regression tests: Place in `tests/issues/regression/` (auto-marked)
4. Reproductions: Place in `tests/issues/reproductions/<category>/`

**Example**:
```python
@pytest.mark.network
def test_company_facts(aapl_company):
    """Use session fixture for performance"""
    facts = aapl_company.get_facts()
    assert facts.revenue is not None
```

**Regression** (no marker needed):
```python
# File: tests/issues/regression/test_issue_429.py
def test_issue_429_period_selection():
    # Test specific bug - auto-marked as regression
    pass
```

---

## Common Patterns

### Basic Usage

```python
# Search filings
from edgar import find
filings = find(form="10-K", ticker="AAPL")

# Get company
from edgar import Company
company = Company("AAPL")
filings = company.get_filings(form="10-K")

# Parse XBRL
filing = filings[0]
xbrl = filing.xbrl()
income = xbrl.statements.income

# Search documents
doc = filing.document()
from edgar.documents import DocumentSearch
results = DocumentSearch(doc).ranked_search("revenue")
```

**More examples**: See `edgar/ai/skills/core/quickstart-by-task.md` and `workflows.md`.

### Data Flow

- **Filing → Report**: `filing.obj()` → `TenK/TenQ/EightK`
- **Filing → XBRL**: `filing.xbrl()` → `XBRL` → `statements`
- **Company → Facts**: `company.get_facts()` → `EntityFacts` → `Statement`
- **Filing → Document**: `filing.document()` → `Document` → extractors

---

## Quick Reference

| Need | File | Key Classes |
|------|------|-------------|
| Filing access | `_filings.py` | `Filing`, `Filings` |
| Company data | `entity/core.py` | `Company`, `Entity` |
| XBRL parsing | `xbrl/xbrl.py` | `XBRL` |
| Statements | `xbrl/statements.py` | `Statement` |
| Documents | `documents/parser.py` | `Document`, `HTMLParser` |
| Search | `documents/search.py` | `DocumentSearch` |
| Reports | `company_reports.py` | `TenK`, `TenQ`, `EightK` |
| Reference | `reference/` | Tickers, forms |

### Large Files (Context Management)

Files >30KB that may need chunking:
- `_filings.py` (72KB)
- `xbrl/rendering.py` (72KB)
- `xbrl/xbrl.py` (66KB)
- `files/html.py` (65KB)
- `entity/entity_facts.py` (63KB)
- `xbrl/facts.py` (55KB)
- `xbrl/statements.py` (46KB)
- `company_reports.py` (37KB)
- `documents/document.py` (33KB)

---

**Version**: Check `edgar/__about__.py`
**Full Docs**: See `edgar/ai/skills/core/` directory
