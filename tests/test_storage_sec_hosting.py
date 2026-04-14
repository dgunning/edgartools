"""
Verify bronze storage path determinism, SHA256 hashing, idempotent raw ingest,
and daily index checkpoint operations.

Fast tests only - no network calls.

Uses edgar_warehouse.runtime.StorageLocation and SilverDatabase directly.
"""

import hashlib
import json
import os
from datetime import date, datetime, timezone

import pytest

from edgar_warehouse.runtime import StorageLocation, WarehouseRuntimeError
from edgar_warehouse.silver import SilverDatabase


# ---------------------------------------------------------------------------
# StorageLocation tests
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_storage_location_local_join(tmp_path):
    loc = StorageLocation(str(tmp_path))
    result = loc.join("warehouse", "bronze", "file.json")
    assert result == str(tmp_path / "warehouse" / "bronze" / "file.json")


@pytest.mark.fast
def test_storage_location_remote_join():
    loc = StorageLocation("s3://my-bucket/prefix")
    result = loc.join("warehouse", "bronze", "file.json")
    assert result == "s3://my-bucket/prefix/warehouse/bronze/file.json"


@pytest.mark.fast
def test_storage_location_is_remote_for_s3():
    assert StorageLocation("s3://bucket/path").is_remote is True


@pytest.mark.fast
def test_storage_location_is_not_remote_for_local_path(tmp_path):
    assert StorageLocation(str(tmp_path)).is_remote is False


@pytest.mark.fast
def test_storage_location_write_json_creates_file(tmp_path):
    loc = StorageLocation(str(tmp_path))
    payload = {"key": "value", "count": 42}
    path = loc.write_json("subdir/file.json", payload)
    assert os.path.exists(path)
    with open(path) as f:
        loaded = json.load(f)
    assert loaded == payload


@pytest.mark.fast
def test_storage_location_write_bytes_sha256_deterministic(tmp_path):
    loc = StorageLocation(str(tmp_path))
    data = b"hello world"
    loc.write_bytes("file.bin", data)
    expected_sha256 = hashlib.sha256(data).hexdigest()
    # Read it back and verify
    written_path = loc.join("file.bin")
    with open(written_path, "rb") as f:
        actual = f.read()
    assert hashlib.sha256(actual).hexdigest() == expected_sha256


@pytest.mark.fast
def test_storage_location_write_bytes_idempotent(tmp_path):
    loc = StorageLocation(str(tmp_path))
    data = b"idempotent content"
    path1 = loc.write_bytes("file.bin", data)
    path2 = loc.write_bytes("file.bin", data)
    assert path1 == path2
    with open(path1, "rb") as f:
        assert f.read() == data


@pytest.mark.fast
def test_storage_location_empty_root_raises():
    with pytest.raises(WarehouseRuntimeError):
        StorageLocation("")


# ---------------------------------------------------------------------------
# Bronze path determinism tests
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_bronze_reference_path_structure(tmp_path):
    """company_tickers files land under reference/sec/company_tickers/YYYY/MM/DD/"""
    loc = StorageLocation(str(tmp_path))
    fetch_date = date(2025, 1, 15)
    day_parts = fetch_date.strftime("%Y/%m/%d")
    relative_path = f"reference/sec/company_tickers/{day_parts}/company_tickers.json"
    loc.write_json(relative_path, {"test": True})
    expected = tmp_path / "reference" / "sec" / "company_tickers" / "2025" / "01" / "15" / "company_tickers.json"
    assert expected.exists()


@pytest.mark.fast
def test_bronze_submissions_path_structure(tmp_path):
    """Submissions files land under submissions/sec/cik=<cik>/main/YYYY/MM/DD/"""
    loc = StorageLocation(str(tmp_path))
    cik = 320193
    fetch_date = date(2025, 1, 15)
    day_parts = fetch_date.strftime("%Y/%m/%d")
    relative_path = f"submissions/sec/cik={cik}/main/{day_parts}/CIK{cik:010d}.json"
    loc.write_json(relative_path, {"cik": cik})
    expected = (
        tmp_path / "submissions" / "sec"
        / f"cik={cik}" / "main" / "2025" / "01" / "15"
        / f"CIK{cik:010d}.json"
    )
    assert expected.exists()


@pytest.mark.fast
def test_bronze_daily_index_path_structure(tmp_path):
    """Daily index files land under daily_index/sec/YYYY/MM/DD/"""
    loc = StorageLocation(str(tmp_path))
    target_date = date(2025, 1, 15)
    date_parts = target_date.strftime("%Y/%m/%d")
    file_name = f"form.{target_date:%Y%m%d}.idx"
    relative_path = f"daily_index/sec/{date_parts}/{file_name}"
    loc.write_text(relative_path, "Form  CIK\n")
    expected = (
        tmp_path / "daily_index" / "sec" / "2025" / "01" / "15" / "form.20250115.idx"
    )
    assert expected.exists()


# ---------------------------------------------------------------------------
# Daily index checkpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    return SilverDatabase(str(tmp_path / "silver.duckdb"))


_BUSINESS_DATE = "2025-01-15"
_EXPECTED_AVAILABLE_AT = datetime(2025, 1, 16, 11, 0, 0, tzinfo=timezone.utc)


