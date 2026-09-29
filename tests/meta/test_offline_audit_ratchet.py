"""The offline-audit ratchet has to be right about both directions.

``scripts/check_offline_audit.py`` is the only gate in this repo whose answer
comes from running the tests rather than reading them, and it is the only one
that can be wrong in two ways: missing a test that newly needs the SEC, or
failing to notice one that stopped. Both matter — the first is the defect the
script exists to close, the second is what stops
``tests/offline_audit_baseline.txt`` from rotting into a list nobody trusts.

These are unit tests over the pure parts. The end-to-end behaviour (does pytest
with sockets blocked actually name the right tests?) is what the script does in
CI, and is not re-run here: it costs about seven minutes and needs the network
blocked, which is the one thing a test in this suite must not arrange for
itself.

Bead: edgartools-9zrf
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# `fast`, and measured rather than assumed: these exercise the script's pure
# functions and read one committed text file, so the whole module passes under
# `pytest -p tests._offline_harness`. Nothing here may reach the SEC — a test
# of the network ratchet that needed the network would land in its own baseline.
pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_offline_audit.py"


def _load():
    """Import the script by path — `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("check_offline_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_offline_audit"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    assert SCRIPT.exists(), f"missing script: {SCRIPT}"
    return _load()


# A real short-summary block, including the harness's own `ERROR edgar.core:`
# log line, which is not a node id and must not be read as one.
REPORT = """\
........F...
=================================== FAILURES ===================================
ERROR    edgar.core:company_subsets.py:347 Error fetching company data: outbound network blocked
=========================== short test summary info ============================
FAILED tests/core/test_filing.py::test_filing_url - tests._offline_harness.Ne...
FAILED tests/test_htmltools.py::test_list_items_in_tenk
ERROR tests/reference/test_filter_filings.py::test_filter_by_cik - tests._off...
1 failed, 7446 passed, 9 skipped in 384.58s
"""


def test_parses_failed_and_errored_node_ids(audit):
    assert audit.parse_report(REPORT) == {
        "tests/core/test_filing.py::test_filing_url",
        "tests/test_htmltools.py::test_list_items_in_tenk",
        "tests/reference/test_filter_filings.py::test_filter_by_cik",
    }


def test_the_harness_log_line_is_not_mistaken_for_a_node_id(audit):
    """`ERROR edgar.core:...` is logged for every blocked fetch. Counting it
    would put a non-existent test in the baseline on the first --write."""
    assert not any(node.startswith("edgar") for node in audit.parse_report(REPORT))


@pytest.mark.parametrize("node,paths,expected", [
    # A directory prefix must match on a path boundary, not a character one,
    # or `tests/core` would claim `tests/core_helpers/...`.
    ("tests/core/test_filing.py::test_x", ["tests/core"], True),
    ("tests/core_helpers/test_a.py::test_x", ["tests/core"], False),
    # An exact file, with and without the node part.
    ("tests/core/test_filing.py::test_x", ["tests/core/test_filing.py"], True),
    ("tests/core/test_other.py::test_x", ["tests/core/test_filing.py"], False),
    # A trailing slash is the same path.
    ("tests/core/test_filing.py::test_x", ["tests/core/"], True),
    # No paths means the whole tree is in scope.
    ("tests/anything.py::test_x", [], True),
])
def test_scope_matching(audit, node, paths, expected):
    assert audit.in_scope(node, paths) is expected


def test_baseline_file_is_parseable_and_non_empty(audit):
    """The committed baseline must survive its own reader — a stray blank or
    comment line silently dropping an entry would let that test go unwatched."""
    baseline = audit.read_baseline()
    assert len(baseline) >= 80, f"baseline looks truncated: {len(baseline)} entries"
    for node in baseline:
        assert node.startswith("tests/"), f"not a node id: {node!r}"
        assert "::" in node, f"not a node id: {node!r}"


def test_baseline_comments_are_ignored(audit, tmp_path, monkeypatch):
    path = tmp_path / "baseline.txt"
    path.write_text(
        "# a header\n"
        "\n"
        "tests/a.py::test_one\n"
        "# NOT a network debt: explains the next line\n"
        "tests/b.py::test_two\n"
    )
    monkeypatch.setattr(audit, "BASELINE_PATH", path)
    assert audit.read_baseline() == {"tests/a.py::test_one", "tests/b.py::test_two"}


def test_every_baseline_entry_names_a_test_that_exists(audit):
    """An entry whose file has been deleted or renamed reads as coverage this
    list does not have, and would never fail the ratchet — it simply stops
    matching anything. Same failure mode the NETWORK_PATTERNS comment in
    tests/conftest.py records for its own stale entries."""
    missing = sorted({node.split("::", 1)[0] for node in audit.read_baseline()
                      if not (ROOT / node.split("::", 1)[0]).exists()})
    assert missing == [], f"baseline names files that no longer exist: {missing}"
