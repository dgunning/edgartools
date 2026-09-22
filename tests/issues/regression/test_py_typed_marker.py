"""
The PEP 561 marker that makes edgartools' annotations visible downstream.

Bead: edgartools-07lk.6 (public issue gh-932, shared with 07lk.5)

Every annotation in this library was invisible to a downstream type checker.
Without `edgar/py.typed`, mypy refuses to look inside an installed package at
all:

    error: Skipping analyzing "edgar": module is installed, but missing library
           stubs or py.typed marker  [import-untyped]

and every symbol it exports degrades to `Any` — so a consumer calling
`Company(cik_or_ticker=[1, 2, 3])` got no error. With the marker, mypy reports
the argument type. That was the entire user-visible payoff of the typing work
in edgartools-v7iz and edgartools-q9tf, and it was one empty file away.

TWO WAYS TO LOSE IT, one test each. The file can be deleted, or — the quieter
one, and the reason this test exists rather than a note in a checklist — it can
survive in the repo while falling out of the distribution. `[tool.hatch.build]`
`include` is an allowlist whose only source pattern is `edgar/**/*.py`. A
zero-byte file with no extension is exactly what such a list drops silently:
the repo looks correct, the tests pass, and the wheel ships untyped. That is
what 5.47.0 did.
"""
import re
from pathlib import Path

import edgar

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_py_typed_marker_exists():
    """The marker sits inside the package, next to __init__.py."""
    marker = Path(edgar.__file__).resolve().parent / "py.typed"
    assert marker.is_file(), (
        f"{marker} is missing. Without it every type annotation in this library "
        f"is invisible to mypy and to pyright in stub-only mode: `import edgar` "
        f"reports import-untyped and the whole API resolves to Any."
    )


def test_py_typed_is_a_bare_marker():
    """PEP 561 marks inline-typed packages with an empty file.

    `partial\\n` means something specific — a stub-only package covering part of
    a runtime package — and edgartools is not one. Anything else in here is a
    stray edit.
    """
    marker = Path(edgar.__file__).resolve().parent / "py.typed"
    assert marker.read_text().strip() == "", (
        f"{marker} should be empty; it contains {marker.read_text()!r}. PEP 561 "
        f"reserves 'partial' for stub-only distributions."
    )


def test_py_typed_is_in_the_build_include_list():
    """The marker must be named in the packaging allowlist, or it never ships.

    This is the failure the file-exists test above cannot see: `include` matches
    `edgar/**/*.py` and nothing else that would catch an extensionless file, so
    dropping this entry ships a wheel whose annotations are, once again, dead
    weight.
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    assert pyproject.is_file(), (
        f"expected the repo's pyproject.toml at {pyproject}; this test resolves "
        f"it relative to its own location, so a move of this file breaks it"
    )

    text = pyproject.read_text()
    build_section = re.search(
        r"^\[tool\.hatch\.build\]$(.*?)(?=^\[)", text, re.MULTILINE | re.DOTALL
    )
    assert build_section, "[tool.hatch.build] section not found in pyproject.toml"

    assert "edgar/py.typed" in build_section.group(1), (
        "pyproject.toml no longer lists 'edgar/py.typed' under "
        "[tool.hatch.build] include. The built wheel will not contain the "
        "marker, and every downstream type checker goes back to treating "
        "edgartools as untyped — silently, because the file still exists here."
    )
