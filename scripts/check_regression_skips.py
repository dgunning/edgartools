#!/usr/bin/env python
"""Fail if a regression test skips itself at runtime.

A regression test exists to catch one condition. When it calls ``pytest.skip()``
because the data isn't shaped the way it expected, the condition it exists to
catch is usually the condition that makes it skip — so the bug it guards walks
straight past it and the run stays green. Two of these were live in
``test_issue_669.py``: a fiscal-period suffix was added to DataFrame column
names, the helper matching those columns stopped matching anything, and both
tests skipped on "No period columns" in every run afterwards while the feature
they guard went unverified (bead edgartools-07lk.24 finding 3).

THE RULE: no ``pytest.skip()`` under ``tests/issues/regression/``. A regression
test either runs or fails.

Two things that look like exceptions and are not:

* **A missing fixture file.** Every fixture guarded this way in this tree is
  committed — abbv, aapl, nvda, c, wfc, ms, msft and ``data/sgml`` are all
  tracked, verified with ``git ls-files``. In a valid checkout they are present,
  so their absence means a broken checkout, and that belongs in the failure
  report. ``assert path.exists()`` says so; a skip hides it. Anchor the path on
  ``__file__`` rather than the working directory while you are there — two of
  these resolved only under a repo-root invocation and skipped silently
  anywhere else.

* **A missing dependency.** ``@pytest.mark.skipif`` is the mechanism for that:
  it is declarative, evaluated at collection, and reported as its own outcome
  rather than as a test that ran. This gate deliberately does not touch it.

Why a static scan and not a pytest hook: ``pytest.skip()`` fires at runtime, so
a hook only catches a skip on a run that reaches it — and the network-marked
half of this tree runs post-merge. Reading the source catches it on every pull
request, including in tests nothing has executed yet.

Why a per-file count and not per-line: line numbers drift with every edit above
them. The count only ever goes down, so the list is a debt register that cannot
silently grow.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "tests" / "issues" / "regression"

# file name -> number of pytest.skip() calls still to be converted.
#
# EMPTY, and meant to stay that way. It held 23 while each one's data was being
# probed -- the condition every skip was hiding had to be checked against a real
# filing before its assertion could be written -- and all 23 are now assertions.
#
# Adding an entry needs a reason that survives the docstring above, and there is
# not currently a known one. The two shapes that look like reasons are answered
# there: a missing committed fixture is a broken checkout, and a missing
# dependency is what @pytest.mark.skipif is for.
GRANDFATHERED: Dict[str, int] = {}


def _is_skip_call(node: ast.AST) -> bool:
    """True for ``pytest.skip(...)`` and for a bare ``skip(...)`` imported from pytest.

    ``pytest.importorskip`` and ``pytest.mark.skipif`` are deliberately not
    matched: the first is a dependency guard, the second is the declarative
    mechanism this gate is steering people towards.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "skip" and isinstance(func.value, ast.Name) and func.value.id == "pytest"
    return isinstance(func, ast.Name) and func.id == "skip"


def find_skips(path: Path) -> List[Tuple[int, str]]:
    """Return (line, source-ish reason) for every runtime skip in one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # a file that cannot parse is a different problem
        print(f"{path}: could not parse ({exc})", file=sys.stderr)
        return []

    found = []
    for node in ast.walk(tree):
        if _is_skip_call(node):
            reason = ""
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    reason = arg.value
                elif isinstance(arg, ast.JoinedStr):
                    reason = "".join(
                        v.value for v in arg.values
                        if isinstance(v, ast.Constant) and isinstance(v.value, str)
                    )
            found.append((node.lineno, reason))
    return sorted(found)


def iter_test_files(root: Path) -> Iterator[Path]:
    yield from sorted(root.rglob("*.py"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT,
                        help="regression test directory to scan")
    args = parser.parse_args()

    root: Path = args.root
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    violations: List[str] = []
    stale: List[str] = []
    scanned = 0
    seen: Dict[str, int] = {}

    for path in iter_test_files(root):
        scanned += 1
        skips = find_skips(path)
        if not skips:
            continue
        name = path.name
        seen[name] = len(skips)
        allowed = GRANDFATHERED.get(name, 0)
        if len(skips) > allowed:
            for line, reason in skips[allowed:]:
                violations.append(f"{path}:{line}: pytest.skip({reason!r})")

    # An entry that no longer matches reality is its own failure: a stale
    # allowance is how a debt register quietly stops registering the debt.
    for name, allowed in sorted(GRANDFATHERED.items()):
        actual = seen.get(name, 0)
        if actual < allowed:
            stale.append(
                f"{name}: allows {allowed} skip(s) but has {actual} — "
                f"lower it to {actual}" + (" and delete the entry" if actual == 0 else "")
            )

    for line in violations:
        print(line, file=sys.stderr)
    for line in stale:
        print(f"stale allowance: {line}", file=sys.stderr)

    if violations or stale:
        print(
            f"\nRefusing {scanned} scanned file(s). A regression test either runs "
            f"or fails — it does not skip itself.\n"
            f"Missing committed fixture: assert it, anchored on __file__.\n"
            f"Missing dependency: @pytest.mark.skipif, which this gate ignores.\n"
            f"Unexpected data shape: that is the bug — assert, and let it fail.\n"
            f"See {Path(__file__).name} for why, and do not widen the list to "
            f"get past this.",
            file=sys.stderr,
        )
        return 1

    outstanding = sum(GRANDFATHERED.values())
    tail = f" ({outstanding} grandfathered still to convert)" if outstanding else ""
    print(f"OK: {scanned} file(s) scanned, no regression test skips itself{tail}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
