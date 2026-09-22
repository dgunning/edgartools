"""
The exception tree: one vocabulary, and the promises that make it usable.

Bead: edgartools-07lk.10

There were 27 exception classes across ten packages with no shared base and no
cross-package inheritance, of which exactly two were reachable from the
top-level namespace. You could not write `except <something>` without knowing
which module happened to raise, and the most common thing we raised was a bare
`ValueError` — 135 of them.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. The builtin bases. `ValidationError` IS-A `ValueError` and
     `NotFoundError` IS-A `LookupError` — that is the whole reason converting
     raise sites is additive rather than a break, and it would be undone by a
     one-word edit to a base class list.
  2. The MRO order. `EdgarError` must precede `KeyError` so `str(exc)` is the
     message, not KeyError's repr-quoted form.
  3. That importing edgar emits no DeprecationWarning. This is the one that
     bites: it fires the moment our own code imports a deprecated alias, which
     would spray warnings at users for something they cannot fix.
  4. That every alias resolves to the *same object* as its canonical class, so
     `except OldName:` and `pytest.raises(OldName)` still work.
"""
import ast
import pickle
import warnings
from pathlib import Path

import pytest

import edgar
import edgar.exceptions as ex

# Constructor arguments for each public class, so these tests can instantiate
# the whole tree. A new public exception without an entry here fails
# test_every_public_class_is_constructible — deliberately, because an exception
# nobody can construct in a test is one nobody has looked at.
CONSTRUCTOR_ARGS = {
    "EdgarError": ("boom",),
    "TransportError": ("boom",),
    "TooManyRequestsError": ("https://www.sec.gov/x",),
    "IdentityError": ("boom",),
    "IdentityNotSetError": (),
    "SECIdentityError": ("boom",),
    "NotFoundError": ("boom",),
    "CompanyNotFoundError": ("NOSUCHTICKER",),
    "FilingNotFoundError": ("boom",),
    "CompanyFactsNotFoundError": (99999999,),
    "StatementNotFoundError": (),
    "SectionNotFoundError": ("boom",),
    "AttachmentNotFoundError": ("boom",),
    "ParsingError": ("boom",),
    "XBRLProcessingError": ("boom",),
    "DataObjectError": ("boom",),
    "ValidationError": ("boom",),
    "InvalidDateError": ("boom",),
}

# Deprecated spelling -> (module it must still be importable from, canonical class)
DEPRECATED_ALIASES = {
    "InvalidDateException": ("edgar.dates", ex.InvalidDateError),
    "StatementNotFound": ("edgar.xbrl.exceptions", ex.StatementNotFoundError),
    "NoCompanyFactsFound": ("edgar.entity.entity_facts", ex.CompanyFactsNotFoundError),
    "TooManyRequestsException": ("edgar.core", ex.TooManyRequestsError),
    "SECFilingNotFoundError": ("edgar.sgml.sgml_parser", ex.FilingNotFoundError),
    "IdentityNotSetException": ("edgar.httprequests", ex.IdentityNotSetError),
}


def _instance(name):
    return getattr(ex, name)(*CONSTRUCTOR_ARGS[name])


# `__all__` also exports the two helpers the dual-era call sites use
# (strict_errors_enabled, http_status), which are functions rather than classes.
# Everything below is about the tree, so it enumerates the classes only.
EXCEPTION_NAMES = sorted(
    name for name in ex.__all__
    if isinstance(getattr(ex, name), type) and issubclass(getattr(ex, name), BaseException)
)


def test_every_public_class_is_constructible():
    """Guard the guard: the tests below all instantiate the tree."""
    missing = sorted(set(EXCEPTION_NAMES) - set(CONSTRUCTOR_ARGS))
    assert not missing, (
        f"{missing} are exported from edgar.exceptions but have no constructor "
        f"arguments in this file, so nothing below exercises them. Add an entry."
    )


@pytest.mark.parametrize("name", EXCEPTION_NAMES)
def test_every_public_exception_is_an_edgar_error(name):
    """One root, or `except EdgarError` is a lie."""
    cls = getattr(ex, name)
    assert issubclass(cls, ex.EdgarError), f"{name} is outside the tree"


