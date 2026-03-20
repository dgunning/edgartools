# Next-Generation CQS Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the deterministic CQS loop to reach 99%+ pass rate by fixing loop efficiency, diagnosing regressions, adjudicating reference data, adding industry archetypes, and enriching the formula solver — before adding surgical AI agents for the long tail.

**Architecture:** Six tasks implementing Phase 1 (deterministic substrate extensions) in priority order: loop efficiency fixes, regression diff pipeline, reference data adjudication, industry archetype templates, richer formula solver, and then Phase 2 AI agent routing. Each task modifies only Tier 1 config files and the tools/ layer — no changes to the core XBRL parser or orchestrator mapping logic.

**Tech Stack:** Python 3.10+, PyYAML, SQLite (ExperimentLedger), pytest

---

## File Map

| File | Tasks | Responsibility |
|------|-------|----------------|
| `edgar/xbrl/standardization/tools/auto_eval_loop.py` | 1, 2, 6 | Loop efficiency, regression proposals, AI agent routing |
| `edgar/xbrl/standardization/tools/auto_eval.py` | 1, 3 | Gap derivation from CQSResult, reference_disputed gap type |
| `edgar/xbrl/standardization/tools/auto_solver.py` | 5 | Extended formula patterns (sign-flip, scale, 6-component) |
| `edgar/xbrl/standardization/reference_validator.py` | 3 | Trust hierarchy, disputed state detection |
| `edgar/xbrl/standardization/ledger/schema.py` | 2 | Extraction provenance queries for regression diff |
| `edgar/xbrl/standardization/config/industry_metrics.yaml` | 4 | Archetype templates with forbidden/required metrics |
| Tests: `tests/xbrl/standardization/test_next_gen_cqs.py` | 1-6 | All verification for this plan |

---

### Task 1: Loop Efficiency Fixes

**Why:** The overnight run wastes ~36% of time on redundant `identify_gaps()` calls after KEEP decisions. After a KEEP, we already have the new CQSResult — we can derive gaps from it without re-running the full orchestrator (~150s saved per iteration). Also, the proposal cache and graveyard threshold need tuning.

**Files:**
- Modify: `edgar/xbrl/standardization/tools/auto_eval_loop.py` (lines 2063-2070, 2086-2106)
- Modify: `edgar/xbrl/standardization/tools/auto_eval.py` (lines 1006-1098)
- Test: `tests/xbrl/standardization/test_next_gen_cqs.py`

- [ ] **Step 1: Write test for gap derivation from CQSResult**

In `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
"""Tests for next-generation CQS loop improvements."""
import pytest
from unittest.mock import MagicMock, patch
from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult, CompanyCQS, MetricGap, derive_gaps_from_cqs,
)


class TestDeriveGapsFromCQS:
    """Test gap derivation from an existing CQSResult (no orchestrator re-run)."""

    def _make_company_cqs(self, ticker, failed_metrics, **overrides):
        """Helper to construct CompanyCQS with correct positional fields."""
        defaults = dict(
            ticker=ticker, pass_rate=0.8, mean_variance=5.0,
            coverage_rate=1.0, golden_master_rate=0.5,
            regression_count=0, metrics_total=10, metrics_mapped=10,
            metrics_valid=8, metrics_excluded=0, cqs=0.85,
            ef_pass_rate=0.9, sa_pass_rate=0.8, ef_cqs=0.9, sa_cqs=0.8,
            failed_metrics=failed_metrics,
        )
        defaults.update(overrides)
        return CompanyCQS(**defaults)

    def _make_cqs_result(self, company_scores):
        """Helper to construct CQSResult with correct positional fields."""
        return CQSResult(
            pass_rate=0.8, mean_variance=5.0, coverage_rate=1.0,
            golden_master_rate=0.5, regression_rate=0.0, cqs=0.85,
            companies_evaluated=len(company_scores),
            total_metrics=50, total_mapped=45, total_valid=40,
            total_regressions=0,
            company_scores=company_scores, duration_seconds=10.0,
        )

    def test_derive_gaps_returns_gaps_for_failing_metrics(self):
        """Gaps should be derived from company_scores without re-running orchestrator."""
        company_scores = {
            "AAPL": self._make_company_cqs("AAPL", ["Revenue", "COGS"]),
        }
        cqs = self._make_cqs_result(company_scores)

        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 2
        assert {g.metric for g in gaps} == {"Revenue", "COGS"}
        assert all(g.ticker == "AAPL" for g in gaps)

    def test_derive_gaps_respects_dead_ends(self):
        """Dead-end gaps (graveyard >= 6) should be filtered out."""
        company_scores = {
            "AAPL": self._make_company_cqs(
                "AAPL", ["Revenue"],
                metrics_total=5, metrics_mapped=5, metrics_valid=4,
            ),
        }
        cqs = self._make_cqs_result(company_scores)

        graveyard_counts = {"AAPL:Revenue": 7}
        gaps = derive_gaps_from_cqs(cqs, graveyard_counts=graveyard_counts)
        assert len(gaps) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestDeriveGapsFromCQS -v`
Expected: FAIL — `derive_gaps_from_cqs` does not exist yet, `failed_metrics` field missing from CompanyCQS

- [ ] **Step 3: Add `failed_metrics` field to CompanyCQS and populate it**

In `edgar/xbrl/standardization/tools/auto_eval.py`:

**3a.** Add `failed_metrics` to the CompanyCQS dataclass (after line 323, the `explained_variance_count` field):

```python
    failed_metrics: List[str] = field(default_factory=list)  # Metrics that failed validation
```

**3b.** In `_compute_company_cqs()` (line 781), add a `failed_metrics` list after `explained_variance_count = 0` (line 797):

```python
    failed_metrics = []
```

**3c.** In the loop body, after the `regression_count += 1` line (line 815), add tracking for failed metrics. The failed metric check goes at line 812, inside the `elif result.validation_status == "invalid":` block, and also for unmapped metrics:

```python
        # After line 815 (regression_count += 1):
        # Also add after the "elif result.validation_status == "invalid":" check (line 812):
        if result.validation_status == "invalid" or not result.is_mapped:
            failed_metrics.append(metric)
```

Note: Place this AFTER the existing `if result.validation_status == "valid": valid += 1` / `elif result.validation_status == "invalid":` block (around line 816), as a new conditional:

```python
        # Track failed metrics for derive_gaps_from_cqs fast path
        if result.validation_status != "valid" and result.source != MappingSource.CONFIG:
            failed_metrics.append(metric)
```

