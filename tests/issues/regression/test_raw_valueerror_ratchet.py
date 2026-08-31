"""A ratchet on raw `raise ValueError` under edgar/.

Bead: edgartools-35jj
GitHub Issue: https://github.com/dgunning/edgartools/issues/933

6.0 raises from one hierarchy rooted at `EdgarError` (bead edgartools-07lk.10).
`ValidationError` IS-A `ValueError`, so converting a raw raise is additive —
`except ValueError:` written against the old raise keeps catching it — and none
of this sits on the 6.0 critical path. What it does need is a direction.

This is that direction. The count may fall and may not rise.

WHY A RATCHET HERE AND NOT FOR THE SWALLOWED EXCEPTIONS. A count-based ratchet
was rejected for the try-except-pass sites (edgartools-35jj piece 1) because it
prevents the 151st without ever classifying the 150, and would happily permit
swapping a legitimate swallow for a bug-hiding one. Neither objection applies
to this rule: every raw `raise ValueError` is the same defect with the same
mechanical fix, so the count is the whole story.

The number has already moved the wrong way once — the bead recorded 135 on
2026-07-28 and it was 142 when this test was written, which is the argument for pinning it
rather than intending to get to it. Tranche 1 (thirteenf/parsers/primary_xml.py,
seven raises collapsing into one helper) took it to 135, and the #1177
period-length fix took it to 133 — the ratchet caught that gain on the merge
that produced it, which is what the fail-on-improvement rule is for.
"""

import ast
import pathlib

import pytest

# Lower this when you convert raises. It may never be raised.
BASELINE = 133

EDGAR = pathlib.Path(__file__).resolve().parents[3] / "edgar"


def _raw_valueerror_sites():
    """Every `raise ValueError` under edgar/, as (path, lineno).

    Parsed rather than grepped: a grep counts the phrase in docstrings, comments
    and test fixtures, which makes the number drift for reasons that are not
    code changes.  Subclasses do not count — `raise ValidationError(...)` is the
    fixed state, not the defect.
    """
    sites = []
    for path in sorted(EDGAR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not our files
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                name = exc.func.id
            elif isinstance(exc, ast.Name):
                name = exc.id
            else:
                continue
            if name == "ValueError":
                sites.append((path.relative_to(EDGAR.parent), node.lineno))
    return sites


def test_edgar_package_is_importable_from_here():
    """The counter walks a directory; if it walks the wrong one it counts zero."""
    assert EDGAR.is_dir(), f"expected the edgar package at {EDGAR}"
    assert (EDGAR / "__init__.py").exists()
    assert len(list(EDGAR.rglob("*.py"))) > 100


def test_raw_valueerror_count_does_not_grow():
    sites = _raw_valueerror_sites()
    if len(sites) <= BASELINE:
        return
    added = "\n".join(f"  {p}:{n}" for p, n in sites[-8:])
    pytest.fail(
        f"raw `raise ValueError` rose to {len(sites)} from a baseline of {BASELINE}.\n"
        f"Raise `ValidationError` instead — it IS-A `ValueError`, so nothing that "
        f"catches the old raise stops working, and it carries `parameter=` and "
        f"`suggestions=` that tell the caller what to do:\n\n"
        f"    from edgar.exceptions import ValidationError\n"
        f"    raise ValidationError('...', parameter='ticker', invalid_value=ticker,\n"
        f"                          suggestions=['...'])\n\n"
        f"Some of the current sites:\n{added}"
    )


def test_baseline_is_not_stale():
    """A ratchet nobody tightens is a ratchet that rots.

    Failing on an improvement is the point: it costs one line to lower the
    number, and skipping that turns the pin into a ceiling nobody is under.
    """
    count = len(_raw_valueerror_sites())
    assert count >= BASELINE, (
        f"raw `raise ValueError` is down to {count}, below the pinned baseline of "
        f"{BASELINE}. Lower BASELINE to {count} in this file to lock the gain in."
    )
