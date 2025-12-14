# Code Quality Scripts

Quick-reference scripts for scanning code quality during and after development.

## Quick Start

### After making changes (fast):
```bash
./scripts/quality/scan_changed.sh
```

### Before submitting PR (comprehensive):
```bash
./scripts/quality/scan_full.sh
```

### Focus on specific areas:
```bash
./scripts/quality/scan_complexity.sh   # Find complex functions
./scripts/quality/scan_dead_code.sh    # Find unused code
./scripts/quality/scan_security.sh     # Security issues
```

## Available Scripts

### ✅ `scan_changed.sh` (Implemented)
**Purpose:** Quick feedback on git-changed files
**Speed:** ~5-10 seconds
**Usage:** `./scan_changed.sh [branch]`
**Default:** Compares against `main`

**Checks:**
- Ruff linting (auto-fix enabled)
- Pyright type checking
- Complexity analysis (warnings)
- Dead code detection (warnings)
- Security scan (HIGH severity only)

### 🚧 `scan_full.sh` (Planned)
**Purpose:** Comprehensive codebase analysis
**Speed:** ~30-60 seconds
**Output:** JSON reports in `reports/quality/`

### 🚧 `scan_complexity.sh` (Planned)
**Purpose:** Find refactoring candidates
**Speed:** ~5 seconds

### 🚧 `scan_dead_code.sh` (Planned)
**Purpose:** Identify unused code for cleanup
**Speed:** ~5 seconds

### 🚧 `scan_security.sh` (Planned)
**Purpose:** Security vulnerability scan
**Speed:** ~10 seconds

## Tool Installation

### Prerequisites
**uv/uvx** (recommended - runs tools in isolation):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Tools (auto-installed via uvx - no manual install needed!)
- `ruff` - Linter and formatter (via `uvx ruff`)
- `radon` - Complexity metrics (via `uvx radon`)
- `vulture` - Dead code detection (via `uvx vulture`)
- `bandit` - Security scanner (via `uvx bandit`)
- `pyright` - Type checker (already in project via pre-commit)

### Why uvx?
- **No installation needed** - Tools run on-demand
- **Isolated** - Doesn't affect project dependencies
- **Always latest** - Auto-updates cached tools
- **Fast** - uv caches tools for instant re-runs
- **Clean** - No global pip pollution

### Optional (high value):
- **pyscn** - Structural analysis (Go binary)
  - Download: https://github.com/ludo-technologies/pyscn/releases
  - Very fast, AI-friendly, comprehensive

## Integration Points

### Pre-commit Hooks
Scripts run automatically before commits (configured in `.pre-commit-config.yaml`)

### CI/CD
Add to `.github/workflows/quality.yml` for PR checks

### Daily Workflow
```bash
# Make changes
git add .

# Quick check
./scripts/quality/scan_changed.sh

# If all good, commit
git commit -m "Your changes"
```

## Philosophy

- **Fast feedback** - Most scans complete in seconds
- **Non-blocking** - Warnings don't fail builds (except critical security)
- **Actionable** - Clear priority: HIGH > MEDIUM > LOW
- **Incremental** - Focus on changed code, not entire codebase

## See Also

- **Full Plan:** `docs/CODE_QUALITY_TOOLING_PLAN.md`
- **Tool Comparison:** See plan document for detailed analysis
- **Configuration:** See plan document for tool configs
