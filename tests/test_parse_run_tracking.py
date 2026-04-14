"""
Verify sec_parse_run lifecycle tracking.
Fast tests only - no network calls.
"""
import pytest
from datetime import datetime
from edgar_warehouse.silver import SilverDatabase

@pytest.fixture
def db(tmp_path):
    return SilverDatabase(str(tmp_path / "silver.duckdb"))

_BASE_RUN = {
    "parse_run_id": "run-001",
    "parser_name": "generic_text_v1",
    "parser_version": "1.0.0",
    "target_form_family": "10-K",
    "accession_number": "0000320193-24-000123",
}

@pytest.mark.fast
def test_start_parse_run_status_running(db):
    db.start_parse_run(_BASE_RUN)
    row = db.get_parse_run("run-001")
    assert row is not None
    assert row["status"] == "running"

@pytest.mark.fast
def test_start_parse_run_started_at_set(db):
    db.start_parse_run(_BASE_RUN)
    row = db.get_parse_run("run-001")
    assert row["started_at"] is not None

@pytest.mark.fast
def test_complete_parse_run_succeeded(db):
    db.start_parse_run(_BASE_RUN)
    db.complete_parse_run("run-001", status="succeeded")
    row = db.get_parse_run("run-001")
    assert row["status"] == "succeeded"

@pytest.mark.fast
def test_complete_parse_run_failed_with_error(db):
    db.start_parse_run(_BASE_RUN)
    db.complete_parse_run("run-001", status="failed", error_code="E001", error_message="parse error")
    row = db.get_parse_run("run-001")
    assert row["status"] == "failed"
    assert row["error_code"] == "E001"
    assert row["error_message"] == "parse error"

@pytest.mark.fast
def test_complete_parse_run_sets_completed_at(db):
    db.start_parse_run(_BASE_RUN)
    db.complete_parse_run("run-001")
    row = db.get_parse_run("run-001")
    assert row["completed_at"] is not None

@pytest.mark.fast
def test_start_parse_run_unique_ids(db):
    run_a = dict(_BASE_RUN, parse_run_id="run-a")
    run_b = dict(_BASE_RUN, parse_run_id="run-b")
    db.start_parse_run(run_a)
    db.start_parse_run(run_b)
    assert db.get_parse_run("run-a") is not None
    assert db.get_parse_run("run-b") is not None

@pytest.mark.fast
def test_get_parse_run_returns_none_for_unknown(db):
    result = db.get_parse_run("does-not-exist")
    assert result is None

@pytest.mark.fast
def test_start_parse_run_raises_on_missing_parser_name(db):
    bad = {k: v for k, v in _BASE_RUN.items() if k != "parser_name"}
    with pytest.raises(ValueError):
        db.start_parse_run(bad)

@pytest.mark.fast
def test_start_parse_run_raises_on_missing_parse_run_id(db):
    bad = {k: v for k, v in _BASE_RUN.items() if k != "parse_run_id"}
    with pytest.raises(ValueError):
        db.start_parse_run(bad)

@pytest.mark.fast
def test_complete_parse_run_raises_on_empty_id(db):
    with pytest.raises(ValueError):
        db.complete_parse_run("")
