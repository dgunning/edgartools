"""
Regression test for the cash-flow naming inconsistency.

Cash flow had three names across the API — ``Company.cash_flow()``,
``Financials.cashflow_statement()`` and
``xbrl.statements.cash_flow_statement()`` — and which one worked depended on
which object you were holding. AI assistants gave the wrong name, autocomplete
did not help, and beginners hit AttributeError on a method that exists three
feet away. Reported via correspondence; see the bead.

Bead: edgartools-iirl

THE CONTRACT THIS PINS. ``cash_flow_statement`` is canonical, because it is the
name that matches ``income_statement`` and ``balance_sheet`` — the whole
complaint was that one member of that trio was spelled differently. Every
object that exposes an income statement exposes it under that name.
``cashflow_statement`` and ``cash_flow()`` still work and warn; 6.0 removes
them (bead edgartools-07lk.23, which stages the break additively in 5.x first).

Written as a sweep over the package rather than a list of imports on purpose. A
hand-written list is what let this drift in the first place: five of these
sixteen classes were missing the canonical name on 2026-08-10, and nothing
noticed because no test knew the set was supposed to be uniform. A new
statement-bearing class now fails here on the day it is added.
"""
import importlib
import inspect
import pkgutil
import warnings

import pytest

import edgar

CANONICAL = "cash_flow_statement"
DEPRECATED = ("cashflow_statement", "cash_flow")

# Subpackages that are dev tooling or optional integrations rather than the
# public data API. edgar.ai.* needs the `mcp` extra; the rest are excluded from
# coverage in pyproject.toml for the same reason.
_SKIP = (".ai.", "examples", "migration", "training", "diagnose")


def _statement_classes():
    """Every class defining income_statement — the set that must be uniform."""
    found = []
    for mod_info in pkgutil.walk_packages(edgar.__path__, "edgar."):
        if any(s in mod_info.name for s in _SKIP):
            continue
        try:
            module = importlib.import_module(mod_info.name)
        except Exception:
            # An optional dependency being absent is not this test's business.
            continue
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != mod_info.name:
                continue
            if hasattr(cls, "income_statement"):
                found.append((f"{mod_info.name}.{name}", cls))
    return found


def test_the_sweep_finds_the_statement_surface():
    """Guard the guard: an empty sweep would make every test below vacuous."""
    classes = _statement_classes()
    assert len(classes) >= 15, (
        f"expected the statement surface to be ~16 classes, found {len(classes)}: "
        f"{[n for n, _ in classes]}. If the package moved, fix this sweep — do not "
        f"let it silently cover nothing."
    )


