"""Regression test: to_context() navigation hints must reference the real API.

Background
----------
``to_context()`` is the primary surface AI agents read to learn how to navigate a
data object. Several methods emitted *navigation hints* (lines like
``"  - Use .foo() to ..."``) that pointed at symbols which either did not exist or
had the wrong call shape:

* GH #841 -- ``Filing.to_context()`` advertised ``.document()`` (with parens) but
  ``.document`` is a **property** returning an ``Attachment``; calling it raises
  ``TypeError``.
* (audit follow-up) ``Company.to_context()`` advertised ``.financials`` which does
  **not exist** (``AttributeError``); the real accessor is ``.get_financials()``.

This test statically audits every ``to_context()`` implementation in the package so
the class of bug cannot silently return. It is pure introspection -- no network.

Two independent checks:

1. ``test_no_property_advertised_as_callable`` -- any ``.name(`` token in any
   ``to_context`` string whose ``name`` resolves to a class-level **property** is a
   bug (zero false positives: it only fires on real properties).
2. ``test_navigation_hints_resolve`` -- every ``"Use .name"`` navigation hint must
   resolve to a real attribute (class descriptor, dataclass field, ``__init__``
   parameter, or annotation), and the call shape must match (methods shown with
   ``()``, properties/attributes shown without).
"""
from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import os
import re

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.regression]

# Repository root -> edgar package directory
_EDGAR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "edgar",
)

