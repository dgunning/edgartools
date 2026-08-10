#!/usr/bin/env python
"""Attribute every covered line to the tests that reached it.

Answers one question: **which lines would stop being covered if the regression
tree went away?** That is the only measurement that turns "this file has zero
unique coverage" into a defensible statement, and it is the precondition the
pruning section of bead edgartools-07lk.24 was waiting on.

USAGE — two steps, because the measuring run is expensive and worth keeping:

    COVERAGE_FILE=/tmp/attrib.coverage \\
      hatch run pytest -m fast -n auto --cov=edgar --cov-context=test --cov-report=

    hatch run python scripts/coverage_attribution.py /tmp/attrib.coverage

``--cov-context=test`` is the part that matters: without it coverage records
which lines ran but not which test ran them, and the subtraction below is
impossible. It is not on by default anywhere in this repo because it slows the
run down measurably, so this is a deliberate, occasional measurement rather
than something CI carries.

WHAT "UNIQUE" MEANS HERE, AND WHAT IT DOES NOT. A line is unique to the
regression tree when no test outside ``tests/issues/regression/`` reaches it.
That makes a file with zero unique lines a candidate for CONSOLIDATION and
never for silent deletion -- a regression test's job is pinning a specific
value on specific data, not reaching new lines, so the two properties are
independent. The Tier 3 experience is the cautionary tale: the zero-unique-
coverage list was read as a list of files that re-parse the same filings, and
measured, its eight largest entries shared 0.59s of redundant parsing between
them. Zero unique coverage tells you nothing about runtime.

Line counts are statements plus branch arcs as coverage.py records them, so
they are comparable run-to-run but not to a ``coverage report`` percentage.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

REGRESSION_PREFIX = "tests/issues/regression/"


def _test_file(context: str) -> str | None:
    """``tests/x.py::test_y|run`` -> ``tests/x.py``. None for the empty context.

    Coverage appends a phase suffix (``|setup``, ``|run``, ``|teardown``) and
    records lines executed at import time under the empty context.
    """
    context = context.split("|", 1)[0]
    if not context or "::" not in context:
        return None
    return context.split("::", 1)[0]


# IMPORT-TIME LINES COUNT AS "COVERED BY SOMETHING ELSE", and getting this
# wrong inflates the headline number.
#
# 19,642 of the 51,931 covered lines in the 2026-08-10 run were reached under
# coverage's empty context -- module-level code that runs when the package is
# imported, belonging to no test. Dropping them entirely looks tidy and is
# wrong for the question being asked: "would this line stop being covered if
# the regression tree went away?" A line executed at import time stays covered
# either way, so crediting it to the regression tree overstates unique
# coverage. Folding it into the non-regression side is the conservative
# reading and is what the original 2026-08-08 measurement did -- dropping it
# instead made the "rest of the suite" total read 27,639 against that run's
# 46,701 and looked like a 19k-line collapse that had not happened.


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data_file", nargs="?", default=".coverage",
                    help="coverage data file written by the --cov-context run")
    ap.add_argument("--top", type=int, default=15,
                    help="how many files to list in each ranking (default 15)")
    args = ap.parse_args()

    try:
        from coverage import CoverageData
    except ImportError:
        print("coverage is not installed in this environment", file=sys.stderr)
        return 1

    path = Path(args.data_file)
    if not path.exists():
        print(f"no coverage data at {path}\n\n{__doc__}", file=sys.stderr)
        return 1

    data = CoverageData(basename=str(path))
    data.read()

    contexts = data.measured_contexts()
    if contexts <= {""}:
        print(
            f"{path} has no per-test contexts — it was recorded without "
            "--cov-context=test, so attribution is impossible. See this "
            "script's docstring.",
            file=sys.stderr,
        )
        return 1

    reg_lines: set[tuple[str, int]] = set()
    other_lines: set[tuple[str, int]] = set()
    import_lines: set[tuple[str, int]] = set()
    # line -> set of regression test FILES that reached it
    reg_owners: dict[tuple[str, int], set[str]] = defaultdict(set)

    for measured in data.measured_files():
        for lineno, ctxs in data.contexts_by_lineno(measured).items():
            key = (measured, lineno)
            for ctx in ctxs:
                tf = _test_file(ctx)
                if tf is None:
                    # Import-time. See the note above: counts as covered by
                    # something other than the regression tree.
                    import_lines.add(key)
                    other_lines.add(key)
                elif REGRESSION_PREFIX in tf.replace("\\", "/"):
                    reg_lines.add(key)
                    reg_owners[key].add(tf)
                else:
                    other_lines.add(key)

    unique = reg_lines - other_lines

    # Per-regression-file totals: lines it reaches, and lines only it reaches.
    total_by_file: dict[str, int] = defaultdict(int)
    unique_by_file: dict[str, int] = defaultdict(int)
    for key, owners in reg_owners.items():
        for owner in owners:
            total_by_file[owner] += 1
        if key in unique and len(owners) == 1:
            unique_by_file[next(iter(owners))] += 1

    print("=" * 72)
    print("COVERAGE ATTRIBUTION")
    print("=" * 72)
    print(f"  covered by offline regression tests       {len(reg_lines):>7,} lines")
    print(f"  covered by the rest of the offline suite  {len(other_lines):>7,} lines")
    print(f"  covered ONLY by regression tests          {len(unique):>7,} lines")
    print(f"\n  of which reached at import time          {len(import_lines):>7,} lines")
    print("    (counted on the non-regression side — see the note in this file)")
    print(f"\n  regression test files seen               {len(total_by_file):>7,}")
    print(f"  distinct test contexts                   {len(contexts):>7,}")

    ranked = sorted(total_by_file.items(), key=lambda kv: -unique_by_file.get(kv[0], 0))
    print(f"\nDEFEND HARDEST — highest unique contribution (top {args.top}):")
    for name, total in ranked[: args.top]:
        print(f"  {unique_by_file.get(name, 0):>6,} unique of {total:>6,}  {Path(name).name}")

    zero = sorted(
        ((n, t) for n, t in total_by_file.items() if unique_by_file.get(n, 0) == 0),
        key=lambda kv: -kv[1],
    )
    print(f"\nZERO UNIQUE COVERAGE — {len(zero)} files. Consolidation candidates ONLY;")
    print(f"re-derive any runtime work list by measuring, not from this list (top {args.top}):")
    for name, total in zero[: args.top]:
        print(f"  {total:>6,} lines covered, 0 unique  {Path(name).name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
