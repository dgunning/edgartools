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

from edgar_warehouse.runtime import StorageLocation, WarehouseRuntimeError, _filter_ciks_to_universe
from edgar_warehouse.silver import SilverDatabase

_FAKE_SHA256 = "deadbeef" * 8  # 64-char hex string, valid SHA-256 length


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
        "raw_object_id": _FAKE_SHA256,
        "last_sha256": _FAKE_SHA256,
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
    db = SilverDatabase(str(tmp_path / "silver.duckdb"))
    db.seed_tracked_universe({
        "0": {"cik_str": 320193, "ticker": "AAPL", "exchange": "Nasdaq", "name": "Apple Inc."}
    })
    impacted = [320193, 789019, 1045810]
    result = _filter_ciks_to_universe(impacted, db)
    assert result == [320193]


@pytest.mark.fast
def test_filter_ciks_cold_start_fallthrough(tmp_path):
    """Empty tracked universe must not filter out CIKs (cold-start safety)."""
    db = SilverDatabase(str(tmp_path / "silver.duckdb"))
    # Universe is empty - nothing seeded
    impacted = [320193, 789019]
    result = _filter_ciks_to_universe(impacted, db)
    assert result == [320193, 789019]


@pytest.mark.fast
def test_filter_ciks_none_db_fallthrough():
    """None db (remote storage) must return all CIKs unchanged."""
    result = _filter_ciks_to_universe([320193, 789019], None)
    assert result == [320193, 789019]


# --- stg_daily_index_filing ---

from edgar_warehouse.loaders import stage_daily_index_filing_loader  # noqa: E402

_DAILY_IDX_PAYLOAD = b"""Form Type           Company Name                     CIK         Date Filed  Filename
--------------------------------------------------------------------------------
10-K                APPLE INC                        0000320193  20241101    edgar/data/320193/0000320193-24-000123-index.htm
SC 13G/A            VANGUARD GROUP INC               0000092380  20241101    edgar/data/92380/0000092380-24-000456-index.htm
8-K                 MICROSOFT CORP                   0000789019  20241101    edgar/data/789019/0000789019-24-000789-index.htm
"""
_DAILY_IDX_DATE = date(2024, 11, 1)
_DAILY_IDX_SYNC_RUN_ID = "run-daily-001"
_DAILY_IDX_RAW_OBJECT_ID = "raw-daily-001"
_DAILY_IDX_SOURCE_URL = "https://www.sec.gov/Archives/edgar/daily-index/2024/QTR4/form.20241101.idx"


def _load_daily_idx_rows():
    return stage_daily_index_filing_loader(
        payload=_DAILY_IDX_PAYLOAD,
        business_date=_DAILY_IDX_DATE,
        sync_run_id=_DAILY_IDX_SYNC_RUN_ID,
        raw_object_id=_DAILY_IDX_RAW_OBJECT_ID,
        source_url=_DAILY_IDX_SOURCE_URL,
    )


@pytest.mark.fast
def test_stage_daily_index_filing_loader_row_count():
    rows = _load_daily_idx_rows()
    assert len(rows) == 3


@pytest.mark.fast
def test_stage_daily_index_filing_loader_accession_number():
    rows = _load_daily_idx_rows()
    assert rows[0]["accession_number"] == "0000320193-24-000123"


@pytest.mark.fast
def test_stage_daily_index_filing_loader_row_ordinal():
    rows = _load_daily_idx_rows()
    assert [r["row_ordinal"] for r in rows] == [1, 2, 3]


@pytest.mark.fast
def test_stage_daily_index_filing_loader_source_year_quarter():
    rows = _load_daily_idx_rows()
    assert rows[0]["source_year"] == 2024
    assert rows[0]["source_quarter"] == 4


@pytest.mark.fast
def test_stage_daily_index_filing_loader_cik():
    rows = _load_daily_idx_rows()
    assert rows[0]["cik"] == 320193


@pytest.mark.fast
def test_stage_daily_index_filing_loader_form():
    rows = _load_daily_idx_rows()
    assert rows[0]["form"] == "10-K"


@pytest.mark.fast
def test_stage_daily_index_filing_loader_filing_txt_url():
    rows = _load_daily_idx_rows()
    assert rows[0]["filing_txt_url"] == "https://www.sec.gov/Archives/edgar/data/320193/0000320193-24-000123-index.htm"


@pytest.mark.fast
def test_merge_daily_index_filings_row_count(db):
    rows = _load_daily_idx_rows()
    db.merge_daily_index_filings(rows, _DAILY_IDX_SYNC_RUN_ID)
    result = db.get_daily_index_filings("2024-11-01")
    assert len(result) == 3


@pytest.mark.fast
def test_merge_daily_index_filings_idempotent(db):
    rows = _load_daily_idx_rows()
    db.merge_daily_index_filings(rows, _DAILY_IDX_SYNC_RUN_ID)
    db.merge_daily_index_filings(rows, _DAILY_IDX_SYNC_RUN_ID)
    result = db.get_daily_index_filings("2024-11-01")
    assert len(result) == 3


@pytest.mark.fast
def test_merge_daily_index_filings_accession_stored(db):
    rows = _load_daily_idx_rows()
    db.merge_daily_index_filings(rows, _DAILY_IDX_SYNC_RUN_ID)
    result = db.get_daily_index_filings("2024-11-01")
    accessions = {r["accession_number"] for r in result}
    assert "0000320193-24-000123" in accessions


@pytest.mark.fast
def test_stage_daily_index_filing_loader_source_name():
    rows = stage_daily_index_filing_loader(
        _DAILY_IDX_PAYLOAD, _DAILY_IDX_DATE, _DAILY_IDX_SYNC_RUN_ID,
        _DAILY_IDX_RAW_OBJECT_ID, _DAILY_IDX_SOURCE_URL,
    )
    for row in rows:
        assert row["source_name"] == "daily_form_index"


@pytest.mark.fast
def test_stage_daily_index_filing_loader_record_hash():
    import hashlib
    rows = stage_daily_index_filing_loader(
        _DAILY_IDX_PAYLOAD, _DAILY_IDX_DATE, _DAILY_IDX_SYNC_RUN_ID,
        _DAILY_IDX_RAW_OBJECT_ID, _DAILY_IDX_SOURCE_URL,
    )
    row = rows[0]
    # Derive expected hash using same logic as loader
    hash_input = f"{row['form']}|{row['company_name']}|{row['cik']}|{row['filing_date']}|{row['file_name']}"
    expected = hashlib.sha256(hash_input.encode()).hexdigest()
    assert row["record_hash"] == expected
