#!/usr/bin/env python
"""Fail a pull request that stages a 6.0 change without telling the upgrade guide.

Every user-visible 6.0 break ships in two halves: a warning in 5.x, then the
break itself. The warning half is only useful if ``docs/upgrade/6.0.md`` says
what to do about it, because that page is where a user porting to 6.0 (or
their AI assistant) looks. A CHANGELOG entry gets written by habit; an
upgrade-guide entry does not, and nothing caught the difference: PRs #1200 and
#1201 shipped the edgar.files deprecations in 5.55.0 with no guide entry, and
the entries had to be reconstructed after release (bead edgartools-07lk.14).

THE RULE: a pull request whose added lines stage a 6.0 change must also touch
``docs/upgrade/6.0.md``. Staging means any of

- a call that warns about the future: ``warn_will_raise(...)``, or any function
  whose name says ``deprecat`` (``deprecated_alias``, ``_deprecation_warning``)
  or is one of the module-local helpers listed in ``WARNING_HELPERS``;
- a ``DeprecationWarning`` or ``FutureWarning`` written into library code;
- the phrase "removed in 6.0" (also "removed in v6.0", "removed in edgartools
  6.0", and the same with "deprecated");
- a new ``changelog.d/*.deprecated.md`` or ``*.removed.md`` fragment.

Only ADDED lines in ``edgar/`` count and comment lines are ignored. Markers
are also netted across the PR: each staging marker a PR removes (a
``FutureWarning``, a ``warn_will_raise(`` call) cancels one the PR adds. So
deleting a deprecated name in the 6.0 window, or restructuring or moving a
warning that already exists, does not trip the check; adding a new one does.
MEASURED against history: replaying the 265 commits merged to main since the
guide was created (2026-08-05), 10 staged a change and updated the guide
(pass), and 5 fail. Four of those staged a 6.0 change with no guide entry in the
same PR: #1034, #1201, 2464a531 (07lk.12.1 module moves), and 4e31aed6
(07lk.11.5 FilingHomepage soup deprecation, which the guide still lacks). The
fifth, #1384, added a new warning site for a change #1379 had just documented,
which is what the label is for. Netting is what cleared #1037, which only
restructured an existing ``warn_will_raise`` call.

WHERE THE DIFF COMES FROM. The CI checkout is shallow, so there is no merge base
to ``git diff`` against. The workflow asks the GitHub API for the PR's files
instead and pipes them here as JSON lines (one ``{"filename", "status",
"patch"}`` object per line). GitHub omits ``patch`` for very large diffs, and a
file without one is reported rather than silently passed.

THE ESCAPE HATCH is the ``no-upgrade-guide`` label, for the rare PR that
matches without staging anything (say, a test helper that asserts on
``FutureWarning`` inside ``edgar/``). CI passes the PR's labels in
``PR_LABELS``. Using the label is a claim the reviewer can see, which is the
point: skipping the guide has to be a visible decision.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator

GUIDE = "docs/upgrade/6.0.md"
SKIP_LABEL = "no-upgrade-guide"

# Module-local helpers that exist only to emit a deprecation warning, whose
# names the generic pattern below does not catch. #1201 staged the whole
# edgar.files removal through warn_legacy_html_usage, which is how this
# check would otherwise have missed the very PR it was written for.
WARNING_HELPERS = ("warn_legacy_html_usage",)

STAGING = re.compile(
    r"\bwarn_will_raise\s*\("
    r"|\b\w*deprecat\w*\s*\("
    r"|\b(?:" + "|".join(WARNING_HELPERS) + r")\s*\("
    r"|\b(?:DeprecationWarning|FutureWarning)\b"
    r"|(?:removed|deprecated)\s+in\s+(?:edgartools\s+)?v?6\.0",
    re.IGNORECASE,
)

# A definition is the mechanism, not a use of it.
DEFINITION = re.compile(r"^\s*(?:async\s+)?def\s")

FRAGMENT = re.compile(r"^changelog\.d/[^/]+\.(?:deprecated|removed)\.md$")


@dataclass(frozen=True)
class Hit:
    filename: str
    line: str

    def __str__(self) -> str:
        return f"{self.filename}: {self.line.strip()[:110]}"


def _marker(match: re.Match) -> str:
    """One spelling per marker, so 'removed in v6.0' nets against 'Removed in 6.0'."""
    return re.sub(r"\s+|edgartools|v(?=6)|\($", "", match.group(0).lower())


def _code_lines(patch: str, sign: str) -> Iterator[str]:
    """The added (``+``) or removed (``-``) lines of a patch that are not comments or defs."""
    for raw in patch.splitlines():
        if not raw.startswith(sign) or raw.startswith(sign * 3):
            continue
        line = raw[1:]
        if line.strip().startswith("#") or DEFINITION.match(line):
            continue
        yield line


def removed_markers(patch: str) -> Counter:
    """How many of each staging marker a patch removes."""
    return Counter(_marker(m) for line in _code_lines(patch, "-") for m in STAGING.finditer(line))


def staged_lines(filename: str, patch: str, removed: Counter | None = None) -> list[Hit]:
    """The added lines of one file's patch that stage a new 6.0 change.

    ``removed`` is the PR-wide count from `removed_markers`. It is consumed as
    added markers net against it, so pass one Counter through every file.
    """
    removed = Counter() if removed is None else removed
    hits = []
    for line in _code_lines(patch, "+"):
        markers = [_marker(m) for m in STAGING.finditer(line)]
        if not markers:
            continue
        if all(removed[k] > 0 for k in markers):
            removed.subtract(markers)
            continue
        hits.append(Hit(filename, line))
    return hits


@dataclass
class Verdict:
    hits: list[Hit]
    unreadable: list[str]
    guide_touched: bool

    @property
    def ok(self) -> bool:
        return self.guide_touched or not (self.hits or self.unreadable)


def evaluate(files: Iterable[dict]) -> Verdict:
    files = list(files)
    removed = sum((removed_markers(f["patch"]) for f in files
                   if f.get("patch") and f["filename"].startswith("edgar/")), Counter())
    hits: list[Hit] = []
    unreadable: list[str] = []
    guide_touched = False
    for f in files:
        name = f["filename"]
        status = f.get("status", "modified")
        if name == GUIDE and status != "removed":
            guide_touched = True
            continue
        if FRAGMENT.match(name) and status == "added":
            hits.append(Hit(name, "new changelog fragment"))
            continue
        if not (name.startswith("edgar/") and name.endswith(".py")) or status == "removed":
            continue
        patch = f.get("patch")
        if patch is None:
            unreadable.append(name)
            continue
        hits.extend(staged_lines(name, patch, removed))
    return Verdict(hits, unreadable, guide_touched)


def main(argv: list[str]) -> int:
    labels = {s.strip() for s in os.environ.get("PR_LABELS", "").split(",") if s.strip()}
    source = open(argv[1], encoding="utf-8") if len(argv) > 1 else sys.stdin
    with source:
        files = [json.loads(line) for line in source if line.strip()]

    verdict = evaluate(files)
    if verdict.ok:
        reason = "the upgrade guide is updated" if verdict.hits else "nothing stages a 6.0 change"
        print(f"OK: {reason} ({len(files)} files checked).")
        return 0
    if SKIP_LABEL in labels:
        print(f"SKIPPED by the '{SKIP_LABEL}' label; {len(verdict.hits)} staging line(s) not documented:")
        for hit in verdict.hits:
            print(f"  {hit}")
        return 0

    print(f"This PR stages a 6.0 change but does not touch {GUIDE}.\n")
    for hit in verdict.hits:
        print(f"  {hit}")
    for name in verdict.unreadable:
        print(f"  {name}: diff too large for the API to return; could not be checked")
    print(
        f"\nAdd what the user sees in 5.x and what they should do instead to {GUIDE}"
        " (the 'What 6.0 changes' table for None -> raise changes, its own section for a"
        f" move or removal). If nothing here stages a 6.0 change, add the '{SKIP_LABEL}'"
        " label and say why in the PR description."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
