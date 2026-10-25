"""Explicit FactsView clears invalidate DataFrames on queries bound to that view.

The real GBDC acceptance case remains in
tests/issues/reproductions/xbrl-parsing/test_factquery_cache_invalidation.py.
These small synthetic facts isolate cache ownership and configuration behavior.
"""

import gc
import weakref

import pytest

from edgar.xbrl import XBRL, XBRLS
from edgar.xbrl.facts import FactsView
from edgar.xbrl.models import Context, Fact
from edgar.xbrl.stitching.query import StitchedFactQuery, StitchedFactsView

pytestmark = pytest.mark.fast


def _xbrl(*amounts):
    xbrl = XBRL()
    xbrl.parser.units["usd"] = {"type": "simple", "measure": "iso4217:USD"}
    for index, amount in enumerate(amounts, start=1):
        context_id = f"c-{index}"
        xbrl.parser.contexts[context_id] = Context(
            context_id=context_id,
            period={"type": "instant", "instant": f"2025-01-{index:02d}"},
        )
        xbrl.parser.facts[f"f-{index}"] = Fact(
            element_id="example:Amount", context_ref=context_id, fact_id=f"f-{index}",
            value=str(amount), numeric_value=amount, unit_ref="usd",
        )
    return xbrl


def _set_amounts(xbrl, *amounts):
    for index, amount in enumerate(amounts, start=1):
        fact = xbrl.parser.facts[f"f-{index}"]
        fact.value = str(amount)
        fact.numeric_value = amount


@pytest.mark.parametrize("conversion", ["to_dataframe", "to_pandas"])
def test_clear_refreshes_multiple_retained_queries_and_preserves_returned_frames(conversion):
    xbrl = _xbrl(10, 20)
    view = xbrl.facts
    queries = [view.query(), view.query().limit(1)]
    old_frames = [getattr(query, conversion)() for query in queries]
    assert [frame.numeric_value.tolist() for frame in old_frames] == [[10, 20], [10]]

    _set_amounts(xbrl, 30, 40)
    view.clear_cache()
    refreshed = [getattr(query, conversion)() for query in queries]

    assert [frame.numeric_value.tolist() for frame in refreshed] == [[30, 40], [30]]
    assert [frame.numeric_value.tolist() for frame in old_frames] == [[10, 20], [10]]
    for query, old_frame, new_frame in zip(queries, old_frames, refreshed, strict=True):
        assert new_frame is not old_frame
        assert getattr(query, conversion)() is new_frame


def test_repeated_clears_without_data_changes_still_invalidate_query_frames():
    view = _xbrl(10).facts
    query = view.query()
    first = query.to_dataframe()
    assert query.to_dataframe() is first

    # Two clears before the next read must not cancel each other out.
    view.clear_cache()
    view.clear_cache()
    second = query.to_dataframe()
    assert second is not first
    assert second.numeric_value.tolist() == [10]

    view.clear_cache()
    third = query.to_dataframe()
    assert third is not second
    assert third.numeric_value.tolist() == [10]
    assert query.to_dataframe() is third


def test_old_projection_limit_and_sort_configurations_cannot_resurrect_old_frames():
    xbrl = _xbrl(10, 20, 30)
    view = xbrl.facts
    query = view.query()
    columns_a = ("fact_id", "numeric_value")
    columns_b = ("numeric_value",)
    columns_c = ("numeric_value", "fact_id")
    first = query.limit(1).sort_by("numeric_value").to_dataframe(*columns_a)
    assert first.fact_id.tolist() == ["f-1"]
    assert query.limit(2).sort_by("numeric_value", ascending=False).to_dataframe(
        *columns_b).numeric_value.tolist() == [30, 20]
    assert query.limit(3).sort_by("fact_id").to_dataframe(
        *columns_c).numeric_value.tolist() == [10, 20, 30]

    _set_amounts(xbrl, 40, 30, 50)
    view.clear_cache()

    refreshed = query.limit(1).sort_by("numeric_value").to_dataframe(*columns_a)
    assert refreshed.fact_id.tolist() == ["f-2"]
    assert refreshed.numeric_value.tolist() == [30]
    assert query.limit(2).sort_by("numeric_value", ascending=False).to_dataframe(
        *columns_b).numeric_value.tolist() == [50, 40]
    assert query.limit(3).sort_by("fact_id").to_dataframe(
        *columns_c).numeric_value.tolist() == [40, 30, 50]
    assert query.limit(1).sort_by("numeric_value").to_dataframe(*columns_a) is refreshed
    assert first.numeric_value.tolist() == [10]


