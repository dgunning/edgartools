"""FactQuery.to_dataframe(): preferred_sign and fiscal_year are nullable Int64.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1100
Bead: edgartools-rsyt.2

Before 6.0 both columns were inferred from the rows a query returned. On Foot
Locker's FY2024 10-K (0001437749-25-009620), the bare query read preferred_sign
as float64 with NaN, while by_statement_type('IncomeStatement') read it as int64,
because only the bare query matched a fact with no presentation sign. A filter
that worked on one query broke on the other without any upgrade involved.

6.0 pins both columns to pandas' nullable Int64, so the dtype is the same for
every query and an absent value is pd.NA. numeric_value stays float64 with NaN.

Offline, against two committed fixtures:
  - tests/fixtures/xbrl/tsla: Tesla 10-Q for the quarter ended 2024-06-30,
    accession 0001628280-24-032662. No fact lacks a preferred_sign, so in 5.x
    every query read int64.
  - tests/fixtures/xbrl/unp: Union Pacific 10-K for 2012. 681 of its 1,526 facts
    lack a preferred_sign, so in 5.x the bare query read float64.
"""
import pandas as pd
import pytest

from edgar.xbrl import XBRL

PINNED = ("preferred_sign", "fiscal_year")


@pytest.fixture(scope="module")
def tsla():
    return XBRL.from_directory("tests/fixtures/xbrl/tsla")


@pytest.fixture(scope="module")
def unp():
    return XBRL.from_directory("tests/fixtures/xbrl/unp")


def test_ground_truth_preferred_sign_and_fiscal_year(tsla):
    """Tesla presents Interest expense with a negated label: $86M for Q2 FY2024."""
    df = tsla.facts.query().by_concept("us-gaap:InterestExpense", exact=True).to_dataframe()
    row = df[(df["statement_type"] == "IncomeStatement")
             & (df["numeric_value"] == 86_000_000)
             & (df["fiscal_period"] == "Q2")].iloc[0]
    assert row["preferred_sign"] == -1
    assert row["fiscal_year"] == 2024
    assert df["preferred_sign"].dtype == "Int64"
    assert df["fiscal_year"].dtype == "Int64"


def _queries(xbrl):
    concept = next(f["concept"] for f in xbrl.facts.get_facts()
                   if f.get("preferred_sign") is not None)
    return {
        "bare": xbrl.facts.query(),
        "balance_sheet": xbrl.facts.query().by_statement_type("BalanceSheet"),
        "one_signed_concept": xbrl.facts.query().by_concept(concept, exact=True),
        "instant_only": xbrl.facts.query().by_period_type("instant"),
        "limit_5": xbrl.facts.query().limit(5),
        "no_match": xbrl.facts.query().by_concept("ZzzNoSuchConceptExists", exact=True),
    }


@pytest.mark.parametrize("fixture_name", ["tsla", "unp"])
def test_dtype_is_int64_for_every_query(fixture_name, request):
    xbrl = request.getfixturevalue(fixture_name)
    for name, query in _queries(xbrl).items():
        df = query.to_dataframe()
        for col in PINNED:
            assert df[col].dtype == "Int64", f"{fixture_name}/{name}: {col} is {df[col].dtype}"
        assert df["numeric_value"].dtype == "float64", f"{fixture_name}/{name}"


def test_absent_preferred_sign_is_pd_na_not_nan(unp):
    """The sentinel moves from NaN to pd.NA, which is the breaking half."""
    df = unp.facts.query().to_dataframe()
    absent = df["preferred_sign"].isna()
    assert absent.sum() > 0, "fixture has no unsigned facts; test is vacuous"
    assert df["preferred_sign"][absent].iloc[0] is pd.NA
    # The present values stay integers, -1 or 1.
    assert set(df["preferred_sign"].dropna().unique()) <= {-1, 1}


def test_mixed_and_unmixed_queries_agree(unp):
    """The #1100 report: a query matching an unsigned fact and one that matches
    none must report the same dtype."""
    mixed = unp.facts.query().to_dataframe()
    concept = next(f["concept"] for f in unp.facts.get_facts()
                   if f.get("preferred_sign") is not None)
    unmixed = unp.facts.query().by_concept(concept, exact=True).to_dataframe()
    assert mixed["preferred_sign"].isna().any()
    assert not unmixed["preferred_sign"].isna().any()
    assert mixed["preferred_sign"].dtype == unmixed["preferred_sign"].dtype == "Int64"


def test_empty_result_matches_populated_dtypes(tsla):
    """Every column, including is_dimensioned, which was numpy bool when populated
    and nullable boolean when empty."""
    empty = tsla.facts.query().by_concept("ZzzNoSuchConceptExists", exact=True).to_dataframe()
    full = tsla.facts.query().to_dataframe()
    assert empty.empty
    assert empty.dtypes.astype(str).to_dict() == full.dtypes.astype(str).to_dict()
    assert full["is_dimensioned"].dtype == "boolean"


def test_projection_keeps_the_pinned_dtype(tsla):
    df = tsla.facts.query().to_dataframe("concept", "preferred_sign", "fiscal_year")
    assert list(df.columns) == ["concept", "preferred_sign", "fiscal_year"]
    assert df["preferred_sign"].dtype == "Int64"
    assert df["fiscal_year"].dtype == "Int64"
