"""
Experiment Ledger Schema

This module defines the data models and SQLite database schema for
tracking extraction experiments.

Tables:
- extraction_runs: Every extraction attempt with full provenance
- golden_masters: Verified stable configurations (3+ periods)
- cohort_tests: Results of cohort reactor tests
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ExtractionRun:
    """
    Record of a single extraction attempt.

    This captures everything needed to reproduce and analyze an extraction:
    - What was extracted (ticker, metric, period)
    - How it was extracted (strategy, params, fingerprint)
    - What was the result (value, reference, variance)
    """
    # Identity
    ticker: str
    metric: str
    fiscal_period: str          # e.g., "2024-Q4", "2024-FY"
    form_type: str              # e.g., "10-K", "10-Q"

    # Classification
    archetype: str              # A, B, C, D, E
    sub_archetype: Optional[str] = None  # For banks: commercial, dealer, etc.

    # Strategy
    strategy_name: str = ""
    strategy_fingerprint: str = ""
    strategy_params: Dict[str, Any] = field(default_factory=dict)

    # Results
    extracted_value: Optional[float] = None
    reference_value: Optional[float] = None
    variance_pct: Optional[float] = None
    is_valid: bool = False
    confidence: float = 0.0

    # Metadata
    run_id: Optional[str] = None
    run_timestamp: Optional[str] = None
    extraction_notes: str = ""
    components: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Golden master tracking
    is_golden_candidate: bool = False
    golden_master_id: Optional[str] = None

    def __post_init__(self):
        """Calculate derived fields."""
        if self.run_timestamp is None:
            self.run_timestamp = datetime.now().isoformat()

        if self.run_id is None:
            # Generate unique run ID
            import hashlib
            id_str = f"{self.ticker}_{self.metric}_{self.fiscal_period}_{self.run_timestamp}"
            self.run_id = hashlib.sha256(id_str.encode()).hexdigest()[:16]

        # Calculate variance if both values present
        if self.extracted_value is not None and self.reference_value is not None:
            if self.reference_value != 0:
                self.variance_pct = abs(self.extracted_value - self.reference_value) / abs(self.reference_value) * 100
            else:
                self.variance_pct = 100.0 if self.extracted_value != 0 else 0.0

            # Valid if within 20% tolerance
            self.is_valid = self.variance_pct <= 20.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'run_id': self.run_id,
            'ticker': self.ticker,
            'metric': self.metric,
            'fiscal_period': self.fiscal_period,
            'form_type': self.form_type,
            'archetype': self.archetype,
            'sub_archetype': self.sub_archetype,
            'strategy_name': self.strategy_name,
            'strategy_fingerprint': self.strategy_fingerprint,
            'strategy_params': self.strategy_params,
            'extracted_value': self.extracted_value,
            'reference_value': self.reference_value,
            'variance_pct': self.variance_pct,
            'is_valid': self.is_valid,
            'confidence': self.confidence,
            'run_timestamp': self.run_timestamp,
            'extraction_notes': self.extraction_notes,
            'components': self.components,
            'metadata': self.metadata,
            'is_golden_candidate': self.is_golden_candidate,
            'golden_master_id': self.golden_master_id,
        }


@dataclass
class GoldenMaster:
    """
    A verified stable extraction configuration.

    A golden master is created when a strategy+params combination
    produces valid results for 3+ consecutive periods.
    """
    golden_id: str
    ticker: str
    metric: str
    archetype: str
    sub_archetype: Optional[str]
    strategy_name: str
    strategy_fingerprint: str
    strategy_params: Dict[str, Any]

    # Validation history
    validated_periods: List[str]  # List of fiscal_period strings
    validation_count: int = 0
    avg_variance_pct: float = 0.0
    max_variance_pct: float = 0.0

    # Status
    is_active: bool = True
    created_at: str = ""
    last_validated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_validated_at:
            self.last_validated_at = self.created_at
        self.validation_count = len(self.validated_periods)


@dataclass
class CohortTestResult:
    """
    Result of running a strategy change against a cohort.

    Used by the Cohort Reactor to track transferability of fixes.
    """
    test_id: str
    cohort_name: str
    strategy_name: str
    strategy_fingerprint: str

    # Results per ticker
    results: Dict[str, str]  # ticker -> "IMPROVED" | "NEUTRAL" | "REGRESSED"
    improved_count: int = 0
    neutral_count: int = 0
    regressed_count: int = 0

    # Aggregate metrics
    total_variance_before: float = 0.0
    total_variance_after: float = 0.0
    variance_delta: float = 0.0

    # Status
    is_passing: bool = False  # True if no regressions and variance didn't increase
    test_timestamp: str = ""

    def __post_init__(self):
        if not self.test_timestamp:
            self.test_timestamp = datetime.now().isoformat()

        # Calculate counts
        self.improved_count = sum(1 for r in self.results.values() if r == "IMPROVED")
        self.neutral_count = sum(1 for r in self.results.values() if r == "NEUTRAL")
        self.regressed_count = sum(1 for r in self.results.values() if r == "REGRESSED")

        # Passing if no regressions and total variance didn't increase
        self.is_passing = (self.regressed_count == 0) and (self.variance_delta <= 0)


# =============================================================================
# REGRESSION DETECTION
# =============================================================================

@dataclass
class RegressionResult:
    """Result of checking one golden master against new runs."""
    ticker: str
    metric: str
    golden_variance: float       # Historical avg variance from golden master
    current_variance: Optional[float]
    status: str                  # "PASS", "REGRESSION", "NO_DATA"


@dataclass
class RegressionReport:
    """Aggregate regression report across all golden masters."""
    total_golden: int            # How many golden masters exist
    checked: int                 # How many had new runs to compare
    regressions: List[RegressionResult]
    passes: List[RegressionResult]
    no_data: List[RegressionResult]

    @property
    def has_regressions(self) -> bool:
        return len(self.regressions) > 0

    @property
    def exit_code(self) -> int:
        return 1 if self.has_regressions else 0


# =============================================================================
# EXPERIMENT LEDGER
# =============================================================================

class ExperimentLedger:
    """
    SQLite-based ledger for tracking extraction experiments.

    Provides:
    - Recording of extraction runs
    - Golden master management
    - Cohort test result tracking
    - Historical queries
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the experiment ledger.

        Args:
            db_path: Path to SQLite database. If None, uses default location.
                     Use ":memory:" for in-memory databases (e.g., testing).
        """
        if db_path is None:
            # Default location in company_mappings directory
            base_dir = Path(__file__).parent.parent / 'company_mappings'
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / 'experiment_ledger.db')

        self.db_path = db_path
        # Keep a persistent connection for in-memory databases (each connect()
        # to ":memory:" creates a separate empty database otherwise).
        self._persistent_conn = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:")
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        """Get a database connection. Reuses persistent connection for :memory: DBs."""
        if self._persistent_conn is not None:
            return self._persistent_conn
        return sqlite3.connect(self.db_path)

    def _init_database(self):
        """Initialize database schema."""
        with self._connect() as conn:
            cursor = conn.cursor()

            # Extraction runs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS extraction_runs (
                    run_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    fiscal_period TEXT NOT NULL,
                    form_type TEXT NOT NULL,
                    archetype TEXT NOT NULL,
                    sub_archetype TEXT,
                    strategy_name TEXT NOT NULL,
                    strategy_fingerprint TEXT NOT NULL,
                    strategy_params TEXT,
                    extracted_value REAL,
                    reference_value REAL,
                    variance_pct REAL,
                    is_valid INTEGER,
                    confidence REAL,
                    run_timestamp TEXT NOT NULL,
                    extraction_notes TEXT,
                    components TEXT,
                    metadata TEXT,
                    is_golden_candidate INTEGER,
                    golden_master_id TEXT,
                    FOREIGN KEY (golden_master_id) REFERENCES golden_masters(golden_id)
                )
            ''')

            # Golden masters table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS golden_masters (
                    golden_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    archetype TEXT NOT NULL,
                    sub_archetype TEXT,
                    strategy_name TEXT NOT NULL,
                    strategy_fingerprint TEXT NOT NULL,
                    strategy_params TEXT,
                    validated_periods TEXT,
                    validation_count INTEGER,
                    avg_variance_pct REAL,
                    max_variance_pct REAL,
                    is_active INTEGER,
                    created_at TEXT NOT NULL,
                    last_validated_at TEXT NOT NULL
                )
            ''')

            # Cohort test results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cohort_tests (
                    test_id TEXT PRIMARY KEY,
                    cohort_name TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    strategy_fingerprint TEXT NOT NULL,
                    results TEXT,
                    improved_count INTEGER,
                    neutral_count INTEGER,
                    regressed_count INTEGER,
                    total_variance_before REAL,
                    total_variance_after REAL,
                    variance_delta REAL,
                    is_passing INTEGER,
                    test_timestamp TEXT NOT NULL
                )
            ''')

            # Pipeline state table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pipeline_state (
                    ticker TEXT PRIMARY KEY,
                    company_name TEXT,
                    state TEXT NOT NULL DEFAULT 'PENDING',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    pass_rate REAL,
                    gaps_count INTEGER,
                    golden_masters_count INTEGER,
                    filings_populated INTEGER,
                    last_error TEXT,
                    last_state_change TEXT,
                    onboarding_report_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_state ON pipeline_state(state)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_ticker ON extraction_runs(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_metric ON extraction_runs(metric)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_period ON extraction_runs(fiscal_period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_strategy ON extraction_runs(strategy_fingerprint)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_golden_ticker ON golden_masters(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cohort_name ON cohort_tests(cohort_name)')

            conn.commit()

    # =========================================================================
    # EXTRACTION RUNS
    # =========================================================================

    def record_run(self, run: ExtractionRun) -> str:
        """
        Record an extraction run.

        Args:
            run: ExtractionRun to record

        Returns:
            The run_id of the recorded run
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO extraction_runs (
                    run_id, ticker, metric, fiscal_period, form_type,
                    archetype, sub_archetype, strategy_name, strategy_fingerprint,
                    strategy_params, extracted_value, reference_value, variance_pct,
                    is_valid, confidence, run_timestamp, extraction_notes,
                    components, metadata, is_golden_candidate, golden_master_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                run.run_id, run.ticker, run.metric, run.fiscal_period, run.form_type,
                run.archetype, run.sub_archetype, run.strategy_name, run.strategy_fingerprint,
                json.dumps(run.strategy_params), run.extracted_value, run.reference_value,
                run.variance_pct, int(run.is_valid), run.confidence, run.run_timestamp,
                run.extraction_notes, json.dumps(run.components), json.dumps(run.metadata),
                int(run.is_golden_candidate), run.golden_master_id
            ))
            conn.commit()

        logger.debug(f"Recorded run {run.run_id} for {run.ticker}/{run.metric}")
        return run.run_id

    def get_run(self, run_id: str) -> Optional[ExtractionRun]:
        """Get a specific run by ID."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM extraction_runs WHERE run_id = ?', (run_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_run(row)
        return None

    def get_runs_for_ticker(
        self,
        ticker: str,
        metric: Optional[str] = None,
        limit: int = 100
    ) -> List[ExtractionRun]:
        """Get recent runs for a ticker."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if metric:
                cursor.execute('''
                    SELECT * FROM extraction_runs
                    WHERE ticker = ? AND metric = ?
                    ORDER BY run_timestamp DESC
                    LIMIT ?
                ''', (ticker, metric, limit))
            else:
                cursor.execute('''
                    SELECT * FROM extraction_runs
                    WHERE ticker = ?
                    ORDER BY run_timestamp DESC
                    LIMIT ?
                ''', (ticker, limit))

            return [self._row_to_run(row) for row in cursor.fetchall()]

    def get_runs_by_strategy(
        self,
        strategy_fingerprint: str,
        limit: int = 100
    ) -> List[ExtractionRun]:
        """Get all runs using a specific strategy version."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM extraction_runs
                WHERE strategy_fingerprint = ?
                ORDER BY run_timestamp DESC
                LIMIT ?
            ''', (strategy_fingerprint, limit))
            return [self._row_to_run(row) for row in cursor.fetchall()]

    def _row_to_run(self, row: sqlite3.Row) -> ExtractionRun:
        """Convert database row to ExtractionRun."""
        return ExtractionRun(
            run_id=row['run_id'],
            ticker=row['ticker'],
            metric=row['metric'],
            fiscal_period=row['fiscal_period'],
            form_type=row['form_type'],
            archetype=row['archetype'],
            sub_archetype=row['sub_archetype'],
            strategy_name=row['strategy_name'],
            strategy_fingerprint=row['strategy_fingerprint'],
            strategy_params=json.loads(row['strategy_params'] or '{}'),
            extracted_value=row['extracted_value'],
            reference_value=row['reference_value'],
            variance_pct=row['variance_pct'],
            is_valid=bool(row['is_valid']),
            confidence=row['confidence'],
            run_timestamp=row['run_timestamp'],
            extraction_notes=row['extraction_notes'],
            components=json.loads(row['components'] or '{}'),
            metadata=json.loads(row['metadata'] or '{}'),
            is_golden_candidate=bool(row['is_golden_candidate']),
            golden_master_id=row['golden_master_id'],
        )

    # =========================================================================
    # GOLDEN MASTERS
    # =========================================================================

    def create_golden_master(self, master: GoldenMaster) -> str:
        """Create or update a golden master."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO golden_masters (
                    golden_id, ticker, metric, archetype, sub_archetype,
                    strategy_name, strategy_fingerprint, strategy_params,
                    validated_periods, validation_count, avg_variance_pct,
                    max_variance_pct, is_active, created_at, last_validated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                master.golden_id, master.ticker, master.metric, master.archetype,
                master.sub_archetype, master.strategy_name, master.strategy_fingerprint,
                json.dumps(master.strategy_params), json.dumps(master.validated_periods),
                master.validation_count, master.avg_variance_pct, master.max_variance_pct,
                int(master.is_active), master.created_at, master.last_validated_at
            ))
            conn.commit()

        logger.info(f"Created golden master {master.golden_id} for {master.ticker}/{master.metric}")
        return master.golden_id

    def get_golden_master(self, ticker: str, metric: str) -> Optional[GoldenMaster]:
        """Get active golden master for ticker/metric."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM golden_masters
                WHERE ticker = ? AND metric = ? AND is_active = 1
                ORDER BY last_validated_at DESC
                LIMIT 1
            ''', (ticker, metric))
            row = cursor.fetchone()
            if row:
                return self._row_to_golden(row)
        return None

    def get_all_golden_masters(self, active_only: bool = True) -> List[GoldenMaster]:
        """Get all golden masters."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if active_only:
                cursor.execute('SELECT * FROM golden_masters WHERE is_active = 1')
            else:
                cursor.execute('SELECT * FROM golden_masters')
            return [self._row_to_golden(row) for row in cursor.fetchall()]

    def _row_to_golden(self, row: sqlite3.Row) -> GoldenMaster:
        """Convert database row to GoldenMaster."""
        return GoldenMaster(
            golden_id=row['golden_id'],
            ticker=row['ticker'],
            metric=row['metric'],
            archetype=row['archetype'],
            sub_archetype=row['sub_archetype'],
            strategy_name=row['strategy_name'],
            strategy_fingerprint=row['strategy_fingerprint'],
            strategy_params=json.loads(row['strategy_params'] or '{}'),
            validated_periods=json.loads(row['validated_periods'] or '[]'),
            validation_count=row['validation_count'],
            avg_variance_pct=row['avg_variance_pct'],
            max_variance_pct=row['max_variance_pct'],
            is_active=bool(row['is_active']),
            created_at=row['created_at'],
            last_validated_at=row['last_validated_at'],
        )

    # =========================================================================
    # COHORT TESTS
    # =========================================================================

    def record_cohort_test(self, result: CohortTestResult) -> str:
        """Record a cohort test result."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cohort_tests (
                    test_id, cohort_name, strategy_name, strategy_fingerprint,
                    results, improved_count, neutral_count, regressed_count,
                    total_variance_before, total_variance_after, variance_delta,
                    is_passing, test_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.test_id, result.cohort_name, result.strategy_name,
                result.strategy_fingerprint, json.dumps(result.results),
                result.improved_count, result.neutral_count, result.regressed_count,
                result.total_variance_before, result.total_variance_after,
                result.variance_delta, int(result.is_passing), result.test_timestamp
            ))
            conn.commit()

        logger.info(f"Recorded cohort test {result.test_id}: {'PASS' if result.is_passing else 'FAIL'}")
        return result.test_id

    def get_cohort_tests(self, cohort_name: str, limit: int = 10) -> List[CohortTestResult]:
        """Get recent cohort test results."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM cohort_tests
                WHERE cohort_name = ?
                ORDER BY test_timestamp DESC
                LIMIT ?
            ''', (cohort_name, limit))
            return [self._row_to_cohort_test(row) for row in cursor.fetchall()]

    def _row_to_cohort_test(self, row: sqlite3.Row) -> CohortTestResult:
        """Convert database row to CohortTestResult."""
        return CohortTestResult(
            test_id=row['test_id'],
            cohort_name=row['cohort_name'],
            strategy_name=row['strategy_name'],
            strategy_fingerprint=row['strategy_fingerprint'],
            results=json.loads(row['results'] or '{}'),
            improved_count=row['improved_count'],
            neutral_count=row['neutral_count'],
            regressed_count=row['regressed_count'],
            total_variance_before=row['total_variance_before'],
            total_variance_after=row['total_variance_after'],
            variance_delta=row['variance_delta'],
            is_passing=bool(row['is_passing']),
            test_timestamp=row['test_timestamp'],
        )

    # =========================================================================
    # GOLDEN MASTER PROMOTION
    # =========================================================================

    def promote_golden_masters(
        self,
        strategy_fingerprint: Optional[str] = None,
        min_periods: int = 3,
        max_variance: float = 20.0,
    ) -> List[GoldenMaster]:
        """
        Promote stable extraction configurations to golden masters.

        Scans extraction_runs for (ticker, metric, strategy_name) combos
        with min_periods distinct valid fiscal periods, then creates/updates
        golden masters for each qualifying group.

        Args:
            strategy_fingerprint: If provided, only consider runs with this fingerprint.
            min_periods: Minimum distinct valid fiscal periods required (default 3).
            max_variance: Maximum average variance allowed for promotion (default 20%).

        Returns:
            List of newly promoted GoldenMaster objects.
        """
        promoted = []

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query to find qualifying groups
            where_clause = "WHERE is_valid = 1"
            params = []
            if strategy_fingerprint:
                where_clause += " AND strategy_fingerprint = ?"
                params.append(strategy_fingerprint)

            cursor.execute(f'''
                SELECT
                    ticker,
                    metric,
                    strategy_name,
                    strategy_fingerprint,
                    archetype,
                    sub_archetype,
                    COUNT(DISTINCT fiscal_period) as period_count,
                    AVG(variance_pct) as avg_variance,
                    MAX(variance_pct) as max_var,
                    GROUP_CONCAT(DISTINCT fiscal_period) as periods
                FROM extraction_runs
                {where_clause}
                GROUP BY ticker, metric, strategy_name
                HAVING COUNT(DISTINCT fiscal_period) >= ?
                    AND AVG(variance_pct) <= ?
            ''', params + [min_periods, max_variance])

            rows = cursor.fetchall()

        for row in rows:
            golden_id = f"gm_{row['ticker']}_{row['metric']}_{row['strategy_name']}"
            validated_periods = sorted(row['periods'].split(','))

            master = GoldenMaster(
                golden_id=golden_id,
                ticker=row['ticker'],
                metric=row['metric'],
                archetype=row['archetype'],
                sub_archetype=row['sub_archetype'],
                strategy_name=row['strategy_name'],
                strategy_fingerprint=row['strategy_fingerprint'],
                strategy_params={},
                validated_periods=validated_periods,
                avg_variance_pct=row['avg_variance'] or 0.0,
                max_variance_pct=row['max_var'] or 0.0,
            )
            self.create_golden_master(master)
            promoted.append(master)

        logger.info(f"Promoted {len(promoted)} golden masters")
        return promoted

    # =========================================================================
    # REGRESSION DETECTION
    # =========================================================================

    def check_regressions(
        self,
        strategy_fingerprint: str,
        variance_threshold: float = 20.0,
    ) -> RegressionReport:
        """
        Check for regressions against golden masters.

        Compares the latest run for each golden master's (ticker, metric)
        against the golden master's historical validity.

        Args:
            strategy_fingerprint: Fingerprint of the current strategy to check.
            variance_threshold: Variance % above which a run is considered failing.

        Returns:
            RegressionReport with PASS/REGRESSION/NO_DATA per golden master.
        """
        golden_masters = self.get_all_golden_masters(active_only=True)
        regressions = []
        passes = []
        no_data = []

        for gm in golden_masters:
            # Find latest run with this fingerprint for (ticker, metric)
            latest_run = self._get_latest_run(
                ticker=gm.ticker,
                metric=gm.metric,
                strategy_fingerprint=strategy_fingerprint,
            )

            if latest_run is None:
                no_data.append(RegressionResult(
                    ticker=gm.ticker,
                    metric=gm.metric,
                    golden_variance=gm.avg_variance_pct,
                    current_variance=None,
                    status="NO_DATA",
                ))
            elif not latest_run.is_valid:
                regressions.append(RegressionResult(
                    ticker=gm.ticker,
                    metric=gm.metric,
                    golden_variance=gm.avg_variance_pct,
                    current_variance=latest_run.variance_pct,
                    status="REGRESSION",
                ))
            else:
                passes.append(RegressionResult(
                    ticker=gm.ticker,
                    metric=gm.metric,
                    golden_variance=gm.avg_variance_pct,
                    current_variance=latest_run.variance_pct,
                    status="PASS",
                ))

        return RegressionReport(
            total_golden=len(golden_masters),
            checked=len(regressions) + len(passes),
            regressions=regressions,
            passes=passes,
            no_data=no_data,
        )

    def _get_latest_run(
        self,
        ticker: str,
        metric: str,
        strategy_fingerprint: str,
    ) -> Optional[ExtractionRun]:
        """Get the most recent run for a (ticker, metric, fingerprint) combo."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM extraction_runs
                WHERE ticker = ? AND metric = ? AND strategy_fingerprint = ?
                ORDER BY run_timestamp DESC
                LIMIT 1
            ''', (ticker, metric, strategy_fingerprint))
            row = cursor.fetchone()
            if row:
                return self._row_to_run(row)
        return None

    def print_regression_report(self, report: RegressionReport):
        """Print a formatted regression report to console."""
        print(f"\n{'='*60}")
        print("REGRESSION REPORT")
        print(f"{'='*60}")
        print(f"Golden masters: {report.total_golden}")
        print(f"Checked:        {report.checked}")
        print(f"Passes:         {len(report.passes)}")
        print(f"Regressions:    {len(report.regressions)}")
        print(f"No data:        {len(report.no_data)}")

        if report.regressions:
            print(f"\n{'REGRESSIONS':}")
            print(f"{'Ticker':<8} {'Metric':<25} {'Golden %':>10} {'Current %':>10}")
            print("-" * 60)
            for r in report.regressions:
                current = f"{r.current_variance:.1f}" if r.current_variance is not None else "N/A"
                print(f"{r.ticker:<8} {r.metric:<25} {r.golden_variance:>10.1f} {current:>10}")

        if not report.has_regressions:
            print("\nSTATUS: CLEAN - No regressions detected")
        else:
            print(f"\nSTATUS: {len(report.regressions)} REGRESSIONS DETECTED")

        print(f"{'='*60}\n")

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_strategy_performance(self, strategy_name: str) -> Dict[str, Any]:
        """Get aggregate performance metrics for a strategy."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) as valid_runs,
                    AVG(variance_pct) as avg_variance,
                    MAX(variance_pct) as max_variance,
                    COUNT(DISTINCT ticker) as unique_tickers
                FROM extraction_runs
                WHERE strategy_name = ?
            ''', (strategy_name,))
            row = cursor.fetchone()

            if row:
                total = row[0] or 0
                valid = row[1] or 0
                return {
                    'strategy_name': strategy_name,
                    'total_runs': total,
                    'valid_runs': valid,
                    'success_rate': valid / total if total > 0 else 0,
                    'avg_variance_pct': row[2],
                    'max_variance_pct': row[3],
                    'unique_tickers': row[4],
                }
            return {}

    # =========================================================================
    # PIPELINE STATE
    # =========================================================================

    VALID_PIPELINE_STATES = [
        'PENDING', 'ONBOARDING', 'ANALYZING', 'RESOLVING',
        'VALIDATING', 'PROMOTING', 'POPULATING', 'COMPLETE', 'FAILED',
    ]

    # Allowed transitions: from_state -> set of allowed to_states
    PIPELINE_TRANSITIONS = {
        'PENDING': {'ONBOARDING'},
        'ONBOARDING': {'ANALYZING', 'FAILED'},
        'ANALYZING': {'RESOLVING', 'VALIDATING', 'FAILED'},
        'RESOLVING': {'ANALYZING', 'VALIDATING', 'FAILED'},
        'VALIDATING': {'PROMOTING', 'ANALYZING', 'FAILED'},
        'PROMOTING': {'POPULATING', 'FAILED'},
        'POPULATING': {'COMPLETE', 'FAILED'},
        'COMPLETE': set(),
        'FAILED': set(),
    }

    def add_pipeline_company(self, ticker: str, company_name: str = '') -> None:
        """
        Add a company to the pipeline in PENDING state.

        Args:
            ticker: Company ticker symbol.
            company_name: Optional company name.
        """
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO pipeline_state (
                    ticker, company_name, state, retry_count, max_retries,
                    created_at, updated_at
                ) VALUES (?, ?, 'PENDING', 0, 3, ?, ?)
            ''', (ticker.upper(), company_name, now, now))
            conn.commit()

    def get_pipeline_state(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current pipeline state for a ticker.

        Returns:
            Dict with all pipeline_state columns, or None if not found.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM pipeline_state WHERE ticker = ?',
                (ticker.upper(),)
            )
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d['metadata'] = json.loads(d.get('metadata') or '{}')
                return d
        return None

    def advance_pipeline(
        self,
        ticker: str,
        new_state: str,
        **kwargs,
    ) -> None:
        """
        Advance a company to a new pipeline state.

        Validates the transition and increments retry_count when
        moving from RESOLVING back to ANALYZING.

        Args:
            ticker: Company ticker symbol.
            new_state: Target state.
            **kwargs: Additional columns to update (pass_rate, gaps_count,
                      golden_masters_count, filings_populated, last_error,
                      onboarding_report_path, metadata).

        Raises:
            ValueError: If the transition is not allowed or ticker not found.
        """
        ticker = ticker.upper()
        current = self.get_pipeline_state(ticker)
        if current is None:
            raise ValueError(f"Ticker {ticker} not in pipeline")

        current_state = current['state']
        if new_state not in self.PIPELINE_TRANSITIONS.get(current_state, set()):
            raise ValueError(
                f"Invalid transition: {current_state} -> {new_state} "
                f"(allowed: {self.PIPELINE_TRANSITIONS.get(current_state, set())})"
            )

        now = datetime.now().isoformat()

        # Increment retry_count when looping back to ANALYZING
        retry_count = current['retry_count']
        max_retries = current['max_retries']
        if new_state == 'ANALYZING' and current_state in ('RESOLVING', 'VALIDATING'):
            retry_count += 1
            if retry_count > max_retries:
                new_state = 'FAILED'
                kwargs.setdefault('last_error', f'Max retries ({max_retries}) exceeded')

        # Build SET clause dynamically from kwargs
        allowed_fields = {
            'pass_rate', 'gaps_count', 'golden_masters_count',
            'filings_populated', 'last_error', 'onboarding_report_path',
            'metadata', 'company_name',
        }
        sets = [
            'state = ?', 'retry_count = ?',
            'last_state_change = ?', 'updated_at = ?',
        ]
        params: list = [new_state, retry_count, now, now]

        for key, value in kwargs.items():
            if key not in allowed_fields:
                continue
            if key == 'metadata':
                # Merge metadata
                merged = current.get('metadata') or {}
                merged.update(value)
                value = json.dumps(merged)
            sets.append(f'{key} = ?')
            params.append(value)

        params.append(ticker)

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE pipeline_state SET {", ".join(sets)} WHERE ticker = ?',
                params,
            )
            conn.commit()

    def get_pipeline_batch(
        self, state: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get companies in a given pipeline state.

        Args:
            state: Pipeline state to filter by.
            limit: Max results.

        Returns:
            List of pipeline state dicts.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM pipeline_state WHERE state = ? ORDER BY updated_at LIMIT ?',
                (state, limit),
            )
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d['metadata'] = json.loads(d.get('metadata') or '{}')
                results.append(d)
            return results

    def get_pipeline_summary(self) -> Dict[str, int]:
        """
        Get counts of companies per pipeline state.

        Returns:
            Dict mapping state name to count, e.g. {'COMPLETE': 82, 'FAILED': 5}.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT state, COUNT(*) as cnt FROM pipeline_state GROUP BY state'
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def reset_pipeline(self, ticker: str) -> None:
        """
        Reset a company back to PENDING state with retry_count=0.

        Args:
            ticker: Company ticker symbol.
        """
        ticker = ticker.upper()
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE pipeline_state
                SET state = 'PENDING', retry_count = 0,
                    last_error = NULL, last_state_change = ?,
                    updated_at = ?
                WHERE ticker = ?
            ''', (now, now, ticker))
            conn.commit()

    def get_pipeline_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent pipeline state transitions.

        Returns:
            List of dicts with ticker, state, last_state_change, pass_rate.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ticker, state, last_state_change, pass_rate, last_error
                FROM pipeline_state
                WHERE last_state_change IS NOT NULL
                ORDER BY last_state_change DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_ticker_summary(self, ticker: str) -> Dict[str, Any]:
        """Get extraction summary for a ticker."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    metric,
                    COUNT(*) as runs,
                    SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) as valid,
                    AVG(variance_pct) as avg_variance
                FROM extraction_runs
                WHERE ticker = ?
                GROUP BY metric
            ''', (ticker,))

            metrics = {}
            for row in cursor.fetchall():
                metrics[row[0]] = {
                    'runs': row[1],
                    'valid': row[2],
                    'success_rate': row[2] / row[1] if row[1] > 0 else 0,
                    'avg_variance_pct': row[3],
                }

            return {
                'ticker': ticker,
                'metrics': metrics,
            }