def test_the_tree_has_four_branches():
    """The shape is the documentation. A fifth branch is a design decision."""
    branches = {c for c in (ex.TransportError, ex.NotFoundError,
                            ex.ParsingError, ex.ValidationError)}
    direct_children = {getattr(ex, n) for n in EXCEPTION_NAMES
                       if ex.EdgarError in getattr(ex, n).__bases__}
    assert direct_children == branches, (
        f"direct children of EdgarError are {sorted(c.__name__ for c in direct_children)}; "
        f"expected exactly the four branches. Adding one is a decision to make "
        f"deliberately — see the design doc for why four."
    )


def test_validation_error_is_a_value_error():
    """The reason converting 135 raw `raise ValueError` sites is additive.

    Without this, every `except ValueError:` written against those call sites
    stops catching them.
    """
    assert issubclass(ex.ValidationError, ValueError)
    assert issubclass(ex.InvalidDateError, ValueError)
    with pytest.raises(ValueError):
        raise ex.ValidationError("bad input")


def test_not_found_is_a_lookup_error():
    assert issubclass(ex.NotFoundError, LookupError)
    with pytest.raises(LookupError):
        raise ex.CompanyNotFoundError("NOSUCHTICKER")


@pytest.mark.parametrize("name", ["SectionNotFoundError", "AttachmentNotFoundError"])
def test_getitem_errors_are_key_errors(name):
    """`except KeyError:` around item access keeps working when these are raised."""
    cls = getattr(ex, name)
    assert issubclass(cls, KeyError)
    with pytest.raises(KeyError):
        raise cls("nope")


@pytest.mark.parametrize("name", ["SectionNotFoundError", "AttachmentNotFoundError"])
def test_edgar_error_wins_the_mro_over_keyerror(name):
    """KeyError.__str__ renders repr(args[0]) — quoted. Ours must win.

    `str(KeyError("Item 7A"))` is `"'Item 7A'"`. A message wrapped in quotes in
    every log line is the visible symptom of getting the base order backwards.
    """
    cls = getattr(ex, name)
    mro = cls.__mro__
    assert mro.index(ex.EdgarError) < mro.index(KeyError), (
        f"{name} lists KeyError before EdgarError, so KeyError.__str__ wins and "
        f"every message renders quoted"
    )
    assert str(cls("Item 7A not found")) == "Item 7A not found"


def test_importing_edgar_emits_no_deprecation_warning():
    """Our own code must not use the deprecated spellings.

    This is the test that earns its keep: an internal `from edgar.xbrl.exceptions
    import StatementNotFound` warns on every `import edgar`, about a name the
    user never typed and cannot fix.
    """
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "-c", "import edgar"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        "importing edgar raised a DeprecationWarning — internal code is still "
        f"using a deprecated exception name:\n{result.stderr[-1500:]}"
    )


@pytest.mark.parametrize("old_name", sorted(DEPRECATED_ALIASES))
def test_deprecated_alias_is_the_same_object_and_warns(old_name):
    """`except OldName:` must still catch, and using it must say so."""
    module_name, canonical = DEPRECATED_ALIASES[old_name]
    module = __import__(module_name, fromlist=["_"])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aliased = getattr(module, old_name)

    assert aliased is canonical, (
        f"{module_name}.{old_name} resolves to {aliased!r}, not to {canonical.__name__}. "
        f"An alias that is a different class breaks `except {old_name}:`."
    )
    assert any(issubclass(w.category, DeprecationWarning) for w in caught), (
        f"{old_name} resolved without a DeprecationWarning, so nobody learns to "
        f"stop using it before 6.0 deletes it"
    )
    assert canonical.__name__ in str(caught[0].message), (
        "the warning must name the replacement — a deprecation that does not say "
        "what to use instead is just an alarm"
    )


