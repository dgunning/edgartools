"""`chunked_document` warns the user, and only the user.

Bead: edgartools-07lk.3 (the `edgar.files` removal).

Two defects, both found by measuring rather than reading:

1. **The library tripped its own deprecation.** `items` and `__getitem__` on
   TenK, TenQ, TwentyF and CurrentReport try the new parser first and fall back
   to the legacy `ChunkedDocument`. Those fallbacks read the *public*
   `chunked_document`, so a plain `twentyf.items` emitted
   "chunked_document is deprecated" — naming an attribute the caller had never
   used, about a choice that was ours. Under `-W error::DeprecationWarning`,
   which plenty of suites run, that is not a warning but an exception.

2. **Two classes had silently dropped the warning.** TenQ and CurrentReport
   overrode `chunked_document` itself to change construction, and an override
   that replaces the property replaces the `warnings.warn` inside it. Their
   users got no notice at all that the attribute disappears in 6.0 — the exact
   population the deprecation exists to reach.

The fix separates the two jobs: `_chunked_document` constructs (subclasses
override this) and `chunked_document` warns then delegates (nobody overrides
this). These tests pin both halves, because the failure mode of each is silence.
"""
import warnings

import pytest
from unittest.mock import MagicMock

from edgar.company_reports import FortyF, TenK, TenQ, TwentyF
from edgar.company_reports.current_report import CurrentReport

HTML = "<html><body><p>Item 5. Operating Review</p><p>body text</p></body></html>"


def _filing(form):
    filing = MagicMock()
    filing.form = form
    filing.html.return_value = HTML
    filing.accession_number = "0000000000-00-000000"
    filing.accession_no = "0000000000-00-000000"
    filing.base_dir = None
    return filing


def _report(cls, form):
    report = cls.__new__(cls)
    report._filing = _filing(form)
    report._parser = None
    report.__dict__["_cross_reference_index"] = None
    return report


REPORTS = [
    pytest.param(TenK, "10-K", id="TenK"),
    pytest.param(TenQ, "10-Q", id="TenQ"),
    pytest.param(TwentyF, "20-F", id="TwentyF"),
    pytest.param(CurrentReport, "8-K", id="CurrentReport"),
    # Found by sweeping CompanyReport.__subclasses__() rather than by grep —
    # the grep that built this list missed TenK's own override, so the class
    # list here is generated from the type system, not from reading files.
    pytest.param(FortyF, "40-F", id="FortyF"),
]


@pytest.mark.fast
@pytest.mark.parametrize("cls,form", REPORTS)
def test_the_public_name_still_warns(cls, form):
    """Every class, not just the two that inherited it.

    A deprecation only some subclasses emit is worse than none: it reads as
    "this call is fine" to exactly the users whose class dropped it.
    """
    report = _report(cls, form)
    with pytest.warns(DeprecationWarning, match="chunked_document is deprecated"):
        report.chunked_document


@pytest.mark.fast
@pytest.mark.parametrize("cls,form", REPORTS)
def test_the_private_accessor_is_silent(cls, form):
    """What our own fallbacks read must not warn."""
    report = _report(cls, form)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report._chunked_document
    offenders = [w for w in caught
                 if "chunked_document is deprecated" in str(w.message)]
    assert not offenders, (
        "the internal accessor warned; fallback paths would blame the user for "
        "our choice"
    )


@pytest.mark.fast
def test_a_plain_items_call_does_not_warn_about_an_attribute_nobody_used():
    """The bug, stated as the user experiences it.

    20-F is the case that always reaches the legacy parser — TwentyF prefers
    `chunked_document` because the pattern-based extractor does not handle the
    TOC format well — so it is the one where the self-inflicted warning fired on
    every call rather than only on a fallback.
    """
    twentyf = _report(TwentyF, "20-F")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            twentyf.items
        except Exception:
            # The parse may fail on this stub; the warning is what is under test,
            # and it would have been emitted before any failure.
            pass
    offenders = [w for w in caught
                 if "chunked_document is deprecated" in str(w.message)]
    assert not offenders, (
        f"`.items` emitted {len(offenders)} deprecation warning(s) naming an "
        f"attribute the caller never touched"
    )


@pytest.mark.fast
def test_no_subclass_overrides_the_warning_away():
    """The guard, generated from the type system rather than from a grep.

    Three classes independently overrode `chunked_document` to change how it was
    built and took the `warnings.warn` with them — TenK, TenQ and CurrentReport.
    Two of those were found by reading; the third was found only when a
    parametrized test failed, because the grep that built the list missed it.

    So this asserts the shape instead of the instances: construction belongs on
    `_chunked_document`, and any subclass that redefines the public name has
    almost certainly deleted the deprecation without meaning to.
    """
    import importlib
    import pkgutil

    import edgar.company_reports as cr
    from edgar.company_reports._base import CompanyReport

    for module in pkgutil.iter_modules(cr.__path__):
        importlib.import_module(f"edgar.company_reports.{module.name}")

    offenders = [cls.__name__ for cls in CompanyReport.__subclasses__()
                 if "chunked_document" in cls.__dict__]
    assert not offenders, (
        f"{offenders} override the public `chunked_document`, which replaces the "
        f"property containing the deprecation warning. Override "
        f"`_chunked_document` instead — that is the construction hook, and the "
        f"warning then stays in exactly one place."
    )


@pytest.mark.fast
def test_the_public_property_returns_the_same_object_the_internals_use():
    """The split must not fork the two paths onto different documents.

    If it did, a user debugging via `chunked_document` would be inspecting
    something other than what produced their result.
    """
    tenk = _report(TenK, "10-K")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert tenk.chunked_document is tenk._chunked_document
