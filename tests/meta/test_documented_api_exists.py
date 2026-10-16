"""
Every method a documentation page names must exist.

Bead: edgartools-m3jpa

docs/quick-guide.md listed ``company.get_facts().to_pandas()`` for months.
EntityFacts had no ``to_pandas``: the method is ``to_dataframe()`` (it now
has ``to_pandas()`` as an alias, because the name was so often guessed). Model
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
import importlib
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
# Attribute steps verified across all of docs/ (4,996 when edgartools-j7s48 fixed 38 names on 17 pages)
ALL_DOCS_FLOOR = 4700


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


def _instance_attributes(cls) -> set[str] | None:
    """Names assigned as ``self.<name>`` anywhere in the class or its bases.

    ``Filing.form`` is set in ``__init__``, so a class-level lookup cannot see it.
    None when a class sets attributes by name (``EntityData`` stores its
    ``**kwargs`` with ``setattr``), so its attributes cannot be known statically.
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
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr"
                    and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "self"):
                return None
            if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name) and node.value.id == "self"):
                names.add(node.attr)
    return names


def _on_a_subclass(cls, name) -> bool:
    """A filing from ``company.get_filings()`` is an EntityFiling, which adds
    ``is_xbrl`` and ``file_number`` to Filing; a page may use either."""
    for sub in cls.__subclasses__():
        known = _instance_attributes(sub)
        if (inspect.getattr_static(sub, name, None) is not None or known is None or name in known
                or _on_a_subclass(sub, name)):
            return True
    return False


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
        hint = (getattr(fn, "__globals__", {}).get(hint) or _imported_name(fn, hint)
                or index.get(hint))
    # `object` (obj() returns "some data object") and `Any` say nothing about attributes
    return hint if inspect.isclass(hint) and hint not in (object, typing.Any) else None


def _imported_name(fn, name):
    """A name the function's module imports only for type checking.

    ``EntityFacts.query() -> 'FactQuery'`` imports FactQuery under
    TYPE_CHECKING. The index cannot settle it: edgar.xbrl.facts has a
    FactQuery too, and the index holds only modules already loaded.
    """
    module = sys.modules.get(getattr(fn, "__module__", "") or "")
    try:
        source = inspect.getsource(module)
    except (OSError, TypeError):
        return None
    match = re.search(rf"^\s*from\s+([\w.]+)\s+import\s+[^\n]*\b{re.escape(name)}\b", source, re.MULTILINE)
    if not match:
        return None
    try:
        return getattr(importlib.import_module(match.group(1)), name, None)
    except ImportError:
        return None


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


# `financials.py` in prose is a filename, not an attribute of a Financials
_FILENAME = re.compile(r"^[\w./-]+\.(py|md|json|ya?ml|txt|csv|html?|toml|ipynb|parquet|pq|xml|zip)$")


def _statements(snippet: str):
    """The snippet's statements in source order, or nothing when it is not Python."""
    if _FILENAME.match(snippet.strip()):
        return []
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return []  # shell lines, prose in backticks, fragments
    stmts = [n for n in ast.walk(tree) if isinstance(n, ast.stmt) and not isinstance(n, ast.Module)]
    return sorted(stmts, key=lambda n: (n.lineno, n.col_offset))


def _own_expressions(stmt):
    """Attribute and call nodes of one statement, without those of nested statements."""
    stack = [c for c in ast.iter_child_nodes(stmt) if not isinstance(c, ast.stmt)]
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.Attribute, ast.Call)):
            yield node
        stack.extend(c for c in ast.iter_child_nodes(node) if not isinstance(c, ast.stmt))


def _walk(parts, roots, index, problems):
    """Follow one chain; return (steps verified, the class it ends on or None)."""
    import edgar
    root, steps = parts[0], parts[1:]
    if root in roots:
        cls = roots[root]
    elif root in getattr(edgar, "__all__", ()):
        target = getattr(edgar, root)
        cls = target if inspect.isclass(target) else _return_class(target, index)
    else:
        return 0, None
    verified = 0
    for step in steps:
        if cls is None or step == "[]":
            return verified, None
        attr = inspect.getattr_static(cls, step, None)
        if attr is None and not hasattr(cls, step):
            known = _instance_attributes(cls)
            if known is None:
                return verified, None
            if step in known or _on_a_subclass(cls, step):
                verified += 1
                return verified, None
            problems.append(f"{'.'.join(parts)}: {cls.__name__} has no {step!r}")
            return verified, None
        verified += 1
        target = attr.fget if isinstance(attr, property) else attr
        target = getattr(target, "__func__", target)
        cls = _return_class(target, index) if callable(target) else None
    return verified, cls


