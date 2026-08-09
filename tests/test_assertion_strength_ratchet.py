"""A regression test that cannot fail is not a regression test (edgartools-07lk.24).

Finding 4 of the regression-suite-health audit was recorded as "463 ``is not
None`` assertions across 125 files", and read that way it is a demoralising
grind with no obvious end. The count is the wrong measurement. A test that pins
real values and *also* checks non-nullity is fine; what matters is whether a
test that passed could have failed. Asked that way, 463 assertions across 125
files came to 15 tests, and all 15 have since been given ground truth. What
this file does now is keep the count at zero.

This file is the sibling of ``scripts/check_regression_skips.py`` and the two
parity ratchets, and exists for the same reason they do: an audit nobody re-runs
is an audit that decays. Three things are enforced.

1. NO NEW EXISTENCE-ONLY TESTS. A test whose only assertions are ``x is not
   None`` is listed in ``KNOWN_EXISTENCE_ONLY`` or it fails here. The list may
   only shrink. ``EXISTENCE_BY_DESIGN`` is the separate, deliberately tiny
   escape hatch for tests whose assertions this scan cannot see at all; keeping
   those on the work list would destroy the only thing the work list is for.

2. A REPAIRED TEST MUST BE BANKED. Fixing one and leaving it listed quietly
   loosens the guard, exactly as an unbanked parity baseline does.

3. NO TEST RETURNS A VALUE, ANYWHERE UNDER ``tests/``. ``return
   positive_count > 0`` instead of ``assert`` always passes; pytest warns, and
   the warning had been scrolling past for years in a suite with thousands of
   them. GH #334's two tests were found that way, and widening the scan beyond
   the regression tree found five more (edgartools-8m2n) — four of them in one
   535-line file that had 57 ``print`` calls and no assertions at all, three of
   which printed "✗ FAIL" on every run. The count is zero across all 6,900-odd
   collected tests and stays zero.

   Rules 1 and 2 stay scoped to the regression tree. Returns-a-value is a
   property of one function with no judgement in it; existence-only needs a
   ground truth per test, and the 104 outstanding elsewhere are not a work list
   anyone has agreed to yet.

WHY AST AND NOT A LINT RULE. The question is not "does this line match a
pattern" but "does this function make any claim that could be false", which
needs the whole function body — and needs to stop at nested ``def``s, because a
monkeypatch stub returning a MagicMock is not the test returning a value. Both
of those cost a false-positive round when this analysis was first written by
hand: ``except X: pytest.fail(...)`` scored as a swallowed exception, and six
correct tests scored as returning instead of asserting. A third came out of the
first repair pass: a claim need not be an ``assert`` statement at all, since
``with pytest.raises(IndexError, match=...)`` is a stricter one than most —
see ``is_raises_context``.

WHAT IS DELIBERATELY NOT ENFORCED. Exception swallowing. The honest classifier
for it -- a handler that neither fails, raises, skips nor asserts -- still flags
three tests here that are correct, because each records the exception and then
asserts something that cannot pass vacuously. A rule with a 100% false-positive
rate teaches people to silence it.
"""
import ast
import pathlib

import pytest

TESTS_DIR = pathlib.Path(__file__).parent
REGRESSION_DIR = TESTS_DIR / "issues" / "regression"

# Tests whose only assertions are `x is not None`. The list started at 15 on
# 2026-08-09 and is now EMPTY: every one of them was given ground truth read
# off a real filing, and one of those readings turned up a live defect
# (edgartools-gi1n — VALE's cash flow statement is in the filing and
# unreachable through the API, so an "acceptable empty result" was neither).
#
# Empty is the state to hold, not a milestone. Anything new that lands here
# fails `test_no_new_existence_only_tests` on the way in, which is the cheapest
# moment to fix it: give the test a value assertion — a figure read off the
# filing — rather than adding a line below.
#
# IF YOU DO ADD ONE: `test_a_repaired_test_is_banked` fails when a listed test
# is later strengthened and the line is left behind, so the list cannot rot
# into a record of work already done.
KNOWN_EXISTENCE_ONLY = set()

