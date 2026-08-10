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
