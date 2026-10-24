"""
set_identity() must not write the identity (name + email) to INFO logs.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1727
"""
import logging
import os

from edgar.settings import set_identity


def test_set_identity_does_not_log_email_or_name(caplog):
    old = os.environ.get("EDGAR_IDENTITY")
    try:
        with caplog.at_level(logging.DEBUG):
            set_identity("Jane Q Tester jane.tester@example.com")
        assert any("set" in r.getMessage() for r in caplog.records)
        text = "\n".join(r.getMessage() + str(r.args) for r in caplog.records)
        assert "jane.tester@example.com" not in text
        assert "Jane Q Tester" not in text
        assert os.environ["EDGAR_IDENTITY"] == "Jane Q Tester jane.tester@example.com"
    finally:
        if old is None:
            os.environ.pop("EDGAR_IDENTITY", None)
        else:
            os.environ["EDGAR_IDENTITY"] = old
            set_identity(old)


def test_mcp_server_self_check_does_not_print_identity(monkeypatch, capsys):
    from edgar.ai.mcp.server import test_server

    monkeypatch.setenv("EDGAR_IDENTITY", "Jane Q Tester jane.tester@example.com")
    test_server()
    out = capsys.readouterr().out
    assert "EDGAR_IDENTITY configured" in out
    assert "jane.tester@example.com" not in out
    assert "Jane Q Tester" not in out
