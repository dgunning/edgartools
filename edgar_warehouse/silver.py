"""Silver layer DuckDB management for the SEC EDGAR warehouse."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError as exc:
    raise ImportError(
        "DuckDB is required for the silver layer. "
        "Install with: pip install 'edgartools[warehouse]'"
    ) from exc


_DDL = """
CREATE TABLE IF NOT EXISTS sec_tracked_universe (
    cik                BIGINT PRIMARY KEY,
    input_ticker       TEXT,
    current_ticker     TEXT,
    universe_source    TEXT    NOT NULL,
    tracking_status    TEXT    NOT NULL DEFAULT 'active',
    history_mode       TEXT    NOT NULL DEFAULT 'recent_only',
    effective_from     TIMESTAMPTZ NOT NULL,
    effective_to       TIMESTAMPTZ,
    load_priority      INTEGER,
    scope_reason       TEXT,
    added_at           TIMESTAMPTZ NOT NULL,
    removed_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sec_company (
    cik                        BIGINT PRIMARY KEY,
    entity_name                TEXT,
    entity_type                TEXT,
    sic                        TEXT,
    sic_description            TEXT,
    state_of_incorporation     TEXT,
    state_of_incorporation_desc TEXT,
    fiscal_year_end            TEXT,
    ein                        TEXT,
    description                TEXT,
    category                   TEXT,
    first_sync_run_id          TEXT,
    last_sync_run_id           TEXT,
    last_synced_at             TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sec_company_address (
    cik             BIGINT,
    address_type    TEXT,
    street1         TEXT,
    street2         TEXT,
    city            TEXT,
    state_or_country TEXT,
    zip_code        TEXT,
    country         TEXT,
    last_sync_run_id TEXT,
    last_synced_at  TIMESTAMPTZ,
    PRIMARY KEY (cik, address_type)
);

CREATE TABLE IF NOT EXISTS sec_company_former_name (
    cik             BIGINT,
    former_name     TEXT,
    date_changed    DATE,
    ordinal         INTEGER,
    last_sync_run_id TEXT,
    PRIMARY KEY (cik, ordinal)
);

CREATE TABLE IF NOT EXISTS sec_company_submission_file (
    cik             BIGINT,
    file_name       TEXT,
    filing_count    INTEGER,
    filing_from     DATE,
    filing_to       DATE,
    last_sync_run_id TEXT,
    last_synced_at  TIMESTAMPTZ,
    PRIMARY KEY (cik, file_name)
);

CREATE TABLE IF NOT EXISTS sec_company_filing (
    accession_number    TEXT PRIMARY KEY,
    cik                 BIGINT,
    form                TEXT,
    filing_date         DATE,
    report_date         DATE,
    acceptance_datetime TEXT,
    act                 TEXT,
    file_number         TEXT,
    film_number         TEXT,
    items               TEXT,
    size                BIGINT,
    is_xbrl             BOOLEAN,
    is_inline_xbrl      BOOLEAN,
    primary_document    TEXT,
    primary_doc_desc    TEXT,
    last_sync_run_id    TEXT,
    last_synced_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS stg_daily_index_filing (
    sync_run_id         TEXT,
    raw_object_id       TEXT,
    source_name         TEXT,
    source_url          TEXT,
    business_date       DATE,
    source_year         SMALLINT,
    source_quarter      SMALLINT,
    row_ordinal         INTEGER,
    form                TEXT,
    company_name        TEXT,
    cik                 BIGINT,
    filing_date         DATE,
    file_name           TEXT,
    accession_number    TEXT,
    filing_txt_url      TEXT,
    record_hash         TEXT,
    staged_at           TIMESTAMPTZ,
    PRIMARY KEY (business_date, accession_number)
);

CREATE TABLE IF NOT EXISTS sec_daily_index_checkpoint (
    business_date             DATE PRIMARY KEY,
    source_name               TEXT NOT NULL DEFAULT 'daily_form_index',
    source_key                TEXT NOT NULL,
    source_url                TEXT NOT NULL,
    expected_available_at     TIMESTAMPTZ NOT NULL,
    first_attempt_at          TIMESTAMPTZ,
    last_attempt_at           TIMESTAMPTZ,
    attempt_count             INTEGER NOT NULL DEFAULT 0,
    raw_object_id             TEXT,
    last_sha256               TEXT,
    row_count                 INTEGER,
    distinct_cik_count        INTEGER,
    distinct_accession_count  INTEGER,
    status                    TEXT NOT NULL DEFAULT 'pending',
    error_message             TEXT,
    finalized_at              TIMESTAMPTZ,
    last_success_at           TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sec_raw_object (
    raw_object_id       TEXT PRIMARY KEY,
    source_type         TEXT,
    cik                 BIGINT,
    accession_number    TEXT,
    form                TEXT,
    source_url          TEXT        NOT NULL,
    storage_path        TEXT        NOT NULL,
    content_type        TEXT,
    content_encoding    TEXT,
    byte_size           BIGINT,
    sha256              TEXT        NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL,
    http_status         INTEGER     NOT NULL,
    source_last_modified TIMESTAMPTZ,
    source_etag         TEXT
);

CREATE TABLE IF NOT EXISTS sec_filing_attachment (
    accession_number    TEXT,
    sequence_number     TEXT,
    document_name       TEXT,
    document_type       TEXT        NOT NULL,
    document_description TEXT,
    document_url        TEXT        NOT NULL,
    is_primary          BOOLEAN     NOT NULL,
    raw_object_id       TEXT,
    last_sync_run_id    TEXT,
    PRIMARY KEY (accession_number, document_name)
);

CREATE TABLE IF NOT EXISTS sec_filing_text (
    accession_number    TEXT        NOT NULL,
    text_version        TEXT        NOT NULL,
    source_document_name TEXT       NOT NULL,
    text_storage_path   TEXT        NOT NULL,
    text_sha256         TEXT        NOT NULL,
    char_count          INTEGER     NOT NULL,
    extracted_at        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (accession_number, text_version)
);

CREATE TABLE IF NOT EXISTS sec_parse_run (
    parse_run_id       TEXT NOT NULL PRIMARY KEY,
    accession_number   TEXT,
    parser_name        TEXT NOT NULL,
    parser_version     TEXT NOT NULL,
    target_form_family TEXT NOT NULL,
    status             TEXT NOT NULL,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    error_code         TEXT,
    error_message      TEXT
);
"""


class SilverDatabase:
    """Manages the silver-layer DuckDB instance for a warehouse root."""

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_DDL)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # sec_tracked_universe
    # ------------------------------------------------------------------

    def seed_tracked_universe(self, company_tickers_exchange: dict[str, Any]) -> int:
        """Upsert rows from company_tickers_exchange.json into sec_tracked_universe.

        Returns the number of rows inserted or updated.
        """
        now = datetime.now(UTC)
        rows = _parse_company_tickers_exchange(company_tickers_exchange)
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO sec_tracked_universe
                    (cik, input_ticker, current_ticker, universe_source,
                     tracking_status, history_mode, effective_from, added_at)
                VALUES (?, ?, ?, 'seeded_from_sec_reference', 'active', 'recent_only', ?, ?)
                ON CONFLICT (cik) DO UPDATE SET
                    input_ticker = excluded.input_ticker,
                    current_ticker = excluded.current_ticker
                """,
                [row["cik"], row["ticker"], row["ticker"], now, now],
            )
            count += 1
        return count

    def get_tracked_universe_entry(self, cik: int) -> dict[str, Any] | None:
        result = self._conn.execute(
            "SELECT * FROM sec_tracked_universe WHERE cik = ?", [cik]
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    def get_tracked_universe_count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM sec_tracked_universe"
        ).fetchone()[0]

    def get_tracked_universe_ciks(self, status_filter: str = "active") -> list[int]:
        rows = self._conn.execute(
            "SELECT cik FROM sec_tracked_universe WHERE tracking_status = ?",
            [status_filter],
        ).fetchall()
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # sec_company (silver merge)
    # ------------------------------------------------------------------

    def merge_company(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        """Upsert staged company rows into sec_company. Returns row count."""
        now = datetime.now(UTC)
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO sec_company
                    (cik, entity_name, entity_type, sic, sic_description,
                     state_of_incorporation, state_of_incorporation_desc,
                     fiscal_year_end, ein, description, category,
                     first_sync_run_id, last_sync_run_id, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (cik) DO UPDATE SET
                    entity_name = excluded.entity_name,
                    entity_type = excluded.entity_type,
                    sic = excluded.sic,
                    sic_description = excluded.sic_description,
                    state_of_incorporation = excluded.state_of_incorporation,
                    state_of_incorporation_desc = excluded.state_of_incorporation_desc,
                    fiscal_year_end = excluded.fiscal_year_end,
                    ein = excluded.ein,
                    description = excluded.description,
                    category = excluded.category,
                    last_sync_run_id = excluded.last_sync_run_id,
                    last_synced_at = excluded.last_synced_at
                """,
                [
                    row["cik"],
                    row.get("entity_name"),
                    row.get("entity_type"),
                    row.get("sic"),
                    row.get("sic_description"),
                    row.get("state_of_incorporation"),
                    row.get("state_of_incorporation_desc"),
                    row.get("fiscal_year_end"),
                    row.get("ein"),
                    row.get("description"),
                    row.get("category"),
                    row.get("first_sync_run_id", sync_run_id),
                    sync_run_id,
                    now,
                ],
            )
            count += 1
        return count

    def get_company(self, cik: int) -> dict[str, Any] | None:
        result = self._conn.execute(
            "SELECT * FROM sec_company WHERE cik = ?", [cik]
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    # ------------------------------------------------------------------
    # sec_company_address
    # ------------------------------------------------------------------

    def merge_addresses(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        now = datetime.now(UTC)
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO sec_company_address
                    (cik, address_type, street1, street2, city,
                     state_or_country, zip_code, country,
                     last_sync_run_id, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (cik, address_type) DO UPDATE SET
                    street1 = excluded.street1,
                    street2 = excluded.street2,
                    city = excluded.city,
                    state_or_country = excluded.state_or_country,
                    zip_code = excluded.zip_code,
                    country = excluded.country,
                    last_sync_run_id = excluded.last_sync_run_id,
                    last_synced_at = excluded.last_synced_at
                """,
                [
                    row["cik"],
                    row["address_type"],
                    row.get("street1"),
                    row.get("street2"),
                    row.get("city"),
                    row.get("state_or_country"),
                    row.get("zip_code"),
                    row.get("country"),
                    sync_run_id,
                    now,
                ],
            )
            count += 1
        return count

    def get_addresses(self, cik: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sec_company_address WHERE cik = ?", [cik]
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # sec_company_former_name
    # ------------------------------------------------------------------

    def merge_former_names(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO sec_company_former_name
                    (cik, former_name, date_changed, ordinal, last_sync_run_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (cik, ordinal) DO UPDATE SET
                    former_name = excluded.former_name,
                    date_changed = excluded.date_changed,
                    last_sync_run_id = excluded.last_sync_run_id
                """,
                [
                    row["cik"],
                    row["former_name"],
                    row.get("date_changed"),
                    row["ordinal"],
                    sync_run_id,
                ],
            )
            count += 1
        return count

    def get_former_names(self, cik: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sec_company_former_name WHERE cik = ? ORDER BY ordinal",
            [cik],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # sec_company_submission_file
    # ------------------------------------------------------------------

    def merge_submission_files(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        now = datetime.now(UTC)
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO sec_company_submission_file
                    (cik, file_name, filing_count, filing_from, filing_to,
                     last_sync_run_id, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (cik, file_name) DO UPDATE SET
                    filing_count = excluded.filing_count,
                    filing_from = excluded.filing_from,
                    filing_to = excluded.filing_to,
                    last_sync_run_id = excluded.last_sync_run_id,
                    last_synced_at = excluded.last_synced_at
                """,
                [
                    row["cik"],
                    row["file_name"],
                    row.get("filing_count"),
                    row.get("filing_from"),
                    row.get("filing_to"),
                    sync_run_id,
                    now,
                ],
            )
            count += 1
        return count

    def get_submission_files(self, cik: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sec_company_submission_file WHERE cik = ?", [cik]
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # sec_company_filing
    # ------------------------------------------------------------------

    def merge_filings(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        now = datetime.now(UTC)
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO sec_company_filing
                    (accession_number, cik, form, filing_date, report_date,
                     acceptance_datetime, act, file_number, film_number, items,
                     size, is_xbrl, is_inline_xbrl, primary_document,
                     primary_doc_desc, last_sync_run_id, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (accession_number) DO UPDATE SET
                    form = excluded.form,
                    filing_date = excluded.filing_date,
                    report_date = excluded.report_date,
                    acceptance_datetime = excluded.acceptance_datetime,
                    size = excluded.size,
                    is_xbrl = excluded.is_xbrl,
                    is_inline_xbrl = excluded.is_inline_xbrl,
                    primary_document = excluded.primary_document,
                    primary_doc_desc = excluded.primary_doc_desc,
                    last_sync_run_id = excluded.last_sync_run_id,
                    last_synced_at = excluded.last_synced_at
                """,
                [
                    row["accession_number"],
                    row["cik"],
                    row.get("form"),
                    row.get("filing_date"),
                    row.get("report_date"),
                    row.get("acceptance_datetime"),
                    row.get("act"),
                    row.get("file_number"),
                    row.get("film_number"),
                    row.get("items"),
                    row.get("size"),
                    row.get("is_xbrl"),
                    row.get("is_inline_xbrl"),
                    row.get("primary_document"),
                    row.get("primary_doc_desc"),
                    sync_run_id,
                    now,
                ],
            )
            count += 1
        return count

    def get_filing_count(self, cik: int) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM sec_company_filing WHERE cik = ?", [cik]
        ).fetchone()[0]

    def get_filing(self, accession_number: str) -> dict[str, Any] | None:
        result = self._conn.execute(
            "SELECT * FROM sec_company_filing WHERE accession_number = ?",
            [accession_number],
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    # ------------------------------------------------------------------
    # stg_daily_index_filing
    # ------------------------------------------------------------------

    def merge_daily_index_filings(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        """Upsert staged daily index filing rows. Returns row count."""
        now = datetime.now(UTC)
        count = 0
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO stg_daily_index_filing
                    (sync_run_id, raw_object_id, source_name, source_url,
                     business_date, source_year, source_quarter, row_ordinal,
                     form, company_name, cik, filing_date, file_name,
                     accession_number, filing_txt_url, record_hash, staged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (business_date, accession_number) DO UPDATE SET
                    sync_run_id = excluded.sync_run_id,
                    raw_object_id = excluded.raw_object_id,
                    source_name = excluded.source_name,
                    source_url = excluded.source_url,
                    source_year = excluded.source_year,
                    source_quarter = excluded.source_quarter,
                    row_ordinal = excluded.row_ordinal,
                    form = excluded.form,
                    company_name = excluded.company_name,
                    cik = excluded.cik,
                    filing_date = excluded.filing_date,
                    file_name = excluded.file_name,
                    filing_txt_url = excluded.filing_txt_url,
                    record_hash = excluded.record_hash,
                    staged_at = excluded.staged_at
                """,
                [
                    sync_run_id,
                    row.get("raw_object_id"),
                    row.get("source_name", "daily_form_index"),
                    row.get("source_url"),
                    row["business_date"],
                    row.get("source_year"),
                    row.get("source_quarter"),
                    row.get("row_ordinal"),
                    row.get("form"),
                    row.get("company_name"),
                    row.get("cik"),
                    row.get("filing_date"),
                    row.get("file_name"),
                    row.get("accession_number"),
                    row.get("filing_txt_url"),
                    row.get("record_hash"),
                    now,
                ],
            )
            count += 1
        return count

    def get_daily_index_filings(self, business_date: str) -> list[dict[str, Any]]:
        """Return all stg_daily_index_filing rows for a given business_date."""
        rows = self._conn.execute(
            "SELECT * FROM stg_daily_index_filing WHERE business_date = ? ORDER BY row_ordinal",
            [business_date],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # sec_daily_index_checkpoint
    # ------------------------------------------------------------------

    def upsert_daily_index_checkpoint(self, row: dict[str, Any]) -> None:
        """Insert or update a daily index checkpoint row."""
        self._conn.execute(
            """
            INSERT INTO sec_daily_index_checkpoint
                (business_date, source_name, source_key, source_url,
                 expected_available_at, first_attempt_at, last_attempt_at,
                 attempt_count, raw_object_id, last_sha256, row_count,
                 distinct_cik_count, distinct_accession_count, status,
                 error_message, finalized_at, last_success_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (business_date) DO UPDATE SET
                last_attempt_at = excluded.last_attempt_at,
                attempt_count = sec_daily_index_checkpoint.attempt_count + 1,
                raw_object_id = excluded.raw_object_id,
                last_sha256 = excluded.last_sha256,
                row_count = excluded.row_count,
                distinct_cik_count = excluded.distinct_cik_count,
                distinct_accession_count = excluded.distinct_accession_count,
                status = excluded.status,
                error_message = excluded.error_message,
                finalized_at = excluded.finalized_at,
                last_success_at = excluded.last_success_at
            """,
            [
                row["business_date"],
                row.get("source_name", "daily_form_index"),
                row["source_key"],
                row["source_url"],
                row["expected_available_at"],
                row.get("first_attempt_at"),
                row.get("last_attempt_at"),
                row.get("attempt_count", 1),
                row.get("raw_object_id"),
                row.get("last_sha256"),
                row.get("row_count"),
                row.get("distinct_cik_count"),
                row.get("distinct_accession_count"),
                row.get("status", "pending"),
                row.get("error_message"),
                row.get("finalized_at"),
                row.get("last_success_at"),
            ],
        )

    def get_daily_index_checkpoint(self, business_date: str) -> dict[str, Any] | None:
        result = self._conn.execute(
            "SELECT * FROM sec_daily_index_checkpoint WHERE business_date = ?",
            [business_date],
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    def get_last_successful_checkpoint_date(self) -> str | None:
        """Return the most recent business_date with status='succeeded', or None."""
        result = self._conn.execute(
            """
            SELECT business_date FROM sec_daily_index_checkpoint
            WHERE status = 'succeeded'
            ORDER BY business_date DESC
            LIMIT 1
            """
        ).fetchone()
        return str(result[0]) if result else None

    def get_pending_checkpoint_dates(self, up_to_date: str) -> list[str]:
        """Return business dates that are pending or missing up to up_to_date."""
        rows = self._conn.execute(
            """
            SELECT business_date FROM sec_daily_index_checkpoint
            WHERE status IN ('pending', 'failed_retryable')
              AND business_date <= ?
            ORDER BY business_date ASC
            """,
            [up_to_date],
        ).fetchall()
        return [str(row[0]) for row in rows]

    # ------------------------------------------------------------------
    # sec_raw_object
    # ------------------------------------------------------------------

    def upsert_raw_object(self, row: dict[str, Any]) -> None:
        """Insert or update a raw object row.

        fetched_at is set on first insert and never overwritten on conflict.
        All other mutable fields are updated on conflict.
        """
        for required in ("raw_object_id", "source_url", "storage_path", "sha256", "fetched_at", "http_status"):
            if row.get(required) is None:
                raise ValueError(f"upsert_raw_object: required field '{required}' is missing or None")
        self._conn.execute(
            """
            INSERT INTO sec_raw_object
                (raw_object_id, source_type, cik, accession_number, form,
                 source_url, storage_path, content_type, content_encoding,
                 byte_size, sha256, fetched_at, http_status,
                 source_last_modified, source_etag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (raw_object_id) DO UPDATE SET
                source_type = excluded.source_type,
                cik = excluded.cik,
                accession_number = excluded.accession_number,
                form = excluded.form,
                source_url = excluded.source_url,
                storage_path = excluded.storage_path,
                content_type = excluded.content_type,
                content_encoding = excluded.content_encoding,
                byte_size = excluded.byte_size,
                sha256 = excluded.sha256,
                http_status = excluded.http_status,
                source_last_modified = excluded.source_last_modified,
                source_etag = excluded.source_etag
            """,
            [
                row["raw_object_id"],
                row.get("source_type"),
                row.get("cik"),
                row.get("accession_number"),
                row.get("form"),
                row.get("source_url"),
                row.get("storage_path"),
                row.get("content_type"),
                row.get("content_encoding"),
                row.get("byte_size"),
                row.get("sha256"),
                row.get("fetched_at"),
                row.get("http_status"),
                row.get("source_last_modified"),
                row.get("source_etag"),
            ],
        )

    def get_raw_object(self, raw_object_id: str) -> dict[str, Any] | None:
        result = self._conn.execute(
            "SELECT * FROM sec_raw_object WHERE raw_object_id = ?",
            [raw_object_id],
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    # ------------------------------------------------------------------
    # sec_filing_attachment
    # ------------------------------------------------------------------

    def merge_filing_attachments(self, rows: list[dict[str, Any]], sync_run_id: str) -> int:
        """Upsert filing attachment rows. Returns row count."""
        count = 0
        for row in rows:
            for required in ("accession_number", "document_name", "document_type", "document_url"):
                if not row.get(required):
                    raise ValueError(f"merge_filing_attachments: required field '{required}' is missing or None in row {row}")
            self._conn.execute(
                """
                INSERT INTO sec_filing_attachment
                    (accession_number, sequence_number, document_name,
                     document_type, document_description, document_url,
                     is_primary, raw_object_id, last_sync_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (accession_number, document_name) DO UPDATE SET
                    sequence_number = excluded.sequence_number,
                    document_type = excluded.document_type,
                    document_description = excluded.document_description,
                    document_url = excluded.document_url,
                    is_primary = excluded.is_primary,
                    raw_object_id = excluded.raw_object_id,
                    last_sync_run_id = excluded.last_sync_run_id
                """,
                [
                    row["accession_number"],
                    row.get("sequence_number"),
                    row["document_name"],
                    row.get("document_type"),
                    row.get("document_description"),
                    row.get("document_url"),
                    row.get("is_primary", False),
                    row.get("raw_object_id"),
                    sync_run_id,
                ],
            )
            count += 1
        return count

    def get_filing_attachments(self, accession_number: str) -> list[dict[str, Any]]:
        """Return all attachment rows for the given accession number."""
        rows = self._conn.execute(
            "SELECT * FROM sec_filing_attachment WHERE accession_number = ?",
            [accession_number],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # sec_filing_text
    # ------------------------------------------------------------------

    def upsert_filing_text(self, row: dict[str, Any]) -> None:
        """Insert or update a filing text extraction row.

        Raises ValueError if any required field is missing or None.
        """
        for required in (
            "accession_number",
            "text_version",
            "source_document_name",
            "text_storage_path",
            "text_sha256",
            "char_count",
            "extracted_at",
        ):
            if row.get(required) is None:
                raise ValueError(
                    f"upsert_filing_text: required field '{required}' is missing or None"
                )
        self._conn.execute(
            """
            INSERT INTO sec_filing_text
                (accession_number, text_version, source_document_name,
                 text_storage_path, text_sha256, char_count, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (accession_number, text_version) DO UPDATE SET
                source_document_name = excluded.source_document_name,
                text_storage_path = excluded.text_storage_path,
                text_sha256 = excluded.text_sha256,
                char_count = excluded.char_count,
                extracted_at = excluded.extracted_at
            """,
            [
                row["accession_number"],
                row["text_version"],
                row["source_document_name"],
                row["text_storage_path"],
                row["text_sha256"],
                row["char_count"],
                row["extracted_at"],
            ],
        )

    def get_filing_text(
        self, accession_number: str, text_version: str
    ) -> dict[str, Any] | None:
        """Return the filing text row for the given accession and version, or None."""
        result = self._conn.execute(
            "SELECT * FROM sec_filing_text WHERE accession_number = ? AND text_version = ?",
            [accession_number, text_version],
        ).fetchone()
        if result is None:
            return None
        cols = [d[0] for d in self._conn.description]
        return dict(zip(cols, result))

    def get_all_filing_texts(self, accession_number: str) -> list[dict[str, Any]]:
        """Return all text extraction rows for an accession, ordered by text_version."""
        rows = self._conn.execute(
            "SELECT * FROM sec_filing_text WHERE accession_number = ? ORDER BY text_version",
            [accession_number],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]
        return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # sec_parse_run
    # ------------------------------------------------------------------

    def start_parse_run(self, row: dict) -> None:
        """Insert a new parse run with status='running'."""
        required = ["parse_run_id", "parser_name", "parser_version", "target_form_family"]
        for f in required:
            if not row.get(f):
                raise ValueError(f"Missing required field: {f}")
        started_at = row.get("started_at") or datetime.now(UTC)
        self._conn.execute(
            """
            INSERT INTO sec_parse_run
                (parse_run_id, accession_number, parser_name, parser_version,
                 target_form_family, status, started_at)
            VALUES (?, ?, ?, ?, ?, 'running', ?)
            """,
            [
                row["parse_run_id"],
                row.get("accession_number"),
                row["parser_name"],
                row["parser_version"],
                row["target_form_family"],
                started_at,
            ],
        )

    def complete_parse_run(
        self,
        parse_run_id: str,
        status: str = "succeeded",
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update an existing parse run to a terminal status."""
        if not parse_run_id:
            raise ValueError("parse_run_id must not be empty")
        self._conn.execute(
            """
            UPDATE sec_parse_run
            SET status = ?, completed_at = ?, error_code = ?, error_message = ?
            WHERE parse_run_id = ?
            """,
            [status, datetime.now(UTC), error_code, error_message, parse_run_id],
        )

    def get_parse_run(self, parse_run_id: str) -> dict | None:
        """Return the parse run row as a dict, or None if not found."""
        cursor = self._conn.execute(
            "SELECT * FROM sec_parse_run WHERE parse_run_id = ?", [parse_run_id]
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_company_tickers_exchange(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse company_tickers_exchange.json dict into normalized rows."""
    rows: list[dict[str, Any]] = []
    for entry in payload.values():
        if not isinstance(entry, dict):
            continue
        cik = entry.get("cik_str")
        ticker = entry.get("ticker", "")
        if cik is None:
            continue
        rows.append({"cik": int(cik), "ticker": str(ticker)})
    return rows
