"""A regression test that cannot fail is not a regression test (edgartools-07lk.24).

Finding 4 of the regression-suite-health audit was recorded as "463 ``is not
None`` assertions across 125 files", and read that way it is a demoralising
grind with no obvious end. The count is the wrong measurement. A test that pins
real values and *also* checks non-nullity is fine; what matters is whether a
test that passed could have failed. Asked that way, 463 assertions across 125
files becomes the 15 tests listed below.

This file is the sibling of ``scripts/check_regression_skips.py`` and the two
parity ratchets, and exists for the same reason they do: an audit nobody re-runs
is an audit that decays. Three things are enforced.

1. NO NEW EXISTENCE-ONLY TESTS. A test whose only assertions are ``x is not
   None`` is listed in ``KNOWN_EXISTENCE_ONLY`` or it fails here. The list may
   only shrink.

2. A REPAIRED TEST MUST BE BANKED. Fixing one and leaving it listed quietly
   loosens the guard, exactly as an unbanked parity baseline does.

3. NO TEST RETURNS A VALUE. ``return positive_count > 0`` instead of
   ``assert`` always passes; pytest warns, and the warning had been scrolling
   past for years in a suite with thousands of them. GH #334's two tests were
   found that way. The count is zero and stays zero.

WHY AST AND NOT A LINT RULE. The question is not "does this line match a
pattern" but "does this function make any claim that could be false", which
needs the whole function body — and needs to stop at nested ``def``s, because a
monkeypatch stub returning a MagicMock is not the test returning a value. Both
of those cost a false-positive round when this analysis was first written by
hand: ``except X: pytest.fail(...)`` scored as a swallowed exception, and six
correct tests scored as returning instead of asserting.

WHAT IS DELIBERATELY NOT ENFORCED. Exception swallowing. The honest classifier
for it -- a handler that neither fails, raises, skips nor asserts -- still flags
three tests here that are correct, because each records the exception and then
asserts something that cannot pass vacuously. A rule with a 100% false-positive
rate teaches people to silence it.
"""
import ast
import pathlib

import pytest

REGRESSION_DIR = pathlib.Path(__file__).parent / "issues" / "regression"

# Tests whose only assertions are `x is not None`, measured 2026-08-09.
#
# Each is a real weakness: it cannot distinguish a correct answer from a
# wrong-but-present one. They are listed rather than fixed in one go because
# each needs its own ground truth read off a real filing, which is the slow
# part and the part that must not be rushed -- see the ones already converted
# in this pass (#334, #403, #469, #486, #631, #637, #672, #844, MCP FPI) for
# what "fixed" means here.
#
# TO FIX ONE: give it a value assertion, then delete its line below. The test
# `test_a_repaired_test_is_banked` fails if you do the first without the second.
KNOWN_EXISTENCE_ONLY = {
    ("test_424b_parser.py", "test_backward_compat_related_filings"),
    ("test_fee_table.py", "test_find_fee_table_split_tag_header"),
    ("test_issue_441_current_filings_pagination.py", "test_out_of_bounds_indexing_raises_proper_errors"),
    ("test_issue_486_comprehensive_income_zerodiv.py", "test_comprehensive_income_multiple_affected_companies"),
    ("test_issue_512_13f_manager_assignment.py", "test_13f_backward_compatibility"),
    ("test_issue_523_13f_other_managers_summary_page.py", "test_other_manager_data_correctness"),
    ("test_issue_581_mchp_income_statement.py", "test_income_statement_has_revenue"),
    ("test_issue_599_pandas_futurewarning.py", "test_presentation_values_correct"),
    ("test_issue_674_fallback_simulation.py", "test_fallback_xbrl_available"),
    ("test_issue_683_vale_cashflow.py", "test_vale_stitched_cashflow_no_crash"),
    ("test_issue_821_citi_html_leak.py", "test_cross_reference_index_is_still_detected"),
    ("test_issue_a3ej.py", "test_accepts_str_and_yyyymmdd_dates"),
    ("test_issue_etoo_header_only_submissions.py", "test_from_text_does_not_raise"),
    ("test_issue_koq3_8k_subheading_truncation.py", "test_subheading_is_a_heading_node"),
    ("test_viewer_corpus.py", "test_viewer_corpus_entry"),
}

# Scopes that are not part of the enclosing test. ast.walk descends into these,
# which is how a stub's `return MagicMock()` gets attributed to the test around
# it; every returns-a-value finding in the first pass was this.
_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def own_nodes(fn):
    """Nodes belonging to ``fn`` itself, not to helpers defined inside it."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, _NESTED_SCOPES):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def is_existence_assert(node):
    """``assert x is not None`` — true of a correct value and a wrong one alike."""
    return (isinstance(node, ast.Assert)
            and isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value is None)


def is_value_assert(node):
    """An assertion that could distinguish a right answer from a wrong one.

    Comparisons (``==``, ``in``, ``>``, ``len(...) == n``), calls
    (``df.empty``, ``.startswith(...)``), and boolean/unary combinations all
    qualify. ``assert x is not None`` explicitly does not.
    """
    if not isinstance(node, ast.Assert) or is_existence_assert(node):
        return False
    return isinstance(node.test, (ast.Compare, ast.Call, ast.BoolOp, ast.UnaryOp))


def _test_functions():
    """Every collected test function in the regression tree, with its AST."""
    for path in sorted(REGRESSION_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and fn.name.startswith("test"):
                yield path.name, fn


@pytest.fixture(scope="module")
def classified():
    existence_only, returns_value = set(), set()
    seen = 0
    for filename, fn in _test_functions():
        seen += 1
        body = list(own_nodes(fn))
        if any(is_existence_assert(n) for n in body) \
                and not any(is_value_assert(n) for n in body):
            existence_only.add((filename, fn.name))
        if any(isinstance(n, ast.Return) and n.value is not None for n in body):
            returns_value.add((filename, fn.name))
    return existence_only, returns_value, seen


@pytest.mark.fast
class TestTheSuiteCanStillFail:

    def test_the_tree_was_actually_scanned(self, classified):
        """"Measured nothing" must never read as "nothing wrong"."""
        _existence, _returns, seen = classified
        assert seen > 500, (
            f"only {seen} test functions found under {REGRESSION_DIR}; the "
            "scan is not reaching the tree and every assertion below is vacuous"
        )

    def test_no_new_existence_only_tests(self, classified):
        existence_only, _returns, _seen = classified
        new = sorted(existence_only - KNOWN_EXISTENCE_ONLY)
        assert not new, (
            "these tests assert only that something is not None, which cannot "
            "tell a correct value from a wrong one. Assert the value — a "
            "figure read off the filing — or, if this is genuinely a "
            f"does-not-crash test, say so with a comment and list it here: {new}"
        )

    def test_a_repaired_test_is_banked(self, classified):
        """The ratchet's other half: delete the line in the commit that fixes it."""
        existence_only, _returns, _seen = classified
        repaired = sorted(KNOWN_EXISTENCE_ONLY - existence_only)
        assert not repaired, (
            "these tests now assert values and must be removed from "
            f"KNOWN_EXISTENCE_ONLY in the same commit that fixed them: {repaired}"
        )

    def test_no_test_returns_instead_of_asserting(self, classified):
        """A test that returns always passes, however damning the value it returns."""
        _existence, returns_value, _seen = classified
        assert not sorted(returns_value), (
            "these tests end in `return <something>` rather than an assertion, "
            "so they pass unconditionally — pytest warns about this and the "
            f"warning is easy to miss in a suite this size: {sorted(returns_value)}"
        )
