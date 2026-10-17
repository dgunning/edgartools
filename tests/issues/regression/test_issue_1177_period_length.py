"""Regression test for issue #1177.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1177
Bead: edgartools-07lk.10, edgartools-07lk.22.1

`EntityFacts.income_statement()` and `.cash_flow_statement()` accepted a
`period_length` argument and documented it as "3=quarterly, 12=annual", but
never read it, so a caller asking for quarterly data with `period_length=3`
silently received the annual statement.

5.x honoured it and deprecated it in favour of `period=`.  6.0 removes it: the
silent-failure class is closed by the parameter not existing, so passing it
raises TypeError.  `period='quarterly'` is what quarterly callers use.
"""

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.exceptions import ValidationError


def resolve(period, annual):
    return EntityFacts._resolve_period(period, annual)


# --- period_length is gone ---------------------------------------------------

@pytest.mark.parametrize("method_name", ["income_statement", "cash_flow_statement", "cash_flow"])
@pytest.mark.parametrize("length", [3, 12])
def test_period_length_is_rejected_as_an_unexpected_keyword(method_name, length):
    facts = EntityFacts.__new__(EntityFacts)
    with pytest.raises(TypeError, match="period_length"):
        getattr(facts, method_name)(period_length=length)


# --- period resolution -------------------------------------------------------

def test_period_defaults_to_annual():
    assert resolve(None, None) == "annual"


def test_annual_flag_still_overrides_period():
    assert resolve("quarterly", True) == "annual"
    assert resolve("annual", False) == "quarterly"


def test_invalid_period_still_raises_a_valueerror():
    """ValidationError IS-A ValueError, so existing handlers keep working."""
    with pytest.raises(ValueError, match="period must be one of"):
        resolve("monthly", None)


def test_period_is_case_insensitive():
    assert resolve("QUARTERLY", None) == "quarterly"


# --- the public methods route period='quarterly' to the quarterly builder ----

@pytest.mark.parametrize("method_name", ["income_statement", "cash_flow_statement"])
@pytest.mark.parametrize("period,expected_annual", [("quarterly", False), ("annual", True)])
def test_period_reaches_the_statement_builder(monkeypatch, method_name, period, expected_annual):
    seen = {}

    def fake_build(self, facts, statement_type, periods, annual, as_dataframe, concise_format):
        seen["annual"] = annual
        return "statement"

    monkeypatch.setattr(EntityFacts, "_build_enhanced_statement", fake_build)
    monkeypatch.setattr(EntityFacts, "_ttm_ready_facts", property(lambda self: self), raising=False)

    facts = EntityFacts.__new__(EntityFacts)
    facts._facts = []

    getattr(EntityFacts, method_name)(facts, period=period)

    assert seen["annual"] is expected_annual


def test_statement_methods_reject_an_invalid_period():
    facts = EntityFacts.__new__(EntityFacts)
    for method in (EntityFacts.income_statement, EntityFacts.cash_flow_statement):
        with pytest.raises(ValidationError):
            method(facts, period="monthly")
