"""The wheel ships the library, not the tooling that develops it.

Bead: edgartools-07lk.12.1

`[tool.hatch.build].include` opens with an unrestricted `edgar/**/*.py`, so
anything living under edgar/ shipped to every user by default: ~8,900 lines of
evaluation harnesses, training scripts and demos that no shipped module imports.

Two invariants, and the second is the load-bearing one:

  1. the exclusions are declared;
  2. NOTHING SHIPPED IMPORTS THE EXCLUDED CODE.

(2) is what makes (1) safe. An exclusion whose code is imported at runtime does
not shrink the wheel, it breaks the install — and it breaks it for users only,
never in this repo, where the excluded files are present on disk. That failure
cannot be caught by importing edgartools here, so it is checked structurally.
"""

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
EDGAR = ROOT / "edgar"

EXCLUDED_DIRS = ["edgar/ai/evaluation", "edgar/ai/examples", "edgar/entity/training"]
EXCLUDED_FILES = ["edgar/thirteenf/demo_comparison.py"]

# Module prefixes that must not be imported by shipped code.
EXCLUDED_MODULES = (
    "edgar.ai.evaluation",
    "edgar.ai.examples",
    "edgar.entity.training",
    "edgar.thirteenf.demo_comparison",
)


def _pyproject():
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _excluded_paths():
    return [EDGAR.parent / p for p in EXCLUDED_DIRS + EXCLUDED_FILES]


def _shipped_python_files():
    """Every .py under edgar/ that the wheel will actually contain."""
    excluded = _excluded_paths()
    for path in sorted(EDGAR.rglob("*.py")):
        if any(path == e or e in path.parents for e in excluded):
            continue
        yield path


def test_the_excluded_paths_still_exist_in_the_repo():
    """Otherwise the exclusions are dead patterns and the test proves nothing."""
    for path in _excluded_paths():
        assert path.exists(), f"{path} is gone; drop its exclude pattern too"


def test_the_exclusions_are_declared():
    text = _pyproject()
    assert "exclude = [" in text, "[tool.hatch.build] lost its exclude list"
    for pattern in EXCLUDED_DIRS:
        assert f'"{pattern}/**"' in text, f"{pattern} is no longer excluded from the wheel"
    for pattern in EXCLUDED_FILES:
        assert f'"{pattern}"' in text, f"{pattern} is no longer excluded from the wheel"


def test_no_shipped_module_imports_excluded_code():
    """The invariant that makes the exclusion safe.

    A violation here would install fine in this repo and fail with ImportError
    only on a user's machine, which is the worst shape a packaging bug can take.
    """
    offenders = []
    for path in _shipped_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                if name.startswith(EXCLUDED_MODULES):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} imports {name}")
    assert not offenders, (
        "shipped code imports code excluded from the wheel — this installs fine "
        "here and raises ImportError for users:\n  " + "\n  ".join(offenders)
    )


def test_exporters_is_not_excluded():
    """export_skill is public API; excluding ai/exporters would break `edgar.ai`."""
    assert "edgar/ai/exporters" not in _pyproject().split("exclude = [")[1].split("]")[0]
    assert "from edgar.ai.exporters import export_skill" in (
        EDGAR / "ai" / "__init__.py").read_text(encoding="utf-8")


def test_the_deleted_dead_packages_stay_deleted():
    for gone in ("tools", "analysis", "reference/financials.py"):
        assert not (EDGAR / gone).exists(), f"edgar/{gone} came back; it has no callers"
    assert not (EDGAR / "xbrl" / "analysis").exists()


@pytest.mark.slow
def test_a_built_wheel_actually_omits_them():
    """Ground truth: the config is a claim, the wheel is the fact."""
    import subprocess
    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as out:
        proc = subprocess.run(
            ["hatch", "build", "-t", "wheel", out],
            cwd=ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            pytest.skip(f"hatch build unavailable: {proc.stderr[-300:]}")
        wheels = list(pathlib.Path(out).glob("*.whl"))
        assert wheels, "no wheel produced"
        names = zipfile.ZipFile(wheels[0]).namelist()

    # A floor, so a truncated or empty wheel cannot satisfy the "absent"
    # assertions below by containing nothing at all. 483 files at the time of
    # writing; this only needs to be well clear of zero.
    assert len(names) > 300, f"wheel has only {len(names)} files — build looks broken"

    for pattern in EXCLUDED_DIRS:
        prefix = pattern[len("edgar/"):]
        assert not [n for n in names if n.startswith(f"edgar/{prefix}/")], \
            f"{pattern} shipped in the wheel"
    assert "edgar/thirteenf/demo_comparison.py" not in names
    # ...and the library itself is still there.
    assert "edgar/__init__.py" in names
    assert "edgar/py.typed" in names, "PEP 561 marker missing — wheel would be untyped"
    assert any(n.startswith("edgar/ai/exporters/") for n in names)
