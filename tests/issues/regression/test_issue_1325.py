"""
Regression test for GitHub issue #1325: importing edgar from two threads failed

One thread running ``import edgar`` and another running
``from edgar.reference import describe_form`` made both imports fail, 3 of 3:
the second thread held ``edgar.reference``'s import lock and needed ``edgar``,
while ``edgar/__init__.py`` held ``edgar``'s lock and imported its submodules
eagerly, ten of which reach ``edgar.reference``. Removing single edges only moved
the failure, so the fix is structural: ``import edgar`` imports no submodule, and
each top-level name loads its module on first use (PEP 562 ``__getattr__``).

Both tests run in a fresh interpreter, because the fact under test is what the
first ``import edgar`` of a process does. Every child is bounded by a timeout, so
a regression to a real hang fails instead of stalling the suite.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1325
"""
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# The reporter's script, parameterised: thread "a" runs one statement, thread "b"
# the other, both released by one barrier so they enter the import together.
RACE = """
import sys, threading
results = {}
barrier = threading.Barrier(2)

def run(key, statement):
    try:
        barrier.wait(timeout=30)
        exec(statement, {})
        results[key] = "ok"
    except BaseException as exc:  # noqa: BLE001 - the failure is the point
        results[key] = f"{type(exc).__name__}: {exc}"

t = threading.Thread(target=run, args=("b", sys.argv[2]), daemon=True)
t.start()
run("a", sys.argv[1])
t.join(timeout=60)
print(results)
"""


def _python(*args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k in ("PATH", "PYTHONPATH", "HOME", "SYSTEMROOT", "TEMP", "TMP", "EDGAR_IDENTITY")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-c", *args], capture_output=True, text=True,  # noqa: S603
                          timeout=120, cwd=REPO_ROOT, env=env)


@pytest.mark.fast
@pytest.mark.parametrize("submodule_import", [
    "from edgar.reference import describe_form",
    "from edgar.entity import Company",
    "from edgar.xbrl import XBRL",
])
def test_import_edgar_races_a_submodule_import(submodule_import):
    result = _python(RACE, "import edgar", submodule_import)
    assert result.stdout.strip() == "{'a': 'ok', 'b': 'ok'}", result.stdout + result.stderr[-2000:]


@pytest.mark.fast
def test_import_edgar_imports_no_submodule():
    """The structural guarantee behind the race test: nothing to hold a lock on."""
    result = _python(
        "import sys, edgar\n"
        "print(sorted(m for m in sys.modules if m.startswith('edgar.')))\n"
        "print(edgar.Company.__module__, edgar.get_latest_filings is edgar.get_current_filings)\n"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    loaded, resolved = result.stdout.strip().splitlines()
    assert loaded == "[]"
    assert resolved == "edgar.entity.core True"
