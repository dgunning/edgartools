"""The silent-`None` returns that become exceptions in 6.0.

Bead: edgartools-07lk.10, PR3 of 3. Design §4.

Four calls answered `None` for something that was really a failure, so the
caller could not tell "there is no such thing" from "we could not tell you".
Each now warns, names what it will raise, and raises it under
EDGARTOOLS_STRICT_ERRORS.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. **`.get()` stays silent.** It is the migration target we point people at,
     and it reaches the miss through the same `__getitem__`. If the suppression
     regresses, everyone who took our advice gets warned for taking it — and
     the warning would look correct to anyone reading the code that emits it.
  2. **The warning names the exception it becomes.** A `FutureWarning` that says
     "this will change" without naming what to catch leaves the reader to go and
     find out, which is the step nobody takes. These assert message CONTENT.
  3. **The legitimate `None`s still return `None`.** The point of the change is
     the distinction; a flip that also swallowed the true absences would destroy
     it while every "does it raise?" test still passed.
  4. **Every documented example in the guide runs.** Errors are the one area
     where a wrong example is worse than none: it teaches a handler that will
     never fire.
"""
import re
import warnings
from pathlib import Path

import pytest

import edgar
from edgar import _no_xml_to_parse
from edgar.company_reports import TenK, TenQ
from edgar.company_reports._base import CompanyReport, section_not_found
from edgar.exceptions import (
    DataObjectError,
    EdgarError,
    SectionNotFoundError,
    ValidationError,
    strict_errors_enabled,
    warn_will_raise,
)

GUIDE = Path(__file__).parents[3] / "docs" / "guides" / "error-handling.md"


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")


@pytest.fixture
def lenient(monkeypatch):
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)


class _Filing:
    """The smallest thing the report classes read on a lookup miss."""
    accession_number = "0000320193-23-000106"
    accession_no = "0000320193-23-000106"
    form = "10-K"

    def html(self):
        return None


class _Report(TenK):
    """A 10-K whose every lookup misses, without touching the network."""

    def __init__(self, items=("Item 1", "Item 7")):
        self._filing = _Filing()
        self._items = list(items)
        # _cross_reference_index is a cached_property that parses HTML; there
        # is none here, so seed the cache rather than let it try.
        self.__dict__["_cross_reference_index"] = None

    @property
    def sections(self):
        return {}

    @property
    def items(self):
        return self._items

    @property
    def _chunked_document(self):
        # The private accessor: it is what TenK's fallback path reads. Stubbing
        # the public `chunked_document` would leave the real constructor in
        # play, which needs a filing this fake does not have.
        class _Empty:
            def __getitem__(self, key):
                return None
        return _Empty()


def _report_filed_as(accession: str) -> _Report:
    """A `_Report` whose filing carries a specific accession number.

    The dedup tests need many reports that differ only in the identifier the
    message interpolates, which is exactly the axis a corpus loop varies along.
    """
    report = _Report()
    report._filing = _Filing()
    report._filing.accession_number = accession
    report._filing.accession_no = accession
    return report


# ---------------------------------------------------------------------------
# warn_will_raise, the primitive under all four sites
# ---------------------------------------------------------------------------

def test_warn_will_raise_warns_by_default(lenient):
    with pytest.warns(FutureWarning, match="raises ValidationError in edgartools 6.0"):
        warn_will_raise(ValidationError("bad input"))


def test_warn_will_raise_raises_under_strict(strict):
    with pytest.raises(ValidationError, match="bad input"):
        warn_will_raise(ValidationError("bad input"))


