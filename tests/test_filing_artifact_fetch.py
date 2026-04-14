"""
Verify sec_raw_object and sec_filing_attachment silver operations.
Fast tests only - no network calls.
"""
import pytest
from datetime import datetime, timezone
from edgar_warehouse.silver import SilverDatabase

_NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_ACCESSION = "0000320193-24-000123"
_RAW_OBJECT_ID = "sha256-abc123"

_RAW_OBJ_ROW = {
    "raw_object_id": _RAW_OBJECT_ID,
    "source_type": "submissions",
    "cik": 320193,
    "accession_number": _ACCESSION,
    "form": "10-K",
    "source_url": "https://data.sec.gov/submissions/CIK0000320193.json",
    "storage_path": "submissions/sec/cik=320193/main/2025/01/15/CIK0000320193.json",
    "sha256": "sha256-abc123",
    "fetched_at": _NOW,
    "http_status": 200,
}

_ATTACHMENT_ROWS = [
    {
        "accession_number": _ACCESSION,
        "document_name": "aapl-20240928.htm",
        "document_type": "10-K",
        "document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
        "is_primary": True,
    },
    {
        "accession_number": _ACCESSION,
        "document_name": "R1.htm",
        "document_type": "EX-101.SCH",
        "document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/R1.htm",
        "is_primary": False,
    },
]


@pytest.fixture
def db(tmp_path):
    return SilverDatabase(str(tmp_path / "silver.duckdb"))


# ------------------------------------------------------------------
# sec_raw_object tests
# ------------------------------------------------------------------


@pytest.mark.fast
def test_upsert_raw_object_new_row(db):
    db.upsert_raw_object(_RAW_OBJ_ROW)
    result = db.get_raw_object(_RAW_OBJECT_ID)
    assert result is not None
    assert result["sha256"] == "sha256-abc123"


@pytest.mark.fast
def test_upsert_raw_object_idempotent(db):
    db.upsert_raw_object(_RAW_OBJ_ROW)
    db.upsert_raw_object(_RAW_OBJ_ROW)
    result = db.get_raw_object(_RAW_OBJECT_ID)
    assert result is not None
    assert result["sha256"] == "sha256-abc123"
    count = db._conn.execute(
        "SELECT COUNT(*) FROM sec_raw_object WHERE raw_object_id = ?",
        [_RAW_OBJECT_ID],
    ).fetchone()[0]
    assert count == 1


@pytest.mark.fast
def test_upsert_raw_object_updates_mutable_fields(db):
    row_v1 = dict(_RAW_OBJ_ROW, sha256="hash-v1")
    db.upsert_raw_object(row_v1)
    row_v2 = dict(_RAW_OBJ_ROW, sha256="hash-v2")
    db.upsert_raw_object(row_v2)
    result = db.get_raw_object(_RAW_OBJECT_ID)
    assert result["sha256"] == "hash-v2"


@pytest.mark.fast
def test_upsert_raw_object_retains_fetched_at(db):
    db.upsert_raw_object(_RAW_OBJ_ROW)
    later_row = dict(_RAW_OBJ_ROW, fetched_at=datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc))
    db.upsert_raw_object(later_row)
    result = db.get_raw_object(_RAW_OBJECT_ID)
    # fetched_at must remain the original value
    fetched = result["fetched_at"]
    # compare as UTC-aware datetimes; DuckDB may return tz-aware or naive
    if fetched.tzinfo is None:
        from datetime import timezone as tz
        fetched = fetched.replace(tzinfo=tz.utc)
    assert fetched == _NOW


@pytest.mark.fast
def test_get_raw_object_returns_none_for_unknown(db):
    result = db.get_raw_object("not-found")
    assert result is None


# ------------------------------------------------------------------
# sec_filing_attachment tests
# ------------------------------------------------------------------


@pytest.mark.fast
def test_merge_filing_attachments_row_count(db):
    count = db.merge_filing_attachments(_ATTACHMENT_ROWS, sync_run_id="run-001")
    assert count == 2
    results = db.get_filing_attachments(_ACCESSION)
    assert len(results) == 2


@pytest.mark.fast
def test_merge_filing_attachments_idempotent(db):
    db.merge_filing_attachments(_ATTACHMENT_ROWS, sync_run_id="run-001")
    db.merge_filing_attachments(_ATTACHMENT_ROWS, sync_run_id="run-002")
    results = db.get_filing_attachments(_ACCESSION)
    assert len(results) == 2


@pytest.mark.fast
def test_merge_filing_attachments_is_primary_set(db):
    db.merge_filing_attachments(_ATTACHMENT_ROWS, sync_run_id="run-001")
    results = db.get_filing_attachments(_ACCESSION)
    primary_rows = [r for r in results if r["document_name"] == "aapl-20240928.htm"]
    assert len(primary_rows) == 1
    assert primary_rows[0]["is_primary"] is True


@pytest.mark.fast
def test_merge_filing_attachments_updates_raw_object_id(db):
    rows_no_obj = [dict(r) for r in _ATTACHMENT_ROWS]
    for r in rows_no_obj:
        r["raw_object_id"] = None
    db.merge_filing_attachments(rows_no_obj, sync_run_id="run-001")

    rows_with_obj = [dict(r) for r in _ATTACHMENT_ROWS]
    rows_with_obj[0]["raw_object_id"] = "obj-001"
    db.merge_filing_attachments(rows_with_obj, sync_run_id="run-002")

    results = db.get_filing_attachments(_ACCESSION)
    primary_rows = [r for r in results if r["document_name"] == "aapl-20240928.htm"]
    assert primary_rows[0]["raw_object_id"] == "obj-001"


@pytest.mark.fast
def test_get_filing_attachments_empty_for_unknown(db):
    results = db.get_filing_attachments("0000000000-00-000000")
    assert results == []
