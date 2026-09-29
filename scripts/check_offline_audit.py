#!/usr/bin/env python
"""Ratchet: no NEW test may need the SEC while claiming to be `fast`.

THE RULE: run the offline harness over the `fast` lane and compare the tests
that fail against ``tests/offline_audit_baseline.txt``. A node id that fails and
is not in the baseline fails this check. A baseline entry that now passes also
fails it, so the list shrinks instead of rotting.

WHY THIS EXISTS. `tests/conftest.py` is explicit that an unmarked regression
test which needs the SEC is meant to "fail the pull-request gate on its first
run, which is loud and one marker from fixed". It does not, and the reason is
the cache. CI restores a shared SEC HTTP cache (see `Restore SEC HTTP cache` in
.github/workflows/regression-tests.yml), the fetch is served from it, the test
passes, and nothing anywhere records that it went to the network. The marker
never gets added. The same workflow notes the cache is "10.7 GB against a 10 GB
ceiling ... so it is evicting LRU today", so entries fall out on their own
schedule and the test fails weeks later on an unrelated pull request, looking
like a flake in whatever lane happens to catch it. Three red builds on
2026-09-21/22 were this.

So detection cannot depend on cache warmth. Blocking the socket is the only
thing that answers "does this test need the SEC?" the same way twice.

WHY NOT JUST MARK THEM `network`. Because that hides them. All three PR-facing
selectors exclude the network lane, so a test moved there runs only after merge
— bead edgartools-07lk.21 is the story of 1,746 regression tests that were
invisible to pull requests for exactly that reason, and CLAUDE.md's position is
that a test which needs SEC and is not marked should be loud, not relocated.
The baseline is therefore a debt list to pay down (give the test a cassette, or
build its Filings from tests/_offline_filings.py), not a place to file things.

COST. A pytest run with sockets blocked: about 6-7 minutes for the whole lane,
seconds for a handful of files. It runs as a step inside the `test-fast` job
rather than as its own, because that job is the only context pull requests are
required to report and a second required context means changing branch
protection in lockstep — the same reasoning recorded above the regression-skip
check in .github/workflows/python-hatch-workflow.yml.

SCOPE. With no paths it audits the whole `fast` lane, which is what a push to
main should do. Given paths it audits only those, and compares only the baseline
entries under them — a pull request can afford the changed test files but not
seven minutes for the tree, and a test can only become network-dependent in a
file the branch touched. Source changes that strand a test (deleting a cassette,
say) are caught by the full run on main rather than on the pull request.

Usage::

    python scripts/check_offline_audit.py            # whole fast lane, then check
    python scripts/check_offline_audit.py tests/core # only these paths
    python scripts/check_offline_audit.py --write    # refresh the baseline
    python scripts/check_offline_audit.py --report FILE   # check an existing run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "tests" / "offline_audit_baseline.txt"

# `python -m pytest`, not `pytest`: -p imports the plugin before collection puts
# the rootdir on sys.path. `-p no:pytest-retry` because a blocked socket never
# succeeds on a retry, it just triples the cost of the failures we are counting.
# Both are explained at `test-offline-audit` in pyproject.toml.
AUDIT_CMD = [
    sys.executable, "-m", "pytest",
    "-p", "tests._offline_harness",
    "-p", "no:pytest-retry",
    "-p", "no:randomly",
    "-m", "fast",
    "-q", "--no-header", "--tb=no",
]

# pytest's short summary: "FAILED nodeid - message" / "ERROR nodeid - message".
# Only lines whose node id starts with `tests/` — the harness also logs an
# `ERROR edgar.core:...` line for every blocked fetch, which is not a node id.
SUMMARY_RE = re.compile(r"^(?:FAILED|ERROR)\s+(tests/\S+)")


def parse_report(text: str) -> set[str]:
    """Node ids pytest reported as failed or errored."""
    return {m.group(1).split(" - ")[0] for m in
            (SUMMARY_RE.match(line) for line in text.splitlines()) if m}


def read_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    return {line.strip() for line in BASELINE_PATH.read_text().splitlines()
            if line.strip() and not line.startswith("#")}


def run_audit(paths: list[str]) -> str:
    proc = subprocess.run(AUDIT_CMD + paths, cwd=ROOT, capture_output=True, text=True)
    return proc.stdout + proc.stderr


def in_scope(node: str, paths: list[str]) -> bool:
    """Whether a baseline node id lies under one of the audited paths."""
    if not paths:
        return True
    return any(node == p or node.startswith(p.rstrip("/") + "/") or
               node.split("::", 1)[0] == p for p in paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path,
                        help="Parse an existing pytest report instead of running the audit.")
    parser.add_argument("--write", action="store_true",
                        help="Rewrite the baseline from this run. Review the diff before committing.")
    parser.add_argument("paths", nargs="*",
                        help="Limit the audit to these paths (default: the whole fast lane).")
    args = parser.parse_args()

    if args.write and args.paths:
        parser.error("--write rewrites the whole baseline, so it cannot be scoped to paths.")

    text = args.report.read_text() if args.report else run_audit(args.paths)
    failing = parse_report(text)

    if not failing and not args.report:
        # A run that collected nothing also reports no failures. Tell them apart.
        if "passed" not in text:
            print("Audit produced no result — pytest output was:\n" + text[-2000:], file=sys.stderr)
            return 2

    if args.write:
        header = (
            "# Tests that need the SEC while marked `fast`, as measured by\n"
            "# `python scripts/check_offline_audit.py`. See that script for why this\n"
            "# list exists and why marking these `network` is not the fix.\n"
            "#\n"
            "# This list may shrink and may not grow. Pay an entry down by giving the\n"
            "# test a cassette or building its Filings from tests/_offline_filings.py.\n"
        )
        BASELINE_PATH.write_text(header + "\n".join(sorted(failing)) + "\n")
        print(f"Wrote {len(failing)} node id(s) to {BASELINE_PATH.relative_to(ROOT)}")
        return 0

    baseline = read_baseline()
    scoped = {n for n in baseline if in_scope(n, args.paths)}
    new = sorted(failing - baseline)
    fixed = sorted(scoped - failing)

    if new:
        print(f"{len(new)} test(s) need the SEC but are marked `fast`, and are not in the baseline:\n")
        for node in new:
            print(f"    {node}")
        print(
            "\nRe-run them WITHOUT the harness before doing anything else — failing\n"
            "offline and being broken are different facts:\n"
            f"\n    python -m pytest {new[0]}\n"
            "\nIf it passes on the network, it needs a cassette or an offline fixture\n"
            "(tests/_offline_filings.py). Marking it `network` relocates it out of the\n"
            "pull-request lane and is not the fix — see the script docstring.\n"
        )
        return 1

    if fixed:
        print(f"{len(fixed)} baseline entry/entries no longer need the SEC:\n")
        for node in fixed:
            print(f"    {node}")
        print(
            "\nGood — remove them from tests/offline_audit_baseline.txt in the same\n"
            "commit. The list is a debt to pay down, and this check fails on an\n"
            "unclaimed improvement so it cannot silently rot.\n"
        )
        return 1

    scope = f" under {', '.join(args.paths)}" if args.paths else ""
    print(f"OK: {len(failing)} known network-dependent `fast` test(s){scope}, none new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