def test_the_warning_carries_the_error_message_not_just_a_notice(lenient):
    """The text a user reads while porting must be the text they will catch."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_will_raise(ValidationError("'123456-99' is not a valid accession number."))
    message = str(caught[0].message)
    assert "'123456-99' is not a valid accession number." in message
    assert "EDGARTOOLS_STRICT_ERRORS" in message, (
        "the warning must say how to get the new behaviour now — otherwise the "
        "only way to test the 6.0 path is to wait for 6.0"
    )


def test_a_corpus_loop_warns_once_not_once_per_filing(lenient):
    """The warning text must not vary per filing, or the dedup silently dies.

    Python suppresses a repeat only when the rendered text matches exactly, so
    an accession number interpolated into the *warning* turns one warning into
    one per filing. A user looping over a few thousand 10-Ks would get a few
    thousand stderr lines, which reads as a broken library rather than a
    considerate one — and the flood scales with corpus size, so the people hit
    hardest are the bulk users we most want to keep.

    `simplefilter("default")` is what a real interpreter applies to
    FutureWarning; `"always"` (used by the tests above, to inspect a single
    warning) would defeat the very dedup under test.
    """
    errors = [
        section_not_found(_report_filed_as(f"0000320193-24-{i:06d}"), "Item 99")
        for i in range(500)
    ]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        for error in errors:
            warn_will_raise(error)          # one call site, 500 filings
    assert len(caught) == 1, (
        f"500 filings produced {len(caught)} warnings; the warning text is "
        f"varying per filing. Keep per-filing detail on the error (which strict "
        f"mode raises) and out of error.warning_summary."
    )


def test_the_error_still_names_the_filing_even_though_the_warning_does_not(lenient):
    """Deduping the warning must not cost the detail 6.0 raises."""
    error = section_not_found(_report_filed_as("0000320193-24-000106"), "Item 99")
    assert "0000320193-24-000106" in str(error), (
        "the exception is what strict mode raises and what the user debugs "
        "against; it keeps the accession"
    )
    assert "0000320193-24-000106" not in error.warning_summary, (
        "the warning text is what Python dedups on; it must not"
    )


def test_the_obj_site_dedups_too(lenient):
    """`filing.obj()` has the same exposure as `report[item]`.

    Walking a company's whole ownership history crosses every Form 3/4/5 filed
    before roughly 2003, none of which has XML. That is a loop over filings
    hitting one line, so the accession has to stay out of the warning here for
    the same reason it does there.
    """
    filings = []
    for i in range(500):
        filing = _Filing()
        filing.accession_no = f"0000320193-98-{i:06d}"
        filing.form = "4"
        filings.append(filing)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        for filing in filings:
            warn_will_raise(_no_xml_to_parse(filing))
    assert len(caught) == 1, (
        f"500 pre-XML ownership filings produced {len(caught)} warnings"
    )
    assert "0000320193-98-000000" in str(_no_xml_to_parse(filings[0])), (
        "the error still names the filing for whoever turns strict mode on"
    )


def test_it_is_a_futurewarning_not_a_deprecationwarning(lenient):
    """DeprecationWarning is hidden outside __main__ by default.

    That would silence this for exactly the users who most need it: the ones
    whose own code is a library. Nothing here is deprecated either — the calls
    stay, they just stop answering None.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_will_raise(ValidationError("x"))
    assert caught[0].category is FutureWarning


# ---------------------------------------------------------------------------
# find() — a malformed accession number
# ---------------------------------------------------------------------------

def test_find_warns_on_a_malformed_accession_number(lenient):
    edgar.find.cache_clear()
    with pytest.warns(FutureWarning, match="not a valid accession number"):
        assert edgar.find("123456-99") is None


def test_find_raises_a_validation_error_under_strict(strict):
    edgar.find.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        edgar.find("123456-99")
    exc = excinfo.value
    assert exc.parameter == "search_id"
    assert exc.invalid_value == "123456-99"
    assert any("0000320193-23-000106" in s for s in exc.suggestions), (
        "a format complaint that does not show the format is half a message"
    )


def test_the_validation_error_is_still_a_value_error(strict):
    """The reason this conversion is additive rather than a break."""
    edgar.find.cache_clear()
    with pytest.raises(ValueError):
        edgar.find("123456-99")
    edgar.find.cache_clear()


# ---------------------------------------------------------------------------
# report[item] — a section that is not there
# ---------------------------------------------------------------------------

def test_getitem_warns_and_still_returns_none(lenient):
    report = _Report()
    with pytest.warns(FutureWarning, match="raises SectionNotFoundError"):
        assert report["Item 99"] is None


