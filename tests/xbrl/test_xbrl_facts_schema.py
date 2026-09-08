"""The output schema of ``FactQuery.to_dataframe()`` is declared, not inferred.

The contract (engineering/decisions/facts-dataframe-schema.md, edgartools-rsyt):
the column set is a function of the query's *configuration*, never of the rows
that came back. Narrowing a query returns fewer rows, not a different table.

This is the check that was missing when the drift went unnoticed: every test
here compares several queries against **one** XBRL instance, so a failure means
the code changed the shape, never that the data differed.

Runs offline against the committed Tesla 10-Q fixture.
"""
import pandas as pd
import pytest
from pandas.api import types as pdt

from edgar.xbrl import XBRL
from edgar.xbrl.facts import _CONTEXT_COLUMNS, _CORE_COLUMNS, _DIMENSION_COLUMNS

FIXTURE = "tests/fixtures/xbrl/tsla"

# Ground truth: the exact columns and order a default query emits, verified by
# hand against the fixture. Pinned as a list so an accidental reorder is caught.
EXPECTED_COLUMNS = [
    'concept', 'label', 'balance', 'preferred_sign', 'weight', 'value',
    'numeric_value', 'period_key', 'period_start', 'period_end',
    'period_instant', 'is_dimensioned', 'decimals', 'statement_type',
    'statement_name', 'fact_id', 'context_ref', 'unit_ref', 'currency',
    'period_type', 'entity_identifier', 'entity_scheme', 'fiscal_period',
    'fiscal_year',
]


@pytest.fixture(scope='module')
def xbrl():
    return XBRL.from_directory(FIXTURE)


def _queries(xbrl):
    """Queries that return very different row sets from the same instance.

    Each one previously produced a different column set: narrowing to instant
    facts removed period_start/period_end, .limit() removed whichever columns
    those few rows left null, and a no-match query returned no columns at all.
    """
    return {
        'bare': xbrl.facts.query(),
        'income_statement': xbrl.facts.query().by_statement_type('IncomeStatement'),
        'balance_sheet': xbrl.facts.query().by_statement_type('BalanceSheet'),
        'instant_only': xbrl.facts.query().by_period_type('instant'),
        'duration_only': xbrl.facts.query().by_period_type('duration'),
        'limit_5': xbrl.facts.query().limit(5),
        'no_match': xbrl.facts.query().by_concept('ZzzNoSuchConceptExists'),
    }


def test_declared_columns_ground_truth(xbrl):
    """A default query emits exactly these 24 columns, in this order."""
    df = xbrl.facts.query().to_dataframe()
    assert list(df.columns) == EXPECTED_COLUMNS
    assert len(df) == 1059


def test_column_set_is_identical_across_queries(xbrl):
    """The invariant. One instance, seven row sets, one table shape."""
    shapes = {name: list(q.to_dataframe().columns)
              for name, q in _queries(xbrl).items()}

    for name, columns in shapes.items():
        assert columns == EXPECTED_COLUMNS, (
            f"{name} produced a different column set: "
            f"missing {sorted(set(EXPECTED_COLUMNS) - set(columns))}, "
            f"extra {sorted(set(columns) - set(EXPECTED_COLUMNS))}"
        )


def test_narrowing_a_query_does_not_drop_inapplicable_columns(xbrl):
    """Instant facts have no start/end date, so those columns are null — present."""
    df = xbrl.facts.query().by_period_type('instant').to_dataframe()

    assert 'period_start' in df.columns
    assert 'period_end' in df.columns
    assert df['period_start'].isna().all()
    assert df['period_instant'].notna().any()


def test_all_null_declared_columns_keep_their_declared_dtype(xbrl):
    """A column with no data still has a usable type.

    Inference has nothing to work with on an all-null column and lands somewhere
    arbitrary — an all-None ``decimals`` infers as object/None rather than
    string/pd.NA. This previously went unseen because ``dropna(axis=1)`` deleted
    such columns outright, which is how ``.limit(5)`` came to return 5 fewer
    columns than the same query unlimited.
    """
    for name, query in _queries(xbrl).items():
        df = query.to_dataframe()
        for column in df.columns:
            if column not in _CORE_COLUMNS or not df[column].isna().all():
                continue
            expected = _CORE_COLUMNS[column]
            assert df[column].dtype == expected, (
                f"{name}: all-null column {column!r} has inferred dtype "
                f"{df[column].dtype}, expected the declared {expected}"
            )


def test_string_columns_never_hold_the_literal_string_nan(xbrl):
    """astype('str') on a null yields the string "nan"; the declared dtype must not.

    Guards the pandas 2/3 split — the default string dtype changed from object to
    str, and the naive cast silently turns missing data into the text "nan".
    """
    df = xbrl.facts.query().limit(5).to_dataframe()

    for column in df.columns:
        if pdt.is_string_dtype(df[column].dtype) or df[column].dtype == object:
            assert not (df[column] == 'nan').any(), f"{column} holds the string 'nan'"


