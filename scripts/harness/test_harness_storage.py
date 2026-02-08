"""Unit tests for test harness storage layer."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import os

from scripts.harness import (
    HarnessStorage,
    Session,
    TestRun,
    TestResult,
    FilingMetadata
)


@pytest.fixture
def storage():
    """Create in-memory storage for testing."""
    return HarnessStorage(":memory:")


@pytest.fixture
def temp_storage():
    """Create temporary file-based storage for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_harness.db"
        yield HarnessStorage(db_path)


class TestHarnessStorage:
    """Test harness storage functionality."""

    def test_create_in_memory_storage(self):
        """Test creating in-memory storage."""
        storage = HarnessStorage(":memory:")
        assert storage.db_path == ":memory:"
        assert storage.conn is not None

    def test_create_file_storage(self, tmp_path):
        """Test creating file-based storage."""
        db_path = tmp_path / "harness.db"
        storage = HarnessStorage(db_path)
        assert storage.db_path == db_path
        assert db_path.exists()
        storage.close()

    def test_default_storage_location(self):
        """Test default storage location."""
        storage = HarnessStorage()
        expected_path = Path("~/.edgar_test/harness.db").expanduser()
        assert storage.db_path == expected_path
        storage.close()
        # Clean up
        if expected_path.exists():
            expected_path.unlink()
            expected_path.parent.rmdir()

    def test_schema_creation(self, storage):
        """Test database schema is created."""
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert 'sessions' in tables
        assert 'test_runs' in tables
        assert 'test_results' in tables
        assert 'filing_metadata' in tables

    def test_indexes_created(self, storage):
        """Test indexes are created."""
        cursor = storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert 'idx_results_run' in indexes
        assert 'idx_results_status' in indexes
        assert 'idx_results_filing' in indexes
        assert 'idx_runs_session' in indexes