def test_getitem_raises_under_strict(strict):
    report = _Report()
    with pytest.raises(SectionNotFoundError, match="has no 'Item 99'"):
        report["Item 99"]


def test_the_miss_message_lists_what_the_filing_does_have(strict):
    """Items are optional in ways that surprise people — 10-K Item 16 is a
    summary a filer may simply omit. "Not found" without "here is what is" sends
    the reader back to the filing to find out."""
    report = _Report(items=["Item 1", "Item 1A", "Item 7"])
    with pytest.raises(SectionNotFoundError) as excinfo:
        report["Item 99"]
    exc = excinfo.value
    assert exc.context["requested"] == "Item 99"
    assert exc.context["available"] == ["Item 1", "Item 1A", "Item 7"]
    assert any(".get(" in s for s in exc.suggestions)


def test_section_not_found_is_still_a_keyerror(strict):
    """`except KeyError:` around item access keeps working after the flip."""
    report = _Report()
    with pytest.raises(KeyError):
        report["Item 99"]


def test_a_miss_message_survives_a_report_that_cannot_list_its_items(strict):
    """An error message must not raise a different error on its way out."""
    class _Broken(_Report):
        @property
        def items(self):
            raise RuntimeError("the parser fell over")

    with pytest.raises(SectionNotFoundError) as excinfo:
        _Broken()["Item 99"]
    assert excinfo.value.context["available"] == []


# ---------------------------------------------------------------------------
# .get() — the migration target, which must be silent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", ["1", None])
def test_get_never_warns_and_never_raises(monkeypatch, flag):
    """THE test in this file.

    `.get()` is what we tell people to move to, and it reaches the miss through
    the same `__getitem__` that warns. If the suppression regresses, every user
    who took our advice is warned for taking it — and nothing about the code
    emitting the warning would look wrong.
    """
    if flag:
        monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", flag)
    else:
        monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)

    report = _Report()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert report.get("Item 99") is None
        assert report.get("Item 99", "") == ""
        assert report.get("Item 99", default="fallback") == "fallback"
    flip_warnings = [w for w in caught if w.category is FutureWarning]
    assert not flip_warnings, (
        f"`.get()` emitted {[str(w.message)[:60] for w in flip_warnings]} — the "
        f"migration target must be quieter than the thing it replaces"
    )


def test_get_suppression_does_not_leak_past_the_call(lenient):
    """The context flag has to be reset, or one `.get()` silences the process."""
    report = _Report()
    report.get("Item 99")
    with pytest.warns(FutureWarning):
        report["Item 99"]


def test_get_suppression_is_reset_even_when_the_lookup_raises(lenient):
    class _Exploding(_Report):
        def __getitem__(self, item):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _Exploding().get("Item 1")

    with pytest.warns(FutureWarning):
        _Report()["Item 99"]


def test_get_exists_on_every_report_class():
    """Shipped on the base, so the flip does not arrive somewhere without it."""
    for cls in (CompanyReport, TenK, TenQ):
        assert callable(getattr(cls, "get", None)), f"{cls.__name__} has no .get()"


def test_get_returns_the_value_when_the_item_is_present(lenient):
    class _Present(_Report):
        def __getitem__(self, item):
            return "Item 1 - Business ..."

    assert _Present().get("Item 1") == "Item 1 - Business ..."
    assert _Present().get("Item 1", "unused") == "Item 1 - Business ..."


# ---------------------------------------------------------------------------
# obj() — a modelled form whose data will not read
# ---------------------------------------------------------------------------

class _OwnershipFiling:
    """A Form 4 with no XML — a real shape for pre-2003 ownership filings."""
    form = "4"
    accession_no = "0000320193-99-000001"
    accession_number = "0000320193-99-000001"

    def xml(self):
        return None

    def xbrl(self):
        return None


def test_obj_warns_when_a_modelled_form_has_no_data(lenient):
    with pytest.warns(FutureWarning, match="raises DataObjectError"):
        assert edgar.obj(_OwnershipFiling()) is None


