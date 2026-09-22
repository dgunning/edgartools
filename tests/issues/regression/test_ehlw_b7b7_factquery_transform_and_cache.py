"""Two adjacent defects in the fluent fact query: a transform that never fired, and a
DataFrame cache that answered for a query it no longer described.

beads edgartools-ehlw (GH #1187) and edgartools-b7b7 (GH #1186). One PR, because they
live in the same file, in the block the GH #1175 fix had already touched without
noticing either.

Ground truth here is synthetic rather than a filing, deliberately: both defects are
properties of FactQuery's own bookkeeping, not of any filer's data, and a fact ledger
written out in full is what makes the arithmetic checkable by eye. The shapes are taken
from a real AAPL 10-K, where `value` is a `str` on all 1,131 facts and `numeric_value`
is a float on 976 and None on the other 155 -- so `numeric_value is None` is the exact
test for "this fact is not numeric".
"""

import pandas as pd
import pytest

from edgar.xbrl.facts import FactQuery
from edgar.xbrl.stitching.query import StitchedFactQuery

# AAPL FY2025 net income, as filed: the string in `value`, the float in `numeric_value`.
NET_INCOME = 112_010_000_000


def _fact(concept, value, numeric_value, period_type="duration", **extra):
    fact = {
        "concept": concept,
        "value": value,
        "numeric_value": numeric_value,
        "period_type": period_type,
        "decimals": "-6",
        "period_key": f"{period_type}_2024-09-29_2025-09-27",
        "fiscal_year": 2025,
        "fiscal_period": "FY",
    }
    fact.update(extra)
    return fact


def _ledger():
    """Two numeric facts and one text fact -- the three cases the transform must tell apart."""
    return [
        _fact("us-gaap:NetIncomeLoss", str(NET_INCOME), float(NET_INCOME)),
        _fact("us-gaap:Assets", "352583000000", 352583000000.0, period_type="instant"),
        # A TextBlock: `value` is prose and `numeric_value` is None.
        _fact("us-gaap:SegmentReportingDisclosureTextBlock",
              "The following tables show net sales", None),
    ]


class _FakeFactsView:
    """Stands in for FactsView. Hands back the SAME row objects every call, which is what
    makes the shared-cache property (GH #1175) testable: if a transform writes in place,
    the second query sees the first one's arithmetic."""

    def __init__(self, facts):
        self._facts = facts
        self.call_count = 0

    def get_facts(self, *args, **kwargs):
        self.call_count += 1
        return self._facts


class _FakeStitchedFactsView(_FakeFactsView):
    """StitchedFactsView.get_facts() takes the stitching kwargs; the rows are the same shape."""

    def get_facts(self, max_periods=None, standard=None, statement_types=None):
        self.call_count += 1
        return self._facts


# --------------------------------------------------------------------------- #
# GH #1187 -- scale() was a silent no-op on every parsed fact
# --------------------------------------------------------------------------- #

def test_scale_actually_scales_the_numeric_value():
    """The defect: `value` holds the filed STRING, so scale()'s own
    `isinstance(value, (int, float, Decimal))` guard rejected it and returned it
    unchanged -- and `numeric_value`, which every consumer reads, was never
    transformed on any path. scale(1000), the example in its own docstring, did
    nothing at all."""
    view = _FakeFactsView(_ledger())
    row = FactQuery(view).by_concept("us-gaap:NetIncomeLoss").scale(1000).execute()[0]

    assert row["numeric_value"] == NET_INCOME / 1000 == 112_010_000.0, (
        f"scale(1000) left numeric_value at {row['numeric_value']}")


def test_value_and_numeric_value_cannot_disagree_after_a_transform():
    """`numeric_value` is authoritative and `value` is its string rendering. Writing one
    without the other is how a row comes to report two different numbers for one fact."""
    view = _FakeFactsView(_ledger())
    row = FactQuery(view).by_concept("us-gaap:NetIncomeLoss").scale(1000).execute()[0]

    assert float(row["value"]) == row["numeric_value"]
    assert isinstance(row["value"], str), "value has always been a string; keep it one"


def test_scale_leaves_a_non_numeric_fact_alone():
    """A TextBlock has no numeric value to scale. It is left exactly as filed -- by
    scale()'s isinstance guard, which now does the job it was written for instead of
    swallowing every fact that reached it."""
    original = _ledger()[2]["value"]
    view = _FakeFactsView(_ledger())
    rows = FactQuery(view).scale(1000).execute()
    text_row = [r for r in rows if r["numeric_value"] is None][0]

    assert text_row["value"] == original


def test_a_text_transform_still_reaches_non_numeric_facts():
    """The control. transform() is a general-purpose hook, and routing numeric facts to
    `numeric_value` must not cost text facts the ability to be transformed at all --
    which is the obvious way to 'fix' #1187 while breaking every other caller."""
    view = _FakeFactsView(_ledger())
    rows = (FactQuery(view)
            .transform(lambda v: v.upper() if isinstance(v, str) else v)
            .execute())
    text_row = [r for r in rows if r["numeric_value"] is None][0]

    assert text_row["value"] == "THE FOLLOWING TABLES SHOW NET SALES"


