"""Moved modules: the old import paths are gone in 6.0.

Bead: edgartools-07lk.12.1 (the moves, shipped with shims in 5.55.0) and
edgartools-07lk.22.1 (the shims removed in 6.0).

`edgar.effect` -> `edgar.offerings.effect` and `edgar.form144` ->
`edgar.ownership.form144`. Through 5.x the old paths forwarded to the new
modules with a DeprecationWarning. 6.0 deletes them, as docs/upgrade/6.0.md
promised, so an old import fails at the import line instead of somewhere later.

What still matters: `filing.obj()` routes 144/EFFECT filings through the new
modules, so ordinary use never touched the old paths and is unaffected.
"""

import importlib
import sys
import warnings

import pytest

MOVES = [
    ("edgar.effect", "edgar.offerings.effect", "Effect"),
    ("edgar.form144", "edgar.ownership.form144", "Form144"),
]


@pytest.mark.parametrize("old,new,symbol", MOVES)
def test_the_new_location_is_the_real_module(old, new, symbol):
    module = importlib.import_module(new)
    assert getattr(module, symbol).__module__ == new


@pytest.mark.parametrize("old,new,symbol", MOVES)
def test_the_old_path_is_removed(old, new, symbol):
    sys.modules.pop(old, None)
    with pytest.raises(ModuleNotFoundError, match=old.replace(".", r"\.")):
        importlib.import_module(old)


def test_form144_symbols_beyond_the_headline_class_live_at_the_new_path():
    from edgar.ownership.form144 import SecuritiesInformationHolder, SecuritiesToBeSoldHolder
    assert SecuritiesInformationHolder.__module__ == "edgar.ownership.form144"
    assert SecuritiesToBeSoldHolder.__module__ == "edgar.ownership.form144"


def test_form144_is_still_exported_at_the_top_level():
    import edgar
    from edgar.ownership.form144 import Form144
    assert edgar.Form144 is Form144


def test_obj_dispatch_names_the_new_modules():
    """Read structurally rather than by calling obj(): a filing would need network
    or a fixture, and the thing under test is which module the dispatch names."""
    source = (importlib.import_module("edgar").__file__)
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    assert "from edgar.offerings.effect import Effect" in text
    assert "from edgar.ownership.form144 import Form144" in text
    assert "from edgar.effect import Effect" not in text
    assert "from edgar.form144 import Form144" not in text


# ---------------------------------------------------------------------------
# edgar.muniadvisors — module became a package of the SAME name
# ---------------------------------------------------------------------------
#
# No shim and no deprecation: the dotted path is unchanged, so this is invisible
# to callers. What can break is subtler — `__all__` names only
# MunicipalAdvisorForm while the module carried 19 public top-level names that
# attribute access could reach. A package __init__ that re-exported `__all__`
# alone would drop the other 18 and look entirely correct doing it.

MUNI_PUBLIC_NAMES = [
    "Filer", "Contact", "Employer", "Office", "MunicipalAdvisorOffice",
    "CriminalDisclosure", "RegulatoryDisclosure", "CivilDisclosure",
    "ComplaintDisclosure", "TerminationDisclosure", "FinancialDisclosure",
    "JudgementLienDisclosure", "InvestigationDisclosure", "employment_date",
    "EmploymentHistory", "Applicant", "Disclosures", "Signature",
    "MunicipalAdvisorForm",
]


def test_muniadvisors_is_now_a_package():
    import edgar.muniadvisors as muni
    assert muni.__file__.endswith("muniadvisors/__init__.py")
    assert muni.MunicipalAdvisorForm.__module__ == "edgar.muniadvisors.core"


def test_the_import_path_is_unchanged_and_does_not_warn():
    """A same-name package conversion is invisible; a warning here is a bug."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(importlib.import_module("edgar.muniadvisors"))
    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]


@pytest.mark.parametrize("name", MUNI_PUBLIC_NAMES)
def test_every_public_name_survived_the_package_conversion(name):
    import edgar.muniadvisors as muni
    from edgar.muniadvisors import core
    assert getattr(muni, name) is getattr(core, name)


def test_star_import_surface_is_unchanged():
    import edgar.muniadvisors as muni
    assert muni.__all__ == ["MunicipalAdvisorForm"]


def test_unknown_attribute_still_raises():
    import edgar.muniadvisors as muni
    with pytest.raises(AttributeError):
        muni.no_such_attribute_anywhere
