"""The ``edgartools`` console script.

MCP clients that install from the Official MCP Registry launch a PyPI server as
``uvx [runtime args] edgartools@<version> [package args]``, so the executable is
always named after the package. ``server.json`` passes ``mcp`` as the package
argument; the subcommand keeps the ``edgartools`` name free for other commands.
"""
import sys

USAGE = "usage: edgartools mcp [--transport {stdio,streamable-http}] [--host HOST] [--port PORT] [--test]"


def main(argv: list[str] | None = None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(USAGE + "\n")
        sys.exit(0 if argv else 2)

    command, rest = argv[0], argv[1:]
    if command != "mcp":
        sys.exit(f"edgartools: unknown command {command!r}\n{USAGE}")

    try:
        from edgar.ai.mcp.server import main as mcp_main
    except ImportError as e:
        sys.exit(f"edgartools mcp needs the [ai] extra ({e}). "
                 "Run: uvx --from 'edgartools[ai]' edgartools mcp")
    mcp_main(rest)
