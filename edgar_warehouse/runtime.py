"""Warehouse runtime helpers for infrastructure-oriented command execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from edgar_warehouse.loaders import (
    stage_address_loader,
    stage_company_loader,
    stage_former_name_loader,
    stage_manifest_loader,
    stage_pagination_filing_loader,
    stage_recent_filing_loader,
)
from edgar_warehouse.silver import SilverDatabase

GOLD_AFFECTING_COMMANDS = {
    "bootstrap-full",
    "bootstrap-recent-10",
    "daily-incremental",
    "targeted-resync",
    "full-reconcile",
}

SNOWFLAKE_EXPORT_TABLES = {
    "COMPANY": "company",
    "FILING_ACTIVITY": "filing_activity",
    "OWNERSHIP_ACTIVITY": "ownership_activity",
    "OWNERSHIP_HOLDINGS": "ownership_holdings",
    "ADVISER_OFFICES": "adviser_offices",
    "ADVISER_DISCLOSURES": "adviser_disclosures",
    "PRIVATE_FUNDS": "private_funds",
    "FILING_DETAIL": "filing_detail",
}

SNOWFLAKE_METADATA_FIELDS = (
    "account",
    "database",
    "source_schema",
    "gold_schema",
    "refresh_warehouse",
    "runtime_role",
    "storage_integration",
    "stage_name",
    "file_format_name",
    "status_table_name",
    "source_load_procedure",
    "refresh_procedure",
)

FORBIDDEN_SNOWFLAKE_METADATA_FIELDS = (
    "password",
    "private_key",
    "token",
    "secret",
    "client_secret",
)

WAREHOUSE_RUNTIME_MODES = {
    "bronze_capture",
    "infrastructure_validation",
}

_DAILY_INDEX_LINE_PATTERN = re.compile(
    r"^.+?\s{2,}(?P<cik>\d{4,10})\s+(?:\d{8}|\d{4}-\d{2}-\d{2})\s+edgar/data/"
)


class WarehouseRuntimeError(RuntimeError):
    """Raised when a warehouse command cannot run in the current environment."""


@dataclass(frozen=True)
class StorageLocation:
    """A storage root that can point to either a local path or a cloud URI."""

    root: str

    def __post_init__(self) -> None:
        normalized = self.root.strip()
        if not normalized:
            raise WarehouseRuntimeError("storage root must not be empty")
        object.__setattr__(self, "root", normalized.rstrip("/\\"))

    @property
    def is_remote(self) -> bool:
        return "://" in self.root

    def join(self, *parts: str) -> str:
        relative = "/".join(part.strip("/\\") for part in parts if part)
        if not relative:
            return self.root
        if self.is_remote:
            return f"{self.root}/{relative}"
        return str(Path(self.root) / Path(relative))

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> str:
        return self.write_text(relative_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def write_text(self, relative_path: str, payload: str) -> str:
        return self.write_bytes(relative_path, payload.encode("utf-8"))

    def write_bytes(self, relative_path: str, payload: bytes) -> str:
        destination = self.join(relative_path)
        if self.is_remote:
            protocol = self.root.split("://", 1)[0]
            import fsspec

            fs = fsspec.filesystem(protocol)
            with fs.open(destination, "wb") as handle:
                handle.write(payload)
            return destination

        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(payload)
        return str(destination_path)


@dataclass(frozen=True)
class WarehouseCommandContext:
    """Runtime context shared by canonical warehouse commands."""

    bronze_root: StorageLocation
    storage_root: StorageLocation
    snowflake_export_root: StorageLocation | None
    identity: str
    runtime_mode: str


@dataclass(frozen=True)
class SnowflakeSyncContext:
    """Runtime context shared by Snowflake sync validation commands."""

    export_root: StorageLocation
    metadata: dict[str, str]


def run_command(command_name: str, args: Any) -> int:
    """Execute a warehouse command and emit a JSON result payload."""
    arguments = _namespace_to_payload(args)
    runtime_mode = os.environ.get("WAREHOUSE_RUNTIME_MODE", "infrastructure_validation").strip() or "infrastructure_validation"
    try:
        if command_name == "snowflake-sync-after-load":
            context = _build_snowflake_sync_context()
            payload = _execute_snowflake_sync(context=context, command_name=command_name, arguments=arguments)
        else:
            context = _build_warehouse_context(command_name)
            runtime_mode = context.runtime_mode
            payload = _execute_warehouse(context=context, command_name=command_name, arguments=arguments)
    except WarehouseRuntimeError as exc:
        print(json.dumps(_error_payload(command_name, arguments, str(exc), runtime_mode=runtime_mode), indent=2, sort_keys=True))
        return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _build_warehouse_context(command_name: str) -> WarehouseCommandContext:
    identity = os.environ.get("EDGAR_IDENTITY", "").strip()
    if not identity:
        raise WarehouseRuntimeError("EDGAR_IDENTITY is required for warehouse commands")
    if "@" not in identity:
        raise WarehouseRuntimeError("EDGAR_IDENTITY must include an email address")

    runtime_mode = os.environ.get("WAREHOUSE_RUNTIME_MODE", "infrastructure_validation").strip() or "infrastructure_validation"
    if runtime_mode not in WAREHOUSE_RUNTIME_MODES:
        raise WarehouseRuntimeError(
            "WAREHOUSE_RUNTIME_MODE must be one of: " + ", ".join(sorted(WAREHOUSE_RUNTIME_MODES))
        )

    bronze_root_value = os.environ.get("WAREHOUSE_BRONZE_ROOT", "").strip()
    storage_root_value = os.environ.get("WAREHOUSE_STORAGE_ROOT", "").strip()
    if not bronze_root_value:
        raise WarehouseRuntimeError("WAREHOUSE_BRONZE_ROOT is required for warehouse commands")
    if not storage_root_value:
        raise WarehouseRuntimeError("WAREHOUSE_STORAGE_ROOT is required for warehouse commands")

    bronze_root = StorageLocation(bronze_root_value)
    storage_root = StorageLocation(storage_root_value)

    if bronze_root.root == storage_root.root:
        raise WarehouseRuntimeError("WAREHOUSE_BRONZE_ROOT and WAREHOUSE_STORAGE_ROOT must be different locations")

    snowflake_export_root = None
    if command_name in GOLD_AFFECTING_COMMANDS:
        snowflake_export_root_value = os.environ.get("SNOWFLAKE_EXPORT_ROOT", "").strip()
        if not snowflake_export_root_value:
            raise WarehouseRuntimeError("SNOWFLAKE_EXPORT_ROOT is required for gold-affecting warehouse commands")
        snowflake_export_root = StorageLocation(snowflake_export_root_value)
        if snowflake_export_root.root in {bronze_root.root, storage_root.root}:
            raise WarehouseRuntimeError("SNOWFLAKE_EXPORT_ROOT must be isolated from bronze and warehouse roots")

    return WarehouseCommandContext(
        bronze_root=bronze_root,
        storage_root=storage_root,
        snowflake_export_root=snowflake_export_root,
        identity=identity,
        runtime_mode=runtime_mode,
    )


def _build_snowflake_sync_context() -> SnowflakeSyncContext:
    export_root_value = os.environ.get("SNOWFLAKE_EXPORT_ROOT", "").strip()
    if not export_root_value:
        raise WarehouseRuntimeError("SNOWFLAKE_EXPORT_ROOT is required for Snowflake sync commands")

    raw_metadata = os.environ.get("SNOWFLAKE_RUNTIME_METADATA", "").strip()
    if not raw_metadata:
        raise WarehouseRuntimeError("SNOWFLAKE_RUNTIME_METADATA is required for Snowflake sync commands")

    try:
        metadata = json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise WarehouseRuntimeError("SNOWFLAKE_RUNTIME_METADATA must be valid JSON") from exc
    if not isinstance(metadata, dict):
        raise WarehouseRuntimeError("SNOWFLAKE_RUNTIME_METADATA must decode to a JSON object")

    missing = [field for field in SNOWFLAKE_METADATA_FIELDS if not str(metadata.get(field, "")).strip()]
    if missing:
        raise WarehouseRuntimeError(
            "SNOWFLAKE_RUNTIME_METADATA is missing required fields: " + ", ".join(sorted(missing))
        )

    present_forbidden = sorted(
        field for field in FORBIDDEN_SNOWFLAKE_METADATA_FIELDS if field in metadata and metadata[field]
    )
    if present_forbidden:
        raise WarehouseRuntimeError(
            "SNOWFLAKE_RUNTIME_METADATA must not include credential material: "
            + ", ".join(present_forbidden)
        )

    normalized = {field: str(metadata[field]).strip() for field in SNOWFLAKE_METADATA_FIELDS}
    return SnowflakeSyncContext(export_root=StorageLocation(export_root_value), metadata=normalized)


def _execute_warehouse(
    context: WarehouseCommandContext,
    command_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if context.runtime_mode == "bronze_capture":
        return _execute_warehouse_bronze_capture(context=context, command_name=command_name, arguments=arguments)
    return _execute_warehouse_infrastructure_validation(context=context, command_name=command_name, arguments=arguments)


def _execute_warehouse_infrastructure_validation(
    context: WarehouseCommandContext,
    command_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    run_id = _resolve_run_id(arguments)
    command_path = command_name.replace("_", "-")
    scope = _resolve_scope(command_name=command_name, arguments=arguments, now=now)

    writes = []
    for layer, relative_path in _planned_writes(command_name=command_name, command_path=command_path, run_id=run_id, scope=scope).items():
        target = context.bronze_root if layer == "bronze" else context.storage_root
        manifest = _layer_manifest(
            command_name=command_name,
            run_id=run_id,
            layer=layer,
            relative_path=relative_path,
            arguments=arguments,
            scope=scope,
            now=now,
            runtime_mode=context.runtime_mode,
        )
        writes.append(
            {
                "layer": layer,
                "path": target.write_json(relative_path, manifest),
                "relative_path": relative_path,
            }
        )

    snowflake_exports = []
    if context.snowflake_export_root is not None:
        export_business_date = _resolve_export_business_date(command_name=command_name, scope=scope, now=now)
        for table_name, table_path in SNOWFLAKE_EXPORT_TABLES.items():
            relative_path = (
                f"{table_path}/business_date={export_business_date}/run_id={run_id}/manifest.json"
            )
            export_manifest = _snowflake_export_manifest(
                table_name=table_name,
                command_name=command_name,
                run_id=run_id,
                business_date=export_business_date,
                arguments=arguments,
                now=now,
                runtime_mode=context.runtime_mode,
            )
            snowflake_exports.append(
                {
                    "layer": "snowflake_export",
                    "path": context.snowflake_export_root.write_json(relative_path, export_manifest),
                    "relative_path": relative_path,
                    "table_name": table_name,
                }
            )
        writes.extend(snowflake_exports)

    return {
        "arguments": arguments,
        "command": command_name,
        "environment": {
            "bronze_root": context.bronze_root.root,
            "warehouse_root": context.storage_root.root,
            "identity_present": True,
            "snowflake_export_root": context.snowflake_export_root.root if context.snowflake_export_root else None,
        },
        "message": _warehouse_success_message(context.snowflake_export_root is not None),
        "run_id": run_id,
        "runtime_mode": context.runtime_mode,
        "scope": scope,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "writes": writes,
    }


def _execute_warehouse_bronze_capture(
    context: WarehouseCommandContext,
    command_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    run_id = _resolve_run_id(arguments)
    command_path = command_name.replace("_", "-")
    scope = _resolve_scope(command_name=command_name, arguments=arguments, now=now)

    raw_writes, silver_staging = _capture_bronze_raw(
        context=context,
        command_name=command_name,
        arguments=arguments,
        scope=scope,
        now=now,
    )

    # Write silver layer from staged submissions payloads (skipped for remote storage)
    if silver_staging and not context.storage_root.is_remote:
        recent_limit = arguments.get("recent_limit")
        db = _open_silver_database(context.storage_root)
        for cik, raw_object_id, main_payload, pagination_payloads in silver_staging:
            _apply_silver_from_submissions(
                db=db,
                sync_run_id=run_id,
                cik=cik,
                raw_object_id=raw_object_id,
                load_mode=command_name.replace("-", "_"),
                main_payload=main_payload,
                pagination_payloads=pagination_payloads,
                recent_limit=recent_limit,
            )

    writes = []
    for layer, relative_path in _planned_writes(command_name=command_name, command_path=command_path, run_id=run_id, scope=scope).items():
        target = context.bronze_root if layer == "bronze" else context.storage_root
        manifest = _layer_manifest(
            command_name=command_name,
            run_id=run_id,
            layer=layer,
            relative_path=relative_path,
            arguments=arguments,
            scope=scope,
            now=now,
            runtime_mode=context.runtime_mode,
        )
        writes.append(
            {
                "layer": layer,
                "path": target.write_json(relative_path, manifest),
                "relative_path": relative_path,
            }
        )

    snowflake_exports = []
    if context.snowflake_export_root is not None:
        export_business_date = _resolve_export_business_date(command_name=command_name, scope=scope, now=now)
        for table_name, table_path in SNOWFLAKE_EXPORT_TABLES.items():
            relative_path = (
                f"{table_path}/business_date={export_business_date}/run_id={run_id}/manifest.json"
            )
            export_manifest = _snowflake_export_manifest(
                table_name=table_name,
                command_name=command_name,
                run_id=run_id,
                business_date=export_business_date,
                arguments=arguments,
                now=now,
                runtime_mode=context.runtime_mode,
            )
            snowflake_exports.append(
                {
                    "layer": "snowflake_export",
                    "path": context.snowflake_export_root.write_json(relative_path, export_manifest),
                    "relative_path": relative_path,
                    "table_name": table_name,
                }
            )
        writes.extend(snowflake_exports)

    return {
        "arguments": arguments,
        "bronze_object_count": len(raw_writes),
        "command": command_name,
        "environment": {
            "bronze_root": context.bronze_root.root,
            "warehouse_root": context.storage_root.root,
            "identity_present": True,
            "snowflake_export_root": context.snowflake_export_root.root if context.snowflake_export_root else None,
        },
        "message": (
            "Warehouse bronze capture completed successfully. "
            "Raw SEC files and run manifests were written to the configured bronze"
            + (", warehouse, and Snowflake export roots." if context.snowflake_export_root is not None else " and warehouse roots.")
        ),
        "raw_writes": raw_writes,
        "run_id": run_id,
        "runtime_mode": context.runtime_mode,
        "scope": scope,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "writes": writes,
    }


def _open_silver_database(storage_root: StorageLocation) -> SilverDatabase:
    """Open (or create) the silver DuckDB at the canonical path under storage_root."""
    db_path = storage_root.join("silver", "sec", "silver.duckdb")
    if storage_root.is_remote:
        raise WarehouseRuntimeError(
            "Silver DuckDB is not yet supported on remote storage roots. "
            "Use a local path for WAREHOUSE_STORAGE_ROOT in bronze_capture mode."
        )
    return SilverDatabase(db_path)


def _apply_silver_from_submissions(
    db: SilverDatabase,
    sync_run_id: str,
    cik: int,
    raw_object_id: str,
    load_mode: str,
    main_payload: dict[str, Any],
    pagination_payloads: list[tuple[str, dict[str, Any]]],
    recent_limit: int | None = None,
) -> None:
    """Write silver rows for one company from its parsed submissions JSON payloads."""
    company_rows = stage_company_loader(main_payload, cik, sync_run_id, raw_object_id, load_mode)
    address_rows = stage_address_loader(main_payload, cik, sync_run_id, raw_object_id, load_mode)
    former_name_rows = stage_former_name_loader(main_payload, cik, sync_run_id, raw_object_id, load_mode)
    manifest_rows = stage_manifest_loader(main_payload, cik, sync_run_id, raw_object_id, load_mode)
    recent_rows = stage_recent_filing_loader(
        main_payload, cik, sync_run_id, raw_object_id, load_mode, recent_limit=recent_limit
    )

    db.merge_company(company_rows, sync_run_id)
    db.merge_addresses(address_rows, sync_run_id)
    db.merge_former_names(former_name_rows, sync_run_id)
    db.merge_submission_files(manifest_rows, sync_run_id)
    db.merge_filings(recent_rows, sync_run_id)

    for _file_name, pagination_payload in pagination_payloads:
        pagination_rows = stage_pagination_filing_loader(pagination_payload, cik, sync_run_id, raw_object_id, load_mode)
        db.merge_filings(pagination_rows, sync_run_id)


def _capture_bronze_raw(
    context: WarehouseCommandContext,
    command_name: str,
    arguments: dict[str, Any],
    scope: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[tuple[int, str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]]:
    """Capture raw bronze objects and return (write_records, silver_staging).

    silver_staging is a list of (cik, raw_object_id, main_payload, pagination_payloads)
    tuples suitable for passing to _apply_silver_from_submissions.
    """
    raw_writes: list[dict[str, Any]] = []
    silver_staging: list[tuple[int, str, dict[str, Any], list[tuple[str, dict[str, Any]]]]] = []

    if arguments.get("include_reference_refresh"):
        raw_writes.extend(_capture_reference_files(context=context, fetch_date=now.date()))

    if command_name == "daily-incremental":
        db = None
        if not context.storage_root.is_remote:
            db = _open_silver_database(context.storage_root)
        impacted_ciks: list[int] = []
        for target_date in _date_range(
            start=date.fromisoformat(scope["business_date_start"]),
            end=date.fromisoformat(scope["business_date_end"]),
        ):
            try:
                daily_index_write, daily_index_ciks = _capture_daily_index_file(context=context, target_date=target_date)
                raw_writes.append(daily_index_write)
                impacted_ciks.extend(daily_index_ciks)
                if db is not None:
                    db.upsert_daily_index_checkpoint({
                        "business_date": target_date.isoformat(),
                        "source_key": f"date:{target_date.isoformat()}",
                        "source_url": _build_daily_index_url(target_date),
                        "expected_available_at": _expected_available_at(target_date),
                        "last_attempt_at": now,
                        "last_success_at": now,
                        "raw_object_id": daily_index_write["sha256"],
                        "last_sha256": daily_index_write["sha256"],
                        "row_count": len(daily_index_ciks),
                        "status": "succeeded",
                    })
            except WarehouseRuntimeError as exc:
                if db is not None:
                    db.upsert_daily_index_checkpoint({
                        "business_date": target_date.isoformat(),
                        "source_key": f"date:{target_date.isoformat()}",
                        "source_url": _build_daily_index_url(target_date),
                        "expected_available_at": _expected_available_at(target_date),
                        "last_attempt_at": now,
                        "status": "failed_retryable",
                        "error_message": str(exc),
                    })
                raise
        if db is not None:
            tracked = db.get_tracked_universe_ciks(status_filter="active")
            if tracked:
                tracked_set = set(tracked)
                impacted_ciks = [c for c in impacted_ciks if c in tracked_set]
        selected_ciks = _apply_bronze_cik_limit(_dedupe_ints(impacted_ciks))
        if selected_ciks:
            writes, staging = _capture_submissions_scope(
                context=context,
                ciks=selected_ciks,
                include_pagination=False,
                fetch_date=now.date(),
            )
            raw_writes.extend(writes)
            silver_staging.extend(staging)
        return raw_writes, silver_staging

    if command_name == "load-daily-form-index-for-date":
        daily_index_write, _ = _capture_daily_index_file(context=context, target_date=date.fromisoformat(scope["target_date"]))
        raw_writes.append(daily_index_write)
        return raw_writes, silver_staging

    if command_name == "bootstrap-recent-10":
        ciks = _require_cik_list(scope.get("cik_list"), command_name)
        writes, staging = _capture_submissions_scope(
            context=context, ciks=ciks, include_pagination=False, fetch_date=now.date()
        )
        raw_writes.extend(writes)
        silver_staging.extend(staging)
        return raw_writes, silver_staging

    if command_name == "bootstrap-full":
        ciks = _require_cik_list(scope.get("cik_list"), command_name)
        writes, staging = _capture_submissions_scope(
            context=context, ciks=ciks, include_pagination=True, fetch_date=now.date()
        )
        raw_writes.extend(writes)
        silver_staging.extend(staging)
        return raw_writes, silver_staging

    if command_name == "targeted-resync":
        scope_type = str(scope.get("scope_type", "")).strip()
        scope_key = str(scope.get("scope_key", "")).strip()
        if scope_type == "reference":
            return raw_writes, silver_staging
        if scope_type == "cik":
            writes, staging = _capture_submissions_scope(
                context=context,
                ciks=[_parse_cik(scope_key)],
                include_pagination=True,
                fetch_date=now.date(),
            )
            raw_writes.extend(writes)
            silver_staging.extend(staging)
            return raw_writes, silver_staging
        raise WarehouseRuntimeError("targeted-resync in bronze_capture mode does not yet support accession scope")

    if command_name == "full-reconcile":
        ciks = _require_cik_list(scope.get("cik_list"), command_name)
        writes, staging = _capture_submissions_scope(
            context=context, ciks=ciks, include_pagination=True, fetch_date=now.date()
        )
        raw_writes.extend(writes)
        silver_staging.extend(staging)
        return raw_writes, silver_staging

    if command_name == "catch-up-daily-form-index":
        end_date = date.fromisoformat(scope["end_date"])
        writes, staging = _capture_catch_up_daily_form_index(
            context=context, end_date=end_date
        )
        raw_writes.extend(writes)
        silver_staging.extend(staging)
        return raw_writes, silver_staging

    raise WarehouseRuntimeError(f"bronze_capture mode does not support {command_name}")


def _capture_reference_files(context: WarehouseCommandContext, fetch_date: date) -> list[dict[str, Any]]:
    day_parts = fetch_date.strftime("%Y/%m/%d")
    sources = (
        (
            "company_tickers",
            _build_company_tickers_url(),
            f"reference/sec/company_tickers/{day_parts}/company_tickers.json",
        ),
        (
            "company_tickers_exchange",
            _build_company_tickers_exchange_url(),
            f"reference/sec/company_tickers_exchange/{day_parts}/company_tickers_exchange.json",
        ),
    )
    return [
        _write_bronze_object(
            context=context,
            relative_path=relative_path,
            source_name=source_name,
            source_url=source_url,
            payload=_download_sec_bytes(url=source_url, identity=context.identity),
        )
        for source_name, source_url, relative_path in sources
    ]


def _capture_daily_index_file(context: WarehouseCommandContext, target_date: date) -> tuple[dict[str, Any], list[int]]:
    date_parts = target_date.strftime("%Y/%m/%d")
    file_name = f"form.{target_date:%Y%m%d}.idx"
    source_url = _build_daily_index_url(target_date)
    payload = _download_sec_bytes(url=source_url, identity=context.identity)
    record = _write_bronze_object(
        context=context,
        relative_path=f"daily_index/sec/{date_parts}/{file_name}",
        source_name="daily_index",
        source_url=source_url,
        payload=payload,
        business_date=target_date.isoformat(),
    )
    return record, _extract_impacted_ciks_from_daily_index(payload=payload, source_url=source_url)


def _capture_submissions_scope(
    context: WarehouseCommandContext,
    ciks: list[int],
    include_pagination: bool,
    fetch_date: date,
) -> tuple[list[dict[str, Any]], list[tuple[int, str, dict[str, Any], list[tuple[str, dict[str, Any]]]]]]:
    """Download submissions JSON for each CIK, write to bronze, and return staging data.

    Returns (write_records, silver_staging) where silver_staging is a list of
    (cik, raw_object_id, main_payload_dict, pagination_payloads) tuples.
    """
    day_parts = fetch_date.strftime("%Y/%m/%d")
    raw_writes: list[dict[str, Any]] = []
    silver_staging: list[tuple[int, str, dict[str, Any], list[tuple[str, dict[str, Any]]]]] = []

    for cik in ciks:
        main_file_name = f"CIK{cik:010d}.json"
        main_url = _build_submissions_url(cik)
        main_payload_bytes = _download_sec_bytes(url=main_url, identity=context.identity)
        write_record = _write_bronze_object(
            context=context,
            relative_path=f"submissions/sec/cik={cik}/main/{day_parts}/{main_file_name}",
            source_name="submissions_main",
            source_url=main_url,
            payload=main_payload_bytes,
            cik=cik,
        )
        raw_writes.append(write_record)
        raw_object_id = write_record["sha256"]
        main_document = _decode_json_bytes(main_payload_bytes, main_url)
        pagination_payloads: list[tuple[str, dict[str, Any]]] = []

        if include_pagination:
            for file_name in _pagination_file_names(main_document):
                pagination_url = _build_submission_pagination_url(file_name)
                pagination_payload_bytes = _download_sec_bytes(url=pagination_url, identity=context.identity)
                raw_writes.append(
                    _write_bronze_object(
                        context=context,
                        relative_path=f"submissions/sec/cik={cik}/pagination/{day_parts}/{file_name}",
                        source_name="submissions_pagination",
                        source_url=pagination_url,
                        payload=pagination_payload_bytes,
                        cik=cik,
                    )
                )
                pagination_payloads.append((file_name, _decode_json_bytes(pagination_payload_bytes, pagination_url)))

        silver_staging.append((cik, raw_object_id, main_document, pagination_payloads))

    return raw_writes, silver_staging


def _capture_catch_up_daily_form_index(
    context: WarehouseCommandContext,
    end_date: date,
) -> tuple[list[dict[str, Any]], list]:
    """Fetch missing daily index files in ascending date order up to end_date.

    Uses sec_daily_index_checkpoint to determine which dates still need loading.
    Stops on the first fetch failure and updates checkpoint status accordingly.
    Returns (write_records, []) - no silver staging from daily index fetches alone.
    """
    if context.storage_root.is_remote:
        raise WarehouseRuntimeError(
            "catch-up-daily-form-index in bronze_capture mode requires local storage root "
            "(silver checkpoint is not yet supported on remote storage)"
        )

    db = _open_silver_database(context.storage_root)
    last_success = db.get_last_successful_checkpoint_date()

    if last_success is not None:
        start_date = date.fromisoformat(last_success) + timedelta(days=1)
    else:
        start_date = end_date  # No history; only fetch the end date

    raw_writes: list[dict[str, Any]] = []
    now = datetime.now(UTC)

    for target_date in _date_range(start_date, end_date):
        if not _is_business_day(target_date):
            continue
        existing = db.get_daily_index_checkpoint(target_date.isoformat())
        if existing and existing.get("status") == "succeeded":
            continue

        source_url = _build_daily_index_url(target_date)
        expected_available_at = _expected_available_at(target_date)

        try:
            write_record, _ = _capture_daily_index_file(context=context, target_date=target_date)
            raw_writes.append(write_record)
            db.upsert_daily_index_checkpoint({
                "business_date": target_date.isoformat(),
                "source_key": f"date:{target_date.isoformat()}",
                "source_url": source_url,
                "expected_available_at": expected_available_at,
                "last_attempt_at": now,
                "raw_object_id": write_record["sha256"],
                "last_sha256": write_record["sha256"],
                "row_count": None,
                "status": "succeeded",
                "last_success_at": now,
            })
        except WarehouseRuntimeError as exc:
            db.upsert_daily_index_checkpoint({
                "business_date": target_date.isoformat(),
                "source_key": f"date:{target_date.isoformat()}",
                "source_url": source_url,
                "expected_available_at": expected_available_at,
                "last_attempt_at": now,
                "status": "failed_retryable",
                "error_message": str(exc),
            })
            break  # Stop on first failure per spec

    return raw_writes, []


def _is_business_day(d: date) -> bool:
    """Return True if d is Monday-Friday (US federal holidays not yet filtered)."""
    return d.weekday() < 5  # 0=Monday, 4=Friday


def _expected_available_at(business_date: date) -> datetime:
    """Return the expected availability timestamp: 06:00 America/New_York on next calendar day.

    Stored as UTC (06:00 EST = 11:00 UTC, 06:00 EDT = 10:00 UTC).
    Using a conservative 11:00 UTC (EST) approximation.
    """
    next_day = business_date + timedelta(days=1)
    return datetime(next_day.year, next_day.month, next_day.day, 11, 0, 0, tzinfo=UTC)


def _write_bronze_object(
    context: WarehouseCommandContext,
    relative_path: str,
    source_name: str,
    source_url: str,
    payload: bytes,
    *,
    business_date: str | None = None,
    cik: int | None = None,
) -> dict[str, Any]:
    destination = context.bronze_root.write_bytes(relative_path, payload)
    record: dict[str, Any] = {
        "layer": "bronze_raw",
        "path": destination,
        "relative_path": relative_path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "source_name": source_name,
        "source_url": source_url,
    }
    if business_date is not None:
        record["business_date"] = business_date
    if cik is not None:
        record["cik"] = cik
    return record


def _download_sec_bytes(url: str, identity: str) -> bytes:
    last_error: Exception | None = None
    headers = {
        "Accept": "*/*",
        "User-Agent": identity,
    }
    timeout = httpx.Timeout(30.0, connect=10.0)
    for attempt in range(1, 4):
        try:
            with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status_code = exc.response.status_code
            if status_code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(attempt)
                continue
            raise WarehouseRuntimeError(f"SEC request failed for {url}: HTTP {status_code}") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
                continue
            raise WarehouseRuntimeError(f"SEC request failed for {url}: {exc}") from exc

    raise WarehouseRuntimeError(f"SEC request failed for {url}: {last_error}")


def _build_company_tickers_url() -> str:
    return f"{_sec_base_url()}/files/company_tickers.json"


def _build_company_tickers_exchange_url() -> str:
    return f"{_sec_base_url()}/files/company_tickers_exchange.json"


def _build_daily_index_url(target_date: date) -> str:
    quarter = ((target_date.month - 1) // 3) + 1
    return f"{_sec_archive_url()}/daily-index/{target_date.year}/QTR{quarter}/form.{target_date:%Y%m%d}.idx"


def _build_submissions_url(cik: int) -> str:
    return f"{_sec_data_url()}/submissions/CIK{cik:010d}.json"


def _build_submission_pagination_url(file_name: str) -> str:
    return f"{_sec_data_url()}/submissions/{file_name}"


def _sec_base_url() -> str:
    return os.environ.get("EDGAR_BASE_URL", "https://www.sec.gov").rstrip("/")


def _sec_data_url() -> str:
    return os.environ.get("EDGAR_DATA_URL", "https://data.sec.gov").rstrip("/")


def _sec_archive_url() -> str:
    return f"{_sec_base_url()}/Archives/edgar"


def _require_cik_list(raw_ciks: Any, command_name: str) -> list[int]:
    if not raw_ciks:
        raise WarehouseRuntimeError(
            f"{command_name} in bronze_capture mode requires --cik-list until sec_tracked_universe is implemented"
        )
    return [_parse_cik(value) for value in raw_ciks]


def _parse_cik(value: Any) -> int:
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise WarehouseRuntimeError(f"Invalid CIK value: {value}") from exc


def _decode_json_bytes(payload: bytes, source_url: str) -> dict[str, Any]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarehouseRuntimeError(f"Expected JSON payload from {source_url}") from exc
    if not isinstance(document, dict):
        raise WarehouseRuntimeError(f"Expected JSON object from {source_url}")
    return document


def _pagination_file_names(submissions_document: dict[str, Any]) -> list[str]:
    filings = submissions_document.get("filings", {})
    files = filings.get("files", []) if isinstance(filings, dict) else []
    if not isinstance(files, list):
        return []
    names: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        file_name = str(entry.get("name", "")).strip()
        if file_name:
            names.append(file_name)
    return names


def _extract_impacted_ciks_from_daily_index(payload: bytes, source_url: str) -> list[int]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WarehouseRuntimeError(f"Expected text daily index payload from {source_url}") from exc

    ciks: list[int] = []
    for line in text.splitlines():
        if "edgar/data/" not in line:
            continue
        match = _DAILY_INDEX_LINE_PATTERN.match(line.rstrip())
        if match is None:
            continue
        ciks.append(int(match.group("cik")))
    return _dedupe_ints(ciks)


def _apply_bronze_cik_limit(ciks: list[int]) -> list[int]:
    raw_limit = os.environ.get("WAREHOUSE_BRONZE_CIK_LIMIT", "").strip()
    if not raw_limit:
        return ciks
    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise WarehouseRuntimeError("WAREHOUSE_BRONZE_CIK_LIMIT must be a positive integer") from exc
    if limit <= 0:
        raise WarehouseRuntimeError("WAREHOUSE_BRONZE_CIK_LIMIT must be a positive integer")
    return ciks[:limit]


def _dedupe_ints(values: list[int]) -> list[int]:
    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _execute_snowflake_sync(
    context: SnowflakeSyncContext,
    command_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    workflow_name = str(arguments.get("workflow_name", "")).strip()
    if not workflow_name:
        raise WarehouseRuntimeError("workflow_name is required for snowflake-sync-after-load")

    run_id = _resolve_run_id(arguments)
    now = datetime.now(UTC)

    return {
        "arguments": arguments,
        "command": command_name,
        "environment": {
            "snowflake_export_root": context.export_root.root,
            "snowflake_runtime_metadata_present": True,
            "wif_only": True,
        },
        "message": (
            "Snowflake sync infrastructure validation completed successfully. "
            "The runtime metadata passed validation and the source-load plus refresh wrapper calls "
            "were derived."
        ),
        "source_load_call": (
            f"CALL {context.metadata['source_load_procedure']}('{workflow_name}', '{run_id}')"
        ),
        "refresh_call": (
            f"CALL {context.metadata['refresh_procedure']}('{workflow_name}', '{run_id}')"
        ),
        "run_id": run_id,
        "runtime_mode": "infrastructure_validation",
        "snowflake": {
            "account": context.metadata["account"],
            "database": context.metadata["database"],
            "source_schema": context.metadata["source_schema"],
            "gold_schema": context.metadata["gold_schema"],
            "refresh_warehouse": context.metadata["refresh_warehouse"],
            "runtime_role": context.metadata["runtime_role"],
            "stage_name": context.metadata["stage_name"],
            "file_format_name": context.metadata["file_format_name"],
            "status_table_name": context.metadata["status_table_name"],
            "source_load_procedure": context.metadata["source_load_procedure"],
            "storage_integration": context.metadata["storage_integration"],
        },
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "workflow_name": workflow_name,
    }


def _resolve_scope(command_name: str, arguments: dict[str, Any], now: datetime) -> dict[str, Any]:
    if command_name == "bootstrap-recent-10":
        return {
            "cik_list": arguments.get("cik_list"),
            "recent_limit": arguments.get("recent_limit"),
            "tracking_status_filter": arguments.get("tracking_status_filter"),
        }

    if command_name == "bootstrap-full":
        return {
            "cik_list": arguments.get("cik_list"),
            "tracking_status_filter": arguments.get("tracking_status_filter"),
        }

    if command_name == "daily-incremental":
        start_date = _parse_date(arguments.get("start_date"), "start_date")
        end_date = _parse_date(arguments.get("end_date"), "end_date")
        if start_date is None and end_date is None:
            start_date = _previous_business_day(now.date())
            end_date = start_date
        elif start_date is None:
            start_date = end_date
        elif end_date is None:
            end_date = start_date
        if start_date is None or end_date is None:
            raise WarehouseRuntimeError("daily_incremental could not resolve a business date range")
        if start_date > end_date:
            raise WarehouseRuntimeError("start_date must be on or before end_date")
        return {
            "business_date_start": start_date.isoformat(),
            "business_date_end": end_date.isoformat(),
            "tracking_status_filter": arguments.get("tracking_status_filter"),
        }

    if command_name == "load-daily-form-index-for-date":
        target_date = _parse_date(arguments.get("target_date"), "target_date")
        if target_date is None:
            raise WarehouseRuntimeError("target_date is required")
        return {"target_date": target_date.isoformat()}

    if command_name == "catch-up-daily-form-index":
        end_date = _parse_date(arguments.get("end_date"), "end_date")
        if end_date is None:
            end_date = _previous_business_day(now.date())
        return {"end_date": end_date.isoformat()}

    if command_name == "targeted-resync":
        return {
            "scope_key": arguments.get("scope_key"),
            "scope_type": arguments.get("scope_type"),
        }

    if command_name == "full-reconcile":
        return {
            "auto_heal": arguments.get("auto_heal"),
            "cik_list": arguments.get("cik_list"),
            "sample_limit": arguments.get("sample_limit"),
        }

    raise WarehouseRuntimeError(f"Unsupported warehouse command: {command_name}")


def _planned_writes(command_name: str, command_path: str, run_id: str, scope: dict[str, Any]) -> dict[str, str]:
    bronze_rel = f"runs/{command_path}/{run_id}/manifest.json"
    shared = {
        "artifacts": f"artifacts/runs/{command_path}/{run_id}/manifest.json",
        "staging": f"staging/runs/{command_path}/{run_id}/manifest.json",
    }

    if command_name in {"bootstrap-recent-10", "bootstrap-full", "daily-incremental", "targeted-resync", "full-reconcile"}:
        shared["silver"] = f"silver/sec/runs/{command_path}/{run_id}/manifest.json"
        shared["gold"] = f"gold/runs/{command_path}/{run_id}/manifest.json"
        shared["bronze"] = bronze_rel
        return {key: shared[key] for key in ("bronze", "staging", "silver", "gold", "artifacts")}

    if command_name == "load-daily-form-index-for-date":
        target_date = scope["target_date"]
        return {
            "bronze": f"daily-index/date={target_date}/{run_id}/manifest.json",
            "staging": f"staging/daily-index/date={target_date}/{run_id}/manifest.json",
            "artifacts": shared["artifacts"],
        }

    if command_name == "catch-up-daily-form-index":
        end_date = scope["end_date"]
        return {
            "bronze": f"daily-index/catch-up/end-date={end_date}/{run_id}/manifest.json",
            "staging": f"staging/daily-index/catch-up/end-date={end_date}/{run_id}/manifest.json",
            "artifacts": shared["artifacts"],
        }

    raise WarehouseRuntimeError(f"Unsupported warehouse command: {command_name}")


def _resolve_export_business_date(command_name: str, scope: dict[str, Any], now: datetime) -> str:
    if command_name == "daily-incremental":
        return str(scope["business_date_end"])
    if command_name == "load-daily-form-index-for-date":
        return str(scope["target_date"])
    if command_name == "catch-up-daily-form-index":
        return str(scope["end_date"])
    return now.date().isoformat()


def _layer_manifest(
    command_name: str,
    run_id: str,
    layer: str,
    relative_path: str,
    arguments: dict[str, Any],
    scope: dict[str, Any],
    now: datetime,
    runtime_mode: str,
) -> dict[str, Any]:
    return {
        "arguments": arguments,
        "command": command_name,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "layer": layer,
        "relative_path": relative_path,
        "run_id": run_id,
        "runtime_mode": runtime_mode,
        "scope": scope,
    }


def _snowflake_export_manifest(
    table_name: str,
    command_name: str,
    run_id: str,
    business_date: str,
    arguments: dict[str, Any],
    now: datetime,
    runtime_mode: str,
) -> dict[str, Any]:
    return {
        "business_date": business_date,
        "command": command_name,
        "compression": "snappy",
        "exported_at": now.isoformat().replace("+00:00", "Z"),
        "file_count": 0,
        "format": "parquet",
        "row_count": 0,
        "run_id": run_id,
        "runtime_mode": runtime_mode,
        "schema_version": 1,
        "table_name": table_name,
        "workflow_name": command_name.replace("-", "_"),
        "workflow_arguments": arguments,
    }


def _error_payload(command_name: str, arguments: dict[str, Any], message: str, runtime_mode: str = "infrastructure_validation") -> dict[str, Any]:
    return {
        "arguments": arguments,
        "command": command_name,
        "message": message,
        "runtime_mode": runtime_mode,
        "status": "error",
    }


def _parse_date(value: Any, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise WarehouseRuntimeError(f"{field_name} must be a date string in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise WarehouseRuntimeError(f"{field_name} must be a date string in YYYY-MM-DD format") from exc


def _previous_business_day(today: date) -> date:
    candidate = today - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _namespace_to_payload(args: Any) -> dict[str, Any]:
    payload = vars(args).copy()
    payload.pop("handler", None)
    return payload


def _resolve_run_id(arguments: dict[str, Any]) -> str:
    candidate = str(arguments.get("run_id", "") or "").strip()
    return candidate or str(uuid.uuid4())


def _warehouse_success_message(has_snowflake_exports: bool) -> str:
    if has_snowflake_exports:
        return (
            "Warehouse infrastructure validation completed successfully. "
            "Run manifests were written to the configured bronze, warehouse, and Snowflake export roots."
        )
    return (
        "Warehouse infrastructure validation completed successfully. "
        "Run manifests were written to the configured bronze and warehouse roots."
    )
