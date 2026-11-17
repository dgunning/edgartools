"""
A cold ``import edgar.funds`` no longer fails with a circular import.

Bead: edgartools-y4puq.5

In a fresh interpreter, the first import of ``edgar.funds`` (directly, through
``from edgar import Fund`` / ``FundReport`` / ``MoneyMarketFund`` and the other
fund names, through ``edgar.ats``, or through ``filing.obj()``, which imports
``edgar.ats`` before routing any form) raised::

    ImportError: cannot import name 'FundData' from partially initialized module 'edgar.funds'

CAUSE. ``edgar.funds.core`` imports ``edgar.entity.core.Entity`` to define its
classes, which runs ``edgar/entity/__init__.py``, which imported
``FundData``/``FundSeries`` from the half-built ``edgar.funds``. Both edges date
from 4.0. Until 6.1 the package init imported ``edgar.entity`` eagerly, so
``edgar.funds`` was never the first to load and the cycle never closed. 6.1 made
``import edgar`` lazy (GitHub #1325), which exposed it: 6.1.0 and 6.2.0 ship it.
``find(...).obj()`` was unaffected because ``find()`` loads ``edgar.entity`` first.

FIX. ``edgar.entity`` re-exports the two fund names on first access (PEP 562)
instead of importing ``edgar.funds`` at module level.

Every check runs in a fresh interpreter, because what is under test is the first
import of a process. The sweep covers every module behind a lazy top-level name,
so the next cycle a lazy init exposes fails here rather than in a user's script.
"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

pytestmark = pytest.mark.fast


def _python(code: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k in ("PATH", "PYTHONPATH", "HOME", "SYSTEMROOT", "TEMP", "TMP", "EDGAR_IDENTITY")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,  # noqa: S603
                          timeout=120, cwd=REPO_ROOT, env=env)


def _assert_ok(code: str, result: subprocess.CompletedProcess):
    assert result.returncode == 0 and result.stdout.strip().endswith("ok"), (
        f"{code!r} failed in a fresh interpreter:\n{result.stderr[-2000:]}")


# obj() imports its data-object modules before it looks at the form. A stub
# filing whose form nothing models and which has no XBRL reaches the one
# legitimate None without touching the network.
OBJ_FIRST = """
import edgar
class StubFiling:
    form = "ZZZ-NOT-A-FORM"
    accession_no = "0000000000-00-000000"
    def xbrl(self):
        return None
assert edgar.obj(StubFiling()) is None
print("ok")
"""


@pytest.mark.parametrize("code", [
    "import edgar.funds; print('ok')",
    "from edgar import Fund; print('ok')",
    "from edgar import find_fund; print('ok')",
    "from edgar import FundReport; print('ok')",
    "from edgar import MoneyMarketFund; print('ok')",
    "from edgar import AlternativeTradingSystem; print('ok')",
    OBJ_FIRST,
])
def test_first_import_of_a_fund_module_succeeds(code):
    _assert_ok(code, _python(code))


def test_entity_still_re_exports_the_fund_names():
    code = ("from edgar.entity import FundData, FundSeries\n"
            "import edgar.entity, edgar.funds\n"
            "assert FundData is edgar.funds.FundData and FundSeries is edgar.funds.FundSeries\n"
            "assert {'FundData', 'FundSeries'} <= set(edgar.entity.__all__)\n"
            "print('ok')")
    _assert_ok(code, _python(code))


def test_every_lazy_export_module_imports_cold():
    import edgar
    modules = sorted(edgar._EXPORTS_BY_MODULE)
    assert len(modules) > 20
    codes = [f"import {module}; print('ok')" for module in modules]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_python, codes))
    failures = {code: result.stderr.strip().splitlines()[-1:]
                for code, result in zip(codes, results, strict=True)
                if result.returncode != 0 or not result.stdout.strip().endswith("ok")}
    assert not failures, f"cold imports that fail: {failures}"
