"""Frame-gated deprecation helper for legacy edgar.files.* modules.

The legacy HTML stack (edgar.files.html, edgar.files.html_documents,
edgar.files.htmltools) is deprecated in favor of edgar.documents, but
edgartools' own code still instantiates these classes during normal
operation. Naive module-top warnings.warn() calls fire on every
internal import and pollute downstream test suites that run with
``-W error`` — turning every ``import edgar`` into a failure.

This helper suppresses the deprecation signal when the call site is
edgartools-internal, and re-emits it for user code so the deprecation
notice is preserved where it matters.
"""

import inspect
import warnings

#: Emitted by ``Filing.markdown()`` and ``Attachment.markdown()`` when a caller
#: asks for page breaks. ``{cls}`` is the class name of the call site. Page
#: break rendering lives only in ``edgar.files.markdown``; the ``edgar.documents``
#: builder treats page-break ``<hr>``s and page-number containers as print
#: chrome and drops them (``strategies/document_builder.py``). So the flag does
#: not select a feature, it selects a whole renderer — which is the reason it is
#: going away rather than being ported.
PAGE_BREAK_DEPRECATION = (
    "{cls}.markdown(include_page_breaks=True) renders through the legacy "
    "edgar.files pipeline, which drops images and formats tables differently "
    "from the default path. It is deprecated and will be removed in "
    "edgartools 6.0; call {cls}.markdown() without the flag for the supported "
    "renderer."
)

# Modules that are transparent to the caller check: the deprecated
# modules themselves and (for dataclass-generated __init__ trampolines)
# the standard library's dataclasses module. The dataclass machinery
# emits an __init__ that runs in the *defining* module's namespace, so
# we also skip the deprecated modules when walking up.
#
# EVERY MODULE THAT CALLS THIS HELPER MUST BE LISTED. The walk below starts at
# the caller's own frame, so a deprecated function whose module is absent here
# is read as an edgartools-internal call and silenced — the warning becomes a
# no-op that looks correct at the call site and survives any test that only
# asserts the call exists. `edgar.files.page_breaks` was added when
# `detect_page_breaks`/`mark_page_breaks` got their warnings and hit exactly
# that: they fired for nobody until the module was named here.
# `test_07lk3_page_break_deprecation.py` derives the caller list by scanning
# the package, so a new call site is covered the day it lands.
#: Frames always skipped regardless of origin: the helper itself, and the
#: dataclass machinery whose synthesized ``__init__`` runs in the defining
#: module's namespace.
_SELF_SKIP = frozenset({'edgar.files._deprecation', 'dataclasses'})

#: Retained for the drift test in
#: tests/issues/regression/test_07lk3_page_break_deprecation.py, which asserts
#: every module calling the helper is listed. The walk above no longer reads
#: this set — it derives the origin from the calling frame — but the list still
#: documents which modules carry deprecations.
_TRANSPARENT_MODULES = frozenset({
    'edgar.files._deprecation',
    'edgar.files.html',
    'edgar.files.html_documents',
    'edgar.files.htmltools',
    'edgar.files.markdown',
    'edgar.files.page_breaks',
    'edgar.files.tables',
    'edgar.files.text',
    'dataclasses',
})


def warn_legacy_html_usage(message: str) -> None:
    """Emit a ``DeprecationWarning`` unless the call site is internal.

    Walks up the call stack past the deprecation helper and the
    deprecated modules themselves (and the ``dataclasses`` module that
    hosts synthesized ``__init__`` trampolines) to find the first
    non-transparent frame. If that frame's module is ``edgar`` or any
    ``edgar.*`` submodule, the call is internal and the warning is
    suppressed. Any other caller — user code, notebooks, third-party
    libraries, tests — receives the standard ``DeprecationWarning`` at
    its own call site.
    """
    current = inspect.currentframe()
    frame = current.f_back if current is not None else None

    # Skip the frames belonging to the module that RAISED this warning, not
    # every deprecated module. Skipping them all made a legacy module calling
    # another one look like a user call: `Document.parse(...).to_markdown()`
    # emitted four warnings, two of them naming `edgar.files.tables` and
    # `edgar.files.markdown` — modules the caller never touched — because the
    # walk skipped `edgar.files.html` on its way out and landed on the user.
    # Four warnings for one call is how a deprecation gets filtered wholesale.
    #
    # The self-skip is still required: a dataclass's synthesized `__init__`
    # runs in its DEFINING module's namespace, so `Document(...)` called by a
    # user would otherwise read as internal and never warn at all.
    origin = frame.f_globals.get('__name__', '') if frame is not None else ''

    while frame is not None:
        mod_name = frame.f_globals.get('__name__', '')
        if mod_name == origin or mod_name in _SELF_SKIP:
            frame = frame.f_back
            continue
        if mod_name == 'edgar' or mod_name.startswith('edgar.'):
            return  # edgartools-internal call — stay quiet
        break

    warnings.warn(message, DeprecationWarning, stacklevel=3)
