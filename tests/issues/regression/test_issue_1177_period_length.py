"""Regression test for issue #1177.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1177
Bead: edgartools-07lk.10

`EntityFacts.income_statement()` and `.cash_flow_statement()` accepted a
`period_length` argument and documented it as "3=quarterly, 12=annual", but
never read it — it appeared nowhere in either method body.  A caller asking for
quarterly data with `period_length=3` silently received the annual statement.

This is the silent-failure class 6.0 closes (bead edgartools-07lk.10, GH #933):
the parameter is now honoured, and deprecated in favour of `period=`.
"""

import warnings

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.exceptions import ValidationError

def resolve(period, annual, period_length):
    """Call the resolver at test time, not import time, so this module still
    collects against a build that lacks it."""
    return EntityFacts._resolve_period(period, annual, period_length)


# --- the bug: period_length was ignored ------------------------------------

def test_period_length_3_selects_quarterly():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert resolve(None, None, 3) == "quarterly"


def test_period_length_12_selects_annual():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert resolve(None, None, 12) == "annual"


# --- deprecation ------------------------------------------------------------

def test_period_length_warns_and_names_its_replacement():
    with pytest.warns(DeprecationWarning, match=r"period='quarterly'"):
        resolve(None, None, 3)


def test_no_warning_when_period_length_is_unused():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert resolve(None, None, None) == "annual"
        assert resolve("quarterly", None, None) == "quarterly"


# --- contradictions raise rather than silently picking one ------------------

@pytest.mark.parametrize("period,length", [("annual", 3), ("quarterly", 12), ("ttm", 3), ("ttm", 12)])
def test_contradicting_period_and_period_length_raises(period, length):
    with pytest.raises(ValidationError) as exc:
        resolve(period, None, length)
    assert exc.value.parameter == "period_length"


def test_contradicting_annual_and_period_length_raises():
    with pytest.raises(ValidationError):
        resolve(None, True, 3)      # annual=True vs period_length=3
    with pytest.raises(ValidationError):
        resolve(None, False, 12)    # annual=False vs period_length=12


def test_agreeing_period_and_period_length_is_accepted():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert resolve("quarterly", None, 3) == "quarterly"
        assert resolve(None, True, 12) == "annual"


@pytest.mark.parametrize("length", [0, 1, 6, 9, 24, -3])
def test_unsupported_period_length_raises(length):
    with pytest.raises(ValidationError) as exc:
        resolve(None, None, length)
    assert exc.value.invalid_value == length


# --- existing behaviour is preserved ----------------------------------------

def test_period_defaults_to_annual():
    assert resolve(None, None, None) == "annual"


def test_annual_flag_still_overrides_period():
    assert resolve("quarterly", True, None) == "annual"
    assert resolve("annual", False, None) == "quarterly"


def test_invalid_period_still_raises_a_valueerror():
    """ValidationError IS-A ValueError, so existing handlers keep working."""
    with pytest.raises(ValueError, match="period must be one of"):
        resolve("monthly", None, None)


def test_period_is_case_insensitive():
    assert resolve("QUARTERLY", None, None) == "quarterly"


# --- the public methods actually route through the resolver -----------------

@pytest.mark.parametrize("method_name", ["income_statement", "cash_flow_statement"])
@pytest.mark.parametrize("period_length,expected_annual", [(3, False), (12, True)])
def test_period_length_reaches_the_statement_builder(monkeypatch, method_name, period_length, expected_annual):
    """The original defect: period_length never reached the builder at all.

    Before the fix both values produced annual=True, so period_length=3
    silently returned the annual statement.
    """
    seen = {}

    def fake_build(self, facts, statement_type, periods, annual, as_dataframe, concise_format):
        seen["annual"] = annual
        return "statement"

    monkeypatch.setattr(EntityFacts, "_build_enhanced_statement", fake_build)
    monkeypatch.setattr(EntityFacts, "_ttm_ready_facts", property(lambda self: self), raising=False)

    facts = EntityFacts.__new__(EntityFacts)
    facts._facts = []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        getattr(EntityFacts, method_name)(facts, period_length=period_length)

    assert seen["annual"] is expected_annual


def test_statement_methods_reject_a_contradiction(monkeypatch):
    facts = EntityFacts.__new__(EntityFacts)
    for method in (EntityFacts.income_statement, EntityFacts.cash_flow_statement):
        with pytest.raises(ValidationError):
            method(facts, period="annual", period_length=3)
