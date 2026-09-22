#!/usr/bin/env python3
"""Assert a built or published artifact actually contains the code we think it does.

Step 3 of the release runbook (``docs-internal/release-publishing.md``) says to
install the wheel into a clean venv and check ``edgar.__version__`` plus a
ground-truth value from the release's headline fix. This is that check, written
down, because a release verified by hand is verified differently every time.

WHY THIS IS NOT A pytest FILE. It must run against the *installed* package in a
throwaway venv that has only edgartools and its dependencies — no pytest, no
repo on ``sys.path``. Running it under the repo's test suite would defeat the
one thing it exists to prove.

USAGE

    # after `hatch build` in a worktree at the merged release commit
    python3 -m venv /tmp/relverify
    /tmp/relverify/bin/pip install /path/to/dist/edgartools-X.Y.Z-py3-none-any.whl
    /tmp/relverify/bin/python scripts/release/verify_wheel.py X.Y.Z

    # or against what PyPI actually served, once published
    /tmp/relverify/bin/pip install --no-cache-dir edgartools==X.Y.Z

DO NOT CHECK THE VERSION WITH A ``python -c`` ONE-LINER. Running this file as a
script is safe from any directory, because ``sys.path[0]`` is then the script's
own directory (``scripts/release``). ``python -c`` is different: ``sys.path[0]``
is ``''``, the current directory, so from the repo root ``import edgar`` finds
``./edgar/`` — your working tree, on whatever branch you left it — and never
touches the venv. Measured while releasing 5.49.0:

    $ cd ~/PycharmProjects/edgartools
    $ /tmp/relverify/bin/python -c "import edgar; print(edgar.__version__)"
    5.48.0                      # the working tree, not the wheel just installed

That is a verification that proves nothing, and it looks exactly like one that
worked. Step 0 below asserts the package really came from ``site-packages`` so
the same mistake through any other route (``PYTHONPATH=.``, ``python -m``) is
loud rather than silent.

The repo path is only needed to reach a committed fixture; nothing is imported
from it.
"""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Ground truth that does not move between releases.
#
# 0000950153-99-001234 is Medicis Pharmaceutical's FY1999 10-K, whose headers
# read "Item 1:  Business". Before 5.49.0 the whole filing resolved to a single
# section and `TenK.items` was `['Item 8']`; the colon defeated every
# item-numbered pattern at once. It is a good permanent anchor precisely because
# it is unforgiving — a package built from stale source fails it outright rather
# than merely looking different.
_FIXTURE = "tests/fixtures/parity_gate/10-K/0000950153-99-001234.html"
_EXPECTED_ITEMS = ("1", "2", "3", "5", "6", "7", "8", "9", "10", "11", "12", "13")


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, label: str, got: object, expected: object) -> None:
        ok = got == expected
        detail = "" if ok else f"  (expected {expected!r})"
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r}{detail}")
        if not ok:
            self.failures.append(label)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        print("error: expected a version, e.g. `verify_wheel.py 5.49.0`")
        return 2
    expected_version = argv[1]
    repo = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parents[2]

    import edgar

    c = Checker()

    print("0. this is the installed package, not the working tree")
    package_dir = Path(edgar.__file__).parent
    print(f"     imported from: {package_dir}")
    if "site-packages" not in str(package_dir):
        print("  FAIL  imported from a source tree, not the installed package — "
              "check PYTHONPATH and that you used the venv's python "
              "(see the module docstring)")
        return 1
    print("  PASS  under site-packages")

    print("\n1. version")
    c.check("edgar.__version__", edgar.__version__, expected_version)

    print("\n2. section extraction on a filing that once resolved to one section")
    fixture = repo / _FIXTURE
    if not fixture.exists():
        print(f"  FAIL  fixture not found: {fixture}")
        print("        pass the repo path as the second argument")
        return 1

    from edgar.documents.config import ParserConfig
    from edgar.documents.parser import HTMLParser

    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(
        fixture.read_text(errors="ignore")
    )
    found = sorted({s.item for s in doc.sections.values() if s.item})
    print(f"     items found: {found}")
    for item in _EXPECTED_ITEMS:
        c.check(f"Item {item} present", item in found, True)

    print("\n3. the item-header separator is shared, not spelled per pattern")
    from edgar.documents.form_schema import _ITEM_SEP, get_form_schema

    pattern = get_form_schema("10-K").section_patterns["business"][0][0]
    c.check("_ITEM_SEP used by the 10-K business pattern", _ITEM_SEP in pattern, True)
    for header in ("Item 1. Business", "Item 1:  Business", "Item 1 - Business"):
        c.check(f"{header!r} matches", bool(re.match(pattern, header, re.IGNORECASE)), True)

    print()
    if c.failures:
        print(f"FAILURES ({len(c.failures)}): {c.failures}")
        print("Do not publish this artifact.")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
