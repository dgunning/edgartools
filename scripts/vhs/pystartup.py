"""Off-camera REPL prelude for VHS recordings.

Loaded via PYTHONSTARTUP inside the recording container so that on-camera we
only ever type the one expression we want to demo. Responsibilities:

  1. Set the SEC identity (required for EDGAR access).
  2. Pre-import the common entry points so typing is short and fetches are warm.
  3. Install a Rich display hook so a bare REPL expression (e.g.
     ``Company("AAPL").get_financials().income_statement()``) renders the
     formatted table in full colour at a deterministic width — instead of the
     default ``repr()``.

Nothing here should print to stdout; the launch command is hidden in the tape,
so any stray output would leak into the clean opening frame.
"""
import os
import sys

from rich.console import Console

# Fixed width keeps table layout identical across renders regardless of the
# PTY size VHS happens to allocate. force_terminal=True keeps colour on.
_DEMO_WIDTH = int(os.environ.get("VHS_CONSOLE_WIDTH", "100"))
_console = Console(width=_DEMO_WIDTH, force_terminal=True)


def _rich_displayhook(value):
    """Render REPL results through Rich (uses __rich__ when available)."""
    if value is None:
        return
    # Keep `_` working like the standard REPL does.
    import builtins
    builtins._ = value
    _console.print(value)


sys.displayhook = _rich_displayhook

# Identity: prefer the env var passed into the container, fall back to a
# generic demo identity so recordings never fail on a missing identity.
from edgar import set_identity  # noqa: E402

set_identity(os.environ.get("EDGAR_IDENTITY") or "EdgarTools Demo demo@edgartools.io")

# Common entry points — pre-imported so on-camera lines stay short.
from edgar import (  # noqa: E402,F401
    Company,
    Fund,
    find,
    find_funds,
    get_current_filings,
    get_filings,
)
