import json
import shutil
import uuid
from pathlib import Path

import pytest

import edgar_warehouse.runtime as warehouse_runtime
from edgar_warehouse.cli import main


def _snowflake_runtime_metadata() -> str:
    return json.dumps(
        {
            "account": "acme-account",
            "database": "EDGARTOOLS_DEV",
            "source_schema": "EDGARTOOLS_SOURCE",
            "gold_schema": "EDGARTOOLS_GOLD",
            "refresh_warehouse": "EDGARTOOLS_DEV_REFRESH_WH",
            "runtime_role": "EDGARTOOLS_DEV_REFRESHER",
            "storage_integration": "EDGARTOOLS_DEV_S3_INTEGRATION",
            "stage_name": "EDGARTOOLS_SOURCE_EXPORT_STAGE",
            "file_format_name": "EDGARTOOLS_SOURCE_EXPORT_FILE_FORMAT",
            "status_table_name": "SNOWFLAKE_REFRESH_STATUS",
            "source_load_procedure": "EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN",
            "refresh_procedure": "EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD",
        }
    )


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
        ["snowflake-sync-after-load", "--help"],
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
        (["bootstrap-full"], {"bronze", "staging", "silver", "gold", "artifacts", "snowflake_export"}),
        (["bootstrap-recent-10"], {"bronze", "staging", "silver", "gold", "artifacts", "snowflake_export"}),
        (["daily-incremental"], {"bronze", "staging", "silver", "gold", "artifacts", "snowflake_export"}),
        (["load-daily-form-index-for-date", "2026-04-10"], {"bronze", "staging", "artifacts"}),
        (["catch-up-daily-form-index"], {"bronze", "staging", "artifacts"}),
        (
            ["targeted-resync", "--scope-type", "cik", "--scope-key", "320193"],
            {"bronze", "staging", "silver", "gold", "artifacts", "snowflake_export"},
        ),
        (["full-reconcile"], {"bronze", "staging", "silver", "gold", "artifacts", "snowflake_export"}),
    ],
)
def test_warehouse_cli_runtime_writes_expected_layers(argv, expected_layers, capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))

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
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))

    run_id = "bootstrap-recent-10-test-run"
    exit_code = main(["bootstrap-recent-10", "--cik-list", "320193,789019", "--run-id", run_id])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["arguments"]["cik_list"] == [320193, 789019]
    assert payload["scope"]["recent_limit"] == 10
    assert payload["run_id"] == run_id

    assert (bronze_root / "runs").exists()
    assert not (bronze_root / "silver").exists()
    assert not (bronze_root / "gold").exists()
    assert (warehouse_root / "staging").exists()
    assert (warehouse_root / "silver" / "sec").exists()
    assert (warehouse_root / "gold").exists()
    assert (warehouse_root / "artifacts").exists()
    company_export = next(
        write for write in payload["writes"] if write["layer"] == "snowflake_export" and write["table_name"] == "COMPANY"
    )
    assert Path(company_export["path"]).exists()


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


