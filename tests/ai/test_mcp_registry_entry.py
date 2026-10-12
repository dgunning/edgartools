"""
The Official MCP Registry entry (server.json) and the `edgartools` console script it launches.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1413
Bead: edgartools-deq9

Registry clients build the launch command from server.json themselves. VS Code
(src/vs/platform/mcp/common/mcpManagementService.ts) emits, for a PyPI package,

    uvx <runtimeArguments> <identifier>@<version> <packageArguments>

so the executable uvx runs is always named after the package. Before this fix the
wheel had no `edgartools` executable (only `edgartools-mcp`), and the entry pinned
5.21.1, which resolves mcp 2.x and cannot import the server. These checks run
offline on every pull request; the end-to-end launch was verified by hand against
a locally built wheel with a real MCP client (13 tools, 7 prompts).
"""
import json
import sys
from pathlib import Path

import pytest
from packaging.version import Version

from edgar.__about__ import __version__

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def server_json():
    return json.loads((ROOT / "server.json").read_text())


@pytest.fixture(scope="module")
def package(server_json):
    return server_json["packages"][0]


def vscode_launch(package):
    """Assemble argv the way VS Code's mcpManagementService does for registryType pypi."""
    args = []
    for arg in package.get("runtimeArguments", []):
        args += [arg["name"], arg["value"]] if arg["type"] == "named" else [arg["value"]]
    args.append(f'{package["identifier"]}@{package["version"]}')
    for arg in package.get("packageArguments", []):
        args += [arg["name"], arg["value"]] if arg["type"] == "named" else [arg["value"]]
    return [package["runtimeHint"], *args]


class TestServerJson:

    def test_launch_command_runs_the_mcp_subcommand_with_the_ai_extra(self, package):
        version = package["version"]
        assert vscode_launch(package) == [
            "uvx", "--with", f"edgartools[ai]=={version}", f"edgartools@{version}", "mcp",
        ]

    def test_versions_agree(self, server_json, package):
        assert server_json["version"] == package["version"]
        assert package["runtimeArguments"][0]["value"] == f'edgartools[ai]=={package["version"]}'

    def test_entry_is_never_behind_the_library(self, server_json):
        # The registry entry was hand-published at 5.21.1 and then forgotten for 39 releases.
        # Bump server.json in every release commit, then republish with mcp-publisher.
        assert Version(server_json["version"]) >= Version(__version__)

    def test_identity_is_required(self, package):
        env = {e["name"]: e for e in package["environmentVariables"]}
        assert env["EDGAR_IDENTITY"]["isRequired"] is True

    def test_name_matches_the_readme_ownership_marker(self, server_json):
        # The registry verifies PyPI ownership by finding this marker in the package description.
        assert f'<!-- mcp-name: {server_json["name"]} -->' in (ROOT / "README.md").read_text()


@pytest.fixture(scope="module")
def console_scripts():
    tomllib = pytest.importorskip("tomllib")  # stdlib from 3.11; the 3.10 floor goes in 6.0
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]


class TestConsoleScripts:

    def test_executable_named_after_the_package_exists(self, console_scripts):
        scripts = console_scripts
        assert scripts["edgartools"] == "edgar._cli:main"
        assert scripts["edgartools-mcp"] == "edgar.ai.mcp.server:main"

    def test_every_console_script_target_is_shipped(self, console_scripts):
        # edgar-test pointed at tests.harness.cli, which is in neither the wheel nor the repo.
        for name, target in console_scripts.items():
            assert target.startswith("edgar."), f"{name} -> {target} is not in the edgar package"


class TestEdgartoolsCli:

    def test_mcp_subcommand_forwards_its_arguments(self, monkeypatch):
        import edgar.ai.mcp.server as server
        from edgar._cli import main

        received = []
        monkeypatch.setattr(server, "main", lambda argv: received.append(argv))
        main(["mcp", "--transport", "stdio", "--test"])
        assert received == [["--transport", "stdio", "--test"]]

    def test_unknown_command_exits_with_usage(self):
        from edgar._cli import main

        with pytest.raises(SystemExit) as exc:
            main(["serve"])
        assert "unknown command 'serve'" in str(exc.value.code)
        assert "edgartools mcp" in str(exc.value.code)

    def test_no_command_prints_usage_and_fails(self, capsys):
        from edgar._cli import main

        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2
        assert "usage: edgartools mcp" in capsys.readouterr().out

    def test_missing_ai_extra_says_how_to_install_it(self, monkeypatch):
        from edgar._cli import main

        # None in sys.modules makes the import raise ImportError, as it does without mcp installed.
        monkeypatch.setitem(sys.modules, "edgar.ai.mcp.server", None)
        with pytest.raises(SystemExit) as exc:
            main(["mcp"])
        assert "needs the [ai] extra" in exc.value.code
        assert "uvx --from 'edgartools[ai]' edgartools mcp" in exc.value.code
