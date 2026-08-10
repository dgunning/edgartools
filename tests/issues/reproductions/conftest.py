"""Conftest for the reproductions directory.

Every .py file here must be named `test_*.py`. That is not a style rule; it is
the only thing that makes a file in this tree mean anything, because pytest
collects `test_*.py` and nothing else.

This file used to do the opposite. It walked the directory and added every
non-`test_*.py` file to `collect_ignore`, which is to say it took each script
someone left behind and made pytest's silence about it official. Under that
arrangement the tree grew to 137 files yielding 54 tests: 95 files with no test
function at all, and 22 that had test functions pytest never ran. Two of those
22 were worse than dead. `issue_251_citigroup_extraction_reproduction.py`
asserted `item1 is None` -- the Citigroup extraction bug, written down as the
expected result -- and it kept saying so for as long as nothing ran it. Issue
#251 was fixed; that test fails today.

So the suppression is gone and a stray file is now an error at collection time,
loud and one rename from fixed. The choice a stray file needs is the same one
each of the 22 needed: it either asserts something, in which case name it
`test_*.py` and let it run, or it does not, in which case it is a script and
does not belong in a test tree. Scratch work goes outside the repo.

Same rule and same reasoning as `scripts/check_regression_skips.py` next door:
a test that cannot fail is not covering anything, and a directory listing that
implies otherwise is worse than an empty one.

THE SECOND RULE: nothing here may carry `@pytest.mark.regression`.

A reproduction is a scratch record of a bug as reported. A regression test is a
permanent guard, and it lives in `tests/issues/regression/`, where the tree-wide
gates apply to it -- provenance in the docstring
(`scripts/check_regression_provenance.py`), no runtime `pytest.skip()`
(`scripts/check_regression_skips.py`), and fast/network classification by
measurement in `tests/conftest.py`. A regression-marked test *here* is selected
by `-m regression` and so runs in the regression lane while sitting outside
every one of those gates.

32 tests across 6 files were in that state on 2026-08-10 (bead
edgartools-07lk.24, Tier 2). They were nominally duplicates of regression-tree
files; measured, four of the six were not, and two carried the exact defects the
gates exist to catch -- a `pytest.skip()` on missing data, and assertions
wrapped in `if` guards whose false branch was the bug. Their unique coverage was
ported into the regression tree, one file was moved across whole
(`test_issue_438_deduplication_integration.py`), one was deleted as a true
duplicate, and this hook is what stops the boundary re-forming.

It is a collection hook rather than a source scan on purpose: the marker can
arrive from a decorator, a `pytestmark`, a class, or another hook, and only the
collected item knows which markers it actually ended up with.
"""
from pathlib import Path

import pytest

_ALLOWED_NON_TEST = {"conftest.py", "__init__.py"}

_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items):
    """Fail collection if anything in this tree is marked `regression`."""
    offenders = sorted(
        item.nodeid
        for item in items
        if _HERE in Path(str(item.fspath)).parents
        and any(m.name == "regression" for m in item.iter_markers())
    )
    if offenders:
        raise pytest.UsageError(
            f"{len(offenders)} test(s) under tests/issues/reproductions/ are "
            "marked `regression`:\n  "
            + "\n  ".join(offenders)
            + "\n\n`-m regression` selects these, so they run in the regression "
            "lane while sitting outside the provenance, no-skip and "
            "fast/network gates that apply to tests/issues/regression/. Move "
            "the test to tests/issues/regression/ (and give it a provenance "
            "line in the module docstring), or drop the marker. See this "
            "file's docstring."
        )


def _stray_files() -> list[str]:
    root = Path(__file__).parent
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if p.name not in _ALLOWED_NON_TEST and not p.name.startswith("test_")
    )


_strays = _stray_files()
if _strays:
    raise pytest.UsageError(
        "tests/issues/reproductions/ may only contain test_*.py files, and "
        f"{len(_strays)} file(s) do not match:\n  "
        + "\n  ".join(_strays)
        + "\n\nA file here that pytest does not collect asserts nothing while "
        "reading, from the directory listing, as coverage. Rename it to "
        "test_*.py so it runs, or delete it -- exploratory scripts belong "
        "outside the repo. See this file's docstring."
    )
