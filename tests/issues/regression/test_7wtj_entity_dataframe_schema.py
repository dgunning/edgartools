"""The entity fact DataFrames changed shape and dtype according to which rows a
query matched, so a consumer's filter could break by filtering differently.

bead edgartools-7wtj. Same failure mode as edgartools-rsyt on a different code
path -- see engineering/decisions/facts-dataframe-schema.md for the rule.

``FactQuery.to_dataframe()`` and ``EntityFacts.to_dataframe()`` both built their
frame with ``pd.DataFrame(records)``, which infers the column set and every dtype
from the rows that came back. Two consequences, both measured across 12 companies
in different industries (344,769 base rows):

* ``value`` flipped ``float64`` -> ``int64`` on **16 of 36** narrowing queries,
  whenever the matched rows happened to be whole numbers. That changes division
  semantics and the null sentinel for a caller who only narrowed a filter.
* A query matching nothing returned a bare frame with **zero columns**, so
  ``df['value']`` raised ``KeyError``. A real query reaches this: Main Street
  Capital reports no ``Revenues`` concept.

Ground truth is the tracked fixtures ``tests/fixtures/entity/snow_facts.json``
(Snowflake FY2025) and ``lpa_facts.json``, so this runs offline.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.entity.dataframe_schema import FACT_QUERY_COLUMNS, entity_facts_columns
from edgar.entity.entity_facts import EntityFacts
from edgar.entity.parser import EntityFactsParser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "entity"

# Concepts whose values in these fixtures are all whole numbers -- the condition
# that made `value` infer int64 once a query narrowed to them.
INTEGRAL_CONCEPTS = ["Assets", "Liabilities", "StockholdersEquity"]


@pytest.fixture(scope="module", params=["snow_facts.json", "lpa_facts.json"])
def facts(request):
    path = FIXTURES / request.param
    assert path.exists(), f"missing fixture: {path}"
    return EntityFactsParser.parse_company_facts(json.loads(path.read_text("utf-8")))


def test_value_dtype_does_not_follow_the_matched_rows(facts):
    """The headline defect: narrowing to whole numbers flipped `value` to int64."""
    base = facts.query().to_dataframe()
    assert base["value"].dtype == "float64"

    narrowed = 0
    for concept in INTEGRAL_CONCEPTS:
        df = facts.query().by_concept(concept).to_dataframe()
        if df.empty:
            continue
        narrowed += 1
        # Every value here is a whole number, which is exactly what used to make
        # inference choose int64.
        assert all(float(v).is_integer() for v in df["value"])
        assert df["value"].dtype == "float64", (
            f"{concept}: value dtype followed the matched rows")

    assert narrowed, "fixture matched none of the integral concepts -- test is vacuous"


def test_column_set_and_dtypes_are_identical_across_queries(facts):
    """Narrowing chooses fewer rows, not a different table."""
    base = facts.query().to_dataframe()
    assert list(base.columns) == list(FACT_QUERY_COLUMNS)

    for narrow in (facts.query().by_concept("Assets"),
                   facts.query().by_fiscal_year(2023),
                   facts.query().by_period_type("annual")):
        df = narrow.to_dataframe()
        assert list(df.columns) == list(base.columns)
        assert df.dtypes.astype(str).to_dict() == base.dtypes.astype(str).to_dict()


def test_empty_result_carries_the_declared_columns(facts):
    """A query matching nothing yielded zero columns, so df['value'] raised."""
    df = facts.query().by_concept("NoSuchConceptAtAll").to_dataframe()
    assert df.empty
    assert list(df.columns) == list(FACT_QUERY_COLUMNS)

    # The actual user-visible symptom: this used to raise KeyError.
    assert len(df["value"]) == 0
    assert df["value"].dtype == "float64"

    # An empty result is dtype-identical to a populated one, or this is just the
    # same bug in the zero-row case.
    base = facts.query().to_dataframe()
    assert df.dtypes.astype(str).to_dict() == base.dtypes.astype(str).to_dict()


def test_projection_keeps_the_callers_order_and_declared_dtypes(facts):
    df = facts.query().to_dataframe("value", "concept")
    assert list(df.columns) == ["value", "concept"]
    assert df["value"].dtype == "float64"


def test_entity_facts_to_dataframe_shape_follows_its_arguments(facts):
    """EntityFacts.to_dataframe() is the same rule with its own configuration.

    Narrowed via filter_by_period_type, not just the full fact set: the full set
    infers float64 on its own, so asserting only against it would pass on the
    unfixed code and guard nothing.
    """
    narrowed = facts.filter_by_period_type("annual")
    assert len(narrowed) < len(facts), "filter did not narrow -- assertion is vacuous"

    for source in (facts, narrowed):
        for pit_mode in (False, True):
            for include_metadata in (False, True):
                df = source.to_dataframe(pit_mode=pit_mode,
                                         include_metadata=include_metadata)
                declared = entity_facts_columns(pit_mode=pit_mode,
                                                include_metadata=include_metadata)
                assert list(df.columns) == list(declared), (
                    f"pit_mode={pit_mode} include_metadata={include_metadata}")
                assert df["value"].dtype == "float64"


def test_entity_facts_with_no_facts_carries_the_declared_columns():
    """An EntityFacts holding nothing returned a bare frame with zero columns.

    Built directly rather than filtered from a fixture: both tracked fixtures have
    facts of every period type, so a filter-based version would never run.
    """
    empty = EntityFacts(cik=1318605, name="Nothing Filed Inc", facts=[])

    for pit_mode in (False, True):
        for include_metadata in (False, True):
            df = empty.to_dataframe(pit_mode=pit_mode, include_metadata=include_metadata)
            declared = entity_facts_columns(pit_mode=pit_mode,
                                            include_metadata=include_metadata)
            assert list(df.columns) == list(declared)
            # The symptom: this used to raise KeyError.
            assert len(df["value"]) == 0
            assert df["value"].dtype == "float64"


def test_entity_facts_unknown_column_still_raises(facts):
    """Reindexing must not turn a caller's typo into a column of nulls."""
    with pytest.raises(KeyError):
        facts.to_dataframe(columns=["concept", "no_such_column"])


