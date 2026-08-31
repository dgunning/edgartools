"""Phase 0 of removing edgar.files: every user-reachable entry point warns.

Bead: edgartools-07lk.3
GitHub Issue: https://github.com/dgunning/edgartools/issues/930

6.0 DELETES edgar.files. A user whose code reaches it through a module that
never warned gets no notice at all — just an ImportError on upgrade. This
covers the modules that had no deprecation before: markdown, tables and text.

Two properties, and the second is the one that has already gone wrong once in
this package (see `edgar/files/_deprecation.py`, where `page_breaks` warned for
nobody until it was named transparent):

  IT FIRES FOR USERS. Asserted by calling from a module whose `__name__` is not
  `edgar.*`, which is what the frame gate actually inspects.

  IT IS SILENT INTERNALLY. edgartools itself still calls these during ordinary
  operation — `Filing.markdown()` reaches `to_markdown`, `edgar.sgml` reaches
  `ProcessedTable`. A warning there fires at users doing nothing wrong and
  turns `import edgar` into a failure under `-W error`.

WHAT IS DELIBERATELY NOT COVERED: edgar.files.styles. `parse_style` runs 24
times on an 11KB fixture and into the thousands on a real 10-K, and the frame
gate walks the stack on every call. It is an internal helper of the legacy
parser, not an entry point, and the entry points above it (Document,
SECHTMLParser) already warn.
"""

import warnings

import pytest

ENTRY_POINTS = """
from edgar.files.markdown import to_markdown
from edgar.files.tables import TableProcessor
from edgar.files.text import JsonDocument, PlainDocument, XmlDocument


def call_all():
    to_markdown("<p>hi</p>")
    try:
        TableProcessor.process_table(object())
    except Exception:
        pass
    PlainDocument("x")
    XmlDocument("<a/>")
    JsonDocument("{}")
"""


def _call_from(module_name: str):
    """Run the entry points from a frame whose module really is `module_name`.

    The frame gate reads `frame.f_globals['__name__']`, so a lambda defined in
    the test module claims the test module's name no matter where it is stored.
    Building a real module namespace is the only way to pose as edgartools.
    """
    namespace = {"__name__": module_name}
    exec(compile(ENTRY_POINTS, f"<{module_name}>", "exec"), namespace)  # noqa: S102
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        namespace["call_all"]()
    return [w for w in caught if issubclass(w.category, DeprecationWarning)]


def test_user_call_sites_are_warned():
    assert len(_call_from("some_user_script")) >= 5


def test_edgartools_internal_call_sites_stay_quiet():
    assert _call_from("edgar.some_internal_module") == []


@pytest.mark.parametrize("module,fragment", [
    ("markdown", "edgar.files.markdown"),
    ("tables", "edgar.files.tables"),
    ("text", "edgar.files.text"),
])
def test_each_message_names_its_module_and_the_release(module, fragment):
    messages = [str(w.message) for w in _call_from("some_user_script")]
    mine = [m for m in messages if fragment in m]
    assert mine, f"no deprecation names {fragment}"
    assert all("6.0" in m for m in mine), f"{fragment} message does not name the release"


@pytest.mark.parametrize("module", ["markdown", "tables", "text"])
def test_the_module_is_transparent_to_the_frame_gate(module):
    """Without this the warning is silenced at its own call site and fires for nobody."""
    from edgar.files._deprecation import _TRANSPARENT_MODULES
    assert f"edgar.files.{module}" in _TRANSPARENT_MODULES


def test_one_legacy_render_does_not_emit_a_pile_of_warnings():
    """A legacy module calling another must not read as a user call.

    `Document.parse(...).to_markdown()` reaches edgar.files.tables and
    edgar.files.markdown internally. Before the frame gate skipped only the
    WARNING'S OWN module, it skipped every legacy module on the way out, landed
    on the user's frame and warned three times over — twice naming modules the
    caller never touched. Four warnings for one call is how a deprecation stops
    being read.
    """
    src = """
from edgar.files.html import Document
HTML = "<html><body><p>hi</p><table><tr><td>1</td><td>2</td></tr></table></body></html>"


def call_all():
    d = Document.parse(HTML)
    if d:
        d.to_markdown()
"""
    namespace = {"__name__": "some_user_script"}
    exec(compile(src, "<some_user_script>", "exec"), namespace)  # noqa: S102
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        namespace["call_all"]()
    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]

    # The entry point the user actually touched warns...
    assert any("edgar.files.html" in m for m in messages)
    # ...and the modules it reached internally do not.
    assert not [m for m in messages if "edgar.files.tables" in m], messages
    assert not [m for m in messages if "edgar.files.markdown" in m], messages


def test_styles_is_deliberately_not_warned():
    """A hot path, and its entry points already warn — see the module docstring.

    Pinned so the omission reads as a decision rather than an oversight; if it
    is ever revisited, this test is the place that records why it was skipped.
    """
    import edgar.files.styles as styles
    source = open(styles.__file__, encoding="utf-8").read()
    assert "warn_legacy_html_usage" not in source


def test_the_unreachable_id_parser_is_gone():
    """687 lines, three classes, zero callers (bead edgartools-07lk.3.1)."""
    import pathlib

    import edgar.files as files_pkg
    path = pathlib.Path(files_pkg.__file__).parent / "html_documents_id_parser.py"
    assert not path.exists()