class TestSessionManagement:
    """Test session CRUD operations."""

    def test_create_session(self, storage):
        """Test creating a session."""
        session = storage.create_session(
            name="Test Session",
            description="A test session",
            tags=["test", "v1.0"]
        )
        assert session.id is not None
        assert session.name == "Test Session"
        assert session.description == "A test session"
        assert session.tags == ["test", "v1.0"]
        assert session.created_at is not None

    def test_create_session_minimal(self, storage):
        """Test creating session with minimal parameters."""
        session = storage.create_session(name="Minimal Session")
        assert session.id is not None
        assert session.name == "Minimal Session"
        assert session.description is None
        assert session.tags == []

    def test_get_session(self, storage):
        """Test retrieving a session by ID."""
        created = storage.create_session(name="Get Test")
        retrieved = storage.get_session(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_nonexistent_session(self, storage):
        """Test retrieving nonexistent session returns None."""
        result = storage.get_session(99999)
        assert result is None

    def test_list_sessions(self, storage):
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(5):
            storage.create_session(name=f"Session {i}")

        sessions = storage.list_sessions(limit=10)
        assert len(sessions) == 5
        # Should be ordered by most recent first
        assert sessions[0].name == "Session 4"
        assert sessions[4].name == "Session 0"

    def test_list_sessions_with_limit(self, storage):
        """Test listing sessions respects limit."""
        for i in range(10):
            storage.create_session(name=f"Session {i}")

        sessions = storage.list_sessions(limit=3)
        assert len(sessions) == 3


class TestRunManagement:
    """Test test run CRUD operations."""

    def test_create_run(self, storage):
        """Test creating a test run."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(
            session_id=session.id,
            name="Test Run",
            test_type="comparison",
            config={"form": "10-K", "sample": 10}
        )
        assert run.id is not None
        assert run.session_id == session.id
        assert run.name == "Test Run"
        assert run.test_type == "comparison"
        assert run.config == {"form": "10-K", "sample": 10}
        assert run.status == "running"
        assert run.started_at is not None

    def test_update_run_status(self, storage):
        """Test updating run status."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        storage.update_run_status(run.id, "completed")
        updated = storage.get_run(run.id)
        assert updated.status == "completed"
        assert updated.completed_at is not None

    def test_update_run_status_with_timestamp(self, storage):
        """Test updating run status with custom timestamp."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        storage.update_run_status(run.id, "completed", completed_at=custom_time)

        updated = storage.get_run(run.id)
        assert updated.status == "completed"
        assert updated.completed_at.date() == custom_time.date()

    def test_get_run(self, storage):
        """Test retrieving a run by ID."""
        session = storage.create_session(name="Test Session")
        created = storage.create_run(session.id, "Test Run", "performance", {})

        retrieved = storage.get_run(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_list_runs_all(self, storage):
        """Test listing all runs."""
        session = storage.create_session(name="Test Session")
        for i in range(3):
            storage.create_run(session.id, f"Run {i}", "validation", {})

        runs = storage.list_runs()
        assert len(runs) == 3

    def test_list_runs_by_session(self, storage):
        """Test listing runs filtered by session."""
        session1 = storage.create_session(name="Session 1")
        session2 = storage.create_session(name="Session 2")

        storage.create_run(session1.id, "Run 1", "validation", {})
        storage.create_run(session1.id, "Run 2", "validation", {})
        storage.create_run(session2.id, "Run 3", "validation", {})

        runs_s1 = storage.list_runs(session_id=session1.id)
        runs_s2 = storage.list_runs(session_id=session2.id)

        assert len(runs_s1) == 2
        assert len(runs_s2) == 1


class TestResultManagement:
    """Test test result CRUD operations."""

    def test_save_result(self, storage):
        """Test saving a test result."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        result = TestResult(
            run_id=run.id,
            filing_accession="0001234567-24-000001",
            filing_form="10-K",
            filing_company="Test Corp",
            filing_date="2024-01-01",
            test_name="validation_test",
            status="pass",
            duration_ms=150.5,
            details={"items_found": 5}
        )

        result_id = storage.save_result(result)
        assert result_id is not None

    def test_save_result_with_error(self, storage):
        """Test saving a failed result with error message."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        result = TestResult(
            run_id=run.id,
            filing_accession="0001234567-24-000002",
            filing_form="10-Q",
            filing_company="Test Corp",
            filing_date="2024-02-01",
            test_name="validation_test",
            status="error",
            error_message="Connection timeout"
        )

        result_id = storage.save_result(result)
        assert result_id is not None

        # Verify error message was saved
        results = storage.get_results(run.id)
        assert results[0].error_message == "Connection timeout"

    def test_save_results_batch(self, storage):
        """Test batch saving of results."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        results = [
            TestResult(
                run_id=run.id,
                filing_accession=f"000123456-24-00000{i}",
                filing_form="10-K",
                filing_company=f"Company {i}",
                filing_date="2024-01-01",
                test_name="batch_test",
                status="pass"
            )
            for i in range(10)
        ]

        storage.save_results_batch(results)

        saved = storage.get_results(run.id)
        assert len(saved) == 10

    def test_get_results(self, storage):
        """Test retrieving results for a run."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        # Save multiple results
        for i in range(5):
            result = TestResult(
                run_id=run.id,
                filing_accession=f"000123456-24-00000{i}",
                filing_form="10-K",
                filing_company=f"Company {i}",
                filing_date="2024-01-01",
                test_name="test",
                status="pass"
            )
            storage.save_result(result)

        results = storage.get_results(run.id)
        assert len(results) == 5

    def test_query_results(self, storage):
        """Test querying results with filters."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        # Save results with different statuses
        for status in ['pass', 'fail', 'error']:
            result = TestResult(
                run_id=run.id,
                filing_accession=f"000123456-24-{status}",
                filing_form="10-K",
                filing_company="Test Corp",
                filing_date="2024-01-01",
                test_name="test",
                status=status
            )
            storage.save_result(result)

        # Query for failures
        failures = storage.query_results({'status': 'fail'})
        assert len(failures) == 1
        assert failures[0].status == 'fail'


class TestFilingMetadataCache:
    """Test filing metadata caching."""

    def test_cache_filing(self, storage):
        """Test caching filing metadata."""
        metadata = FilingMetadata(
            accession="0001234567-24-000001",
            form="10-K",
            company="Test Corp",
            cik=1234567,
            filing_date="2024-01-01",
            period_end="2023-12-31"
        )

        storage.cache_filing(metadata)

        # Verify it was cached
        cached = storage.get_filing_metadata(metadata.accession)
        assert cached is not None
        assert cached.accession == metadata.accession
        assert cached.form == metadata.form
        assert cached.company == metadata.company

    def test_cache_filing_overwrite(self, storage):
        """Test that caching updates existing entries."""
        accession = "0001234567-24-000001"

        # Cache initial metadata
        metadata1 = FilingMetadata(
            accession=accession,
            form="10-K",
            company="Test Corp",
            cik=1234567,
            filing_date="2024-01-01"
        )
        storage.cache_filing(metadata1)

        # Update with new data
        metadata2 = FilingMetadata(
            accession=accession,
            form="10-K",
            company="Test Corp Updated",
            cik=1234567,
            filing_date="2024-01-01"
        )
        storage.cache_filing(metadata2)

        # Should have updated company name
        cached = storage.get_filing_metadata(accession)
        assert cached.company == "Test Corp Updated"

    def test_get_nonexistent_filing_metadata(self, storage):
        """Test retrieving nonexistent filing metadata returns None."""
        result = storage.get_filing_metadata("0000000000-00-000000")
        assert result is None