def check(text: str) -> tuple[list[str], int]:
    """(missing-name problems, number of attribute steps verified) for a page.

    A name the snippet assigns (``facts = xbrl.facts``) takes the type of its
    right-hand side for the rest of that snippet, or no type when that is
    unknown, instead of the page-wide root of the same name.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        default_roots = _roots()
        index = _class_index()
    problems, verified = [], 0
    for snippet in _code_snippets(text):
        roots = dict(default_roots)
        for stmt in _statements(snippet):
            for node in _own_expressions(stmt):
                parts = _chain(node)
                if parts and len(parts) >= 2:
                    verified += _walk(parts, roots, index, problems)[0]
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                parts = _chain(stmt.value)
                roots[stmt.targets[0].id] = _walk(parts, roots, index, [])[1] if parts else None
            elif isinstance(stmt, (ast.For, ast.With, ast.AnnAssign, ast.AugAssign)):
                targets = ([stmt.target] if not isinstance(stmt, ast.With)
                           else [i.optional_vars for i in stmt.items if i.optional_vars is not None])
                for t in targets:
                    for name in ast.walk(t):
                        if isinstance(name, ast.Name):
                            roots[name.id] = None
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
def test_no_docs_page_names_a_missing_api():
    """Everything under docs/ is published to Read the Docs, and models train on it.

    Edgartools-j7s48: the first run over docs/ found 38 invented names on 17
    pages, such as company.get_latest_filing, filing.form_type and
    financials.income.
    """
    problems, verified = [], 0
    for page in sorted(DOCS.rglob("*.md")):
        page_problems, page_verified = check(page.read_text(encoding="utf-8"))
        problems += [f"docs/{page.relative_to(DOCS)}: {p}" for p in page_problems]
        verified += page_verified
    assert not problems, "documented APIs that do not exist:\n" + "\n".join(problems)
    assert verified >= ALL_DOCS_FLOOR, f"only {verified} attribute steps verified across docs/ (floor {ALL_DOCS_FLOOR})"


@pytest.mark.fast
@pytest.mark.parametrize("line, missing", [
    ("| fact count | `company.get_facts().num_facts()` |", "EntityFacts has no 'num_facts'"),
    ("| by accession | `company.get_filing(accession_number=\"x\")` |", "Company has no 'get_filing'"),
    ("| open | `attachment.open()` |", "Attachment has no 'open'"),
    ("```python\nfacts = company.get_facts()\ncount = facts.num_facts()\n```\n", "EntityFacts has no 'num_facts'"),
])
def test_the_lines_this_bead_fixed_are_caught(line, missing):
    """The checker must see through the chains that were actually wrong."""
    problems, _ = check(line)
    assert any(missing in p for p in problems), problems


@pytest.mark.fast
def test_a_name_that_exists_is_not_reported():
    """The walk resolves get_facts() to EntityFacts, and to_pandas() is on it now."""
    problems, verified = check("| facts as a DataFrame | `company.get_facts().to_pandas()` |")
    assert problems == []
    assert verified >= 2  # get_facts, then to_pandas on EntityFacts (nested nodes count again)


@pytest.mark.fast
@pytest.mark.parametrize("snippet", [
    # the snippet binds `facts` to XBRL facts, not to the page-wide EntityFacts root
    "```python\nxbrl = filing.xbrl()\nfacts = xbrl.facts\nfacts.query().by_statement_type('IncomeStatement')\n```\n",
    # EntityFacts.query() imports its FactQuery only under TYPE_CHECKING
    "`company.get_facts().query().by_form_type('10-K').by_period_length(12)`",
    # a filename in prose
    "Edit `financials.py` and `filing.md`.",
    # EntityData stores its **kwargs with setattr
    "```python\ncompany_data = company.data\nprint(company_data.former_names)\n```\n",
    # a filing from company.get_filings() is an EntityFiling
    "`filing.is_xbrl`",
])
def test_names_the_checker_cannot_see_are_not_reported(snippet):
    """Edgartools-j7s48: the false-positive classes from the first run over docs/."""
    problems, _ = check(snippet)
    assert problems == []


@pytest.mark.fast
def test_a_local_binding_is_still_checked():
    """A name the snippet assigns is checked as the type of its right-hand side."""
    problems, _ = check("```python\nquarterly = company.get_quarterly_financials()\nq = quarterly.income\n```\n")
    assert problems == ["quarterly.income: Financials has no 'income'"]