@pytest.mark.fast
def test_gold_affecting_commands_require_snowflake_export_root(capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.delenv("SNOWFLAKE_EXPORT_ROOT", raising=False)

    exit_code = main(["bootstrap-full"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "SNOWFLAKE_EXPORT_ROOT" in payload["message"]


@pytest.mark.fast
def test_snowflake_sync_after_load_validates_runtime_metadata(capsys, monkeypatch, workspace_tmp_dir):
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"

    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))
    monkeypatch.setenv("SNOWFLAKE_RUNTIME_METADATA", _snowflake_runtime_metadata())

    exit_code = main(
        [
            "snowflake-sync-after-load",
            "--workflow-name",
            "daily_incremental",
            "--run-id",
            "snowflake-sync-run",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["snowflake"]["database"] == "EDGARTOOLS_DEV"
    assert payload["snowflake"]["runtime_role"] == "EDGARTOOLS_DEV_REFRESHER"
    assert payload["snowflake"]["file_format_name"] == "EDGARTOOLS_SOURCE_EXPORT_FILE_FORMAT"
    assert payload["source_load_call"] == "CALL EDGARTOOLS_SOURCE.LOAD_EXPORTS_FOR_RUN('daily_incremental', 'snowflake-sync-run')"
    assert payload["refresh_call"] == "CALL EDGARTOOLS_GOLD.REFRESH_AFTER_LOAD('daily_incremental', 'snowflake-sync-run')"


@pytest.mark.fast
def test_snowflake_sync_after_load_rejects_credential_material(capsys, monkeypatch, workspace_tmp_dir):
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"
    metadata = json.loads(_snowflake_runtime_metadata())
    metadata["password"] = "not-allowed"

    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))
    monkeypatch.setenv("SNOWFLAKE_RUNTIME_METADATA", json.dumps(metadata))

    exit_code = main(
        [
            "snowflake-sync-after-load",
            "--workflow-name",
            "daily_incremental",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "credential material" in payload["message"]


@pytest.mark.fast
def test_bronze_capture_daily_incremental_writes_reference_and_daily_index_raw_objects(
    capsys,
    monkeypatch,
    workspace_tmp_dir,
):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"
    fetch_day_parts = warehouse_runtime.datetime.now(warehouse_runtime.UTC).date().strftime("%Y/%m/%d")
    company_tickers_payload = Path("data/company_tickers.json").read_bytes()
    exchange_payload = b'{\"fields\":[\"cik\",\"name\",\"ticker\",\"exchange\"],\"data\":[[320193,\"Apple Inc.\",\"AAPL\",\"Nasdaq\"]]}'
    daily_index_payload = (
        b"Description: Daily Index of EDGAR Dissemination Feed by Form Type\n"
        b"Last Data Received:    Apr 10, 2026\n"
        b"Comments:              webmaster@sec.gov\n"
        b"Anonymous FTP:         ftp://ftp.sec.gov/edgar/\n"
        b"\n\n\n\n"
        b"Form Type   Company Name                                                  CIK         Date Filed  File Name\n"
        b"---------------------------------------------------------------------------------------------------------------------------------------------\n"
        b"10-K             Apple Inc.                                                   320193     20260410    edgar/data/320193/0000320193-26-000001.txt\n"
        b"10-Q             MICROSOFT CORP                                               789019     20260410    edgar/data/789019/0000789019-26-000001.txt\n"
    )
    submissions_payload = {
        "320193": {"cik": "0000320193", "filings": {"recent": {"accessionNumber": ["0000320193-26-000001"]}, "files": []}},
        "789019": {"cik": "0000789019", "filings": {"recent": {"accessionNumber": ["0000789019-26-000001"]}, "files": []}},
    }

    def fake_download(url: str, identity: str) -> bytes:
        assert identity == "Warehouse Test warehouse-test@example.com"
        if url.endswith("/files/company_tickers.json"):
            return company_tickers_payload
        if url.endswith("/files/company_tickers_exchange.json"):
            return exchange_payload
        if url.endswith("/daily-index/2026/QTR2/form.20260410.idx"):
            return daily_index_payload
        if url.endswith("/submissions/CIK0000320193.json"):
            return json.dumps(submissions_payload["320193"]).encode("utf-8")
        if url.endswith("/submissions/CIK0000789019.json"):
            return json.dumps(submissions_payload["789019"]).encode("utf-8")
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(warehouse_runtime, "_download_sec_bytes", fake_download)
    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_RUNTIME_MODE", "bronze_capture")
    monkeypatch.setenv("WAREHOUSE_BRONZE_CIK_LIMIT", "2")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))

    exit_code = main(["daily-incremental", "--start-date", "2026-04-10", "--include-reference-refresh"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_mode"] == "bronze_capture"
    assert payload["bronze_object_count"] == 5
    assert {item["source_name"] for item in payload["raw_writes"]} == {
        "company_tickers",
        "company_tickers_exchange",
        "daily_index",
        "submissions_main",
    }
    assert any(item["relative_path"].endswith(f"reference/sec/company_tickers/{fetch_day_parts}/company_tickers.json") for item in payload["raw_writes"])
    assert any(item["relative_path"].endswith(f"reference/sec/company_tickers_exchange/{fetch_day_parts}/company_tickers_exchange.json") for item in payload["raw_writes"])
    assert any(item["relative_path"].endswith("daily_index/sec/2026/04/10/form.20260410.idx") for item in payload["raw_writes"])
    assert any(item["relative_path"].endswith(f"submissions/sec/cik=320193/main/{fetch_day_parts}/CIK0000320193.json") for item in payload["raw_writes"])
    assert any(item["relative_path"].endswith(f"submissions/sec/cik=789019/main/{fetch_day_parts}/CIK0000789019.json") for item in payload["raw_writes"])
    for item in payload["raw_writes"]:
        assert Path(item["path"]).exists()


@pytest.mark.fast
def test_bronze_capture_bootstrap_recent_10_writes_main_submissions_only(capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"
    fetch_day_parts = warehouse_runtime.datetime.now(warehouse_runtime.UTC).date().strftime("%Y/%m/%d")
    submissions_payload = {
        "cik": "0000320193",
        "filings": {
            "recent": {"accessionNumber": ["0000320193-26-000001"]},
            "files": [{"name": "CIK0000320193-submissions-001.json"}],
        },
    }

    def fake_download(url: str, identity: str) -> bytes:
        assert identity == "Warehouse Test warehouse-test@example.com"
        if url.endswith("/submissions/CIK0000320193.json"):
            return json.dumps(submissions_payload).encode("utf-8")
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(warehouse_runtime, "_download_sec_bytes", fake_download)
    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_RUNTIME_MODE", "bronze_capture")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))

    exit_code = main(["bootstrap-recent-10", "--cik-list", "320193", "--no-include-reference-refresh"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_mode"] == "bronze_capture"
    assert payload["bronze_object_count"] == 1
    assert payload["raw_writes"][0]["source_name"] == "submissions_main"
    assert payload["raw_writes"][0]["relative_path"].endswith(
        f"submissions/sec/cik=320193/main/{fetch_day_parts}/CIK0000320193.json"
    )


@pytest.mark.fast
def test_bronze_capture_bootstrap_full_writes_main_and_pagination_submissions(capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"
    submissions_payload = {
        "cik": "0000320193",
        "filings": {
            "recent": {"accessionNumber": ["0000320193-26-000001"]},
            "files": [{"name": "CIK0000320193-submissions-001.json"}],
        },
    }
    pagination_payload = {"accessionNumber": ["0000320193-15-000001"]}

    def fake_download(url: str, identity: str) -> bytes:
        assert identity == "Warehouse Test warehouse-test@example.com"
        if url.endswith("/submissions/CIK0000320193.json"):
            return json.dumps(submissions_payload).encode("utf-8")
        if url.endswith("/submissions/CIK0000320193-submissions-001.json"):
            return json.dumps(pagination_payload).encode("utf-8")
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(warehouse_runtime, "_download_sec_bytes", fake_download)
    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_RUNTIME_MODE", "bronze_capture")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))

    exit_code = main(["bootstrap-full", "--cik-list", "320193", "--no-include-reference-refresh"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_mode"] == "bronze_capture"
    assert payload["bronze_object_count"] == 2
    assert {item["source_name"] for item in payload["raw_writes"]} == {"submissions_main", "submissions_pagination"}


@pytest.mark.fast
def test_bronze_capture_requires_explicit_cik_list_for_bootstrap_scope(capsys, monkeypatch, workspace_tmp_dir):
    bronze_root = workspace_tmp_dir / "bronze-root" / "warehouse" / "bronze"
    warehouse_root = workspace_tmp_dir / "warehouse-root" / "warehouse"
    snowflake_export_root = workspace_tmp_dir / "snowflake-export-root"

    monkeypatch.setenv("EDGAR_IDENTITY", "Warehouse Test warehouse-test@example.com")
    monkeypatch.setenv("WAREHOUSE_RUNTIME_MODE", "bronze_capture")
    monkeypatch.setenv("WAREHOUSE_BRONZE_ROOT", str(bronze_root))
    monkeypatch.setenv("WAREHOUSE_STORAGE_ROOT", str(warehouse_root))
    monkeypatch.setenv("SNOWFLAKE_EXPORT_ROOT", str(snowflake_export_root))

    exit_code = main(["bootstrap-recent-10", "--no-include-reference-refresh"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime_mode"] == "bronze_capture"
    assert "--cik-list" in payload["message"]
