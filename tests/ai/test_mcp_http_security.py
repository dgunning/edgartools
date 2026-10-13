"""
The MCP server's Streamable HTTP transport and the dependency floors a security scan reads.

mcp-marketplace.io scored 5.61.0 at 4.2/10. Its 13 dependency findings were the floors in
pyproject.toml, not what installs: pip-audit finds nothing in a fresh `edgartools[ai]`
resolve, but pyarrow 17.0.0, lxml 4.4, orjson 3.6.0, pydantic 2.0.0, jinja2 3.1.0 and
tqdm 4.62.0 all carry advisories, as do the [ai] extra's starlette 0.36.0 and mcp 1.12.3.

The HTTP transport defaulted to 0.0.0.0 with no Host/Origin check, so any machine on the
network, or any web page through DNS rebinding, could drive it under the user's
EDGAR_IDENTITY. It now binds 127.0.0.1 and rejects foreign Host and Origin headers there.
"""
import logging
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from starlette.testclient import TestClient  # noqa: E402

from edgar.ai.mcp import server  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

INITIALIZE = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def http_app(monkeypatch):
    """The Starlette app `_run_http` builds, captured instead of served."""
    import uvicorn

    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port: captured.update(app=app, host=host, port=port))

    def build(host, port=8000):
        server._run_http(host, port, "test")
        return captured["app"]

    return build


@pytest.mark.fast
def test_http_transport_binds_loopback_by_default():
    assert server._parse_args(["--transport", "streamable-http"]).host == "127.0.0.1"


@pytest.mark.fast
@pytest.mark.parametrize("extra, status", [
    ({}, 200),                                    # a local client sends no Origin
    ({"Origin": "http://localhost:8000"}, 200),
    ({"Host": "evil.example"}, 421),              # DNS rebinding: the page's own name
    ({"Origin": "http://evil.example"}, 403),     # a foreign page calling localhost
])
def test_loopback_server_rejects_foreign_host_and_origin(http_app, extra, status):
    with TestClient(http_app("127.0.0.1"), base_url="http://127.0.0.1:8000") as client:
        response = client.post("/mcp", json=INITIALIZE, headers={**HEADERS, **extra})
    assert response.status_code == status


@pytest.mark.fast
def test_network_bound_server_accepts_any_host_and_says_it_is_unauthenticated(http_app, caplog):
    with caplog.at_level(logging.WARNING, logger="edgartools-mcp"):
        app = http_app("0.0.0.0")  # noqa: S104 - the case under test
    assert "reachable from other machines and has no authentication" in caplog.text

    with TestClient(app, base_url="http://mcp.internal:8000") as client:
        response = client.post("/mcp", json=INITIALIZE, headers=HEADERS)
    assert response.status_code == 200


# Each floor is the first release without a known advisory (pip-audit, 2026-10-06).
PATCHED_FLOORS = {
    "pyarrow": "23.0.1",
    "lxml": "6.1.0",
    "orjson": "3.11.6",
    "pydantic": "2.4.0",
    "jinja2": "3.1.6",
    "tqdm": "4.66.3",
    "mcp": "1.28.1",
    "starlette": "1.3.1",
}


def _version(text):
    return tuple(int(part) for part in text.split("."))


@pytest.mark.fast
@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib is stdlib from 3.11")
def test_dependency_floors_exclude_versions_with_known_advisories():
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    declared = project["dependencies"] + project["optional-dependencies"]["ai"]
    floors = {}
    for spec in declared:
        match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*>=\s*([0-9.]+)", spec)
        if match:
            floors[match.group(1).lower()] = match.group(2)

    for name, patched in PATCHED_FLOORS.items():
        assert _version(floors[name]) >= _version(patched), f"{name}>={floors[name]} admits a version with a known advisory"
