"""
Cohort Reactor Implementation

The Cohort Reactor tests strategy changes against groups of similar companies
to identify transferability opportunities and prevent regressions.

Key Concepts:
- Cohort: A group of companies with similar characteristics (e.g., GSIB banks)
- Baseline: The current extraction results before applying changes
- Change: The proposed strategy modification
- Impact: IMPROVED, NEUTRAL, or REGRESSED per company
"""

import hashlib
import logging
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from ..ledger import ExperimentLedger, ExtractionRun, CohortTestResult
from ..archetypes import AccountingArchetype, BankSubArchetype

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CohortDefinition:
    """
    Definition of a company cohort for testing.

    Cohorts group companies with similar characteristics for
    transferability testing.
    """
    name: str
    members: List[str]  # List of ticker symbols
    archetype: str      # A, B, C, D, E
    sub_archetype: Optional[str] = None  # For banks: commercial, dealer, etc.
    description: str = ""
    metrics: List[str] = field(default_factory=list)  # Metrics to test


@dataclass
class CompanyResult:
    """
    Result of testing a single company.
    """
    ticker: str
    metric: str
    baseline_value: Optional[float]
    baseline_variance: Optional[float]
    new_value: Optional[float]
    new_variance: Optional[float]
    reference_value: Optional[float]
    impact: str  # "IMPROVED", "NEUTRAL", "REGRESSED"
    notes: str = ""

    @property
    def variance_delta(self) -> float:
        """Change in variance (negative is better)."""
        if self.baseline_variance is None or self.new_variance is None:
            return 0.0
        return self.new_variance - self.baseline_variance


@dataclass
class CohortTestSummary:
    """
    Summary of cohort test results.
    """
    test_id: str
    cohort_name: str
    strategy_name: str
    strategy_fingerprint: str
    test_timestamp: str

    # Results
    company_results: List[CompanyResult]
    improved_count: int = 0
    neutral_count: int = 0
    regressed_count: int = 0

    # Aggregate metrics
    total_variance_before: float = 0.0
    total_variance_after: float = 0.0
    variance_delta: float = 0.0

    # Status
    is_passing: bool = False

    def __post_init__(self):
        """Calculate aggregate metrics."""
        self.improved_count = sum(1 for r in self.company_results if r.impact == "IMPROVED")
        self.neutral_count = sum(1 for r in self.company_results if r.impact == "NEUTRAL")
        self.regressed_count = sum(1 for r in self.company_results if r.impact == "REGRESSED")

        # Sum variances
        before_variances = [r.baseline_variance for r in self.company_results if r.baseline_variance is not None]
        after_variances = [r.new_variance for r in self.company_results if r.new_variance is not None]

        self.total_variance_before = sum(before_variances) if before_variances else 0.0
        self.total_variance_after = sum(after_variances) if after_variances else 0.0
        self.variance_delta = self.total_variance_after - self.total_variance_before

        # Passing if no regressions and total variance didn't increase
        self.is_passing = (self.regressed_count == 0) and (self.variance_delta <= 0)


# =============================================================================
# COHORT REACTOR
# =============================================================================