# A token like ``.name`` optionally followed by a call ``(``.
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_)\]])\.([a-z_][a-z0-9_]*)(\s*\()?")

# str / common builtin method names that may appear incidentally inside f-string
# expressions or examples and are not API-navigation references.
_SKIP_NAMES = {
    "format", "join", "split", "strip", "lower", "upper", "get", "items", "keys",
    "values", "append", "replace", "startswith", "endswith", "title", "encode",
    "decode", "find", "count", "rstrip", "lstrip", "group", "match", "search",
    "sub", "isoformat", "strftime", "total_seconds", "as_integer_ratio", "name",
}

# Known, intentional cross-object references in a "Use ." hint, i.e. the hint names
# a symbol that lives on a *different* class than the one emitting it. Add entries
# as ``(emitting_class_name, symbol)`` if a legitimate cross-object hint is added.
_CROSS_OBJECT_ALLOW: set[tuple[str, str]] = set()


def _collect_to_context_methods():
    """Yield (module_name, class_name, [string literals]) for every to_context()."""
    for dirpath, _dirs, files in os.walk(_EDGAR_DIR):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                src = open(path, encoding="utf-8").read()
                tree = ast.parse(src)
            except (OSError, SyntaxError):
                continue
            # module name relative to the edgar package
            rel = os.path.relpath(path, os.path.dirname(_EDGAR_DIR))
            mod = rel[:-3].replace(os.sep, ".")
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "to_context":
                        strings = [
                            s.value
                            for s in ast.walk(item)
                            if isinstance(s, ast.Constant) and isinstance(s.value, str)
                        ]
                        yield mod, node.name, strings


def _load_class(mod_name: str, class_name: str):
    """Import and return the class, or None if it cannot be loaded."""
    try:
        module = importlib.import_module(mod_name)
    except Exception:
        return None
    return getattr(module, class_name, None)


def _classify_one(klass, name: str) -> str:
    """Resolve ``name`` on ``klass`` -> 'property' | 'method' | 'attr' | 'missing'.

    'attr' covers instance attributes (dataclass fields, ``__init__`` parameters,
    class annotations) that introspection of the class object alone cannot see.
    """
    try:
        static = inspect.getattr_static(klass, name)
    except AttributeError:
        static = None
    if static is not None:
        if isinstance(static, property) or type(static).__name__ == "cached_property":
            return "property"
        if callable(static):
            return "method"
        return "attr"
    # Instance attribute? dataclass field
    if dataclasses.is_dataclass(klass):
        if any(f.name == name for f in dataclasses.fields(klass)):
            return "attr"
    # __init__ parameter
    try:
        params = inspect.signature(klass.__init__).parameters
        if name in params:
            return "attr"
    except (ValueError, TypeError):
        pass
    # class annotations (incl. inherited)
    for base in inspect.getmro(klass):
        if name in getattr(base, "__annotations__", {}):
            return "attr"
    return "missing"


def _all_subclasses(klass) -> list:
    """Every transitive subclass of ``klass`` currently loaded."""
    seen: list = []
    stack = list(klass.__subclasses__())
    while stack:
        sub = stack.pop()
        if sub in seen:
            continue
        seen.append(sub)
        stack.extend(sub.__subclasses__())
    return seen


def _classify(klass, name: str) -> str:
    """Resolve ``name``, treating a mixin's hints as the concrete host's API.

    ``to_context()`` may live on a render *mixin* while the attributes it
    documents are supplied by the concrete subclass that inherits it
    (e.g. ``FormCRenderMixin`` -> ``FormC``). Classify against the defining
    class first, then fall back to its subclasses before declaring a reference
    dead, so the legitimate mixin pattern isn't a false positive.
    """
    kind = _classify_one(klass, name)
    if kind != "missing":
        return kind
    for sub in _all_subclasses(klass):
        sub_kind = _classify_one(sub, name)
        if sub_kind != "missing":
            return sub_kind
    return "missing"


def _collect_targets():
    targets = list(_collect_to_context_methods())
    assert targets, "no to_context() methods discovered -- audit harness is broken"
    return targets


def test_no_property_advertised_as_callable():
    """A class-level property must never be advertised with call syntax (``.x()``)."""
    violations = []
    for mod, cls, strings in _collect_targets():
        klass = _load_class(mod, cls)
        if klass is None:
            continue
        for s in strings:
            for line in s.split("\n"):
                for name, paren in _TOKEN_RE.findall(line):
                    if not paren or name in _SKIP_NAMES:
                        continue
                    if _classify(klass, name) == "property":
                        violations.append(f"{cls}.to_context(): .{name}() is a PROPERTY -> {line.strip()!r}")
    assert not violations, "Property advertised as callable in to_context():\n" + "\n".join(sorted(set(violations)))


def test_navigation_hints_resolve():
    """Every ``Use .name`` navigation hint must resolve with the correct call shape."""
    dead_refs = []
    wrong_shape = []
    for mod, cls, strings in _collect_targets():
        klass = _load_class(mod, cls)
        if klass is None:
            continue
        for s in strings:
            for line in s.split("\n"):
                if "Use ." not in line:
                    continue
                # only inspect tokens that appear after the "Use" verb
                hint = line[line.index("Use ."):]
                for name, paren in _TOKEN_RE.findall(hint):
                    if name in _SKIP_NAMES or (cls, name) in _CROSS_OBJECT_ALLOW:
                        continue
                    called = bool(paren)
                    kind = _classify(klass, name)
                    if kind == "missing":
                        dead_refs.append(f"{cls}.to_context(): .{name} does not exist -> {line.strip()!r}")
                    elif kind == "property" and called:
                        wrong_shape.append(f"{cls}.to_context(): .{name}() but is a property -> {line.strip()!r}")
                    elif kind == "method" and not called:
                        wrong_shape.append(f"{cls}.to_context(): .{name} is a method (needs parens) -> {line.strip()!r}")
    problems = []
    if dead_refs:
        problems.append("Dead navigation references:\n" + "\n".join(sorted(set(dead_refs))))
    if wrong_shape:
        problems.append("Wrong call shape:\n" + "\n".join(sorted(set(wrong_shape))))
    assert not problems, "\n\n".join(problems)


def test_known_fixed_hints():
    """Pin the specific symbols fixed during the to_context audit (#840/#841)."""
    from edgar._filings import Filing
    from edgar.entity.core import Company

    # Filing.document is a property (not callable); text/markdown are the methods.
    assert isinstance(inspect.getattr_static(Filing, "document"), property)
    assert callable(inspect.getattr_static(Filing, "text"))
    assert callable(inspect.getattr_static(Filing, "markdown"))

    # Company exposes get_financials() (method); bare .financials must not exist.
    assert callable(inspect.getattr_static(Company, "get_financials"))
    with pytest.raises(AttributeError):
        inspect.getattr_static(Company, "financials")
