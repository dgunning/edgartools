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
"""
from pathlib import Path

import pytest

_ALLOWED_NON_TEST = {"conftest.py", "__init__.py"}


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
