"""
`from edgar import *` must not warn.

Bead: edgartools-2db17

The README Quick Start tells every new user to run `from edgar import *`. Up to
5.62.0 that line printed three DeprecationWarnings, one each for NORMAL, CAUTION
and CRAWL. The access modes (GH #1326) are served lazily so `import edgar` stays
silent, but they were still listed in `__all__`, and a star-import resolves every
name in `__all__`. `edgar.core` and `edgar.settings` had the same problem.

Each star-import runs in a fresh interpreter: the deprecation fires once per
lookup, but whether it reaches the user depends on a clean warnings registry,
which an in-process pytest run does not have.
"""
import os
import subprocess
import sys

import pytest


def _run(code: str) -> subprocess.CompletedProcess:
    env = {**os.environ}
    env.pop("EDGAR_ACCESS_MODE", None)  # setting it warns at import, by design
    return subprocess.run(  # noqa: S603 -- sys.executable with a literal argv, no shell
        [sys.executable, "-W", "error::DeprecationWarning", "-c", code],
        capture_output=True, text=True, timeout=180, env=env,
    )


@pytest.mark.parametrize("module", ["edgar", "edgar.core", "edgar.settings"])
def test_star_import_raises_no_deprecation_warning(module):
    result = _run(f"from {module} import *")
    assert result.returncode == 0, (
        f"`from {module} import *` raised under -W error::DeprecationWarning:\n"
        f"{result.stderr[-1500:]}"
    )


def test_star_import_still_brings_in_the_readme_names():
    """Silence by emptying __all__ would pass the test above; this rules that out."""
    result = _run(
        "from edgar import *\n"
        "assert callable(set_identity) and Company and get_filings and Filing\n"
        "assert 'NORMAL' not in dir()\n"
    )
    assert result.returncode == 0, result.stderr[-1500:]


def test_naming_a_mode_still_warns():
    """Out of __all__ is not removed: the explicit import keeps its deprecation."""
    result = _run("from edgar import CAUTION")
    assert result.returncode != 0
    assert "CAUTION is deprecated" in result.stderr
