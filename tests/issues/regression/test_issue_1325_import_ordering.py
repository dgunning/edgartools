"""GH #1325: importing an ``edgar`` submodule from a thread while another thread
imports ``edgar`` fails deterministically.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1325

`docs/common-pitfalls.md` tells users to import ``edgar`` once on the main thread
before starting any thread that imports a submodule. This pins that advice: if the
documented pattern ever stops working, the documentation is wrong and this fails.

The unsafe ordering is deliberately not asserted. It depends on thread interleaving,
so asserting the failure would be a flaky test that says nothing useful; the
structural fix is tracked for 6.0 (lazy submodule loading).
"""
import os
import subprocess
import sys

import pytest

# The documented pattern: warm `edgar` on the main thread, then let threads reach
# for submodules. Uses several submodules, since the ordering rule is not specific
# to edgar.reference.
DOCUMENTED_PATTERN = """
import edgar                      # warm on the main thread first
import threading

results = {}
barrier = threading.Barrier(4)

def grab(name, fn):
    try:
        barrier.wait(timeout=30)
        fn()
        results[name] = "ok"
    except BaseException as exc:            # noqa: BLE001 - the failure is the point
        results[name] = f"{type(exc).__name__}: {exc}"

def a():
    from edgar.reference import describe_form  # noqa: F401
def b():
    from edgar.entity import Entity            # noqa: F401
def c():
    import edgar                               # noqa: F401

threads = [threading.Thread(target=grab, args=(n, f), daemon=True)
           for n, f in (("reference", a), ("entity", b), ("edgar", c))]
for t in threads:
    t.start()
barrier.wait(timeout=30)
for t in threads:
    t.join(timeout=60)

bad = {k: v for k, v in results.items() if v != "ok"}
assert not bad, bad
assert len(results) == 3, results
print("OK")
"""


def _run(source: str) -> subprocess.CompletedProcess:
    """Run `source` in a fresh interpreter with a clean, explicit environment.

    The environment is built rather than inherited so an ambient setting on the
    developer's machine cannot change what the child imports.
    """
    env = {
        k: v for k, v in os.environ.items()
        if k in ("PATH", "PYTHONPATH", "HOME", "SYSTEMROOT", "TEMP", "TMP", "EDGAR_IDENTITY")
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True, text=True, timeout=180,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        env=env,
    )


@pytest.mark.fast
def test_documented_import_ordering_lets_threads_import_submodules():
    """Warming `edgar` first, as the docs say, keeps threaded submodule imports safe."""
    result = _run(DOCUMENTED_PATTERN)
    assert result.returncode == 0, (
        "The import ordering documented in docs/common-pitfalls.md no longer works.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr[-2000:]}"
    )
    assert "OK" in result.stdout


@pytest.mark.fast
def test_plain_import_edgar_is_unaffected():
    """The ordinary single-threaded import keeps working; the rule is threads-only."""
    result = _run("from edgar.reference import describe_form\nprint('OK')\n")
    assert result.returncode == 0, result.stderr[-2000:]
    assert "OK" in result.stdout