**3d.** Add `failed_metrics=failed_metrics` to the CompanyCQS constructor call at line 877:

```python
    return CompanyCQS(
        # ... existing fields ...
        explained_variance_count=explained_variance_count,
        failed_metrics=failed_metrics,  # NEW
    )
```

- [ ] **Step 4: Implement `derive_gaps_from_cqs()`**

In `edgar/xbrl/standardization/tools/auto_eval.py`, add after `identify_gaps()`:

```python
def derive_gaps_from_cqs(
    cqs_result: CQSResult,
    graveyard_counts: Dict[str, int],
) -> List[MetricGap]:
    """
    Derive gaps from an existing CQSResult without re-running the orchestrator.

    This is the fast path after a KEEP decision — we already have per-company
    scores and know which metrics failed. ~0s vs ~150s for identify_gaps().

    Args:
        cqs_result: CQSResult with company_scores populated.
        graveyard_counts: Dict of "ticker:metric" -> graveyard count.

    Returns:
        List of MetricGap, sorted by estimated impact (highest first).
    """
    gaps: List[MetricGap] = []

    for ticker, score in cqs_result.company_scores.items():
        company_total = max(score.total, 1)
        per_metric_impact = 0.50 / company_total

        for metric in score.failed_metrics:
            graveyard_key = f"{ticker}:{metric}"
            gc = graveyard_counts.get(graveyard_key, 0)

            gap = MetricGap(
                ticker=ticker,
                metric=metric,
                gap_type="validation_failure",  # Conservative default
                estimated_impact=per_metric_impact,
                graveyard_count=gc,
                notes="Derived from CQSResult (fast path)",
            )
            if not gap.is_dead_end:
                gaps.append(gap)

    gaps.sort(key=lambda g: (-g.estimated_impact, g.graveyard_count))
    return gaps
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestDeriveGapsFromCQS -v`
Expected: PASS

- [ ] **Step 6: Write test for proposal dedup cache**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import ProposalCache


class TestProposalCache:
    """Test in-session proposal dedup cache."""

    def test_cache_blocks_duplicate_proposals(self):
        cache = ProposalCache()
        # First proposal for this gap should be allowed
        assert not cache.was_tried("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")
        cache.record("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")
        # Same proposal should now be blocked
        assert cache.was_tried("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")

    def test_cache_allows_different_proposals_for_same_gap(self):
        cache = ProposalCache()
        cache.record("AAPL", "Revenue", "add_concept:Revenues")
        assert not cache.was_tried("AAPL", "Revenue", "add_concept:SalesRevenueNet")

    def test_cache_allows_same_proposal_for_different_companies(self):
        cache = ProposalCache()
        cache.record("AAPL", "Revenue", "add_concept:Revenues")
        assert not cache.was_tried("MSFT", "Revenue", "add_concept:Revenues")
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestProposalCache -v`
Expected: FAIL — `ProposalCache` does not exist

- [ ] **Step 8: Implement ProposalCache**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`, add after the `_SubtypeFailureTracker` class:

```python
class ProposalCache:
    """
    In-session cache to prevent re-proposing identical changes.

    Tracks (ticker, metric, proposal_key) tuples. Resets each session.
    This avoids wasting evaluation time on proposals that were already
    rejected in the current session.
    """

    def __init__(self):
        self._tried: set = set()

    def was_tried(self, ticker: str, metric: str, proposal_key: str) -> bool:
        return (ticker, metric, proposal_key) in self._tried

    def record(self, ticker: str, metric: str, proposal_key: str):
        self._tried.add((ticker, metric, proposal_key))

    def proposal_key_for(self, change: 'ConfigChange') -> str:
        """Generate a dedup key from a ConfigChange."""
        return f"{change.change_type.value}:{change.new_value}"
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestProposalCache -v`
Expected: PASS

- [ ] **Step 10: Integrate efficiency fixes into `run_overnight()`**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`, modify `run_overnight()`:

**10a.** After the `_SubtypeFailureTracker` initialization (line ~2040), add:
```python
proposal_cache = ProposalCache()
```

**10b.** After a KEEP decision (line ~2145-2159), instead of always calling `identify_gaps()`, use the fast path:
```python
# After KEEP: derive gaps from the new CQSResult (fast path)
# instead of re-running identify_gaps() (~150s savings)
if result.new_cqs_result is not None:
    current_baseline = result.new_cqs_result
    graveyard_counts = _get_graveyard_counts(ledger)
    gaps = derive_gaps_from_cqs(current_baseline, graveyard_counts)
    # Apply focus filter if needed
    if focus_area:
        gaps = _filter_gaps_by_focus(gaps, focus_area)
else:
    # Fallback to full identify_gaps() if no CQSResult available
    gaps, current_baseline = identify_gaps(...)
```

**10c.** Before calling `propose_fn()` (line ~2103), add dedup check:
```python
change = propose_fn(gap, ledger.get_graveyard_entries(gap.metric))
if change is not None:
    pkey = proposal_cache.proposal_key_for(change)
    if proposal_cache.was_tried(gap.ticker, gap.metric, pkey):
        logger.debug(f"Skipping duplicate proposal: {gap.ticker}:{gap.metric} {pkey}")
        null_proposals += 1
        continue
    proposal_cache.record(gap.ticker, gap.metric, pkey)
```

- [ ] **Step 11: Add import for `derive_gaps_from_cqs` in auto_eval_loop.py**

Update the imports at the top of `auto_eval_loop.py`:
```python
from edgar.xbrl.standardization.tools.auto_eval import (
    # ... existing imports ...
    derive_gaps_from_cqs,
    _get_graveyard_counts,
)
```

- [ ] **Step 12: Run full test suite to verify no regressions**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/ -v -x -q`
Expected: All existing tests PASS

- [ ] **Step 13: Commit**

```bash
git add tests/xbrl/standardization/test_next_gen_cqs.py \
  edgar/xbrl/standardization/tools/auto_eval.py \
  edgar/xbrl/standardization/tools/auto_eval_loop.py
git commit -m "feat: loop efficiency — derive gaps from CQSResult + proposal dedup cache

After KEEP decisions, derive gaps from the existing CQSResult instead of
re-running the full orchestrator (~150s saved per iteration). Add ProposalCache
to skip proposals identical to already-rejected ones in the current session."
```

---

### Task 2: Regression Diff Pipeline

**Why:** 10 pre-existing regressions block all progress. The `propose_change()` function returns `None` for regressions. We need a provenance diff that compares the golden master's original extraction run against the current run to diagnose WHY it regressed.

