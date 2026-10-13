"""Regression test for issue: DeprecationWarning emitted at `import edgar` time.

The legacy ``edgar.files`` modules once warned at module top, and edgartools
imported them during its own startup, so every ``import edgar`` warned and
downstream suites running under ``-W error`` broke. Those modules were removed
in 6.0, together with the tests of their per-class deprecation warnings. The
property that matters to users survives them and is pinned here: importing
edgartools must not warn.
"""

import subprocess
import sys


def _run_python(code: str, *args: str) -> subprocess.CompletedProcess:
    """Run a snippet in a clean Python interpreter."""
    return subprocess.run(
        [sys.executable, *args, "-c", code],
        capture_output=True,
        text=True,
    )


def test_import_edgar_under_W_error():
    """`python -W error -c "import edgar"` must succeed cleanly.

    A fresh interpreter is required so module-import side effects run
    end-to-end; doing this in-process would hit cached modules.
    """
    result = _run_python("import edgar", "-W", "error")
    assert result.returncode == 0, (
        f"import edgar under -W error failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