class TestAnalytics:
    """Test analytics methods."""

    def test_get_success_rate(self, storage):
        """Test calculating success rate."""
        session = storage.create_session(name="Test Session")
        run = storage.create_run(session.id, "Test Run", "validation", {})

        # Save 7 pass, 2 fail, 1 error = 70% success rate
        for i in range(7):
            storage.save_result(TestResult(
                run_id=run.id,
                filing_accession=f"pass-{i}",
                filing_form="10-K",
                filing_company="Test",
                filing_date="2024-01-01",
                test_name="test",
                status="pass"
            ))

        for i in range(2):
            storage.save_result(TestResult(
                run_id=run.id,
                filing_accession=f"fail-{i}",
                filing_form="10-K",
                filing_company="Test",
                filing_date="2024-01-01",
                test_name="test",
                status="fail"
            ))

        storage.save_result(TestResult(
            run_id=run.id,
            filing_accession="error-0",
            filing_form="10-K",
            filing_company="Test",
            filing_date="2024-01-01",
            test_name="test",
            status="error"
        ))

        success_rate = storage.get_success_rate(run.id)
        assert success_rate == 0.7

    def test_compare_runs(self, storage):
        """Test comparing two runs."""
        session = storage.create_session(name="Test Session")
        run1 = storage.create_run(session.id, "Run 1", "validation", {})
        run2 = storage.create_run(session.id, "Run 2", "validation", {})

        # Run 1: 8 pass, 2 fail
        for i in range(8):
            storage.save_result(TestResult(
                run_id=run1.id,
                filing_accession=f"r1-{i}",
                filing_form="10-K",
                filing_company="Test",
                filing_date="2024-01-01",
                test_name="test",
                status="pass"
            ))
        for i in range(2):
            storage.save_result(TestResult(
                run_id=run1.id,
                filing_accession=f"r1-fail-{i}",
                filing_form="10-K",
                filing_company="Test",
                filing_date="2024-01-01",
                test_name="test",
                status="fail"
            ))

        # Run 2: 6 pass, 3 fail, 1 error
        for i in range(6):
            storage.save_result(TestResult(
                run_id=run2.id,
                filing_accession=f"r2-{i}",
                filing_form="10-K",
                filing_company="Test",
                filing_date="2024-01-01",
                test_name="test",
                status="pass"
            ))
        for i in range(3):
            storage.save_result(TestResult(
                run_id=run2.id,
                filing_accession=f"r2-fail-{i}",
                filing_form="10-K",
                filing_company="Test",
                filing_date="2024-01-01",
                test_name="test",
                status="fail"
            ))
        storage.save_result(TestResult(
            run_id=run2.id,
            filing_accession="r2-error",
            filing_form="10-K",
            filing_company="Test",
            filing_date="2024-01-01",
            test_name="test",
            status="error"
        ))

        comparison = storage.compare_runs(run1.id, run2.id)

        assert comparison['run1']['total'] == 10
        assert comparison['run1']['passed'] == 8
        assert comparison['run1']['failed'] == 2

        assert comparison['run2']['total'] == 10
        assert comparison['run2']['passed'] == 6
        assert comparison['run2']['failed'] == 3
        assert comparison['run2']['errors'] == 1

    def test_get_trends(self, storage):
        """Test getting historical trends."""
        session = storage.create_session(name="Test Session")

        # Create 3 runs with different success rates
        for run_num in range(3):
            run = storage.create_run(session.id, f"Run {run_num}", "validation", {})

            # Decreasing success rate: 100%, 80%, 60%
            passes = 10 - (run_num * 2)
            fails = run_num * 2

            for i in range(passes):
                storage.save_result(TestResult(
                    run_id=run.id,
                    filing_accession=f"r{run_num}-pass-{i}",
                    filing_form="10-K",
                    filing_company="Test",
                    filing_date="2024-01-01",
                    test_name="trend_test",
                    status="pass",
                    duration_ms=100.0
                ))

            for i in range(fails):
                storage.save_result(TestResult(
                    run_id=run.id,
                    filing_accession=f"r{run_num}-fail-{i}",
                    filing_form="10-K",
                    filing_company="Test",
                    filing_date="2024-01-01",
                    test_name="trend_test",
                    status="fail",
                    duration_ms=100.0
                ))

        trends = storage.get_trends("trend_test", limit=10)

        assert len(trends) == 3
        # Most recent first
        assert trends[0]['success_rate'] == 0.6
        assert trends[1]['success_rate'] == 0.8
        assert trends[2]['success_rate'] == 1.0


class TestContextManager:
    """Test storage context manager functionality."""

    def test_context_manager(self, tmp_path):
        """Test storage can be used as context manager."""
        db_path = tmp_path / "context_test.db"

        with HarnessStorage(db_path) as storage:
            session = storage.create_session(name="Context Test")
            assert session.id is not None

        # Database should still exist after context exit
        assert db_path.exists()
