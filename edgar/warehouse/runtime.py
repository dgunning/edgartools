"""Warehouse runtime helpers for infrastructure-oriented command execution."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


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
        destination = self.join(relative_path)
        if self.is_remote:
            protocol = self.root.split("://", 1)[0]
            import fsspec

            fs = fsspec.filesystem(protocol)
            with fs.open(destination, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            return destination

        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return str(destination_path)


@dataclass(frozen=True)
class CommandContext:
    """Runtime context shared by warehouse commands."""

    bronze_root: StorageLocation
    storage_root: StorageLocation
    identity: str


def run_command(command_name: str, args: Any) -> int:
    """Execute a warehouse command and emit a JSON result payload."""
    arguments = _namespace_to_payload(args)
    try:
        context = _build_context()
        payload = _execute(context=context, command_name=command_name, arguments=arguments)
    except WarehouseRuntimeError as exc:
        print(json.dumps(_error_payload(command_name, arguments, str(exc)), indent=2, sort_keys=True))
        return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _build_context() -> CommandContext:
    identity = os.environ.get("EDGAR_IDENTITY", "").strip()
    if not identity:
        raise WarehouseRuntimeError("EDGAR_IDENTITY is required for warehouse commands")
    if "@" not in identity:
        raise WarehouseRuntimeError("EDGAR_IDENTITY must include an email address")

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

    return CommandContext(
        bronze_root=bronze_root,
        storage_root=storage_root,
        identity=identity,
    )


def _execute(context: CommandContext, command_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    run_id = str(uuid.uuid4())
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
        )
        writes.append(
            {
                "layer": layer,
                "path": target.write_json(relative_path, manifest),
                "relative_path": relative_path,
            }
        )

    return {
        "arguments": arguments,
        "command": command_name,
        "environment": {
            "bronze_root": context.bronze_root.root,
            "warehouse_root": context.storage_root.root,
            "identity_present": True,
        },
        "message": (
            "Warehouse infrastructure validation completed successfully. "
            "Run manifests were written to the configured bronze and warehouse roots."
        ),
        "run_id": run_id,
        "runtime_mode": "infrastructure_validation",
        "scope": scope,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "writes": writes,
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


def _layer_manifest(
    command_name: str,
    run_id: str,
    layer: str,
    relative_path: str,
    arguments: dict[str, Any],
    scope: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    return {
        "arguments": arguments,
        "command": command_name,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "layer": layer,
        "relative_path": relative_path,
        "run_id": run_id,
        "runtime_mode": "infrastructure_validation",
        "scope": scope,
    }


def _error_payload(command_name: str, arguments: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "arguments": arguments,
        "command": command_name,
        "message": message,
        "runtime_mode": "infrastructure_validation",
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
