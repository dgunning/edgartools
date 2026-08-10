#!/usr/bin/env python
"""Fail if a regression test cannot be traced back to the bug it guards.

A regression test is a claim that some specific bug stays fixed. A year later
the assertion is the only surviving record of what that bug was — and the only
question that justifies ever deleting the test is "is this bug still
reachable?", which nobody can answer without the report.

THE RULE: every file under ``tests/issues/regression/`` names its origin in the
module docstring, as one of

    GitHub Issue: https://github.com/dgunning/edgartools/issues/<n>
    GitHub PR:    https://github.com/dgunning/edgartools/pull/<n>
    Bead:         edgartools-<id>

A bare ``#819`` in prose does not count, and that is the whole point of the
check rather than an oversight. 109 of these files named their issue in prose
and nothing else (bead edgartools-07lk.24 finding 5): the number was there, but
it was not a link, the form varied ("GH #812", "GitHub issue #488", "issue
#762"), and no tool could follow it. Requiring one canonical shape is what makes
"which of these bugs are still open?" answerable by a script instead of by
reading 256 docstrings.

WHY THE DOCSTRING AND NOT THE FILENAME. The filename usually carries the number
too, and that is exactly why it is not enough: 67 files here are named after a
beads slug and 9 are free-form, so the filename answers for some of the tree and
silently not for the rest. The docstring answers for all of it, and it is where
someone reading the test is already looking.

WHAT THIS DELIBERATELY DOES NOT CHECK. Whether the issue exists, is open, or
matches the test. That needs the network, and this runs in the pull-request
gate. The one-time normalisation that seeded these lines did verify every number
against the GitHub API — 103 of 103 resolved — but keeping that true is a
periodic audit, not a per-commit gate.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REGRESSION_DIR = Path(__file__).resolve().parent.parent / "tests" / "issues" / "regression"

# One canonical shape per source. Matched against the module docstring only.
PROVENANCE = re.compile(
    r"(?:https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+"
    r"|\bedgartools-[a-z0-9]+(?:\.[0-9]+)*\b)",
    re.IGNORECASE,
)

# A number mentioned in prose — real provenance that is merely not linkable.
# Reported separately because the fix is mechanical and the message should say so.
PROSE_ONLY = re.compile(
    r"(?:GH[ -]?#?\s*|github\s+issue\s*#?\s*|issue\s*#\s*|#)(\d{2,4})\b",
    re.IGNORECASE,
)

SKIP_NAMES = {"conftest.py", "__init__.py"}


def main() -> int:
    if not REGRESSION_DIR.is_dir():
        print(f"not a directory: {REGRESSION_DIR}", file=sys.stderr)
        return 1

    missing: list[tuple[str, str]] = []
    scanned = 0

    for path in sorted(REGRESSION_DIR.rglob("*.py")):
        if path.name in SKIP_NAMES:
            continue
        scanned += 1
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            docstring = ast.get_docstring(ast.parse(source)) or ""
        except SyntaxError as exc:
            missing.append((path.name, f"does not parse: {exc}"))
            continue

        if PROVENANCE.search(docstring):
            continue

        prose = PROSE_ONLY.findall(docstring)
        if prose:
            n = prose[0]
            missing.append((
                path.name,
                f"names #{n} in prose but not as a link — add "
                f"'GitHub Issue: https://github.com/dgunning/edgartools/issues/{n}'",
            ))
        elif not docstring.strip():
            missing.append((path.name, "has no module docstring at all"))
        else:
            missing.append((path.name, "names no issue, PR or bead"))

    for name, why in missing:
        print(f"{name}: {why}", file=sys.stderr)

    if missing:
        print(
            f"\nRefusing {len(missing)} of {scanned} scanned file(s). A regression "
            f"test has to say which bug it guards.\n"
            f"Add ONE of these to the module docstring:\n"
            f"    GitHub Issue: https://github.com/dgunning/edgartools/issues/<n>\n"
            f"    GitHub PR:    https://github.com/dgunning/edgartools/pull/<n>\n"
            f"    Bead:         edgartools-<id>\n"
            f"If you cannot find the origin, `git log --reverse -- <file>` names the "
            f"commit that added it, and its pull request or bead id is the answer "
            f"— that is how the last four in this tree were traced.\n"
            f"See {Path(__file__).name} for why prose does not count.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {scanned} regression file(s) scanned, every one traceable to its bug.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