class CohortReactor:
    """
    Cohort Reactor for transferability testing.

    Tests strategy changes against cohorts of similar companies to:
    1. Identify knowledge transfer opportunities
    2. Prevent regressions
    3. Track experiment results
    """

    # Default cohorts
    DEFAULT_COHORTS: Dict[str, CohortDefinition] = {
        'GSIB_Banks': CohortDefinition(
            name='GSIB_Banks',
            members=['JPM', 'BAC', 'C', 'WFC', 'GS', 'MS', 'BK', 'STT'],
            archetype='B',
            description='Global Systemically Important Banks',
            metrics=['ShortTermDebt', 'CashAndEquivalents'],
        ),
        'Hybrid_Banks': CohortDefinition(
            name='Hybrid_Banks',
            members=['JPM', 'BAC', 'C'],
            archetype='B',
            sub_archetype='hybrid',
            description='Hybrid/Universal Banks',
            metrics=['ShortTermDebt'],
        ),
        'Commercial_Banks': CohortDefinition(
            name='Commercial_Banks',
            members=['WFC', 'USB', 'PNC'],
            archetype='B',
            sub_archetype='commercial',
            description='Commercial Banks',
            metrics=['ShortTermDebt'],
        ),
        'Dealer_Banks': CohortDefinition(
            name='Dealer_Banks',
            members=['GS', 'MS'],
            archetype='B',
            sub_archetype='dealer',
            description='Investment/Dealer Banks',
            metrics=['ShortTermDebt'],
        ),
        'Custodial_Banks': CohortDefinition(
            name='Custodial_Banks',
            members=['BK', 'STT'],
            archetype='B',
            sub_archetype='custodial',
            description='Custodial Banks',
            metrics=['ShortTermDebt'],
        ),
    }

    def __init__(
        self,
        ledger: Optional[ExperimentLedger] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize the Cohort Reactor.

        Args:
            ledger: ExperimentLedger for recording results
            config_path: Path to companies.yaml with cohort definitions
        """
        self.ledger = ledger or ExperimentLedger()
        self.cohorts = dict(self.DEFAULT_COHORTS)

        # Load custom cohorts from config
        if config_path:
            self._load_cohorts_from_config(config_path)
        else:
            # Try default config path
            default_config = Path(__file__).parent.parent / 'config' / 'companies.yaml'
            if default_config.exists():
                self._load_cohorts_from_config(str(default_config))

    def _load_cohorts_from_config(self, config_path: str):
        """Load cohort definitions from YAML config."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            cohorts_config = config.get('cohorts', {})
            for name, defn in cohorts_config.items():
                self.cohorts[name] = CohortDefinition(
                    name=name,
                    members=defn.get('members', []),
                    archetype=defn.get('archetype', 'A'),
                    sub_archetype=defn.get('sub_archetype'),
                    description=defn.get('description', ''),
                    metrics=defn.get('metrics', ['ShortTermDebt']),
                )
            logger.info(f"Loaded {len(cohorts_config)} cohorts from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load cohorts from {config_path}: {e}")

    def get_cohort(self, name: str) -> Optional[CohortDefinition]:
        """Get a cohort definition by name."""
        return self.cohorts.get(name)

    def list_cohorts(self) -> List[str]:
        """List all available cohort names."""
        return list(self.cohorts.keys())

    def test_strategy_change(
        self,
        cohort_name: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        metric: str = 'ShortTermDebt',
        extractor_fn: Optional[Callable] = None,
        baseline_fn: Optional[Callable] = None,
        reference_fn: Optional[Callable] = None,
    ) -> CohortTestSummary:
        """
        Test a strategy change against a cohort.

        Args:
            cohort_name: Name of the cohort to test
            strategy_name: Name of the strategy being tested
            strategy_params: Parameters for the strategy
            metric: Metric to test (default: ShortTermDebt)
            extractor_fn: Function(ticker, params) -> extracted_value
            baseline_fn: Function(ticker) -> baseline_value, baseline_variance
            reference_fn: Function(ticker) -> reference_value

        Returns:
            CohortTestSummary with results for all companies
        """
        cohort = self.get_cohort(cohort_name)
        if not cohort:
            raise ValueError(f"Unknown cohort: {cohort_name}")

        # Generate test ID
        test_id = self._generate_test_id(cohort_name, strategy_name, strategy_params)
        test_timestamp = datetime.now().isoformat()

        # Calculate strategy fingerprint
        import json
        fingerprint_data = {'strategy': strategy_name, 'params': strategy_params}
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True).encode()
        ).hexdigest()[:16]

        # Test each company
        company_results = []
        for ticker in cohort.members:
            result = self._test_company(
                ticker=ticker,
                metric=metric,
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                extractor_fn=extractor_fn,
                baseline_fn=baseline_fn,
                reference_fn=reference_fn,
            )
            company_results.append(result)

        # Create summary
        summary = CohortTestSummary(
            test_id=test_id,
            cohort_name=cohort_name,
            strategy_name=strategy_name,
            strategy_fingerprint=fingerprint,
            test_timestamp=test_timestamp,
            company_results=company_results,
        )

        # Record to ledger
        self._record_to_ledger(summary)

        return summary

    def _test_company(
        self,
        ticker: str,
        metric: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        extractor_fn: Optional[Callable] = None,
        baseline_fn: Optional[Callable] = None,
        reference_fn: Optional[Callable] = None,
    ) -> CompanyResult:
        """Test a single company."""
        # Get baseline (from ledger or provided function)
        baseline_value = None
        baseline_variance = None

        if baseline_fn:
            baseline_value, baseline_variance = baseline_fn(ticker)
        else:
            # Try to get from ledger
            runs = self.ledger.get_runs_for_ticker(ticker, metric=metric, limit=1)
            if runs:
                baseline_value = runs[0].extracted_value
                baseline_variance = runs[0].variance_pct

        # Get reference value
        reference_value = None
        if reference_fn:
            reference_value = reference_fn(ticker)

        # Get new extraction value
        new_value = None
        new_variance = None

        if extractor_fn:
            try:
                new_value = extractor_fn(ticker, strategy_params)
                if new_value is not None and reference_value is not None and reference_value != 0:
                    new_variance = abs(new_value - reference_value) / abs(reference_value) * 100
            except Exception as e:
                logger.warning(f"Extraction failed for {ticker}: {e}")

        # Determine impact
        impact = self._determine_impact(baseline_variance, new_variance)

        return CompanyResult(
            ticker=ticker,
            metric=metric,
            baseline_value=baseline_value,
            baseline_variance=baseline_variance,
            new_value=new_value,
            new_variance=new_variance,
            reference_value=reference_value,
            impact=impact,
        )

    def _determine_impact(
        self,
        baseline_variance: Optional[float],
        new_variance: Optional[float],
    ) -> str:
        """
        Determine the impact of a change.

        Impact categories:
        - IMPROVED: Variance decreased by >2%
        - REGRESSED: Variance increased by >2%
        - NEUTRAL: Variance change within +-2%
        """
        if baseline_variance is None or new_variance is None:
            return "NEUTRAL"

        delta = new_variance - baseline_variance

        if delta < -2.0:
            return "IMPROVED"
        elif delta > 2.0:
            return "REGRESSED"
        else:
            return "NEUTRAL"

    def _generate_test_id(
        self,
        cohort_name: str,
        strategy_name: str,
        strategy_params: Dict[str, Any],
    ) -> str:
        """Generate unique test ID."""
        import json
        id_data = {
            'cohort': cohort_name,
            'strategy': strategy_name,
            'params': strategy_params,
            'timestamp': datetime.now().isoformat(),
        }
        return hashlib.sha256(
            json.dumps(id_data, sort_keys=True).encode()
        ).hexdigest()[:16]

    def test_from_e2e_results(
        self,
        cohort_name: str,
        e2e_results: List[Dict],
        strategy_name: str,
        strategy_fingerprint: str,
        metrics: Optional[List[str]] = None,
    ) -> CohortTestSummary:
        """
        Test a cohort using pre-computed E2E results from Pool.map().

        Compares current E2E results against baseline runs from the ledger
        (with a DIFFERENT fingerprint) to classify impact per company/metric.

        Args:
            cohort_name: Name of the cohort to test.
            e2e_results: List of dicts from Pool.map(), each with 'ticker' and 'ledger_runs'.
            strategy_name: Name of the current strategy.
            strategy_fingerprint: Fingerprint of the current strategy.
            metrics: Override metrics to test (defaults to cohort definition).

        Returns:
            CohortTestSummary with results for all member companies.
        """
        cohort = self.get_cohort(cohort_name)
        if not cohort:
            raise ValueError(f"Unknown cohort: {cohort_name}")

        test_metrics = metrics or cohort.metrics
        if not test_metrics:
            test_metrics = ['Revenue', 'OperatingIncome']

        # Build lookup: ticker -> list of ledger_run dicts
        results_by_ticker = {}
        for r in e2e_results:
            ticker = r.get('ticker')
            if ticker:
                results_by_ticker[ticker] = r.get('ledger_runs', [])

        # Generate test ID
        test_id = self._generate_test_id(cohort_name, strategy_name, {'fp': strategy_fingerprint})
        test_timestamp = datetime.now().isoformat()

        company_results = []
        for metric in test_metrics:
            for ticker in cohort.members:
                ledger_runs = results_by_ticker.get(ticker, [])

                # Find current run for this metric
                current_run = next(
                    (lr for lr in ledger_runs if lr.get('metric') == metric),
                    None,
                )

                new_value = current_run.get('extracted_value') if current_run else None
                new_variance = None
                reference_value = current_run.get('reference_value') if current_run else None

                if new_value is not None and reference_value is not None and reference_value != 0:
                    new_variance = abs(new_value - reference_value) / abs(reference_value) * 100

                # Get baseline from ledger: most recent run with DIFFERENT fingerprint
                baseline_value = None
                baseline_variance = None
                runs = self.ledger.get_runs_for_ticker(ticker, metric=metric, limit=10)
                baseline_run = next(
                    (r for r in runs if r.strategy_fingerprint != strategy_fingerprint),
                    None,
                )
                if baseline_run:
                    baseline_value = baseline_run.extracted_value
                    baseline_variance = baseline_run.variance_pct

                impact = self._determine_impact(baseline_variance, new_variance)

                company_results.append(CompanyResult(
                    ticker=ticker,
                    metric=metric,
                    baseline_value=baseline_value,
                    baseline_variance=baseline_variance,
                    new_value=new_value,
                    new_variance=new_variance,
                    reference_value=reference_value,
                    impact=impact,
                ))

        summary = CohortTestSummary(
            test_id=test_id,
            cohort_name=cohort_name,
            strategy_name=strategy_name,
            strategy_fingerprint=strategy_fingerprint,
            test_timestamp=test_timestamp,
            company_results=company_results,
        )

        self._record_to_ledger(summary)
        return summary

    def _record_to_ledger(self, summary: CohortTestSummary):
        """Record test results to the experiment ledger."""
        # Record cohort test
        cohort_result = CohortTestResult(
            test_id=summary.test_id,
            cohort_name=summary.cohort_name,
            strategy_name=summary.strategy_name,
            strategy_fingerprint=summary.strategy_fingerprint,
            results={r.ticker: r.impact for r in summary.company_results},
            total_variance_before=summary.total_variance_before,
            total_variance_after=summary.total_variance_after,
        )
        self.ledger.record_cohort_test(cohort_result)

    def print_summary(self, summary: CohortTestSummary):
        """Print a formatted summary of test results."""
        print(f"\n{'='*60}")
        print(f"COHORT TEST: {summary.cohort_name}")
        print(f"{'='*60}")
        print(f"Strategy: {summary.strategy_name}")
        print(f"Fingerprint: {summary.strategy_fingerprint}")
        print(f"Timestamp: {summary.test_timestamp}")
        print()

        # Results table
        print(f"{'Ticker':<8} {'Baseline %':>12} {'New %':>12} {'Delta':>10} {'Impact':<10}")
        print("-" * 60)

        for r in summary.company_results:
            baseline = f"{r.baseline_variance:.1f}" if r.baseline_variance else "N/A"
            new = f"{r.new_variance:.1f}" if r.new_variance else "N/A"
            delta = f"{r.variance_delta:+.1f}" if r.baseline_variance and r.new_variance else "N/A"

            # Color coding for impact
            impact_symbol = {
                'IMPROVED': '+++',
                'NEUTRAL': '   ',
                'REGRESSED': '---',
            }.get(r.impact, '???')

            print(f"{r.ticker:<8} {baseline:>12} {new:>12} {delta:>10} {impact_symbol} {r.impact}")

        print("-" * 60)
        print(f"Total Variance: {summary.total_variance_before:.1f}% -> {summary.total_variance_after:.1f}% ({summary.variance_delta:+.1f}%)")
        print(f"Improved: {summary.improved_count}, Neutral: {summary.neutral_count}, Regressed: {summary.regressed_count}")
        print()

        if summary.is_passing:
            print("STATUS: PASS - Safe to merge")
        else:
            print("STATUS: BLOCKED - Regressions detected or variance increased")

        print(f"{'='*60}\n")