def test_materialized_null_column_is_not_fabricated_data(facts):
    """A column no returned row populated comes back null, never False or 0.

    `is_audited` is declared `bool`, which cannot hold a null: casting an all-null
    column to it yields False. Declaring the non-nullable dtype for a materialized
    column would make the one path that fabricates data the path taken when data is
    missing.
    """
    from edgar.datatools import apply_declared_schema
    from edgar.entity.dataframe_schema import NULL_DTYPES, PINNED

    df = pd.DataFrame({"concept": ["Assets"], "value": [1.0]})
    out = apply_declared_schema(df, FACT_QUERY_COLUMNS, list(FACT_QUERY_COLUMNS),
                                PINNED, NULL_DTYPES)
    assert out["is_audited"].isna().all()
    assert out["is_audited"].dtype == "boolean"
    # The mutation this guards: dtype 'bool' here would assert "not audited".
    assert not (out["is_audited"] == False).any()  # noqa: E712


def test_all_null_object_column_keeps_none():
    """A column that is null for every row must keep None, not become NaN.

    `pd.Series(index=..., dtype=object)` fills with NaN, so rewriting a column that
    already had its declared dtype silently turned `period_start=None` into a
    float, and downstream date arithmetic raised "unsupported operand type(s) for
    -: 'datetime.date' and 'float'". Moving a null sentinel is the failure class
    this schema exists to prevent, including when the schema code is what moves it.

    Built directly: no query against the tracked fixtures returns rows whose date
    column is null throughout, so a query-level version of this would never fail.
    test_issue_1138_edgar_trends_concepts.py is the end-to-end guard -- it is what
    caught this.
    """
    from edgar.datatools import apply_declared_schema
    from edgar.entity.dataframe_schema import NULL_DTYPES, PINNED

    df = pd.DataFrame({"concept": ["Assets", "Assets"],
                       "value": [1.0, 2.0],
                       "period_start": [None, None]})
    out = apply_declared_schema(df, FACT_QUERY_COLUMNS, list(FACT_QUERY_COLUMNS),
                               PINNED, NULL_DTYPES)
    assert list(out["period_start"]) == [None, None]
    assert all(v is None for v in out["period_start"]), (
        "an all-None object column was rewritten and its nulls became NaN")