@pytest.mark.parametrize("name", sorted(CONSTRUCTOR_ARGS))
def test_public_exceptions_survive_pickling(name):
    """Exceptions cross process boundaries under multiprocessing.

    BaseException.__reduce__ replays `args` through the constructor, which drops
    every attribute set from a different signature — TooManyRequestsError(url,
    retry_after) keeps only its built message in args. EdgarError.__reduce__
    restores __dict__ afterwards.
    """
    original = _instance(name)
    restored = pickle.loads(pickle.dumps(original))  # noqa: S301 - our own object
    assert type(restored) is type(original)
    assert str(restored) == str(original)
    assert restored.__dict__ == original.__dict__


def test_company_facts_not_found_has_a_message():
    """NoCompanyFactsFound.__init__ called super().__init__() with no arguments.

    It set self.message and nothing else, so str(exc) was '' — the message never
    reached a traceback, a log line, or a user. Three raise sites, all silent.
    """
    exc = ex.CompanyFactsNotFoundError(cik=99999999)
    assert str(exc) == "No Company facts found for cik 99999999"
    assert str(exc) != ""
    assert "99999999" in str(exc)


def test_exceptions_module_imports_stdlib_only():
    """Every edgar module must be able to import this one.

    A single `from edgar.something import ...` at module level here creates an
    import cycle that only shows up for whichever module imports us first.
    """
    source = Path(edgar.exceptions.__file__).read_text()
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.col_offset == 0:
            if node.module and node.module.split(".")[0] == "edgar":
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import) and node.col_offset == 0:
            for alias in node.names:
                if alias.name.split(".")[0] == "edgar":
                    offenders.append(f"line {node.lineno}: import {alias.name}")
    assert not offenders, (
        "edgar/exceptions.py imports from edgar at module level: "
        f"{offenders}. It must import stdlib only."
    )


def test_no_third_party_type_in_the_public_tree():
    """No httpx (or other dependency) type in a base class of the tree.

    Owning our own types is what makes swapping the HTTP client a non-event
    rather than a breaking change to every user's `except` clause.
    """
    for name in EXCEPTION_NAMES:
        for base in getattr(ex, name).__mro__:
            root = base.__module__.split(".")[0]
            assert root in ("edgar", "builtins"), (
                f"{name} inherits {base.__module__}.{base.__name__}, which puts a "
                f"third-party type in our public exception contract"
            )


def test_statement_not_found_message_is_unchanged():
    """It stopped being a dataclass; the message users read must not change."""
    exc = ex.StatementNotFoundError(
        statement_type="CashFlowStatement",
        confidence=0.0,
        found_statements=[],
        entity_name="VALE S.A.",
        reason="No statements available in XBRL data",
    )
    assert str(exc) == (
        "Failed to resolve CashFlowStatement for VALE S.A. "
        "(CIK: Unknown, Period: Unknown). No matching statements found. "
        "No statements available. No statements available in XBRL data"
    )


def test_rate_limit_message_survived_the_move():
    """TooManyRequestsError is the house style's best example — moving it must
    not dilute it. The numbered steps are the part users act on."""
    text = str(ex.TooManyRequestsError("https://www.sec.gov/x", retry_after=42))
    for expected in ["SEC Rate Limit Exceeded (HTTP 429)", "Retry-After: 42 seconds",
                     "Do NOT retry immediately", "What to do:",
                     "EDGAR_RATE_LIMIT_PER_SEC"]:
        assert expected in text, f"the rate-limit message lost {expected!r}"


def test_identity_error_tells_you_how_to_fix_it():
    """It used to say only 'User-Agent identity is not set'."""
    text = str(ex.IdentityNotSetError())
    assert "set_identity" in text
    assert "EDGAR_IDENTITY" in text


def test_transport_error_is_not_a_not_found_error():
    """The distinction the whole branch split exists for.

    "We could not ask" and "we asked and the answer is no" must never be the
    same `except` clause, or an outage reads as an empty result.
    """
    assert not issubclass(ex.TransportError, ex.NotFoundError)
    assert not issubclass(ex.NotFoundError, ex.TransportError)
    with pytest.raises(ex.TransportError):
        raise ex.TooManyRequestsError("https://www.sec.gov/x")
    with pytest.raises(ex.NotFoundError):
        raise ex.CompanyNotFoundError("NOSUCHTICKER")
