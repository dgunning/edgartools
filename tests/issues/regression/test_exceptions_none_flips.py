"""The silent-`None` returns that become exceptions in 6.0.

Bead: edgartools-07lk.10, PR3 of 3. Design §4.

Calls that answered `None` for something that was really a failure, so the
caller could not tell "there is no such thing" from "we could not tell you".
In 5.x each warned and named what it would raise; since 6.0 each raises.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. **`.get()` never raises.** It is the migration target we point people at,
     and it reaches the miss through the same `__getitem__` that raises. If the
     suppression regresses, everyone who took our advice gets the exception.
  2. **The error says what to do.** A miss that does not list what the filing
     does have sends the reader back to the filing. These assert message CONTENT.
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
from edgar.company_reports import TenK, TenQ
from edgar.company_reports._base import CompanyReport
from edgar.exceptions import (
    DataObjectError,
    EdgarError,
    SectionNotFoundError,
    ValidationError,
)

GUIDE = Path(__file__).parents[3] / "docs" / "guides" / "error-handling.md"


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


# ---------------------------------------------------------------------------
# find() — a malformed accession number
# ---------------------------------------------------------------------------

def test_find_raises_a_validation_error():
    edgar.find.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        edgar.find("123456-99")
    exc = excinfo.value
    assert exc.parameter == "search_id"
    assert exc.invalid_value == "123456-99"
    assert any("0000320193-23-000106" in s for s in exc.suggestions), (
        "a format complaint that does not show the format is half a message"
    )


def test_the_validation_error_is_still_a_value_error():
    """The reason this conversion is additive rather than a break."""
    edgar.find.cache_clear()
    with pytest.raises(ValueError):
        edgar.find("123456-99")
    edgar.find.cache_clear()


# ---------------------------------------------------------------------------
# report[item] — a section that is not there
# ---------------------------------------------------------------------------

def test_getitem_raises():
    report = _Report()
    with pytest.raises(SectionNotFoundError, match="has no 'Item 99'"):
        report["Item 99"]


def test_the_miss_message_lists_what_the_filing_does_have():
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


def test_section_not_found_is_still_a_keyerror():
    """`except KeyError:` around item access keeps working after the flip."""
    report = _Report()
    with pytest.raises(KeyError):
        report["Item 99"]


def test_a_miss_message_survives_a_report_that_cannot_list_its_items():
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

def test_get_never_raises():
    """THE test in this file.

    `.get()` is what we tell people to move to, and it reaches the miss through
    the same `__getitem__` that raises. If the suppression regresses, every user
    who took our advice gets the exception for taking it.
    """
    report = _Report()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert report.get("Item 99") is None
        assert report.get("Item 99", "") == ""
        assert report.get("Item 99", default="fallback") == "fallback"


def test_get_suppression_does_not_leak_past_the_call():
    """The context flag has to be reset, or one `.get()` silences the process."""
    report = _Report()
    report.get("Item 99")
    with pytest.raises(SectionNotFoundError):
        report["Item 99"]


def test_get_suppression_is_reset_even_when_the_lookup_raises():
    class _Exploding(_Report):
        def __getitem__(self, item):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _Exploding().get("Item 1")

    with pytest.raises(SectionNotFoundError):
        _Report()["Item 99"]


def test_get_exists_on_every_report_class():
    """Shipped on the base, so no report class raises without offering it."""
    for cls in (CompanyReport, TenK, TenQ):
        assert callable(getattr(cls, "get", None)), f"{cls.__name__} has no .get()"


def test_get_returns_the_value_when_the_item_is_present():
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


def test_obj_raises_when_a_modelled_form_has_no_data():
    with pytest.raises(DataObjectError) as excinfo:
        edgar.obj(_OwnershipFiling())
    exc = excinfo.value
    assert exc.form == "4"
    assert exc.accession_no == "0000320193-99-000001"
    assert "no XML document" in str(exc)


def test_obj_still_returns_none_for_a_form_we_do_not_model():
    """The legitimate None, and it must survive the flip.

    This is the distinction the whole change exists for. A flip that made every
    None into a raise would pass every "does it raise?" test and destroy the
    thing being protected.
    """
    class _Unmodelled:
        # Was "SC 14D9" until that form got a data object (Schedule14D9, GH
        # #922). Any form here must be one `obj()` genuinely does not route:
        # once it is modelled, `obj()` builds the object and this test fails
        # on whatever that constructor touches, not on the None it is about.
        # "SC 14D1" is the withdrawn tender-offer form, adjacent in subject and
        # unlikely to be modelled.
        form = "SC 14D1"
        accession_no = "0000320193-23-000999"

        def xbrl(self):
            return None

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


def test_edgar_error_is_the_outer_net_the_guide_promises():
    """The guide tells people `except EdgarError` catches anything we raise."""
    import edgar.exceptions as ex

    for name in ex.__all__:
        obj = getattr(ex, name)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            assert issubclass(obj, EdgarError), f"{name} escapes `except EdgarError`"