# Reviewed and correct as they stand — NOT a work list. Keeping these in
# KNOWN_EXISTENCE_ONLY would have made that list stop meaning "outstanding
# work", which is the only reason anyone would read it.
#
# A test belongs here when its assertions live somewhere this analysis cannot
# see, not when it is weak. Each entry carries the reason.
EXISTENCE_BY_DESIGN = {
    # Its real assertions are in ASSERTION_RUNNERS, dispatched per manifest
    # entry, and the test already refuses to pass on an entry that declares
    # none. No static analysis of this function will find them.
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


def is_raises_context(node):
    """``with pytest.raises(SomeError, match=...)`` — a claim, and a strict one.

    It is not an ``ast.Assert``, so the first version of this file scored
    GH #441's out-of-bounds test as existence-only: its only bare assert is
    ``assert filing is not None`` and the actual subject of the test —
    "IndexError, not AssertionError, and with this message" — is expressed
    entirely by two ``pytest.raises`` blocks.
    """
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        call = item.context_expr
        if isinstance(call, ast.Call):
            func = call.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
            if name == 'raises':
                return True
    return False


def is_value_assert(node):
    """An assertion that could distinguish a right answer from a wrong one.

    Comparisons (``==``, ``in``, ``>``, ``len(...) == n``), calls
    (``df.empty``, ``.startswith(...)``), and boolean/unary combinations all
    qualify. ``assert x is not None`` explicitly does not.
    """
    if not isinstance(node, ast.Assert) or is_existence_assert(node):
        return False
    return isinstance(node.test, (ast.Compare, ast.Call, ast.BoolOp, ast.UnaryOp))


def _is_fixture(fn):
    """``@pytest.fixture`` — a fixture RETURNS its value; that is its job."""
    for dec in fn.decorator_list:
        node = dec.func if isinstance(dec, ast.Call) else dec
        name = node.attr if isinstance(node, ast.Attribute) else getattr(node, 'id', None)
        if name == 'fixture':
            return True
    return False


def _test_functions(root):
    """Every function pytest would COLLECT under ``root``, with its AST.

    Collection rules matter here, and getting them wrong is how a scan reports
    work that does not exist. "Every function whose name starts with test"
    over-counts twice:

    * ``@pytest.fixture def test_company(...)`` returns a value because that is
      what a fixture does. Two of these were briefly mistaken for defective
      tests.
    * A method of a class pytest does not collect is not a test. ``class
      FastTableRendererTestSuite`` does not match ``Test*``, so its
      ``test_basic_rendering`` runs only under ``__main__`` — its trailing
      ``return`` cannot make a suite green because nothing runs it.

    Both classes of false positive appeared in the first sweep outside the
    regression tree; nine findings came down to five real ones.
    """
    for path in sorted(root.rglob("test_*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith("test") and not _is_fixture(node):
                yield path.name, node
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and item.name.startswith("test") and not _is_fixture(item):
                        yield path.name, item


@pytest.fixture(scope="module")
def classified():
    """Existence-only over the regression tree; returns-a-value over all of it.

    The two rules have different scopes on purpose. Returns-a-value is a
    property of a single function, has no false positives once collection is
    modelled correctly, and a test that has it cannot fail — so it is enforced
    everywhere. Existence-only needs a judgement about each test's subject and
    a ground truth to replace it with; 104 of those remain outside the
    regression tree and are not yet a work list anyone has agreed to.
    """
    existence_only, returns_value = set(), set()
    seen = {'regression': 0, 'all': 0}

    for filename, fn in _test_functions(REGRESSION_DIR):
        seen['regression'] += 1
        body = list(own_nodes(fn))
        if any(is_existence_assert(n) for n in body) \
                and not any(is_value_assert(n) or is_raises_context(n) for n in body):
            existence_only.add((filename, fn.name))

    for filename, fn in _test_functions(TESTS_DIR):
        seen['all'] += 1
        if any(isinstance(n, ast.Return) and n.value is not None
               for n in own_nodes(fn)):
            returns_value.add((filename, fn.name))

    return existence_only, returns_value, seen


@pytest.mark.fast
class TestTheSuiteCanStillFail:

    def test_the_tree_was_actually_scanned(self, classified):
        """"Measured nothing" must never read as "nothing wrong"."""
        _existence, _returns, seen = classified
        assert seen['regression'] > 500, (
            f"only {seen['regression']} test functions found under "
            f"{REGRESSION_DIR}; the scan is not reaching the tree and every "
            "assertion below is vacuous"
        )
        assert seen['all'] > 4000, (
            f"only {seen['all']} test functions found under {TESTS_DIR}; the "
            "returns-a-value rule below is scanning almost nothing"
        )

    def test_no_new_existence_only_tests(self, classified):
        existence_only, _returns, _seen = classified
        new = sorted(existence_only - KNOWN_EXISTENCE_ONLY - EXISTENCE_BY_DESIGN)
        assert not new, (
            "these tests assert only that something is not None, which cannot "
            "tell a correct value from a wrong one. Assert the value — a "
            "figure read off the filing — or, if the assertions genuinely live "
            "somewhere this scan cannot see, add it to EXISTENCE_BY_DESIGN "
            f"with the reason: {new}"
        )

    def test_a_repaired_test_is_banked(self, classified):
        """The ratchet's other half: delete the line in the commit that fixes it."""
        existence_only, _returns, _seen = classified
        repaired = sorted((KNOWN_EXISTENCE_ONLY | EXISTENCE_BY_DESIGN) - existence_only)
        assert not repaired, (
            "these tests now assert values and must be removed from "
            "KNOWN_EXISTENCE_ONLY / EXISTENCE_BY_DESIGN in the same commit "
            f"that fixed them: {repaired}"
        )

    def test_no_test_returns_instead_of_asserting(self, classified):
        """A test that returns always passes, however damning the value it returns."""
        _existence, returns_value, _seen = classified
        assert not sorted(returns_value), (
            "these tests end in `return <something>` rather than an assertion, "
            "so they pass unconditionally — pytest warns about this and the "
            f"warning is easy to miss in a suite this size: {sorted(returns_value)}"
        )