class TestEmptyResults:
    """An empty result is zero rows, not zero columns."""

    def test_empty_result_has_the_full_column_set(self, xbrl):
        df = xbrl.facts.query().by_concept('ZzzNoSuchConceptExists').to_dataframe()

        assert len(df) == 0
        assert list(df.columns) == EXPECTED_COLUMNS

    def test_a_column_of_an_empty_result_is_addressable(self, xbrl):
        """Previously KeyError: a bare DataFrame() has no columns to address."""
        df = xbrl.facts.query().by_concept('ZzzNoSuchConceptExists').to_dataframe()

        assert len(df['decimals']) == 0          # not KeyError
        assert df['decimals'].isna().all()       # vacuously true, and not a crash
        assert len(df[df['concept'] == 'Revenue']) == 0

    def test_an_empty_query_can_still_be_displayed(self, xbrl):
        """Rendering must survive the empty frame having columns.

        Declaring the columns gave an empty result a `concept` column with no
        rows to measure, so the width calculation in __rich__ produced NaN and
        rich failed to render it. A mistyped concept in a REPL is enough to hit
        this, which is exactly the interaction the panel invites.
        """
        query = xbrl.facts.query().by_concept('ZzzNoSuchConceptExists')

        assert repr(query)  # previously TypeError inside rich's box rendering

    def test_empty_result_of_a_projection_keeps_the_projection(self, xbrl):
        df = (xbrl.facts.query()
              .by_concept('ZzzNoSuchConceptExists')
              .to_dataframe('concept', 'value'))

        assert list(df.columns) == ['concept', 'value']


class TestConfigurationDrivenColumns:
    """What the flags change, they change deterministically."""

    def test_exclude_contexts_drops_exactly_the_context_block(self, xbrl):
        df = xbrl.facts.query().exclude_contexts().to_dataframe()

        assert set(EXPECTED_COLUMNS) - set(df.columns) == set(_CONTEXT_COLUMNS)
        assert list(df.columns) == [c for c in EXPECTED_COLUMNS
                                    if c not in _CONTEXT_COLUMNS]

    def test_exclude_contexts_is_stable_across_row_sets(self, xbrl):
        """The flag decides the shape; the rows do not get a vote."""
        wide = xbrl.facts.query().exclude_contexts().to_dataframe()
        narrow = (xbrl.facts.query().exclude_contexts()
                  .by_period_type('instant').limit(3).to_dataframe())

        assert list(narrow.columns) == list(wide.columns)

    def test_dimension_columns_are_declared_when_dimensions_included(self, xbrl):
        """Including dimensions adds the five fixed columns whether or not any
        returned fact is dimensioned — the case that previously varied."""
        everything = xbrl.facts.query().with_dimensions().to_dataframe()
        undimensioned = (xbrl.facts.query().with_dimensions()
                         .by_dimension(None)
                         .to_dataframe())

        assert len(undimensioned) > 0, "fixture has no undimensioned facts"

        for column in _DIMENSION_COLUMNS:
            assert column in everything.columns
            assert column in undimensioned.columns


class TestProjection:
    """`to_dataframe('a', 'b')` names columns, and gets them."""

    def test_projection_returns_the_requested_columns_in_order(self, xbrl):
        df = xbrl.facts.query().to_dataframe('value', 'concept')

        assert list(df.columns) == ['value', 'concept']

    def test_projection_can_name_a_column_no_row_populated(self, xbrl):
        """Asking for period_instant on duration-only facts yields a null column.

        It previously yielded nothing at all: the projection intersected with
        whichever columns had survived inference.
        """
        df = (xbrl.facts.query().by_period_type('duration')
              .to_dataframe('concept', 'period_instant'))

        assert list(df.columns) == ['concept', 'period_instant']
        assert df['period_instant'].isna().all()

    def test_unknown_column_names_are_dropped(self, xbrl):
        df = xbrl.facts.query().to_dataframe('concept', 'not_a_real_column')

        assert list(df.columns) == ['concept']


def test_repeated_calls_return_the_same_shape(xbrl):
    """The per-query DataFrame cache must not hand back a different table."""
    query = xbrl.facts.query().by_statement_type('IncomeStatement')

    assert list(query.to_dataframe().columns) == list(query.to_dataframe().columns)


def test_declared_schema_covers_the_documented_column_list():
    """The spec and the ground-truth list are the same 24 columns."""
    assert list(_CORE_COLUMNS) == EXPECTED_COLUMNS
    assert _CONTEXT_COLUMNS <= set(_CORE_COLUMNS)
    assert not set(_DIMENSION_COLUMNS) & set(_CORE_COLUMNS)


def test_dtypes_are_valid_pandas_dtypes():
    """A typo in the spec must fail here, not at the first empty query."""
    for column, dtype in {**_CORE_COLUMNS, **_DIMENSION_COLUMNS}.items():
        assert len(pd.Series(index=pd.RangeIndex(0), dtype=dtype)) == 0, column