**Files:**
- Modify: `edgar/xbrl/standardization/ledger/schema.py` (add provenance query)
- Modify: `edgar/xbrl/standardization/tools/auto_eval_loop.py` (add `_propose_regression_fix()`)
- Test: `tests/xbrl/standardization/test_next_gen_cqs.py`

- [ ] **Step 1: Write test for RegressionDiagnosis dataclass**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    RegressionDiagnosis, diagnose_regression,
)


class TestRegressionDiagnosis:
    """Test regression provenance diff pipeline."""

    def test_diagnosis_identifies_concept_change(self):
        """When the selected concept changed between golden and current, flag it."""
        diag = RegressionDiagnosis(
            ticker="CAT",
            metric="Capex",
            golden_concept="PaymentsToAcquirePropertyPlantAndEquipment",
            current_concept="PaymentsToAcquireProductiveAssets",
            golden_value=5_000_000_000,
            current_value=3_200_000_000,
            reference_value=5_100_000_000,
            diagnosis_type="concept_changed",
        )
        assert diag.diagnosis_type == "concept_changed"
        assert diag.has_actionable_fix

    def test_diagnosis_identifies_reference_changed(self):
        """When yfinance reference value changed but extraction is stable."""
        diag = RegressionDiagnosis(
            ticker="D",
            metric="ShortTermDebt",
            golden_concept="ShortTermBorrowings",
            current_concept="ShortTermBorrowings",
            golden_value=2_000_000_000,
            current_value=2_000_000_000,
            reference_value=1_500_000_000,
            golden_reference_value=2_050_000_000,
            diagnosis_type="reference_changed",
        )
        assert diag.diagnosis_type == "reference_changed"
        assert diag.has_actionable_fix
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestRegressionDiagnosis -v`
Expected: FAIL — `RegressionDiagnosis` does not exist

- [ ] **Step 3: Implement RegressionDiagnosis dataclass**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`, add after the `ExperimentDecision` dataclass:

```python
@dataclass
class RegressionDiagnosis:
    """
    Provenance diff for a regressed golden master.

    Compares the golden master's original extraction context against
    the current extraction to identify what changed.
    """
    ticker: str
    metric: str
    golden_concept: Optional[str] = None     # Concept used when golden was created
    current_concept: Optional[str] = None     # Concept used now
    golden_value: Optional[float] = None      # Value when golden was created
    current_value: Optional[float] = None     # Value now
    reference_value: Optional[float] = None   # Current yfinance reference
    golden_reference_value: Optional[float] = None  # Reference when golden was created (if known)
    diagnosis_type: str = "unknown"
    # Types: "concept_changed", "reference_changed", "value_drifted",
    #        "period_changed", "filing_changed", "unknown"
    notes: str = ""

    @property
    def has_actionable_fix(self) -> bool:
        """Whether this diagnosis suggests an automated fix."""
        return self.diagnosis_type in (
            "concept_changed",    # Can revert concept or update golden
            "reference_changed",  # Can add divergence or update golden
            "value_drifted",      # Can add divergence tolerance
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestRegressionDiagnosis -v`
Expected: PASS

- [ ] **Step 5: Add provenance query to ExperimentLedger**

In `edgar/xbrl/standardization/ledger/schema.py`, add a method to `ExperimentLedger`:

```python
def get_golden_extraction_context(
    self,
    ticker: str,
    metric: str,
) -> Optional[Dict[str, Any]]:
    """
    Get the extraction context from when the golden master was created.

    Returns dict with: concept, value, reference_value, fiscal_period,
    strategy_name, run_timestamp, variance_pct.
    """
    with self._connect() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find the golden master
        cursor.execute('''
            SELECT * FROM golden_masters
            WHERE ticker = ? AND metric = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        ''', (ticker, metric))
        gm = cursor.fetchone()
        if gm is None:
            return None

        # Find the extraction run closest to golden master creation
        cursor.execute('''
            SELECT * FROM extraction_runs
            WHERE ticker = ? AND metric = ? AND is_valid = 1
            ORDER BY ABS(julianday(run_timestamp) - julianday(?))
            LIMIT 1
        ''', (ticker, metric, gm['created_at']))
        run = cursor.fetchone()
        if run is None:
            return None

        return {
            "concept": run['strategy_name'] or '',
            "value": run['extracted_value'],
            "reference_value": run['reference_value'],
            "fiscal_period": run['fiscal_period'],
            "strategy_name": run['strategy_name'] or '',
            "run_timestamp": run['run_timestamp'],
            "variance_pct": run['variance_pct'],
        }
```

- [ ] **Step 6: Implement `diagnose_regression()`**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`:

```python
def diagnose_regression(
    ticker: str,
    metric: str,
    current_validation,
    ledger: ExperimentLedger,
) -> RegressionDiagnosis:
    """
    Build a provenance diff for a regressed metric.

    Compares golden master extraction context against current extraction
    to identify what changed. Pure data comparison, no AI.
    """
    golden_ctx = ledger.get_golden_extraction_context(ticker, metric)

    current_concept = None
    current_value = None
    ref_value = None

    if current_validation:
        current_value = current_validation.xbrl_value
        ref_value = current_validation.reference_value
        if hasattr(current_validation, 'components_used') and current_validation.components_used:
            current_concept = current_validation.components_used[0] if current_validation.components_used else None

    if golden_ctx is None:
        return RegressionDiagnosis(
            ticker=ticker, metric=metric,
            current_concept=current_concept,
            current_value=current_value,
            reference_value=ref_value,
            diagnosis_type="unknown",
            notes="No golden extraction context found in ledger",
        )

    golden_concept = golden_ctx.get("concept")
    golden_value = golden_ctx.get("value")
    golden_ref = golden_ctx.get("reference_value")

    # Determine what changed
    diagnosis_type = "unknown"

    # Case 1: Concept selection changed
    if golden_concept and current_concept and golden_concept != current_concept:
        diagnosis_type = "concept_changed"

    # Case 2: Reference value changed (our extraction is stable)
    elif (golden_ref and ref_value and golden_value and current_value
          and abs(golden_value - current_value) / max(abs(golden_value), 1) < 0.05
          and abs(golden_ref - ref_value) / max(abs(golden_ref), 1) > 0.10):
        diagnosis_type = "reference_changed"

    # Case 3: Extracted value drifted (different filing or period)
    elif golden_value and current_value:
        drift_pct = abs(golden_value - current_value) / max(abs(golden_value), 1) * 100
        if drift_pct > 10:
            diagnosis_type = "value_drifted"

    return RegressionDiagnosis(
        ticker=ticker, metric=metric,
        golden_concept=golden_concept,
        current_concept=current_concept,
        golden_value=golden_value,
        current_value=current_value,
        reference_value=ref_value,
        golden_reference_value=golden_ref,
        diagnosis_type=diagnosis_type,
    )