@pytest.mark.parametrize("name,cls", _statement_classes(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_statement_class_has_the_canonical_name(name, cls):
    """income_statement and balance_sheet imply cash_flow_statement."""
    assert hasattr(cls, CANONICAL), (
        f"{name} exposes income_statement() but not {CANONICAL}(). That "
        f"asymmetry is issue iirl exactly: the caller has to know which of "
        f"three spellings this particular object accepts."
    )


@pytest.mark.parametrize("name,cls", _statement_classes(), ids=lambda v: v if isinstance(v, str) else "")
def test_deprecated_spellings_are_not_the_canonical_method(name, cls):
    """A deprecated alias must delegate, not *be* the implementation.

    If the alias and the canonical name resolve to the same function object,
    then either the deprecation warning fires on the supported call path or the
    alias forwards to itself. Both happened while this was being fixed: a
    rename left ``cash_flow_statement`` defined twice in five classes, the
    second one shadowing the implementation and calling itself.
    """
    canonical = getattr(cls, CANONICAL)
    for alias in DEPRECATED:
        if not hasattr(cls, alias):
            continue
        assert getattr(cls, alias) is not canonical, (
            f"{name}.{alias} IS {name}.{CANONICAL} — the alias does not "
            f"delegate, so it either warns on the supported path or recurses"
        )


@pytest.mark.parametrize("name,cls", _statement_classes(), ids=lambda v: v if isinstance(v, str) else "")
def test_deprecated_spellings_warn_and_name_their_replacement(name, cls):
    """Warn on the deprecated call, and say what to use instead.

    Checked on the unbound function with a dummy self, so no filing is fetched:
    the warning fires before any work happens.
    """
    for alias in DEPRECATED:
        if not hasattr(cls, alias):
            continue
        func = getattr(cls, alias)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                func(object())
            except Exception:
                # Delegating into a bare object() fails — after the warning.
                pass
        messages = [str(w.message) for w in caught
                    if issubclass(w.category, DeprecationWarning)]
        assert messages, f"{name}.{alias}() is deprecated but emits no DeprecationWarning"
        assert any(CANONICAL in m for m in messages), (
            f"{name}.{alias}() warns without naming {CANONICAL}: {messages}"
        )


def test_canonical_name_does_not_warn():
    """The supported spelling must be silent, or the deprecation is noise.

    Uses Statements, which carries both spellings, so this is the exact pair
    where a delegation written the wrong way round would warn on every call.
    """
    from edgar.xbrl.statements import Statements

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            Statements.cash_flow_statement(object())
        except Exception:
            pass
    deprecations = [str(w.message) for w in caught
                    if issubclass(w.category, DeprecationWarning)]
    assert not deprecations, (
        f"cash_flow_statement() is the supported name and must not warn: {deprecations}"
    )


# --- Internal callers ------------------------------------------------------
#
# The sweep above proves every class OFFERS the canonical name. It says nothing
# about which name edgartools itself reaches for, and three internal callers
# were still on the old one after the rename. That is worse than an untidy
# import: a deprecation warning the user cannot act on. Calling the canonical
# EntityFacts.cash_flow_statement(period='ttm') told the user to stop using
# cashflow_statement(), which they had not called.

def _module_sources():
    """(path, parsed AST) for every module in the package."""
    import ast
    from pathlib import Path

    root = Path(edgar.__file__).parent
    for path in sorted(root.rglob("*.py")):
        try:
            yield path.relative_to(root.parent), ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - not our problem to police
            continue


def test_no_internal_caller_reaches_for_the_deprecated_attribute():
    """`x.cashflow_statement` may appear only inside the wrapper of that name."""
    import ast

    class Visitor(ast.NodeVisitor):
        def __init__(self, path):
            self.path = path
            self.scope = []
            self.offenders = []

        def visit_FunctionDef(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

        def visit_Attribute(self, node):
            deprecated = node.attr == "cashflow_statement"
            in_own_wrapper = bool(self.scope) and self.scope[-1] == node.attr
            if deprecated and not in_own_wrapper:
                self.offenders.append(f"{self.path}:{node.lineno}")
            self.generic_visit(node)

    offenders = []
    for path, tree in _module_sources():
        visitor = Visitor(path)
        visitor.visit(tree)
        offenders.extend(visitor.offenders)

    assert not offenders, (
        "edgartools calls its own deprecated spelling, which warns the user "
        f"about a method they never called: {offenders}"
    )


def test_no_method_name_table_lists_the_deprecated_spelling():
    """A method name reached through getattr is a call site the linter cannot see.

    `edgar/ai/mcp/tools/reader.py` held ("Cash Flow Statement",
    "cashflow_statement") and did getattr(fin, method)() over it, so every MCP
    filing read emitted the deprecation. Comparisons against the old spelling
    are fine and deliberate — the viewer normalises it — so only literals
    collected into a list, tuple or dict count here.
    """
    import ast

    offenders = []
    for path, tree in _module_sources():
        for node in ast.walk(tree):
            literals = []
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                literals = node.elts
            elif isinstance(node, ast.Dict):
                literals = [k for k in node.keys if k is not None]
            for item in literals:
                if isinstance(item, ast.Constant) and item.value == "cashflow_statement":
                    offenders.append(f"{path}:{item.lineno}")

    assert not offenders, (
        f"deprecated spelling listed as a method name to dispatch on: {offenders}"
    )


def test_viewer_accepts_either_spelling_for_the_same_statement():
    """`FilingViewer.compare_context` used the name twice, and disagreed with itself.

    The keyword table was keyed on the old spelling while the method lookup ran
    against the object, so the canonical name found no viewer report ("No viewer
    report found matching 'cash_flow_statement'") and the old one reached a
    deprecated method. Both spellings now take the canonical path.
    """
    from types import SimpleNamespace

    from edgar.xbrl.viewer import FilingViewer

    report = SimpleNamespace(short_name="CONSOLIDATED STATEMENTS OF CASH FLOWS",
                             text=lambda: "VIEWER CASH FLOW ROWS")
    viewer = SimpleNamespace(financial_statements=[report])

    calls = []

    def cash_flow_statement():
        calls.append("cash_flow_statement")
        return None

    def cashflow_statement():  # must never be the one that runs
        calls.append("cashflow_statement")
        return None

    xbrl = SimpleNamespace(statements=SimpleNamespace(
        cash_flow_statement=cash_flow_statement,
        cashflow_statement=cashflow_statement,
    ))

    for spelling in ("cash_flow_statement", "cashflow_statement"):
        calls.clear()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            out = FilingViewer.compare_context(viewer, xbrl, statement=spelling)

        assert "VIEWER CASH FLOW ROWS" in out, (
            f"compare_context({spelling!r}) failed to find the viewer's cash flow report"
        )
        assert calls == ["cash_flow_statement"], (
            f"compare_context({spelling!r}) dispatched to {calls}, not the canonical name"
        )
        assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