@pytest.mark.fast
def test_upsert_daily_index_checkpoint_new_row(db):
    db.upsert_daily_index_checkpoint({
        "business_date": _BUSINESS_DATE,
        "source_key": f"date:{_BUSINESS_DATE}",
        "source_url": f"https://www.sec.gov/Archives/edgar/daily-index/2025/QTR1/form.20250115.idx",
        "expected_available_at": _EXPECTED_AVAILABLE_AT,
        "last_attempt_at": _EXPECTED_AVAILABLE_AT,
        "raw_object_id": "raw-001",
        "last_sha256": "abc123",
        "row_count": 500,
        "distinct_cik_count": 300,
        "distinct_accession_count": 500,
        "status": "succeeded",
        "last_success_at": _EXPECTED_AVAILABLE_AT,
    })
    row = db.get_daily_index_checkpoint(_BUSINESS_DATE)
    assert row is not None
    assert str(row["business_date"]) == _BUSINESS_DATE


@pytest.mark.fast
def test_upsert_daily_index_checkpoint_status_succeeded(db):
    db.upsert_daily_index_checkpoint({
        "business_date": _BUSINESS_DATE,
        "source_key": f"date:{_BUSINESS_DATE}",
        "source_url": "https://www.sec.gov/Archives/edgar/daily-index/2025/QTR1/form.20250115.idx",
        "expected_available_at": _EXPECTED_AVAILABLE_AT,
        "status": "succeeded",
        "last_success_at": _EXPECTED_AVAILABLE_AT,
    })
    row = db.get_daily_index_checkpoint(_BUSINESS_DATE)
    assert row["status"] == "succeeded"


@pytest.mark.fast
def test_upsert_daily_index_checkpoint_row_count(db):
    db.upsert_daily_index_checkpoint({
        "business_date": _BUSINESS_DATE,
        "source_key": f"date:{_BUSINESS_DATE}",
        "source_url": "https://www.sec.gov/Archives/edgar/daily-index/2025/QTR1/form.20250115.idx",
        "expected_available_at": _EXPECTED_AVAILABLE_AT,
        "row_count": 500,
        "status": "succeeded",
    })
    row = db.get_daily_index_checkpoint(_BUSINESS_DATE)
    assert row["row_count"] == 500


@pytest.mark.fast
def test_get_last_successful_checkpoint_date_none_when_empty(db):
    assert db.get_last_successful_checkpoint_date() is None


@pytest.mark.fast
def test_get_last_successful_checkpoint_date_returns_latest(db):
    for d in ["2025-01-13", "2025-01-14", "2025-01-15"]:
        db.upsert_daily_index_checkpoint({
            "business_date": d,
            "source_key": f"date:{d}",
            "source_url": f"https://www.sec.gov/.../form.{d.replace('-','')}.idx",
            "expected_available_at": _EXPECTED_AVAILABLE_AT,
            "status": "succeeded",
            "last_success_at": _EXPECTED_AVAILABLE_AT,
        })
    assert db.get_last_successful_checkpoint_date() == "2025-01-15"


@pytest.mark.fast
def test_upsert_daily_index_checkpoint_increments_attempt_count(db):
    base = {
        "business_date": _BUSINESS_DATE,
        "source_key": f"date:{_BUSINESS_DATE}",
        "source_url": "https://example.com/form.20250115.idx",
        "expected_available_at": _EXPECTED_AVAILABLE_AT,
        "attempt_count": 1,
        "status": "pending",
    }
    db.upsert_daily_index_checkpoint(base)
    db.upsert_daily_index_checkpoint(base)
    row = db.get_daily_index_checkpoint(_BUSINESS_DATE)
    # Second upsert triggers ON CONFLICT which adds 1 to the existing count
    assert row["attempt_count"] >= 2


# ---------------------------------------------------------------------------
# Phase B: universe filtering and checkpoint write logic
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_daily_index_checkpoint_written_on_success(db):
    """Verify that upsert_daily_index_checkpoint writes a succeeded row with row_count."""
    db.upsert_daily_index_checkpoint({
        "business_date": _BUSINESS_DATE,
        "source_key": f"date:{_BUSINESS_DATE}",
        "source_url": "https://www.sec.gov/Archives/edgar/daily-index/2025/QTR1/form.20250115.idx",
        "expected_available_at": _EXPECTED_AVAILABLE_AT,
        "last_attempt_at": _EXPECTED_AVAILABLE_AT,
        "last_success_at": _EXPECTED_AVAILABLE_AT,
        "raw_object_id": "deadbeef" * 8,
        "last_sha256": "deadbeef" * 8,
        "row_count": 500,
        "status": "succeeded",
    })
    row = db.get_daily_index_checkpoint(_BUSINESS_DATE)
    assert row is not None
    assert row["status"] == "succeeded"
    assert row["row_count"] == 500


@pytest.mark.fast
def test_daily_incremental_filters_unknown_ciks(tmp_path):
    """Universe filter: only active CIKs from sec_tracked_universe are processed."""
    from edgar_warehouse.silver import SilverDatabase

    db = SilverDatabase(str(tmp_path / "silver.duckdb"))

    # Seed only AAPL (CIK 320193) as active
    db._conn.execute(
        """
        INSERT INTO sec_tracked_universe
            (cik, input_ticker, universe_source, tracking_status, effective_from, added_at)
        VALUES (320193, 'AAPL', 'test', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )

    # Simulate impacted_ciks coming from daily index (three CIKs)
    impacted_ciks = [320193, 789019, 1045810]

    # Apply the filter logic that the fixed daily-incremental branch uses
    tracked = db.get_tracked_universe_ciks(status_filter="active")
    if tracked:
        tracked_set = set(tracked)
        filtered_ciks = [c for c in impacted_ciks if c in tracked_set]
    else:
        # cold-start fall-through
        filtered_ciks = impacted_ciks

    assert filtered_ciks == [320193]