```

- [ ] **Step 7: Implement `_propose_regression_fix()`**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`, replace the regression branch in `propose_change()` (line ~1101-1104):

```python
elif gap.gap_type == "regression":
    return _propose_regression_fix(gap, config_dir)
```

And add the function:

```python
def _propose_regression_fix(
    gap: MetricGap,
    config_dir: Path,
) -> Optional[ConfigChange]:
    """
    Propose a fix for a regressed golden master.

    Uses provenance diff to determine the right fix:
    - concept_changed → revert to golden concept via company_override
    - reference_changed → add known_divergence
    - value_drifted → add known_divergence with tolerance
    """
    ledger = ExperimentLedger()
    diag = diagnose_regression(gap.ticker, gap.metric, gap.extraction_evidence, ledger)

    if not diag.has_actionable_fix:
        logger.warning(
            f"Regression {gap.ticker}:{gap.metric} diagnosed as '{diag.diagnosis_type}' "
            f"— no automated fix available"
        )
        return None

    if diag.diagnosis_type == "concept_changed" and diag.golden_concept:
        # Revert to the concept that was working
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_COMPANY_OVERRIDE,
            yaml_path=f"companies.{gap.ticker}.metric_overrides.{gap.metric}",
            new_value={
                "preferred_concept": diag.golden_concept,
                "notes": f"Regression fix: reverted from {diag.current_concept} to golden concept",
            },
            rationale=f"Regression: concept changed from {diag.golden_concept} to {diag.current_concept}",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    if diag.diagnosis_type == "reference_changed":
        # yfinance value changed — add divergence tolerance
        variance = None
        if diag.current_value and diag.reference_value and diag.reference_value != 0:
            variance = abs(diag.current_value - diag.reference_value) / abs(diag.reference_value) * 100

        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path=f"companies.{gap.ticker}.known_divergences.{gap.metric}",
            new_value={
                "form_types": ["10-K"],
                "variance_pct": round(variance * 1.5, 1) if variance else 25.0,
                "reason": f"Reference value changed: golden_ref={diag.golden_reference_value}, current_ref={diag.reference_value}",
                "skip_validation": False,
            },
            rationale=f"Regression: yfinance reference changed, extraction stable at {diag.current_value}",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    if diag.diagnosis_type == "value_drifted":
        # Extraction value changed — likely new filing period
        variance = gap.current_variance or 25.0
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path=f"companies.{gap.ticker}.known_divergences.{gap.metric}",
            new_value={
                "form_types": ["10-K"],
                "variance_pct": round(abs(variance) * 1.5, 1),
                "reason": f"Value drifted: golden={diag.golden_value}, current={diag.current_value}",
                "skip_validation": False,
            },
            rationale=f"Regression: extracted value drifted from golden",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    return None
```

- [ ] **Step 8: Write test for diagnose_regression() with mocked ledger**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
class TestDiagnoseRegression:
    """Test diagnose_regression() with mocked ledger data."""

    def test_diagnose_concept_changed(self):
        """diagnose_regression detects when the selected concept changed."""
        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = {
            "concept": "PaymentsToAcquirePropertyPlantAndEquipment",
            "value": 5_000_000_000,
            "reference_value": 5_100_000_000,
            "fiscal_period": "2024-FY",
            "strategy_name": "PaymentsToAcquirePropertyPlantAndEquipment",
            "run_timestamp": "2025-01-01T00:00:00",
            "variance_pct": 2.0,
        }

        mock_validation = MagicMock()
        mock_validation.xbrl_value = 3_200_000_000
        mock_validation.reference_value = 5_100_000_000
        mock_validation.components_used = ["PaymentsToAcquireProductiveAssets"]

        diag = diagnose_regression("CAT", "Capex", mock_validation, mock_ledger)
        assert diag.diagnosis_type == "concept_changed"
        assert diag.golden_concept == "PaymentsToAcquirePropertyPlantAndEquipment"

    def test_diagnose_unknown_when_no_golden_context(self):
        """Returns unknown when no golden extraction context exists."""
        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = None

        diag = diagnose_regression("CAT", "Capex", None, mock_ledger)
        assert diag.diagnosis_type == "unknown"
```

- [ ] **Step 9: Run all tests**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add tests/xbrl/standardization/test_next_gen_cqs.py \
  edgar/xbrl/standardization/tools/auto_eval_loop.py \
  edgar/xbrl/standardization/ledger/schema.py
git commit -m "feat: regression diff pipeline — diagnose and auto-fix golden master regressions

Add RegressionDiagnosis dataclass and diagnose_regression() to compare golden
master provenance against current extraction. propose_change() now generates
fixes for regressions: concept_changed -> revert via override, reference_changed
-> add divergence tolerance, value_drifted -> add divergence."
```

---

### Task 3: Reference Data Adjudication

**Why:** The system treats yfinance as ground truth. When yfinance is wrong, our correct extraction fails validation. Adding a trust hierarchy and `reference_disputed` gap type stops penalizing correct extractions.

**Files:**
- Modify: `edgar/xbrl/standardization/reference_validator.py` (trust hierarchy)
- Modify: `edgar/xbrl/standardization/tools/auto_eval.py` (reference_disputed gap type)
- Test: `tests/xbrl/standardization/test_next_gen_cqs.py`

- [ ] **Step 1: Write test for reference trust hierarchy**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
from edgar.xbrl.standardization.reference_validator import (
    ReferenceAdjudicator, ReferenceVerdict,
)


class TestReferenceAdjudication:
    """Test the reference data trust hierarchy."""

    def test_verdict_trusted_when_sources_agree(self):
        """When XBRL and yfinance agree, verdict is trusted."""
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=394_328_000_000,
            reference_value=394_328_000_000,
            golden_value=None,
            metric="Revenue",
            ticker="AAPL",
        )
        assert verdict.status == "trusted"
        assert verdict.reference_value == 394_328_000_000

    def test_verdict_disputed_when_xbrl_matches_golden_but_not_ref(self):
        """When XBRL matches golden master but not yfinance, mark disputed."""
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=5_000_000_000,
            reference_value=3_500_000_000,
            golden_value=5_100_000_000,
            metric="ShortTermDebt",
            ticker="D",
        )
        assert verdict.status == "reference_disputed"
        assert verdict.trust_source == "golden_master"

    def test_verdict_uses_reference_when_no_golden(self):
        """Without golden master, yfinance is the default reference."""
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=5_000_000_000,
            reference_value=3_500_000_000,
            golden_value=None,
            metric="ShortTermDebt",
            ticker="D",
        )
        assert verdict.status == "mismatch"
        assert verdict.trust_source == "yfinance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestReferenceAdjudication -v`
