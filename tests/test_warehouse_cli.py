import json
import shutil
import uuid
from pathlib import Path

import pytest

from edgar.warehouse.cli import main


@pytest.fixture
def workspace_tmp_dir():
    base_dir = Path.cwd() / ".tmp-warehouse-tests"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f"run-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.fast
@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["bootstrap-full", "--help"],
        ["bootstrap-recent-10", "--help"],
        ["daily-incremental", "--help"],
        ["load-daily-form-index-for-date", "--help"],
        ["catch-up-daily-form-index", "--help"],
        ["targeted-resync", "--help"],
        ["full-reconcile", "--help"],
    ],
)
def test_warehouse_cli_help(argv, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "edgar-warehouse" in captured.out or "usage:" in captured.out


@pytest.mark.fast
@pytest.mark.parametrize(
    ("argv", "expected_layers"),
    [
        (["bootstrap-full"], {"bronze", "staging", "silver", "gold", "artifacts"}),
        (["bootstrap-recent-10"], {"bronze", "staging", "silver", "gold", "artifacts"}),
        (["daily-incremental"], {"bronze", "staging", "silver", "gold", "artifacts"}),
        (["load-daily-form-index-for-date", "2026-04-10"], {"bronze", "staging", "artifacts"}),
        (["catch-up-daily-form-index"], {"bronze", "staging", "artifacts"}),
        (["targeted-resync", "--scope-type", "cik", "--scope-key", "320193"], {"bronze", "staging", "silver", "gold", "artifacts"}),
        (["full-reconcile"], {"bronze", "staging", "silver", "gold", "artifacts"}),
    ],
)
def test_warehouse_cli_runtime_writes_expected_layers(argv, expected_layers, capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))

    exit_code = main(argv)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["runtime_mode"] == "infrastructure_validation"
    assert payload["command"] == argv[0]
    assert {write["layer"] for write in payload["writes"]} == expected_layers

    for write in payload["writes"]:
        assert Path(write["path"]).exists()


@pytest.mark.fast
def test_warehouse_cli_bootstrap_recent_10_preserves_bucket_separation(capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))

    exit_code = main(["bootstrap-recent-10", "--cik-list", "320193,789019"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["arguments"]["cik_list"] == [320193, 789019]
    assert payload["scope"]["recent_limit"] == 10

    assert (bronze_root / "runs").exists()
    assert not (bronze_root / "silver").exists()
    assert not (bronze_root / "gold").exists()
    assert (warehouse_root / "staging").exists()
    assert (warehouse_root / "silver" / "sec").exists()
    assert (warehouse_root / "gold").exists()
    assert (warehouse_root / "artifacts").exists()


@pytest.mark.fast
def test_warehouse_cli_requires_storage_roots(capsys, monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.delenv("WAREHOUSE_BRONZE_ROOT", raising=False)
    monkeypatch.delenv("WAREHOUSE_STORAGE_ROOT", raising=False)

    exit_code = main(["bootstrap-recent-10"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "WAREHOUSE_BRONZE_ROOT" in payload["message"]


@pytest.mark.fast
def test_warehouse_cli_validates_iso_dates(capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))

    exit_code = main(["load-daily-form-index-for-date", "2026/04/10"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "YYYY-MM-DD" in payload["message"]
