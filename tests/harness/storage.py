"""SQLite-based storage for the Edgar test harness system."""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os

from .models import Session, TestRun, TestResult, FilingMetadata


class HarnessStorage:
    """SQLite-based persistent storage for test harness.

    Manages sessions, test runs, results, and filing metadata in a SQLite database.
    Uses WAL mode for better concurrent access and includes indexes for performance.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize storage.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.edgar_test/harness.db
                    Use ":memory:" for in-memory database (testing only)
        """
        if db_path is None:
            db_path = Path("~/.edgar_test/harness.db")

        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path).expanduser()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = self._create_connection()
        self._create_schema()

    def _create_connection(self) -> sqlite3.Connection:
        """Create database connection with optimal settings."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Access columns by name
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        conn.execute("PRAGMA foreign_keys=ON")  # Enforce foreign keys
        return conn

    def _create_schema(self):
        """Create database tables and indexes if they don't exist."""
        with self.conn:
            # Sessions table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Test runs table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    test_type TEXT NOT NULL,
                    config TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT DEFAULT 'running',
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            # Test results table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    filing_accession TEXT NOT NULL,
                    filing_form TEXT NOT NULL,
                    filing_company TEXT NOT NULL,
                    filing_date TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    details TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES test_runs(id)
                )
            """)

            # Filing metadata cache table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS filing_metadata (
                    accession TEXT PRIMARY KEY,
                    form TEXT NOT NULL,
                    company TEXT NOT NULL,
                    cik INTEGER NOT NULL,
                    filing_date TEXT NOT NULL,
                    period_end TEXT,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_run
                ON test_results(run_id)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_status
                ON test_results(status)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_filing
                ON test_results(filing_accession)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_session
                ON test_runs(session_id)
            """)

    # Session management methods

    def create_session(self, name: str, description: Optional[str] = None,
                      tags: Optional[List[str]] = None) -> Session:
        """Create a new test session.

        Args:
            name: Session name
            description: Optional description
            tags: Optional list of tags

        Returns:
            Created Session object with ID
        """
        tags_json = json.dumps(tags) if tags else '[]'
        created_at = datetime.now()

        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO sessions (name, description, tags, created_at) VALUES (?, ?, ?, ?)",
                (name, description, tags_json, created_at.isoformat())
            )
            session_id = cursor.lastrowid

        return Session(
            id=session_id,
            name=name,
            description=description,
            tags=tags or [],
            created_at=created_at
        )

    def get_session(self, session_id: int) -> Optional[Session]:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session object or None if not found
        """
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        return Session.from_dict(dict(row)) if row else None

    def list_sessions(self, limit: int = 50) -> List[Session]:
        """List recent sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of Session objects, most recent first
        """
        cursor = self.conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [Session.from_dict(dict(row)) for row in cursor.fetchall()]

    # Test run management methods

    def create_run(self, session_id: int, name: str, test_type: str,
                   config: Dict[str, Any]) -> TestRun:
        """Create a new test run.

        Args:
            session_id: Parent session ID
            name: Run name
            test_type: Type of test ('comparison', 'validation', 'performance', 'regression')
            config: Configuration dictionary

        Returns:
            Created TestRun object with ID
        """
        config_json = json.dumps(config)
        started_at = datetime.now()

        with self.conn:
            cursor = self.conn.execute(
                """INSERT INTO test_runs
                   (session_id, name, test_type, config, started_at, status)
                   VALUES (?, ?, ?, ?, ?, 'running')""",
                (session_id, name, test_type, config_json, started_at.isoformat())
            )
            run_id = cursor.lastrowid

        return TestRun(
            id=run_id,
            session_id=session_id,
            name=name,
            test_type=test_type,
            config=config,
            started_at=started_at,
            status='running'
        )

    def update_run_status(self, run_id: int, status: str,
                         completed_at: Optional[datetime] = None):
        """Update test run status.

        Args:
            run_id: Run ID
            status: New status ('running', 'completed', 'failed')
            completed_at: Optional completion timestamp
        """
        if completed_at is None and status in ('completed', 'failed'):
            completed_at = datetime.now()

        with self.conn:
            if completed_at:
                self.conn.execute(
                    "UPDATE test_runs SET status = ?, completed_at = ? WHERE id = ?",
                    (status, completed_at.isoformat(), run_id)
                )
            else:
                self.conn.execute(
                    "UPDATE test_runs SET status = ? WHERE id = ?",
                    (status, run_id)
                )

    def get_run(self, run_id: int) -> Optional[TestRun]:
        """Get a test run by ID.

        Args:
            run_id: Run ID

        Returns:
            TestRun object or None if not found
        """
        cursor = self.conn.execute(
            "SELECT * FROM test_runs WHERE id = ?",
            (run_id,)
        )
        row = cursor.fetchone()
        return TestRun.from_dict(dict(row)) if row else None

    def list_runs(self, session_id: Optional[int] = None, limit: int = 50) -> List[TestRun]:
        """List test runs.

        Args:
            session_id: Optional session ID to filter by
            limit: Maximum number of runs to return

        Returns:
            List of TestRun objects, most recent first
        """
        if session_id:
            cursor = self.conn.execute(
                "SELECT * FROM test_runs WHERE session_id = ? ORDER BY started_at DESC LIMIT ?",
                (session_id, limit)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM test_runs ORDER BY started_at DESC LIMIT ?",
                (limit,)
            )
        return [TestRun.from_dict(dict(row)) for row in cursor.fetchall()]

    # Test result management methods

    def save_result(self, result: TestResult) -> int:
        """Save a single test result.

        Args:
            result: TestResult object

        Returns:
            Result ID
        """
        result_dict = result.to_dict()

        with self.conn:
            cursor = self.conn.execute(
                """INSERT INTO test_results
                   (run_id, filing_accession, filing_form, filing_company, filing_date,
                    test_name, status, duration_ms, details, error_message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result_dict['run_id'], result_dict['filing_accession'],
                 result_dict['filing_form'], result_dict['filing_company'],
                 result_dict['filing_date'], result_dict['test_name'],
                 result_dict['status'], result_dict['duration_ms'],
                 result_dict['details'], result_dict['error_message'],
                 result_dict['created_at'])
            )
            return cursor.lastrowid

    def save_results_batch(self, results: List[TestResult]):
        """Save multiple test results in a batch.

        Args:
            results: List of TestResult objects
        """
        if not results:
            return

        values = [
            (r.run_id, r.filing_accession, r.filing_form, r.filing_company,
             r.filing_date, r.test_name, r.status, r.duration_ms,
             json.dumps(r.details) if r.details else '{}',
             r.error_message, r.created_at.isoformat() if r.created_at else None)
            for r in results
        ]

        with self.conn:
            self.conn.executemany(
                """INSERT INTO test_results
                   (run_id, filing_accession, filing_form, filing_company, filing_date,
                    test_name, status, duration_ms, details, error_message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values
            )

    def get_results(self, run_id: int) -> List[TestResult]:
        """Get all results for a test run.

        Args:
            run_id: Run ID

        Returns:
            List of TestResult objects
        """
        cursor = self.conn.execute(
            "SELECT * FROM test_results WHERE run_id = ? ORDER BY created_at",
            (run_id,)
        )
        return [TestResult.from_dict(dict(row)) for row in cursor.fetchall()]

    def query_results(self, filters: Dict[str, Any]) -> List[TestResult]:
        """Query results with filters.

        Args:
            filters: Dictionary of field: value filters

        Returns:
            List of matching TestResult objects
        """
        where_clauses = []
        params = []

        for field, value in filters.items():
            where_clauses.append(f"{field} = ?")
            params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        query = f"SELECT * FROM test_results WHERE {where_sql} ORDER BY created_at"

        cursor = self.conn.execute(query, params)
        return [TestResult.from_dict(dict(row)) for row in cursor.fetchall()]

    # Filing metadata cache methods

    def cache_filing(self, metadata: FilingMetadata):
        """Cache filing metadata.

        Args:
            metadata: FilingMetadata object
        """
        metadata_dict = metadata.to_dict()

        with self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO filing_metadata
                   (accession, form, company, cik, filing_date, period_end, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (metadata_dict['accession'], metadata_dict['form'],
                 metadata_dict['company'], metadata_dict['cik'],
                 metadata_dict['filing_date'], metadata_dict['period_end'],
                 metadata_dict['cached_at'])
            )

    def get_filing_metadata(self, accession: str) -> Optional[FilingMetadata]:
        """Get cached filing metadata.

        Args:
            accession: Filing accession number

        Returns:
            FilingMetadata object or None if not cached
        """
        cursor = self.conn.execute(
            "SELECT * FROM filing_metadata WHERE accession = ?",
            (accession,)
        )
        row = cursor.fetchone()
        return FilingMetadata.from_dict(dict(row)) if row else None

    # Analytics methods

    def get_success_rate(self, run_id: int) -> float:
        """Calculate success rate for a test run.

        Args:
            run_id: Run ID

        Returns:
            Success rate as a float between 0.0 and 1.0
        """
        cursor = self.conn.execute(
            """SELECT
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passed
               FROM test_results
               WHERE run_id = ?""",
            (run_id,)
        )
        row = cursor.fetchone()
        total = row['total']
        passed = row['passed']
        return passed / total if total > 0 else 0.0

    def compare_runs(self, run_id1: int, run_id2: int) -> Dict[str, Any]:
        """Compare two test runs.

        Args:
            run_id1: First run ID
            run_id2: Second run ID

        Returns:
            Dictionary with comparison metrics
        """
        results1 = self.get_results(run_id1)
        results2 = self.get_results(run_id2)

        return {
            'run1': {
                'id': run_id1,
                'total': len(results1),
                'passed': sum(1 for r in results1 if r.status == 'pass'),
                'failed': sum(1 for r in results1 if r.status == 'fail'),
                'errors': sum(1 for r in results1 if r.status == 'error')
            },
            'run2': {
                'id': run_id2,
                'total': len(results2),
                'passed': sum(1 for r in results2 if r.status == 'pass'),
                'failed': sum(1 for r in results2 if r.status == 'fail'),
                'errors': sum(1 for r in results2 if r.status == 'error')
            }
        }

    def get_trends(self, test_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get historical trends for a test.

        Args:
            test_name: Test name
            limit: Maximum number of runs to include

        Returns:
            List of dictionaries with trend data
        """
        cursor = self.conn.execute(
            """SELECT
                   tr.id as run_id,
                   tr.started_at as date,
                   COUNT(*) as total,
                   SUM(CASE WHEN r.status = 'pass' THEN 1 ELSE 0 END) as passed,
                   AVG(r.duration_ms) as avg_duration
               FROM test_results r
               JOIN test_runs tr ON r.run_id = tr.id
               WHERE r.test_name = ?
               GROUP BY tr.id
               ORDER BY tr.started_at DESC
               LIMIT ?""",
            (test_name, limit)
        )

        trends = []
        for row in cursor.fetchall():
            total = row['total']
            passed = row['passed']
            trends.append({
                'run_id': row['run_id'],
                'date': row['date'],
                'total': total,
                'passed': passed,
                'success_rate': passed / total if total > 0 else 0.0,
                'avg_duration_ms': row['avg_duration']
            })

        return trends

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