Expected: FAIL — `ReferenceAdjudicator` does not exist

- [ ] **Step 3: Implement ReferenceAdjudicator**

In `edgar/xbrl/standardization/reference_validator.py`, add:

```python
@dataclass
class ReferenceVerdict:
    """Result of adjudicating between reference sources."""
    status: str              # "trusted", "reference_disputed", "mismatch", "missing"
    reference_value: Optional[float]
    trust_source: str        # "xbrl", "golden_master", "yfinance", "none"
    notes: str = ""


class ReferenceAdjudicator:
    """
    Deterministic trust hierarchy for reference data.

    Priority:
    1. SEC XBRL filing (primary source — what we extracted)
    2. Prior stable golden master value
    3. yfinance snapshot (check freshness/staleness)

    When XBRL matches golden but not yfinance, the reference is "disputed"
    and excluded from pass rate (but flagged for review).
    """

    def __init__(self, tolerance_pct: float = 15.0):
        self.tolerance_pct = tolerance_pct

    def adjudicate(
        self,
        xbrl_value: Optional[float],
        reference_value: Optional[float],
        golden_value: Optional[float],
        metric: str,
        ticker: str,
    ) -> ReferenceVerdict:
        """
        Adjudicate between XBRL extraction, golden master, and yfinance.

        Returns ReferenceVerdict with the trusted value and status.
        """
        if xbrl_value is None:
            return ReferenceVerdict(
                status="missing", reference_value=reference_value,
                trust_source="none", notes="No XBRL value extracted",
            )

        if reference_value is None:
            return ReferenceVerdict(
                status="missing", reference_value=None,
                trust_source="none", notes="No reference value available",
            )

        # Check if XBRL matches yfinance (within tolerance)
        xbrl_ref_var = abs(xbrl_value - reference_value) / max(abs(reference_value), 1) * 100
        if xbrl_ref_var <= self.tolerance_pct:
            return ReferenceVerdict(
                status="trusted", reference_value=reference_value,
                trust_source="yfinance",
                notes=f"XBRL matches yfinance ({xbrl_ref_var:.1f}% variance)",
            )

        # XBRL doesn't match yfinance — check golden master
        if golden_value is not None:
            xbrl_golden_var = abs(xbrl_value - golden_value) / max(abs(golden_value), 1) * 100
            if xbrl_golden_var <= self.tolerance_pct:
                # XBRL matches golden but not yfinance — disputed reference
                return ReferenceVerdict(
                    status="reference_disputed",
                    reference_value=golden_value,
                    trust_source="golden_master",
                    notes=(
                        f"XBRL matches golden master ({xbrl_golden_var:.1f}%) "
                        f"but not yfinance ({xbrl_ref_var:.1f}%). "
                        f"yfinance may be stale or wrong."
                    ),
                )

        # No golden to fall back on — trust yfinance
        return ReferenceVerdict(
            status="mismatch", reference_value=reference_value,
            trust_source="yfinance",
            notes=f"XBRL vs yfinance variance: {xbrl_ref_var:.1f}%",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestReferenceAdjudication -v`
Expected: PASS

- [ ] **Step 5: Add `reference_disputed` gap type to _classify_gap()**

In `edgar/xbrl/standardization/tools/auto_eval.py`, in `_classify_gap()` (around line 1153), add after the `hv_reference_suspect` subtype detection but before the general high_variance return:

```python
# Reference disputed: XBRL likely correct but yfinance disagrees
# This is detected via hv_subtype "hv_reference_suspect" — promote to gap type
if hv_subtype == "hv_reference_suspect":
    return MetricGap(
        ticker=ticker, metric=metric, gap_type="reference_disputed",
        estimated_impact=per_metric_impact * 0.1,  # Low priority — likely correct
        current_variance=variance, reference_value=ref_val,
        xbrl_value=xbrl_val, graveyard_count=gc,
        notes=f"Reference suspect: yfinance ref={ref_val} may be stale",
        extraction_evidence=evidence,
        hv_subtype="hv_reference_suspect",
        root_cause="reference_error",
    )
```

- [ ] **Step 6: Update `_compute_company_cqs()` to exclude disputed metrics**

In `edgar/xbrl/standardization/tools/auto_eval.py`:

**6a.** Add `disputed_count` field to CompanyCQS (after `explained_variance_count`):
```python
    disputed_count: int = 0  # Metrics excluded due to reference_disputed
```

**6b.** In `_compute_company_cqs()`, add `disputed_count = 0` after `explained_variance_count = 0` (line 797).

**6c.** In the loop body (after the variance collection block, around line 820), detect reference_suspect:
```python
        # Detect reference_disputed — exclude from pass/fail
        if val_result and hasattr(val_result, 'notes') and val_result.notes:
            if 'reference suspect' in (val_result.notes or '').lower():
                disputed_count += 1
```

**6d.** When computing pass_rate (line 839), subtract disputed from total:
```python
    effective_total = total - disputed_count
    pass_rate = valid / effective_total if effective_total > 0 else 0.0
    coverage_rate = mapped / effective_total if effective_total > 0 else 0.0
```

**6e.** Add `disputed_count=disputed_count` to the CompanyCQS constructor.

- [ ] **Step 7: Run full test suite**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/ -v -x -q`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add edgar/xbrl/standardization/reference_validator.py \
  edgar/xbrl/standardization/tools/auto_eval.py \
  tests/xbrl/standardization/test_next_gen_cqs.py
git commit -m "feat: reference adjudication — trust hierarchy and reference_disputed gap type

Add ReferenceAdjudicator with deterministic trust hierarchy: XBRL > golden
master > yfinance. When XBRL matches golden but not yfinance, mark as
reference_disputed and exclude from pass rate. Prevents penalizing correct
extractions when yfinance is stale or wrong."
```

---

### Task 4: Industry Archetype Templates

