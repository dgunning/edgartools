"""The last un-warned public names in `edgar.files`.

Bead: edgartools-07lk.3, staging row for edgartools-07lk.23.

`edgar.files` is deleted in 6.0. Most of its public surface already warned —
`Document`, `ChunkedDocument`, `HtmlDocument` — but `detect_page_breaks` and
`mark_page_breaks` did not, and those two are RE-EXPORTED AT THE TOP LEVEL:
`from edgar import detect_page_breaks` works today. They were the only names a
user could hold, reach through the documented import root, and receive nothing
about before the package disappeared.

THE BUG THIS FILE EXISTS TO PREVENT IS IN THE GATE, NOT THE WARNING.
`warn_legacy_html_usage` is frame-gated: it walks up from its own frame and
stays quiet if the first non-transparent frame belongs to `edgar.*`. The walk
starts at the CALLER'S OWN FRAME, so a deprecated function whose module is
missing from `_TRANSPARENT_MODULES` is read as an internal call and silenced.

Adding the two `warn_legacy_html_usage(...)` calls therefore did nothing at all
until `edgar.files.page_breaks` was added to that set. A test that only asserted
"the call site exists" would have passed against the broken version, and so
would any review reading the diff. These tests call the functions as a user does
and assert a warning actually arrives.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. **The warnings actually reach a user.** Removing `edgar.files.page_breaks`
     from `_TRANSPARENT_MODULES` — an easy tidy, since it looks like a list of
     legacy HTML modules and page_breaks is not one — silently re-suppresses
     both.
  2. **Internal callers stay quiet.** The whole reason the gate exists: the
     `include_page_breaks=True` renderer reaches page-break code on every call,
     and a naive module-level warning turns `import edgar` into a failure for
     any downstream suite running `-W error`.
  3. **The message names the removal and the absence of a replacement.** There
     is no migration target here — `edgar.documents` discards page breaks as
     print chrome — and a deprecation that does not say so sends the reader
     looking for a replacement that was never written.
"""
import warnings

import pytest

HTML = (
    "<html><body>"
    "<p>One</p>"
    '<div style="page-break-before: always"></div>'
    "<p>Two</p>"
    "</body></html>"
)


def _deprecations(fn, *args):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fn(*args)
    return [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]


# --------------------------------------------------------------------------
# The warnings reach a user
# --------------------------------------------------------------------------

def test_detect_page_breaks_warns_from_the_top_level_import():
    """`from edgar import detect_page_breaks` is the path a user actually has."""
    from edgar import detect_page_breaks

    assert _deprecations(detect_page_breaks, HTML)


def test_mark_page_breaks_warns_from_the_top_level_import():
    from edgar import mark_page_breaks

    assert _deprecations(mark_page_breaks, HTML)


@pytest.mark.parametrize("name", ["detect_page_breaks", "mark_page_breaks"])
def test_message_names_the_release_and_the_missing_replacement(name):
    """No migration target exists; the warning has to say so."""
    import edgar

    message = _deprecations(getattr(edgar, name), HTML)[0]
    assert "6.0" in message
    assert "no replacement" in message.lower()
    # Name the function, so a user with several deprecations knows which fired.
    assert name in message


# --------------------------------------------------------------------------
# The frame gate — the part that silently breaks
# --------------------------------------------------------------------------

def test_page_breaks_module_is_transparent_to_the_frame_gate():
    """Without this entry both warnings above are suppressed as 'internal'.

    Asserted directly as well as behaviourally: the behavioural tests say
    something broke, this one says what.
    """
    from edgar.files._deprecation import _TRANSPARENT_MODULES

    assert "edgar.files.page_breaks" in _TRANSPARENT_MODULES


def test_every_module_calling_the_helper_is_transparent():
    """The general form of the bug, so the next call site cannot repeat it.

    Any module that calls `warn_legacy_html_usage` and is not listed as
    transparent silences itself. Derived by scanning the package rather than
    hardcoded, so a new call site is covered the day it lands.
    """
    import ast
    from pathlib import Path

    from edgar.files._deprecation import _TRANSPARENT_MODULES

    files_pkg = Path(__file__).parents[3] / "edgar" / "files"
    callers = set()
    for path in files_pkg.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "warn_legacy_html_usage"):
                callers.add(f"edgar.files.{path.stem}")

    missing = callers - _TRANSPARENT_MODULES
    assert not missing, (
        f"these modules call warn_legacy_html_usage but are not transparent, "
        f"so their warnings are silenced: {sorted(missing)}"
    )


def test_the_scan_finds_the_known_callers():
    """Mutation probe: the scan above must not pass by finding nothing."""
    import ast
    from pathlib import Path

    files_pkg = Path(__file__).parents[3] / "edgar" / "files"
    callers = set()
    for path in files_pkg.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "warn_legacy_html_usage"):
                callers.add(f"edgar.files.{path.stem}")

    assert "edgar.files.page_breaks" in callers
    assert "edgar.files.html" in callers


# --------------------------------------------------------------------------
# Internal callers stay quiet
# --------------------------------------------------------------------------

def test_internal_page_break_marking_stays_quiet():
    """`Document.parse` marks page breaks internally and must not warn twice.

    It emits its own `edgar.files.html` deprecation; adding a second one for
    the page-break hop would make the legacy path noisier than the thing it is
    steering people away from.
    """
    from edgar.files.html import Document

    messages = _deprecations(Document.parse, HTML)
    page_break_warnings = [m for m in messages if "page_breaks()" in m]
    assert not page_break_warnings, messages