def test_transforming_does_not_scale_the_shared_cache():
    """GH #1175's property, re-asserted here because #1187 rewrites the same block: the
    view hands back rows from its own cache, so a transform that writes in place scales
    the cache itself and the next identical query returns values divided twice."""
    facts = _ledger()
    view = _FakeFactsView(facts)

    FactQuery(view).by_concept("us-gaap:NetIncomeLoss").scale(1000).execute()
    again = FactQuery(view).by_concept("us-gaap:NetIncomeLoss").execute()[0]

    assert again["numeric_value"] == NET_INCOME, "the shared row was mutated in place"
    assert facts[0]["numeric_value"] == NET_INCOME


def test_chained_transforms_compose_in_order():
    view = _FakeFactsView(_ledger())
    row = (FactQuery(view)
           .by_concept("us-gaap:NetIncomeLoss")
           .scale(1000)
           .transform(lambda v: v + 1)
           .execute())[0]

    assert row["numeric_value"] == NET_INCOME / 1000 + 1


# --------------------------------------------------------------------------- #
# GH #1186 -- to_dataframe() served a stale table after the query was narrowed
# --------------------------------------------------------------------------- #

def test_narrowing_a_query_after_materializing_it_returns_the_narrowed_rows():
    """The defect: the cache key was the `columns` tuple alone, so the first
    to_dataframe() answered every later one. FactQuery is a documented fluent MUTABLE
    builder whose methods return self, so one object legitimately describes a different
    population after each call -- here execute() saw the narrowing and to_dataframe()
    did not, and the two contradicted each other with no warning."""
    view = _FakeFactsView(_ledger())

    fresh = len(FactQuery(view).by_concept("us-gaap:NetIncomeLoss").to_dataframe())

    query = FactQuery(view)
    assert len(query.to_dataframe()) == 3
    narrowed = query.by_concept("us-gaap:NetIncomeLoss").to_dataframe()

    assert len(narrowed) == fresh == 1, (
        f"got {len(narrowed)} rows from the narrowed query, {fresh} from the equivalent "
        "fresh one; the cache answered for a query this object no longer describes")
    assert len(query.execute()) == len(narrowed), "execute() and to_dataframe() disagree"


def test_changing_an_inclusion_flag_also_invalidates():
    """The flags change the COLUMNS rather than the rows, so a key that tracked only the
    filter chain would still serve the wrong table here."""
    view = _FakeFactsView([
        _fact("us-gaap:NetIncomeLoss", str(NET_INCOME), float(NET_INCOME),
              dim_Segment="Americas"),
    ])
    query = FactQuery(view)
    without = query.to_dataframe()
    with_dims = query.with_dimensions().to_dataframe()

    assert not any(c.startswith("dim_") for c in without.columns)
    assert any(c.startswith("dim_") for c in with_dims.columns), (
        "with_dimensions() did not invalidate the cached table")


def test_the_cache_still_caches():
    """The control, and the reason this is a key fix rather than a cache deletion: an
    unchanged query must still be served from the cache, or #1186 is 'fixed' by making
    every to_dataframe() re-execute."""
    view = _FakeFactsView(_ledger())
    query = FactQuery(view).by_concept("us-gaap:NetIncomeLoss")

    first = query.to_dataframe()
    calls_after_first = view.call_count
    second = query.to_dataframe()

    assert second is first, "identical query re-materialized instead of hitting the cache"
    assert view.call_count == calls_after_first, "the view was queried again"


def test_a_column_projection_is_still_part_of_the_key():
    """The original key was the projection alone. It is still IN the key -- widening it
    must not be served from the narrower table."""
    view = _FakeFactsView(_ledger())
    query = FactQuery(view)

    one_col = query.to_dataframe("concept")
    two_col = query.to_dataframe("concept", "value")

    assert list(one_col.columns) == ["concept"]
    assert list(two_col.columns) == ["concept", "value"]


# --------------------------------------------------------------------------- #
# The stitched sibling inherits both, because it used to duplicate both
# --------------------------------------------------------------------------- #

def test_stitched_query_scales_too():
    """StitchedFactQuery subclasses FactQuery and had its own copy of the transform loop
    and its own copy of the cache key. A fix landed in one place only would leave the
    stitched path quietly wrong -- which is how both defects reached two classes."""
    view = _FakeStitchedFactsView(_ledger())
    row = StitchedFactQuery(view).by_concept("us-gaap:NetIncomeLoss").scale(1000).execute()[0]

    assert row["numeric_value"] == NET_INCOME / 1000


def test_stitched_query_invalidates_its_dataframe_cache():
    view = _FakeStitchedFactsView(_ledger())
    query = StitchedFactQuery(view)

    assert len(query.to_dataframe()) == 3
    narrowed = query.by_concept("us-gaap:NetIncomeLoss").to_dataframe()

    assert len(narrowed) == 1


def test_stitched_cache_key_survives_the_missing_base_attribute():
    """StitchedFactQuery does not call super().__init__() -- it re-initialises the base
    attributes by hand and misses `_requested_dimension`. A cache key reading that
    attribute directly raises AttributeError on every stitched to_dataframe(), so the
    key reads it defensively. This pins that, because the missing attribute is easy to
    'tidy up' into a plain attribute access later."""
    view = _FakeStitchedFactsView(_ledger())
    query = StitchedFactQuery(view)

    assert not hasattr(query, "_requested_dimension"), (
        "if this now exists, the getattr in _df_cache_key can become a plain read "
        "-- but check every other subclass first")
    assert isinstance(query.to_dataframe(), pd.DataFrame)