**Why:** The system handles industries ad-hoc via `industry_metrics.yaml`. No structured archetype system defines forbidden metrics, required alternatives, or default concept routing per industry. This causes structural gaps at scale.

**Files:**
- Modify: `edgar/xbrl/standardization/config/industry_metrics.yaml`
- Modify: `edgar/xbrl/standardization/tools/auto_eval_loop.py` (archetype-aware proposals)
- Test: `tests/xbrl/standardization/test_next_gen_cqs.py`

- [ ] **Step 1: Write test for industry archetype config parsing**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
import yaml
from pathlib import Path


class TestIndustryArchetypes:
    """Test industry archetype template structure in industry_metrics.yaml."""

    def test_banking_has_forbidden_metrics(self):
        """Banking archetype should forbid standard industrial metrics."""
        config_path = Path(__file__).resolve().parents[3] / "edgar/xbrl/standardization/config/industry_metrics.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        banking = config.get("banking", {})
        forbidden = banking.get("forbidden_metrics", [])
        assert "Inventory" in forbidden, "Banking should forbid Inventory"
        assert "COGS" in forbidden, "Banking should forbid COGS (banks use InterestExpense)"

    def test_reit_has_required_alternatives(self):
        """REIT archetype should define required alternative metrics."""
        config_path = Path(__file__).resolve().parents[3] / "edgar/xbrl/standardization/config/industry_metrics.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        reits = config.get("reits", {})
        required = reits.get("required_alternatives", {})
        # REITs should have FFO as alternative for NetIncome analysis
        assert "FFO" in required or len(required) > 0

    def test_archetype_has_sic_mapping(self):
        """Each archetype should have SIC range mapping."""
        config_path = Path(__file__).resolve().parents[3] / "edgar/xbrl/standardization/config/industry_metrics.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        for archetype_name in ["banking", "insurance", "reits"]:
            archetype = config.get(archetype_name, {})
            assert "sic_ranges" in archetype, f"{archetype_name} missing sic_ranges"
```

- [ ] **Step 2: Run test to verify initial state**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestIndustryArchetypes -v`
Expected: FAIL on `forbidden_metrics` assertions

- [ ] **Step 3: Expand industry_metrics.yaml with archetype structure**

Add `forbidden_metrics`, `required_alternatives`, and `default_concept_routing` to each archetype in `edgar/xbrl/standardization/config/industry_metrics.yaml`:

```yaml
banking:
  sic_ranges: [[6020, 6099]]

  # Metrics that don't apply to banks — auto-exclude for banking companies
  forbidden_metrics:
    - COGS          # Banks don't have cost of goods sold
    - Inventory     # Banks don't hold inventory
    - GrossProfit   # Replaced by NetInterestIncome
    - Capex         # Minimal/different for banks

  # Metrics that banks use instead of standard ones
  required_alternatives:
    InterestExpense:
      replaces: COGS
      notes: "Bank raw material cost is interest paid to depositors"
    NetInterestIncome:
      replaces: GrossProfit
      notes: "InterestIncome - InterestExpense"
    PPNR:
      replaces: OperatingIncome
      notes: "Pre-Provision Net Revenue"

  concept_mapping:
    # ... existing mappings stay as-is ...
```

Similarly for insurance and reits:

```yaml
insurance:
  sic_ranges: [[6300, 6399]]
  forbidden_metrics:
    - COGS
    - Inventory
    - GrossProfit
  required_alternatives:
    LossesAndAdjustments:
      replaces: COGS
    UnderwritingIncome:
      replaces: OperatingIncome
  concept_mapping:
    # ... existing ...

reits:
  sic_ranges: [[6500, 6553], [6798, 6798]]
  forbidden_metrics:
    - COGS
    - Inventory
  required_alternatives:
    FFO:
      replaces: NetIncome
      notes: "Funds From Operations — excludes depreciation (phantom expense for RE)"
    NOI:
      replaces: OperatingIncome
      notes: "Net Operating Income"
  concept_mapping:
    # ... existing ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestIndustryArchetypes -v`
Expected: PASS

- [ ] **Step 5: Add archetype-aware exclusion proposal in propose_change()**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`, update `_propose_for_unmapped()` to check if the metric is forbidden for the company's industry:

```python
def _is_metric_forbidden(metric: str, ticker: str, config_dir: Path) -> bool:
    """Check if metric is forbidden by the company's industry archetype."""
    industry_path = config_dir / "industry_metrics.yaml"
    companies_path = config_dir / "companies.yaml"

    if not industry_path.exists() or not companies_path.exists():
        return False

    with open(companies_path) as f:
        companies = yaml.safe_load(f) or {}
    with open(industry_path) as f:
        industry_config = yaml.safe_load(f) or {}

    company = companies.get("companies", {}).get(ticker, {})
    industry = company.get("industry", "").lower()

    if not industry:
        return False

    archetype = industry_config.get(industry, {})
    forbidden = archetype.get("forbidden_metrics", [])
    return metric in forbidden
```

Then in `_propose_for_unmapped()`, before generating concept variations:
```python
# Check if metric is forbidden by industry archetype
if _is_metric_forbidden(gap.metric, gap.ticker, config_dir):
    return ConfigChange(
        file="companies.yaml",
        change_type=ChangeType.ADD_EXCLUSION,
        yaml_path=f"companies.{gap.ticker}.exclude_metrics",
        new_value=gap.metric,
        rationale=f"{gap.metric} is forbidden for {gap.ticker}'s industry archetype",
        target_metric=gap.metric,
        target_companies=gap.ticker,
    )
```

- [ ] **Step 6: Run full test suite**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/ -v -x -q`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add edgar/xbrl/standardization/config/industry_metrics.yaml \
  edgar/xbrl/standardization/tools/auto_eval_loop.py \
  tests/xbrl/standardization/test_next_gen_cqs.py
git commit -m "feat: industry archetype templates with forbidden/required metrics

