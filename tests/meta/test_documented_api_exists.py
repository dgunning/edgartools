"""
Every method a documentation page names must exist.

Bead: edgartools-m3jpa

docs/quick-guide.md listed ``company.get_facts().to_pandas()`` for months.
EntityFacts has no ``to_pandas``: the method is ``to_dataframe()``. Model
training data includes these docs, so a wrong line becomes model behaviour: in
the README eval (bead 07lk.19.8), ``EntityFacts.to_pandas`` was the most
common invented API, 8 of 19 failing Haiku scripts, and Sonnet 5.5 wrote it
too. The same page also documented ``company.get_filing(...)`` and
``attachment.open()``, neither of which exists.

Running the cheat sheet is not an option: it opens a browser and downloads
forty quarterly indexes. So this check is static. Each code cell or block is
parsed, and its attribute chain is walked from a root the page uses
(``company`` is a Company, ``filing`` a Filing, and so on), following each
step's return annotation. A name the class does not have fails the test. A
step whose return type is not annotated ends the walk without failing, so
this catches invented names, not every possible mistake; the count of steps
it did verify is asserted, so it cannot quietly verify nothing.
"""
import ast
import inspect
import re
import sys
import typing
import warnings
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs"

# Pages checked, and the minimum number of attribute steps resolved on each.
# Raise the floor when a page gains examples; it guards against a refactor
# that silently stops the walk (an unresolvable annotation everywhere).
PAGES = {
    "quick-guide.md": 140,  # 147 when written
    "api/company.md": 100,  # 108 when written
}


def _roots():
    from edgar import Company, Filing, Filings
    from edgar.attachments import Attachment
    from edgar.company_reports import TenK
    from edgar.entity.entity_facts import EntityFacts
    from edgar.financials import Financials
    from edgar.proxy import ProxyStatement
    return {
        "company": Company, "financials": Financials, "filings": Filings, "filing": Filing,
        "attachment": Attachment, "tenk": TenK, "proxy": ProxyStatement,
        "facts": EntityFacts, "company_facts": EntityFacts,
    }


def _class_index() -> dict[str, type]:
    """Every class defined in a loaded edgar module, by name, where the name is unique."""
    seen: dict[str, set] = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith("edgar") or module is None:
            continue
        for obj in vars(module).values():
            if inspect.isclass(obj) and obj.__module__.startswith("edgar"):
                seen.setdefault(obj.__name__, set()).add(obj)
    return {name: next(iter(classes)) for name, classes in seen.items() if len(classes) == 1}


def _instance_attributes(cls) -> set[str]:
    """Names assigned as ``self.<name>`` anywhere in the class or its bases.

    ``Filing.form`` is set in ``__init__``, so a class-level lookup cannot see it.
    """
    names = set()
    for klass in cls.__mro__:
        if not klass.__module__.startswith("edgar"):
            continue
        names.update(getattr(klass, "__annotations__", {}))
        try:
            tree = ast.parse(inspect.getsource(klass).lstrip())
        except (OSError, TypeError, SyntaxError, IndentationError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name) and node.value.id == "self"):
                names.add(node.attr)
    return names


def _return_class(fn, index) -> type | None:
    """The class a callable is annotated to return, or None when that is unknown.

    typing.get_type_hints() is not used: it evaluates every annotation on the
    function and raises on any one it cannot resolve, so a single unrelated
    TYPE_CHECKING import hides the return type.
    """
    try:
        hint = inspect.signature(fn).return_annotation
    except (TypeError, ValueError):
        return None
    if hint is inspect.Signature.empty:
        return None
    if typing.get_origin(hint) is typing.Union:
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        if len(args) != 1:
            return None
        hint = args[0]
    if isinstance(hint, typing.ForwardRef):
        hint = hint.__forward_arg__
    if isinstance(hint, str):
        hint = hint.removeprefix("Optional[").removesuffix("]").strip("'\"")
        hint = getattr(fn, "__globals__", {}).get(hint) or index.get(hint)
    # `object` (obj() returns "some data object") says nothing about attributes
    return hint if inspect.isclass(hint) and hint is not object else None


def _chain(node) -> list[str] | None:
    """`a.b().c` -> ['a', 'b', 'c']; None for anything that is not a plain chain."""
    parts = []
    while True:
        if isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Subscript):
            parts.append("[]")
            node = node.value
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            return parts[::-1]
        else:
            return None


def _code_snippets(text: str) -> list[str]:
    blocks = re.findall(r"^```python[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    rest = re.sub(r"^```.*?^```", "", text, flags=re.MULTILINE | re.DOTALL)
    return blocks + re.findall(r"`([^`\n]+)`", rest)


def _expressions(snippet: str):
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return  # shell lines, prose in backticks, fragments
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Call)):
            yield node


def check(text: str) -> tuple[list[str], int]:
    """(missing-name problems, number of attribute steps verified) for a page."""
    import edgar
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        roots = _roots()
        index = _class_index()
    problems, verified = [], 0
    for snippet in _code_snippets(text):
        for node in _expressions(snippet):
            parts = _chain(node)
            if not parts or len(parts) < 2:
                continue
            root, steps = parts[0], parts[1:]
            cls = roots.get(root)
            if cls is None and root in getattr(edgar, "__all__", ()):
                target = getattr(edgar, root)
                cls = target if inspect.isclass(target) else _return_class(target, index)
            for step in steps:
                if cls is None or step == "[]":
                    break
                attr = inspect.getattr_static(cls, step, None)
                if attr is None and not hasattr(cls, step) and step not in _instance_attributes(cls):
                    problems.append(f"{'.'.join(parts)}: {cls.__name__} has no {step!r}")
                    break
                verified += 1
                target = attr.fget if isinstance(attr, property) else attr
                target = getattr(target, "__func__", target)
                cls = _return_class(target, index) if callable(target) else None
    return sorted(set(problems)), verified


@pytest.mark.fast
@pytest.mark.parametrize("page", sorted(PAGES))
def test_every_documented_method_exists(page):
    problems, verified = check((DOCS / page).read_text(encoding="utf-8"))
    assert not problems, f"docs/{page} names APIs that do not exist:\n" + "\n".join(problems)
    assert verified >= PAGES[page], (
        f"only {verified} attribute steps verified on docs/{page} (floor {PAGES[page]}); "
        f"the walk is resolving less than it did"
    )


@pytest.mark.fast
@pytest.mark.parametrize("line, missing", [
    ("| facts as a DataFrame | `company.get_facts().to_pandas()` |", "EntityFacts has no 'to_pandas'"),
    ("| by accession | `company.get_filing(accession_number=\"x\")` |", "Company has no 'get_filing'"),
    ("| open | `attachment.open()` |", "Attachment has no 'open'"),
    ("```python\nfacts = company.get_facts()\ncount = facts.num_facts()\n```\n", "EntityFacts has no 'num_facts'"),
])
def test_the_lines_this_bead_fixed_are_caught(line, missing):
    """The checker must see through the chains that were actually wrong."""
    problems, _ = check(line)
    assert any(missing in p for p in problems), problems
