"""
The declared public API of `edgar`, pinned.

Bead: edgartools-07lk.5

`edgar/__init__.py` had no `__all__`, so "is this part of the API?" had no
answer except whether the import happened to work. Everything reachable from the
top-level namespace looked equally official, including `Optional` and `partial`
— imported for annotations and never API — and `Document`, the *legacy* parser
from `edgar.files`, a different class from `edgar.documents.Document` and
scheduled for removal in 6.0.

NO COUNTS IN THIS PROSE, deliberately. It used to open "141 names were
reachable"; `edgar/__init__.py` and `docs/upgrade/6.0.md` carried the same figure
plus "110 names" and "31 names outside `__all__`". Eleven days later the real
numbers were 153, 123 and 30, and nothing failed — a count written into a
sentence is prose wearing the costume of a measurement, and no test guarded it.
`test_report_the_current_surface` below derives them instead, so the numbers come
from the code that has them rather than from someone remembering to retype them.

WHAT THESE TESTS ARE FOR. Not to freeze the API — names get added, and adding
one here is a two-line change. They exist so that adding a name to the top-level
namespace forces a decision about whether it is public, at the moment it is
added rather than at the moment someone tries to remove it. That is the whole
content of "define the public API": the boundary is only real if crossing it
is noticeable.

Through 5.x `__all__` governed `from edgar import *` only, and the internal
names stayed importable. 6.0 enforced the boundary: those names were made
private, so every non-module name reachable from `edgar` is now in `__all__`,
and the ones that went fail with directions to their supported replacement.
"""
import importlib
import types

import pytest

import edgar

# The names that were importable from `edgar` through 5.x without being in
# __all__, made private in 6.0. Each was stdlib that leaked in through an
# annotation import, or internal plumbing with a supported entry point in front
# of it. Pinned here so the set cannot quietly grow back.
PRIVATE_IN_6_0 = {
    # stdlib, once imported in __init__.py for annotations
    "List", "Optional", "Union", "lru_cache", "partial",
    # filesystem/config plumbing; edgar.paths is the home
    "get_anchor_cache_directory", "get_cache_directory", "get_claude_skills_directory",
    "get_data_directory", "get_search_cache_directory", "get_test_directory",
    "set_cache_directory", "set_claude_skills_directory", "set_data_directory",
    "set_test_directory",
    # internal cache management; clear_cache() is the supported entry point
    "clear_company_facts_cache",
    # helpers and protocols used inside the package
    "listify", "matches_form", "get_obj_info",
    "HasContext", "compose_context",
    # lower-level variants of supported entry points
    "get_by_accession_number_enriched", "get_entity_submissions",
    "get_cik_lookup_data", "get_ticker_to_cik_lookup",
}


def _public_names():
    """Top-level names a user can reach, excluding submodules.

    Submodules are excluded because `from edgar.xbrl import XBRL` works
    regardless of `__all__` — this is about the top-level namespace only.
    """
    return {
        name for name in dir(edgar)
        if not name.startswith("_")
        and not isinstance(getattr(edgar, name), types.ModuleType)
    }


def test_all_is_declared():
    """Guard the guard: without this the tests below are vacuous."""
    assert hasattr(edgar, "__all__"), "edgar.__init__ no longer declares __all__"
    assert len(edgar.__all__) > 50, (
        f"__all__ has shrunk to {len(edgar.__all__)} names, which is not a "
        f"plausible public API for this library — check what removed them"
    )


@pytest.mark.parametrize("name", sorted(edgar.__all__))
def test_every_exported_name_resolves(name):
    """A name in __all__ that does not exist breaks `from edgar import *`."""
    assert hasattr(edgar, name), (
        f"edgar.__all__ exports {name!r}, which does not exist. `from edgar "
        f"import *` raises AttributeError on this."
    )


def test_all_has_no_duplicates():
    assert len(edgar.__all__) == len(set(edgar.__all__)), (
        "duplicates in __all__: "
        f"{sorted(n for n in set(edgar.__all__) if edgar.__all__.count(n) > 1)}"
    )


def test_every_public_name_is_exported():
    """The ratchet. A new top-level name is public, or it is private.

    If this fails, a name became reachable from `edgar` without anyone deciding
    it is API. Add it to `__all__` in edgar/__init__.py if callers should rely
    on it (it is then covered by the deprecation policy), or import it under an
    underscore name if it is plumbing.
    """
    undeclared = _public_names() - set(edgar.__all__)
    assert not undeclared, (
        f"{len(undeclared)} name(s) are importable from `edgar` but not exported in "
        f"__all__: {sorted(undeclared)}. Export them or make them private."
    )


@pytest.mark.parametrize("name", sorted(PRIVATE_IN_6_0))
def test_a_private_name_is_gone_and_says_where_to_go(name):
    assert name not in edgar.__all__
    assert not hasattr(edgar, name)
    with pytest.raises(AttributeError, match=r"made private in edgartools 6\.0; "):
        getattr(edgar, name)
    with pytest.raises(ImportError):
        exec(f"from edgar import {name}", {})  # noqa: S102


@pytest.mark.parametrize("name", sorted(PRIVATE_IN_6_0))
def test_the_directions_are_true(name):
    """A message that names a module must name one that has the name."""
    direction = edgar._PRIVATE_IN_6_0[name]
    if direction.startswith("import it from "):
        module = direction.removeprefix("import it from ").split()[0]
        assert hasattr(importlib.import_module(module), name), (
            f"edgar.{name} says to import it from {module}, which has no {name}"
        )
    elif "or import it from " in direction:
        module = direction.split("or import it from ")[1].split()[0]
        assert hasattr(importlib.import_module(module), name)


def test_the_private_set_is_pinned():
    """The getattr table and this file describe the same names."""
    assert set(edgar._PRIVATE_IN_6_0) == PRIVATE_IN_6_0


def test_the_replacements_named_in_the_messages_exist():
    from edgar import Filing, clear_cache, find  # noqa: F401
    assert isinstance(Filing.obj_type, property)


def test_stdlib_does_not_leak_through_star_import():
    """The specific accident that motivated this: `from edgar import Optional`.

    Named rather than folded into the sweep above, because it is the one a
    reader is most likely to think is intentional.
    """
    for name in ("List", "Optional", "Union", "partial", "lru_cache"):
        assert name not in edgar.__all__, (
            f"{name} is stdlib imported for annotations in edgar/__init__.py, "
            f"not part of the API"
        )


def test_the_legacy_document_class_is_gone_and_says_where_to_go():
    """`edgar.Document` was `edgar.files.html.Document`, which 6.0 removed.

    It was a different class from `edgar.documents.Document`, the one the guides
    teach, under a name that collided with its own replacement — which is why it
    was never in __all__. Reaching for it now has to fail with directions, not a
    bare "no attribute".
    """
    assert "Document" not in edgar.__all__, (
        "if edgar.Document is ever exported again it should be the "
        "edgar.documents one, added deliberately"
    )
    with pytest.raises(AttributeError, match=r"edgar\.documents\.Document"):
        edgar.Document  # noqa: B018


def test_report_the_current_surface(capsys):
    """Derive the surface counts instead of transcribing them into prose.

    Run with `-s` to read them:

        hatch run test:pytest tests/issues/regression/test_public_api_surface.py \
            -k report_the_current_surface -s
    """
    public = _public_names()
    exported = set(edgar.__all__)

    print(f"\npublic top-level names: {len(public)}")
    print(f"declared in __all__:    {len(exported)}")
    print(f"made private in 6.0:    {len(PRIVATE_IN_6_0)}")

    assert public <= exported
