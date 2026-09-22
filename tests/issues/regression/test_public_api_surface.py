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

`__all__` governs `from edgar import *` only. Every name below is still
importable directly whether or not it is listed, so nothing here is a
compatibility guarantee about `from edgar import X` — the enforcement half
lands in 6.0 (bead edgartools-07lk.23).
"""
import types

import pytest

import edgar

# Public names deliberately NOT in __all__. Each is either stdlib that leaked in
# through an annotation import, part of `edgar.files` (removed in 6.0, bead
# edgartools-07lk.3), or internal plumbing with a supported entry point in front
# of it. Moving a name OUT of this set and into __all__ is a promise; moving one
# in is a decision to make it private in 6.0. Either way, do it deliberately.
INTERNAL = {
    # stdlib, imported in __init__.py for annotations
    "List", "Optional", "Union", "lru_cache", "partial",
    # edgar.files — removed in 6.0
    "Document", "detect_page_breaks", "mark_page_breaks",
    # filesystem/config plumbing
    "get_anchor_cache_directory", "get_cache_directory", "get_claude_skills_directory",
    "get_data_directory", "get_search_cache_directory", "get_test_directory",
    "set_cache_directory", "set_claude_skills_directory", "set_data_directory",
    "set_test_directory",
    # internal cache management; clear_cache() is the supported entry point.
    # clear_empty_cached_responses / clear_locale_corrupted_cache left this
    # boundary in the #1051 fix: __init__.py now runs the migrations via
    # _run_import_time_cache_migrations, so they live only in edgar.httpclient.
    "clear_company_facts_cache",
    # helpers and protocols used inside the package
    "listify", "matches_form", "edgar_mode", "get_obj_info",
    "HasContext", "compose_context",
    # `warn_will_raise` stages the 6.0 error flips (bead edgartools-07lk.10).
    # Users observe its effect — a FutureWarning naming what a call will raise —
    # and never call it; `edgar.exceptions.strict_errors_enabled()` is the
    # supported way to ask about the behaviour. It is reachable from `edgar`
    # only because obj() and find() import it. It goes with the flips in 6.0.
    "warn_will_raise",
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


def test_every_public_name_is_classified():
    """The ratchet. A new top-level name is public or internal — pick one.

    This is the test that does the work. If it fails, a name became reachable
    from `edgar` without anyone deciding what it is. Add it to `__all__` if
    callers should rely on it, or to INTERNAL above if it is plumbing.
    """
    unclassified = _public_names() - set(edgar.__all__) - INTERNAL
    assert not unclassified, (
        f"{len(unclassified)} name(s) are importable from `edgar` but are neither "
        f"exported in __all__ nor listed as internal: {sorted(unclassified)}.\n"
        f"Decide which: add to __all__ in edgar/__init__.py (a supported API, "
        f"covered by the deprecation policy) or to INTERNAL in this file (may be "
        f"made private in 6.0)."
    )


def test_internal_names_are_not_also_exported():
    """A name cannot be both supported and internal."""
    both = sorted(set(edgar.__all__) & INTERNAL)
    assert not both, (
        f"{both} appear in both __all__ and INTERNAL. One of the two lists is wrong."
    )


def test_internal_list_has_no_dead_entries():
    """An entry for a name that no longer exists reads as coverage it is not."""
    dead = sorted(INTERNAL - _public_names())
    assert not dead, (
        f"INTERNAL lists {dead}, which are no longer importable from `edgar`. "
        f"Delete the entries — they describe a boundary that has moved."
    )


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


def test_the_exported_document_class_is_not_the_legacy_one():
    """`edgar.Document` is `edgar.files.html.Document` — the parser 6.0 removes.

    It is a different class from `edgar.documents.Document`, which is the one
    the guides teach. Exporting it under a name that collides with its own
    replacement is why it is not in __all__.
    """
    from edgar.documents import Document as ModernDocument

    assert "Document" not in edgar.__all__, (
        "edgar.Document is the legacy edgar.files parser, removed in 6.0. If it "
        "is ever exported again it should be the edgar.documents one."
    )
    assert edgar.Document is not ModernDocument, (
        "edgar.Document now IS edgar.documents.Document — that is a change worth "
        "making deliberately, and this test and __all__ should follow it."
    )


def test_report_the_current_surface(capsys):
    """Derive the surface counts instead of transcribing them into prose.

    Run with `-s` to read them:

        hatch run test:pytest tests/issues/regression/test_public_api_surface.py \
            -k report_the_current_surface -s

    This asserts internal consistency rather than a fixed size — pinning the
    numbers is what rotted last time, and freezing them would fail on every
    added name, which the tests above deliberately do not do. What it does catch
    is the surface drifting in a way the classification missed: every public
    name is either exported or listed INTERNAL, so the three totals must add up.
    """
    public = _public_names()
    exported = set(edgar.__all__)
    undeclared = public - exported

    print(f"\npublic top-level names: {len(public)}")
    print(f"declared in __all__:    {len(exported)}")
    print(f"undeclared (INTERNAL):  {len(undeclared)}")

    assert len(public) == len(exported & public) + len(undeclared)
    assert undeclared == INTERNAL & public, (
        "the undeclared set has drifted from INTERNAL — "
        f"unclassified: {sorted(undeclared - INTERNAL)}"
    )