Define forbidden_metrics and required_alternatives for banking, insurance,
and REIT archetypes. Auto-exclude forbidden metrics when proposing fixes
for companies in these industries."
```

---

### Task 5: Richer Formula Solver

**Why:** The subset-sum solver is capped at 4 components and 50 candidates. It can't find complex formulas involving sign-flips, scale normalization, or additive/subtractive groups. Extending the solver unlocks more formula discoveries.

**Files:**
- Modify: `edgar/xbrl/standardization/tools/auto_solver.py`
- Test: `tests/xbrl/standardization/test_next_gen_cqs.py`

- [ ] **Step 1: Write test for sign-flip candidate detection**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
from edgar.xbrl.standardization.tools.auto_solver import AutoSolver, FormulaCandidate


class TestRicherSolver:
    """Test extended formula solver capabilities."""

    def test_sign_flip_detection(self):
        """Solver should find formulas involving subtraction (A - B)."""
        solver = AutoSolver(max_components=4, allow_subtraction=True)

        # Target: 100, Facts: A=150, B=50 → A - B = 100
        facts = {"ConceptA": 150.0, "ConceptB": 50.0}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=100.0,
            xbrl_facts=facts,
        )
        # Should find ConceptA - ConceptB = 100
        assert len(candidates) >= 1
        found_subtraction = any(
            len(c.components) == 2 and abs(c.variance_pct) < 1.0
            for c in candidates
        )
        assert found_subtraction

    def test_scale_normalization(self):
        """Solver should detect scale mismatches (millions vs thousands)."""
        solver = AutoSolver(max_components=4, allow_scale_search=True)

        # Target: 5,000,000, Facts: A=5000 (in thousands)
        facts = {"ConceptA": 5000.0}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=5_000_000.0,
            xbrl_facts=facts,
        )
        # Should find ConceptA * 1000 = 5,000,000
        assert len(candidates) >= 1

    def test_increased_component_cap(self):
        """Solver should support up to 6 components for specific metrics."""
        solver = AutoSolver(max_components=6)

        # 6 facts that sum to target
        target = 600.0
        facts = {f"C{i}": 100.0 for i in range(6)}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=target,
            xbrl_facts=facts,
        )
        assert any(len(c.components) == 6 for c in candidates)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestRicherSolver -v`
Expected: FAIL — `allow_subtraction` and `allow_scale_search` params don't exist

- [ ] **Step 3: Extend AutoSolver.__init__ with new parameters**

In `edgar/xbrl/standardization/tools/auto_solver.py`, update `__init__`:

```python
def __init__(
    self,
    max_components: int = 4,
    search_tolerance_pct: float = 1.0,
    snapshot_mode: bool = True,
    allow_subtraction: bool = False,
    allow_scale_search: bool = False,
):
    self.max_components = max_components
    self.search_tolerance = search_tolerance_pct / 100.0
    self.snapshot_mode = snapshot_mode
    self.allow_subtraction = allow_subtraction
    self.allow_scale_search = allow_scale_search
```

- [ ] **Step 4: Add subtraction search to solve_metric()**

Insert BEFORE `results.sort(...)` at line 265 (after the additive loop ending at line 262, but before the sort):

```python
# Phase C: Subtraction search (A - B, A + B - C, etc.)
if self.allow_subtraction and len(concept_list) >= 2:
    for size in range(2, min(self.max_components + 1, len(concept_list) + 1)):
        for combo_indices in combinations(range(len(concept_list)), size):
            # Try all possible sign assignments (at least one negative)
            combo_concepts = [concept_list[i] for i in combo_indices]
            combo_values = [value_list[i] for i in combo_indices]

            # For each combo, try subtracting each single element
            for neg_idx in range(len(combo_values)):
                signed_values = list(combo_values)
                signed_values[neg_idx] = -signed_values[neg_idx]
                combo_sum = sum(signed_values)

                if target != 0:
                    variance = abs(combo_sum - target) / target
                else:
                    variance = 0

                if variance <= self.search_tolerance:
                    results.append(FormulaCandidate(
                        metric=metric,
                        ticker=ticker,
                        components=combo_concepts,
                        values=signed_values,
                        total=combo_sum,
                        target=target,
                        variance_pct=variance * 100,
                        statement_family=self._get_statement_family(metric),
                    ))
```

- [ ] **Step 5: Add scale search to solve_metric()**

Insert after the subtraction search block, still BEFORE `results.sort(...)`:

```python
# Phase D: Scale normalization search
if self.allow_scale_search:
    scale_factors = [1000, 1_000_000, 0.001, 0.000001]
    for concept, value in candidates.items():
        for scale in scale_factors:
            scaled = value * scale
            if target != 0:
                variance = abs(scaled - target) / target
            else:
                variance = 0
            if variance <= self.search_tolerance:
                results.append(FormulaCandidate(
                    metric=metric,
                    ticker=ticker,
                    components=[concept],
                    values=[scaled],
                    total=scaled,
                    target=target,
                    variance_pct=variance * 100,
                    statement_family=self._get_statement_family(metric),
                ))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestRicherSolver -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/ -v -x -q`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add edgar/xbrl/standardization/tools/auto_solver.py \
  tests/xbrl/standardization/test_next_gen_cqs.py
git commit -m "feat: richer formula solver — subtraction search, scale normalization, 6-component cap

Extend AutoSolver with allow_subtraction (A - B formulas), allow_scale_search
(detects millions vs thousands mismatches), and support for up to 6 components.
These are opt-in via constructor parameters to avoid breaking existing behavior."
```

---

### Task 6: AI Agent Routing Infrastructure (Phase 2A scaffold)

**Why:** After Phase 1 plateaus, we need infrastructure to route hard gaps to specialized AI agents. This task builds the routing table and agent protocol — not the AI calls themselves, just the dispatch framework that integrates with the existing propose → evaluate → keep/revert loop.

**Files:**
- Modify: `edgar/xbrl/standardization/tools/auto_eval_loop.py`
- Test: `tests/xbrl/standardization/test_next_gen_cqs.py`

- [ ] **Step 1: Write test for AI agent routing**

Add to `tests/xbrl/standardization/test_next_gen_cqs.py`:

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    AIAgentRouter, AIAgentType,
)


class TestAIAgentRouter:
    """Test AI agent routing infrastructure."""

    def test_regression_routes_to_investigator(self):
        """Regression gaps should route to the Regression Investigator agent."""
        router = AIAgentRouter()
        gap = MetricGap(
            ticker="CAT", metric="Capex", gap_type="regression",
            estimated_impact=0.05, graveyard_count=3,
        )
        agent = router.route(gap)
        assert agent == AIAgentType.REGRESSION_INVESTIGATOR

    def test_reference_suspect_routes_to_auditor(self):
        """Reference suspect gaps should route to the Reference Auditor agent."""
        router = AIAgentRouter()
        gap = MetricGap(
            ticker="D", metric="ShortTermDebt", gap_type="high_variance",
            estimated_impact=0.03, graveyard_count=4,
            hv_subtype="hv_reference_suspect",
        )
        agent = router.route(gap)
        assert agent == AIAgentType.REFERENCE_AUDITOR

    def test_solver_exhaustion_routes_to_semantic_mapper(self):
        """Gaps that exhausted the solver should route to Semantic Mapper."""
        router = AIAgentRouter()
        gap = MetricGap(
            ticker="ABBV", metric="DepreciationAmortization",
            gap_type="validation_failure",
            estimated_impact=0.03, graveyard_count=5,
        )
        agent = router.route(gap)
        assert agent == AIAgentType.SEMANTIC_MAPPER

    def test_cross_company_pattern_routes_to_pattern_learner(self):
        """Gaps failing across 3+ companies should route to Pattern Learner."""
        router = AIAgentRouter()
        # Simulate cross-company pattern
        agent = router.route_cross_company(
            metric="IntangibleAssets",
            failing_tickers=["AMZN", "NVDA", "CRM"],
            industry="Technology",
        )
        assert agent == AIAgentType.PATTERN_LEARNER

    def test_simple_gap_returns_none(self):
        """Simple gaps that deterministic solver can handle should not route to AI."""
        router = AIAgentRouter()
        gap = MetricGap(
            ticker="AAPL", metric="Revenue", gap_type="unmapped",
            estimated_impact=0.05, graveyard_count=0,
        )
        agent = router.route(gap)
        assert agent is None  # Deterministic solver handles this
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestAIAgentRouter -v`
Expected: FAIL — `AIAgentRouter` and `AIAgentType` don't exist

