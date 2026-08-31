"""Moved modules keep their old import path working until 6.0.

Bead: edgartools-07lk.12.1

`edgar.effect` -> `edgar.offerings.effect` and `edgar.form144` ->
`edgar.ownership.form144`. Neither name is in `edgar.__all__` and neither had a
top-level re-export, so the MODULE PATH was their entire public surface: moving
without a shim is a break, not a staged deprecation (bead edgartools-07lk.23).

The two properties that matter, and neither is obvious from reading the shim:

  IDENTITY. `edgar.form144.Form144 is edgar.ownership.form144.Form144`. A shim
  that re-exported copies would pass a naive import test and then fail every
  isinstance check written against the other path.

  SILENCE INTERNALLY. `filing.obj()` routes 144/EFFECT filings through these
  parsers. If dispatch imported the shim, every ordinary obj() call would warn
  at a user who did nothing wrong — the deprecation would be noise instead of
  signal, and the usual response to that is to delete the warning.
"""

import importlib
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
def test_the_old_path_still_resolves_to_the_same_object(old, new, symbol):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        shim = importlib.import_module(old)
        assert getattr(shim, symbol) is getattr(importlib.import_module(new), symbol)


@pytest.mark.parametrize("old,new,symbol", MOVES)
def test_the_old_path_warns_and_names_its_replacement(old, new, symbol):
    shim = importlib.import_module(old)
    with pytest.warns(DeprecationWarning, match=new.replace(".", r"\.")):
        getattr(shim, symbol)


@pytest.mark.parametrize("old,new,symbol", MOVES)
def test_an_unknown_attribute_still_raises(old, new, symbol):
    shim = importlib.import_module(old)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(AttributeError):
            shim.no_such_attribute_anywhere


def test_form144_forwards_symbols_beyond_the_headline_class():
    """tests/test_form144.py imports these off the old path."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from edgar.form144 import SecuritiesInformationHolder, SecuritiesToBeSoldHolder
    assert SecuritiesInformationHolder.__module__ == "edgar.ownership.form144"
    assert SecuritiesToBeSoldHolder.__module__ == "edgar.ownership.form144"


def test_obj_dispatch_does_not_route_through_the_shims():
    """The deprecation must reach external callers only.

    Read structurally rather than by calling obj(): a filing would need network
    or a fixture, and the thing under test is which module the dispatch names.
    """
    source = (importlib.import_module("edgar").__file__)
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    assert "from edgar.offerings.effect import Effect" in text
    assert "from edgar.ownership.form144 import Form144" in text
    assert "from edgar.effect import Effect" not in text
    assert "from edgar.form144 import Form144" not in text


def test_importing_edgar_emits_no_move_warning():
    """A deprecation that fires on `import edgar` trains users to filter it out."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(importlib.import_module("edgar"))
    assert not [w for w in caught if "has moved" in str(w.message)]
