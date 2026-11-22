"""
Company statement methods raise for invalid arguments instead of returning None.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1732

``Company.income_statement()``, ``balance_sheet()`` and ``cash_flow_statement()``
wrapped the call to ``EntityFacts`` in ``except Exception`` and returned None,
so ``period="quarter"`` (a typo of ``"quarterly"``) answered None, the value
6.0 reserves for a defined absence. They now validate the period first, the
same way ``EntityFacts`` does, and let errors from ``EntityFacts`` propagate.
None still means SEC has no company facts for the company.

The company is Snowflake Inc. (SNOW, CIK 1640147), the issue's example. The
facts are stubbed so these run offline; the assertions are on our own
validation and propagation, which need no SEC data.
"""
import pytest

from edgar import Company
from edgar.entity.entity_facts import EntityFacts
from edgar.exceptions import ValidationError

SNOWFLAKE_CIK = 1640147


class _ExplodingFacts:
    """Stands in for EntityFacts whose statement builder fails."""

    def __bool__(self):
        return True

    def income_statement(self, **kwargs):
        raise RuntimeError("builder failed: income")

    def balance_sheet(self, **kwargs):
        raise RuntimeError("builder failed: balance")

    def cash_flow_statement(self, **kwargs):
        raise RuntimeError("builder failed: cash flow")


def _company(facts):
    company = Company(SNOWFLAKE_CIK)
    company.__dict__["facts"] = facts  # prime the cached_property
    return company


@pytest.mark.fast
@pytest.mark.parametrize("method, message", [
    ("income_statement", "period must be one of: 'annual', 'quarterly', 'ttm'"),
    ("cash_flow_statement", "period must be one of: 'annual', 'quarterly', 'ttm'"),
    ("balance_sheet", "period must be one of: 'annual', 'quarterly'"),
])
@pytest.mark.parametrize("facts", [None, _ExplodingFacts()], ids=["no-facts", "facts"])
def test_invalid_period_raises_validation_error(method, message, facts):
    with pytest.raises(ValidationError, match=message) as excinfo:
        getattr(_company(facts), method)(period="quarter")
    assert excinfo.value.parameter == "period"
    assert excinfo.value.invalid_value == "quarter"


@pytest.mark.fast
def test_balance_sheet_ttm_is_a_validation_error_on_both_surfaces():
    with pytest.raises(ValidationError, match="TTM not applicable for Balance Sheet"):
        _company(None).balance_sheet(period="ttm")
    with pytest.raises(ValidationError, match="period must be one of: 'annual', 'quarterly'"):
        EntityFacts._resolve_balance_sheet_period("quarter", None)
    # still catchable the 5.x way
    with pytest.raises(ValueError):
        EntityFacts._resolve_balance_sheet_period("ttm", None)


@pytest.mark.fast
@pytest.mark.parametrize("method", ["income_statement", "balance_sheet", "cash_flow_statement"])
def test_builder_errors_propagate(method):
    with pytest.raises(RuntimeError, match="builder failed"):
        getattr(_company(_ExplodingFacts()), method)(period="annual")


@pytest.mark.fast
@pytest.mark.parametrize("method", ["income_statement", "balance_sheet", "cash_flow_statement"])
def test_no_company_facts_is_still_none(method):
    assert getattr(_company(None), method)(period="quarterly") is None
    # the legacy `annual` flag overrides `period`, as before
    assert getattr(_company(None), method)(period="quarter", annual=False) is None