- [ ] **Step 3: Implement AIAgentType enum and AIAgentRouter**

In `edgar/xbrl/standardization/tools/auto_eval_loop.py`:

```python
class AIAgentType(str, Enum):
    """Specialized AI agents for the long-tail gaps."""
    REGRESSION_INVESTIGATOR = "regression_investigator"
    REFERENCE_AUDITOR = "reference_auditor"
    SEMANTIC_MAPPER = "semantic_mapper"
    PATTERN_LEARNER = "pattern_learner"


class AIAgentRouter:
    """
    Routes hard gaps to specialized AI agents.

    Key invariant: AI proposals go through evaluate_experiment() with the
    same CQS gate as deterministic proposals. AI never bypasses the gate.

    Routing rules:
    - regression + high graveyard -> Regression Investigator
    - hv_reference_suspect -> Reference Auditor
    - solver exhaustion (graveyard >= 4) -> Semantic Mapper
    - cross-company pattern (3+ tickers) -> Pattern Learner
    - simple gaps (graveyard < 3) -> None (deterministic solver handles)
    """

    # Minimum graveyard count before AI is invoked
    MIN_GRAVEYARD_FOR_AI = 3

    def route(self, gap: MetricGap) -> Optional[AIAgentType]:
        """
        Route a single gap to the appropriate AI agent.

        Returns None if the gap should be handled deterministically.
        """
        # Only invoke AI for gaps that have exhausted deterministic approaches
        if gap.graveyard_count < self.MIN_GRAVEYARD_FOR_AI:
            return None

        if gap.gap_type == "regression":
            return AIAgentType.REGRESSION_INVESTIGATOR

        if gap.hv_subtype == "hv_reference_suspect":
            return AIAgentType.REFERENCE_AUDITOR

        if gap.gap_type in ("validation_failure", "high_variance"):
            return AIAgentType.SEMANTIC_MAPPER

        return None

    def route_cross_company(
        self,
        metric: str,
        failing_tickers: List[str],
        industry: Optional[str] = None,
    ) -> Optional[AIAgentType]:
        """Route a cross-company pattern to Pattern Learner."""
        if len(failing_tickers) >= 3:
            return AIAgentType.PATTERN_LEARNER
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py::TestAIAgentRouter -v`
Expected: PASS

- [ ] **Step 5: Add `source` field to ConfigChange for AI provenance tracking**

In `auto_eval_loop.py`, add to the `ConfigChange` dataclass:

```python
@dataclass
class ConfigChange:
    # ... existing fields ...
    source: str = "deterministic"   # "deterministic" | "ai_agent"
    ai_agent_type: str = ""         # Which AI agent generated this (if any)
```

- [ ] **Step 6: Wire AI routing into run_overnight() (scaffold only)**

In `run_overnight()`, after the deterministic proposal (line ~2103-2106), add:

```python
# If deterministic proposal failed and gap is AI-eligible, route to AI
if change is None:
    router = AIAgentRouter()
    agent_type = router.route(gap)
    if agent_type is not None:
        logger.info(f"AI routing: {gap.ticker}:{gap.metric} -> {agent_type.value}")
        # TODO: Phase 2 — call the actual AI agent here
        # change = ai_agent_dispatch(agent_type, gap, ...)
        # For now, just log and skip
        null_proposals += 1
        continue
```

- [ ] **Step 7: Run full test suite**

Run: `cd /home/sangicook/projects/edgartools && python -m pytest tests/xbrl/standardization/ -v -x -q`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add edgar/xbrl/standardization/tools/auto_eval_loop.py \
  tests/xbrl/standardization/test_next_gen_cqs.py
git commit -m "feat: AI agent routing infrastructure — dispatch framework for Phase 2

Add AIAgentType enum and AIAgentRouter class that routes hard gaps to
specialized AI agents (Regression Investigator, Reference Auditor, Semantic
Mapper, Pattern Learner). Only invoked for gaps with graveyard >= 3.
AI proposals will go through the same CQS gate as deterministic ones.
Actual AI calls are TODO — this is the routing scaffold only."
```

---

## Verification

After all tasks are complete:

```bash
# Run all new tests
cd /home/sangicook/projects/edgartools
python -m pytest tests/xbrl/standardization/test_next_gen_cqs.py -v

# Run existing standardization tests (regression check)
python -m pytest tests/xbrl/standardization/ -v -x -q

# Run fast tests broadly
hatch run test-fast -- -x -q -k "standardiz"
```

**Phase 1 target:** CQS >= 0.98, pass rate >= 98% on EXPANSION_COHORT_100
**Phase 2 target:** CQS >= 0.99, pass rate >= 99% on EXPANSION_COHORT_100

## What Stays the Same (Non-Negotiable)

1. `compute_cqs(use_ai=False)` — CQS evaluation is always deterministic
2. `evaluate_experiment()` is the only gate — no proposal bypasses it
3. New regressions are hard veto — this invariant holds regardless of proposal source
4. Config-only changes — no Python code modifications by the loop
5. ExperimentLedger records everything — full auditability
6. Graveyard prevents loops — AI proposals that fail are graveyarded too
