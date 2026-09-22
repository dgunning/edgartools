"""Regression tests for issues #1172 and #1175.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1172
GitHub Issue: https://github.com/dgunning/edgartools/issues/1175

#1172 — `XBRLS.query()` stored its option under the keyword `standardize` while
`StitchedFactQuery` read `standard`, so `standardize=False` was silently dropped
and standardization stayed on.

#1175 — `FactQuery.transform()` / `.scale()` wrote transformed values straight
back into the fact dictionaries returned by `get_facts()`.  Those dictionaries
come from the facts view's shared cache, so a transform mutated the cache and
compounded on every later query.
"""

from types import MethodType

from edgar.xbrl import XBRLS
from edgar.xbrl.facts import FactQuery
from edgar.xbrl.stitching.query import StitchedFactQuery, StitchedFactsView

PERIOD = "duration_2025-01-01_2025-12-31"


def _stub_statement(standard: bool):
    return {
        "periods": [(PERIOD, "2025")],
        "statement_data": [
            {
                "concept": "example_Sales",
                "label": "Company-specific sales",
                "original_label": "Company-specific sales",
                "standard_concept": "Revenue" if standard else None,
                "values": {PERIOD: 100},
            }
        ],
    }


# --- #1172 ------------------------------------------------------------------

def test_standardize_false_reaches_get_statement():
    received = []
    xbrls = XBRLS([])

    def fake_get_statement(self, statement_type, max_periods=8, standard=True, **kwargs):
        received.append(standard)
        return _stub_statement(standard)

    xbrls.get_statement = MethodType(fake_get_statement, xbrls)

    result = xbrls.query(standardize=False, statement_types=["IncomeStatement"]).execute()

    assert received == [False]
    assert result[0]["standard_concept"] is None


def test_standardize_defaults_to_true():
    received = []
    xbrls = XBRLS([])

    def fake_get_statement(self, statement_type, max_periods=8, standard=True, **kwargs):
        received.append(standard)
        return _stub_statement(standard)

    xbrls.get_statement = MethodType(fake_get_statement, xbrls)

    result = xbrls.query(statement_types=["IncomeStatement"]).execute()

    assert received == [True]
    assert result[0]["standard_concept"] == "Revenue"


def test_the_base_standard_keyword_still_works():
    """StitchedFactQuery is also constructed directly with `standard`."""
    view = StitchedFactsView(XBRLS([]))
    assert StitchedFactQuery(view, standard=False)._standard is False
    assert StitchedFactQuery(view, standardize=False)._standard is False
    assert StitchedFactQuery(view)._standard is True


# --- #1175 ------------------------------------------------------------------

class _CachingFactsView:
    """A facts view that hands back the same row objects on every call."""

    def __init__(self):
        self.cache = [{"concept": "us-gaap_Revenues", "value": 1000, "label": "Revenues"}]

    def get_facts(self, **kwargs):
        return self.cache


def test_scale_does_not_mutate_the_shared_fact_cache():
    view = _CachingFactsView()

    first = FactQuery(view).scale(1000).execute()
    assert first[0]["value"] == 1.0

    # The cached row must be untouched, so a second identical query agrees.
    assert view.cache[0]["value"] == 1000
    second = FactQuery(view).scale(1000).execute()
    assert second[0]["value"] == 1.0

    # And an untransformed query still sees the original value.
    assert FactQuery(view).execute()[0]["value"] == 1000


def test_stitched_scale_does_not_mutate_the_shared_fact_cache():
    view = _CachingFactsView()

    first = StitchedFactQuery(view).scale(1000).execute()
    assert first[0]["value"] == 1.0

    assert view.cache[0]["value"] == 1000
    second = StitchedFactQuery(view).scale(1000).execute()
    assert second[0]["value"] == 1.0


def test_chained_transforms_still_compose_in_order():
    view = _CachingFactsView()

    result = FactQuery(view).transform(lambda v: v + 1).transform(lambda v: v * 2).execute()

    assert result[0]["value"] == 2002
    assert view.cache[0]["value"] == 1000
