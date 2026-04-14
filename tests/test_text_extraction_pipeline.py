"""
Verify sec_filing_text silver operations.
Fast tests only - no network calls.
"""
import pytest
from datetime import datetime, timezone
from edgar_warehouse.silver import SilverDatabase

_NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_ACCESSION = "0000320193-24-000123"

@pytest.fixture
def db(tmp_path):
    return SilverDatabase(str(tmp_path / "silver.duckdb"))

_TEXT_ROW = {
    "accession_number": _ACCESSION,
    "text_version": "generic_text_v1",
    "source_document_name": "aapl-20240928.htm",
    "text_storage_path": "text/sec/cik=320193/0000320193-24-000123/generic_text_v1.txt",
    "text_sha256": "abc123def456",
    "char_count": 150000,
    "extracted_at": _NOW,
}


@pytest.mark.fast
def test_upsert_filing_text_new_row(db):
    db.upsert_filing_text(_TEXT_ROW)
    result = db.get_filing_text(_ACCESSION, "generic_text_v1")
    assert result is not None
    assert result["char_count"] == 150000


@pytest.mark.fast
def test_upsert_filing_text_idempotent(db):
    db.upsert_filing_text(_TEXT_ROW)
    db.upsert_filing_text(_TEXT_ROW)
    result = db.get_filing_text(_ACCESSION, "generic_text_v1")
    assert result is not None
    all_rows = db.get_all_filing_texts(_ACCESSION)
    assert len(all_rows) == 1


@pytest.mark.fast
def test_upsert_filing_text_updates_mutable_fields(db):
    row_v1 = dict(_TEXT_ROW, text_sha256="hash-v1")
    db.upsert_filing_text(row_v1)
    row_v2 = dict(_TEXT_ROW, text_sha256="hash-v2")
    db.upsert_filing_text(row_v2)
    result = db.get_filing_text(_ACCESSION, "generic_text_v1")
    assert result["text_sha256"] == "hash-v2"


@pytest.mark.fast
def test_upsert_filing_text_updates_char_count(db):
    row_100 = dict(_TEXT_ROW, char_count=100)
    db.upsert_filing_text(row_100)
    row_200 = dict(_TEXT_ROW, char_count=200)
    db.upsert_filing_text(row_200)
    result = db.get_filing_text(_ACCESSION, "generic_text_v1")
    assert result["char_count"] == 200


@pytest.mark.fast
def test_get_filing_text_returns_none_for_unknown(db):
    result = db.get_filing_text("0000000000-00-000000", "generic_text_v1")
    assert result is None


@pytest.mark.fast
def test_get_all_filing_texts_multiple_versions(db):
    row_v1 = dict(_TEXT_ROW, text_version="generic_text_v1")
    row_v2 = dict(_TEXT_ROW, text_version="generic_text_v2")
    db.upsert_filing_text(row_v1)
    db.upsert_filing_text(row_v2)
    results = db.get_all_filing_texts(_ACCESSION)
    assert len(results) == 2


@pytest.mark.fast
def test_get_all_filing_texts_empty_for_unknown(db):
    results = db.get_all_filing_texts("0000000000-00-000000")
    assert results == []


@pytest.mark.fast
def test_upsert_filing_text_raises_on_missing_required_field(db):
    with pytest.raises(ValueError):
        db.upsert_filing_text({})