def test_obj_raises_under_strict(strict):
    with pytest.raises(DataObjectError) as excinfo:
        edgar.obj(_OwnershipFiling())
    exc = excinfo.value
    assert exc.form == "4"
    assert exc.accession_no == "0000320193-99-000001"
    assert "no XML document" in str(exc)


def test_obj_still_returns_none_for_a_form_we_do_not_model(strict):
    """The legitimate None, and it must survive strict mode.

    This is the distinction the whole change exists for. A flip that made every
    None into a raise would pass every "does it raise?" test and destroy the
    thing being protected.
    """
    class _Unmodelled:
        form = "SC 14D9"
        accession_no = "0000320193-23-000999"

        def xbrl(self):
            return None

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert edgar.obj(_Unmodelled()) is None


# ---------------------------------------------------------------------------
# The guide is the specification
# ---------------------------------------------------------------------------

def _python_blocks(markdown: str):
    return re.findall(r"```python\n(.*?)```", markdown, re.DOTALL)


def test_the_error_handling_guide_exists():
    assert GUIDE.exists(), f"{GUIDE} is referenced from mkdocs.yml and upgrade/6.0.md"


def test_every_exception_the_guide_names_exists():
    """A guide that teaches a handler for a class we do not raise is worse than
    no guide: the `except` clause silently never fires.

    Resolution spans more than `edgar.exceptions` on purpose. Two classes live
    elsewhere by design — `SSLVerificationError` categorises an httpx error to
    build its message, and `edgar.exceptions` admits no third-party type — and
    the deprecated spellings resolve through their own modules' `__getattr__`.
    A test that only looked in one module would report those as missing.
    """
    import importlib

    modules = [importlib.import_module(name) for name in (
        "edgar.exceptions", "edgar", "edgar.httprequests", "edgar.dates",
        "edgar.core", "edgar.xbrl.exceptions", "edgar.sgml.sgml_parser",
        "edgar.entity.entity_facts",
    )]

    named = set(re.findall(r"\b([A-Z][A-Za-z]*(?:Error|Warning|Exception))\b", GUIDE.read_text()))
    builtins_and_stdlib = {"ValueError", "LookupError", "KeyError", "ConnectionError",
                           "FutureWarning", "DeprecationWarning", "AttributeError", "TypeError"}

    def resolves(name):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return any(getattr(module, name, None) is not None for module in modules)

    unknown = sorted(name for name in named - builtins_and_stdlib if not resolves(name))
    assert not unknown, f"the guide names exception classes that do not exist: {unknown}"


@pytest.mark.parametrize("index", range(len(_python_blocks(GUIDE.read_text()))))
def test_the_guides_python_examples_are_syntactically_valid(index):
    """Documentation is the specification (verification-constitution §1).

    Compilation only — several blocks fetch from SEC and belong in the network
    lane. What it does catch is the failure this file cares about: an example
    naming a class, keyword or method that no longer exists.
    """
    block = _python_blocks(GUIDE.read_text())[index]
    compile(block, f"{GUIDE.name}#block{index}", "exec")


def test_the_guides_import_lines_all_resolve():
    """The half of the examples that can be checked offline, checked."""
    for block in _python_blocks(GUIDE.read_text()):
        for line in block.splitlines():
            if line.startswith(("from edgar", "import edgar")):
                exec(line, {})  # noqa: S102 - our own documentation, not user input


def test_the_guide_is_wired_into_the_docs_nav():
    """A guide nothing links to is a guide nobody reads."""
    mkdocs = (Path(__file__).parents[3] / "mkdocs.yml").read_text()
    assert "guides/error-handling.md" in mkdocs


def test_strict_flag_helper_is_importable_as_the_guide_says():
    assert strict_errors_enabled() in (True, False)


def test_edgar_error_is_the_outer_net_the_guide_promises():
    """The guide tells people `except EdgarError` catches anything we raise."""
    import edgar.exceptions as ex

    for name in ex.__all__:
        obj = getattr(ex, name)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            assert issubclass(obj, EdgarError), f"{name} escapes `except EdgarError`"
