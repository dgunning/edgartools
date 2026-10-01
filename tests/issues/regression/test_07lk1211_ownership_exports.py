"""The ownership family is importable from `edgar`, and the API docs' import table is true.

Bead: edgartools-07lk.12.1.1

Before 5.60, `from edgar.ownership import Form4` was the only way to reach Form4,
so the three package names (ownership, beneficial_ownership, thirteenf) were
load-bearing public API. The form->class->module table in docs/api/filing.md
sent readers to four ImportErrors: `Schedule13` (no such class), `edgar.holdings`
and `edgar.nport` (no such modules), and `Form144` in `edgar.ownership` (it lives
in `edgar.ownership.form144`). The bead named two of them; importing every row
found the other two.
"""

import importlib
import re
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

import edgar

ROOT = Path(__file__).resolve().parents[3]
FILING_DOC = ROOT / "docs" / "api" / "filing.md"

EXPORTS = {
    "Form3": "edgar.ownership",
    "Form4": "edgar.ownership",
    "Form5": "edgar.ownership",
    "Form144": "edgar.ownership.form144",
    "Schedule13D": "edgar.beneficial_ownership",
    "Schedule13G": "edgar.beneficial_ownership",
}


@pytest.mark.parametrize("name,module", sorted(EXPORTS.items()))
def test_top_level_name_is_the_subpackage_class(name, module):
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a new path, not a deprecated one
        top_level = getattr(edgar, name)
    assert top_level is getattr(importlib.import_module(module), name)
    assert name in edgar.__all__
    assert name in dir(edgar)


def test_from_edgar_import_works():
    from edgar import Form3, Form4, Form5, Form144, Schedule13D, Schedule13G  # noqa: F401

    assert Form4.__module__ == "edgar.ownership.forms"
    assert Schedule13G.__name__ == "Schedule13G"


def test_import_edgar_does_not_load_the_ownership_packages():
    # Lazy on purpose: loading them eagerly cost +19 ms on a 599 ms import.
    code = (
        "import sys, edgar; "
        "print(sorted(m for m in ('edgar.ownership', 'edgar.ownership.form144', "
        "'edgar.beneficial_ownership') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.strip() == "[]"


def _obj_table_rows():
    text = FILING_DOC.read_text(encoding="utf-8")
    table = text.split("| Form Type | Return Class | Module |", 1)[1].split("\n\n", 1)[0]
    rows = []
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and not set(cells[0]) <= set("-"):
            rows.append(tuple(cells))
    return rows


def test_the_docs_table_has_the_rows_it_should():
    rows = _obj_table_rows()
    assert len(rows) == 13
    assert ("13F-HR", "ThirteenF", "edgar.thirteenf") in rows
    assert ("SC 13D", "Schedule13D", "edgar.beneficial_ownership") in rows


@pytest.mark.parametrize("form,cls,module", _obj_table_rows())
def test_every_row_of_the_docs_table_imports(form, cls, module):
    assert hasattr(importlib.import_module(module), cls), f"{form}: {module}.{cls} does not exist"


@pytest.mark.parametrize("package,siblings", [
    ("edgar.ownership", ("edgar.beneficial_ownership", "edgar.thirteenf", "Section 16")),
    ("edgar.beneficial_ownership", ("edgar.ownership", "edgar.thirteenf", "Section 13(d)")),
    ("edgar.thirteenf", ("edgar.ownership", "edgar.beneficial_ownership", "Section 13(f)")),
])
def test_each_package_docstring_points_to_its_siblings(package, siblings):
    doc = importlib.import_module(package).__doc__ or ""
    for needle in siblings:
        assert re.search(re.escape(needle), doc), f"{package} docstring does not mention {needle}"
