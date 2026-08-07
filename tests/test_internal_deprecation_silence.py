"""Regression tests for issue: DeprecationWarning emitted at `import edgar` time.

Before the fix, edgar.files.html_documents, edgar.files.html, and
edgar.files.htmltools each emitted a top-level `warnings.warn(...,
DeprecationWarning)` on first import. Because edgartools itself imports
these modules during its own startup cascade (edgar.__init__ ->
edgar._filings -> edgar._markdown -> edgar.files.html_documents), the
warnings fired on every `import edgar`. Downstream projects that run
under `-W error` (a common, recommended pytest setup) saw their entire
test suites break.

The fix moves each warning out of the module top and into the relevant
class `__init__` (or `__post_init__` for the @dataclass), with frame
inspection that suppresses the signal when the call site is itself
inside edgartools. User code that instantiates these classes still
receives the standard DeprecationWarning.
"""

import contextlib
import subprocess
import sys
import warnings


def _run_python(code: str, *args: str) -> subprocess.CompletedProcess:
    """Run a snippet in a clean Python interpreter."""
    return subprocess.run(
        [sys.executable, *args, "-c", code],
        capture_output=True,
        text=True,
    )


def test_import_edgar_under_W_error():
    """`python -W error -c "import edgar"` must succeed cleanly.

    A fresh interpreter is required so module-import side effects run
    end-to-end; doing this in-process would hit cached modules.
    """
    result = _run_python("import edgar", "-W", "error")
    assert result.returncode == 0, (
        f"import edgar under -W error failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_import_deprecated_submodules_under_W_error():
    """Each deprecated submodule must also be importable under -W error."""
    result = _run_python(
        "import edgar.files.html_documents; "
        "import edgar.files.html; "
        "import edgar.files.htmltools",
        "-W", "error",
    )
    assert result.returncode == 0, (
        f"deprecated submodule import under -W error failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_user_instantiation_of_html_document_warns():
    """User code that instantiates HtmlDocument must still see the warning."""
    from edgar.files.html_documents import HtmlDocument

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        HtmlDocument(blocks=[])

    deprecations = [
        c for c in caught if issubclass(c.category, DeprecationWarning)
    ]
    assert deprecations, (
        "HtmlDocument() must emit DeprecationWarning to user callers"
    )
    assert "edgar.documents" in str(deprecations[0].message)


def test_user_instantiation_of_legacy_document_warns():
    """User code that instantiates edgar.files.html.Document must still warn."""
    from edgar.files.html import Document

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Document(nodes=[])

    deprecations = [
        c for c in caught if issubclass(c.category, DeprecationWarning)
    ]
    assert deprecations, (
        "Document() must emit DeprecationWarning to user callers"
    )


def test_user_instantiation_of_chunked_document_warns():
    """User code that instantiates ChunkedDocument must still warn."""
    from edgar.files.htmltools import ChunkedDocument

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # ChunkedDocument's __init__ runs further processing that may
        # surface unrelated AttributeErrors on minimal HTML; the warning
        # fires before any of that, so we tolerate that specific error.
        with contextlib.suppress(AttributeError):
            ChunkedDocument(html="<html><body><p>x</p></body></html>")

    deprecations = [
        c for c in caught if issubclass(c.category, DeprecationWarning)
    ]
    assert deprecations, (
        "ChunkedDocument() must emit DeprecationWarning to user callers"
    )
