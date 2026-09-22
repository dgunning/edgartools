"""FactQuery.to_dataframe(*columns) must not materialise the full fact width first.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1181
Bead: edgartools-31wd

Asking for two columns used to cost the same as asking for all 103: the frame was
built at full width and the caller's projection applied only at the end, so a
two-column call on the JPM fixture allocated 7.6 MiB and took as long as a
full export. The docs recommend column selection as a performance tip, so the
saving has to be real.

These tests guard the two halves of that change: the projected frame is exactly
what the full-width path produced, and the frame really is built narrow.
"""
import itertools
import tracemalloc
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.facts import _DEDUP_OPTIONAL, _DEDUP_REQUIRED, FactQuery

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "xbrl" / "jpm" / "10k_2024"


@pytest.fixture(scope="module")
def jpm():
    # A committed fixture: its absence is a broken checkout, not a reason to skip.
    assert FIXTURE.is_dir(), f"missing committed fixture: {FIXTURE}"
    return XBRL.from_directory(FIXTURE)


def _full_width(self, columns, results):
    """Stand-in for the pre-fix behaviour: always build every column."""
    return None


def _frame(xbrl, flags, columns, *, projected):
    include_dimensions, include_contexts, include_element_info = flags
    query = xbrl.facts.query()
    query._include_dimensions = include_dimensions
    query._include_contexts = include_contexts
    query._include_element_info = include_element_info
    query._df_cache = {}
    if projected:
        return query.to_dataframe(*columns)
    original = FactQuery._projection_source_columns
    FactQuery._projection_source_columns = _full_width
    try:
        return query.to_dataframe(*columns)
    finally:
        FactQuery._projection_source_columns = original


COLUMN_SETS = [
    ("concept", "value"),
    ("value", "concept"),                     # the caller's order, not the declared one
    ("decimals",),
    ("statement_name",),                      # derived from statement_role
    ("concept", "statement_name", "value"),
    ("element_id",),                          # undeclared but present
    ("definitely_not_a_column",),             # undeclared and absent: must be dropped
    ("concept", "definitely_not_a_column"),
    ("unit_ref", "currency"),
    ("context_ref",),
    ("is_dimensioned", "fiscal_year"),        # nullable and float declared dtypes
]

FLAG_COMBINATIONS = list(itertools.product([True, False], repeat=3))


@pytest.mark.fast
@pytest.mark.parametrize("columns", COLUMN_SETS)
@pytest.mark.parametrize("flags", FLAG_COMBINATIONS)
def test_projected_frame_equals_the_full_width_frame(jpm, flags, columns):
    """Projecting early changes cost, never content."""
    projected = _frame(jpm, flags, columns, projected=True)
    full = _frame(jpm, flags, columns, projected=False)
    pd.testing.assert_frame_equal(projected, full, check_exact=True)


@pytest.mark.fast
def test_empty_result_keeps_its_declared_columns_and_dtypes(jpm):
    """The empty-frame contract survives projection: df['decimals'] still works."""
    flags = (True, True, True)
    columns = ("concept", "decimals")
    query = jpm.facts.query().by_concept("NoSuchConceptExistsAnywhere")
    projected = query.to_dataframe(*columns)
    assert list(projected.columns) == list(columns)
    assert len(projected) == 0
    assert projected["decimals"] is not None

    full = _frame(jpm, flags, columns, projected=False)
    assert list(full.columns) == list(projected.columns)


@pytest.mark.fast
def test_the_frame_is_actually_built_narrow(jpm):
    """The point of the change: two requested columns do not pull in a hundred."""
    query = jpm.facts.query()
    results = query.execute()
    needed = query._projection_source_columns(("concept", "value"), results)

    source_width = len(set().union(*(row.keys() for row in results)))
    assert source_width > 50, f"fixture unexpectedly narrow ({source_width})"
    assert needed is not None
    assert len(needed) <= 10, f"projection is not narrow: {needed}"
    assert set(("concept", "value")).issubset(needed)


@pytest.mark.fast
def test_the_deduplication_identity_is_held_open(jpm):
    """unit_ref is part of fact identity; dropping it merges two currencies (gh #1282)."""
    query = jpm.facts.query()
    results = query.execute()
    needed = query._projection_source_columns(("concept",), results)
    for key in _DEDUP_REQUIRED:
        assert key in needed, f"{key} must survive until de-duplication runs"
    for key in _DEDUP_OPTIONAL:
        if any(key in row for row in results):
            assert key in needed, f"{key} is part of fact identity when present"


@pytest.mark.fast
def test_narrow_request_allocates_far_less_than_a_full_export(jpm):
    """The documented performance tip has to buy something.

    Measured about 10x on both time and peak; asserted at 3x so a slower or
    noisier machine does not make this flaky.
    """
    jpm.facts.query().to_dataframe("concept", "value")  # warm any lazy work

    def peak(*columns):
        query = jpm.facts.query()
        query._df_cache = {}
        tracemalloc.start()
        try:
            query.to_dataframe(*columns)
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    narrow = peak("concept", "value")
    full = peak()
    assert narrow * 3 < full, f"narrow={narrow} full={full}"
