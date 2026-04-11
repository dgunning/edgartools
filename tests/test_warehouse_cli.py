import json

import pytest

from edgar.warehouse.cli import main


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
def test_warehouse_cli_stub_payload(capsys):
    exit_code = main(["bootstrap-recent-10", "--cik-list", "320193,789019"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "bootstrap-recent-10"
    assert payload["arguments"]["cik_list"] == [320193, 789019]
    assert payload["arguments"]["recent_limit"] == 10