def test_next_conversion_releases_all_obsolete_projection_frames():
    view = _xbrl(10, 20).facts
    query = view.query()
    obsolete = [
        weakref.ref(query.to_dataframe("numeric_value")),
        weakref.ref(query.to_dataframe("fact_id")),
    ]
    assert all(reference() is not None for reference in obsolete)

    view.clear_cache()
    current = query.to_dataframe("fact_id", "numeric_value")
    gc.collect()

    assert current.numeric_value.tolist() == [10, 20]
    assert all(reference() is None for reference in obsolete)


def test_view_clear_still_refreshes_its_own_dataframe():
    xbrl = _xbrl(10, 20)
    view = xbrl.facts
    first = view.to_dataframe()
    assert view.to_pandas() is first

    _set_amounts(xbrl, 30, 40)
    view.clear_cache()
    current = view.to_pandas()

    assert current is not first
    assert current.numeric_value.tolist() == [30, 40]
    assert first.numeric_value.tolist() == [10, 20]
    assert view.to_dataframe() is current


def test_clearing_one_view_does_not_invalidate_a_distinct_owner():
    xbrl = _xbrl(10)
    first_view = xbrl.facts
    second_view = FactsView(xbrl)
    first_query = first_view.query()
    second_query = second_view.query()
    first_query.to_dataframe()
    second_frame = second_query.to_dataframe()

    _set_amounts(xbrl, 20)
    first_view.clear_cache()

    assert first_query.to_dataframe().numeric_value.tolist() == [20]
    assert second_query.to_dataframe() is second_frame
    assert second_query.execute()[0]["numeric_value"] == 10
    second_view.clear_cache()
    assert second_query.to_dataframe().numeric_value.tolist() == [20]


def test_cached_frames_keep_existing_shared_return_behavior_until_clear():
    view = _xbrl(10).facts
    query = view.query()
    frame = query.to_dataframe("numeric_value")
    frame.loc[0, "numeric_value"] = 999

    assert query.to_pandas("numeric_value") is frame
    assert query.to_dataframe("numeric_value").numeric_value.tolist() == [999]
    assert query.execute()[0]["numeric_value"] == 10

    view.clear_cache()
    assert query.to_dataframe("numeric_value").numeric_value.tolist() == [10]
    assert frame.numeric_value.tolist() == [999]


def test_generationless_stitched_owner_keeps_manual_init_conversion_and_cache_behavior(monkeypatch):
    period = "duration_2025-01-01_2025-12-31"
    statement = {
        "periods": [(period, "2025")],
        "statement_data": [
            {"concept": "example_Amount", "label": "Amount", "values": {period: 10}},
            {"concept": "example_Other", "label": "Other", "values": {period: 20}},
        ],
    }
    xbrls = XBRLS([])
    monkeypatch.setattr(xbrls, "get_statement", lambda **kwargs: statement)
    view = StitchedFactsView(xbrls)
    query = StitchedFactQuery(view, statement_types=["IncomeStatement"])
    assert not hasattr(view, "_cache_generation")
    full = query.to_dataframe()
    assert full.numeric_value.tolist() == [10, 20]
    assert full.value.tolist() == ["10", "20"]

    columns = ("concept", "numeric_value")
    projected = query.to_dataframe(*columns)
    assert list(projected.columns) == list(columns)
    assert projected.concept.tolist() == ["example_Amount", "example_Other"]
    assert query.to_pandas(*columns) is projected
    assert query.to_dataframe() is full
    projected.loc[0, "numeric_value"] = 999
    assert query.to_dataframe(*columns).numeric_value.tolist() == [999, 20]
    assert query.execute()[0]["numeric_value"] == 10

    limited = query.limit(1).to_dataframe(*columns)
    assert limited.numeric_value.tolist() == [10]
    assert query.to_pandas(*columns) is limited
    with pytest.raises(KeyError, match="does not emit"):
        query.to_dataframe("unknown_column")
