"""The stitched fact DataFrame deleted whichever columns the matched rows left
empty, so narrowing a query changed the shape of the table.

bead edgartools-trhe. Third implementation of the same construction that
edgartools-rsyt declared for `edgar/xbrl/facts.py` and edgartools-7wtj for the
entity path; this one kept the `dropna(axis=1, how='all')` the other two had
removed. See engineering/decisions/facts-dataframe-schema.md.

Measured across five stitched pairs (AAPL 10-K+10-K, 10-K alone, 10-K+10-Q; KO;
MSFT), it deleted a column on every one:

* ``by_statement_type('IncomeStatement')`` lost ``period_instant`` -- 5 of 5 --
  because income-statement rows are all durations;
* ``by_statement_type('BalanceSheet')`` lost ``period_start`` -- 5 of 5 --
  because balance-sheet rows are all instants;
* an empty result returned a bare frame with **zero** columns.

Narrowing to a statement is not a statement about which columns exist, and
``df['period_start']`` raising KeyError on a balance sheet is the GH #1244
column-shift shape.

This is the one path of the three with no breaking half: nothing here flips dtype
across queries (0 flips over 15 query/filer combinations), because the fact dict
is built unconditionally and ``value`` is cast to str explicitly.

Runs offline against tracked fixtures.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL, XBRLS
from edgar.xbrl.stitching.query import _STITCHED_COLUMNS

FX = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"

CASES = {
    "aapl_two_10k": [FX / "aapl" / "10k_2023", FX / "aapl" / "10k_2022"],
    "aapl_10k_10q": [FX / "aapl" / "10k_2023", FX / "aapl" / "10q_2023"],
    "ko_two_10k": [FX / "ko" / "10k_2024", FX / "ko" / "10k_2012"],
    "msft_two_10k": [FX / "msft" / "10k_2024", FX / "msft" / "10k_2015"],
}


@pytest.fixture(scope="module", params=sorted(CASES))
def stitched(request):
    dirs = CASES[request.param]
    for d in dirs:
        assert d.exists(), f"missing fixture: {d}"
    return XBRLS([XBRL.from_directory(d) for d in dirs])


def test_narrowing_to_a_statement_does_not_delete_a_column(stitched):
    """The two columns a statement type always leaves empty."""
    base = stitched.query().to_dataframe()
    assert list(base.columns) == list(_STITCHED_COLUMNS)

    income = stitched.query().by_statement_type("IncomeStatement").to_dataframe()
    assert len(income) > 0
    # Every income-statement row is a duration, so this column is empty for all of
    # them -- which used to delete it.
    assert income["period_instant"].isna().all()
    assert list(income.columns) == list(base.columns)

    balance = stitched.query().by_statement_type("BalanceSheet").to_dataframe()
    assert len(balance) > 0
    assert balance["period_start"].isna().all()
    assert list(balance.columns) == list(base.columns)


def test_empty_result_carries_the_declared_columns(stitched):
    """A bare DataFrame() has no columns, so df['value'] raised KeyError."""
    empty = stitched.query().by_filing_index(99).to_dataframe()
    assert len(empty) == 0
    assert list(empty.columns) == list(_STITCHED_COLUMNS)
    assert len(empty["value"]) == 0


def test_column_set_and_dtypes_are_identical_across_queries(stitched):
    base = stitched.query().to_dataframe()
    base_dtypes = base.dtypes.astype(str).to_dict()

    for narrowed in (stitched.query().by_statement_type("IncomeStatement"),
                     stitched.query().by_statement_type("BalanceSheet"),
                     stitched.query().across_periods(2),
                     stitched.query().by_filing_index(99)):
        df = narrowed.to_dataframe()
        assert list(df.columns) == list(base.columns)
        assert df.dtypes.astype(str).to_dict() == base_dtypes, (
            "an empty or narrowed result is not dtype-identical to the base")


def test_a_materialized_column_is_null_not_fabricated(stitched):
    """A column no row populated must be null, never False or 0."""
    balance = stitched.query().by_statement_type("BalanceSheet").to_dataframe()
    assert balance["period_start"].isna().all()

    # is_abstract/is_total are declared bool; casting an all-null column to numpy
    # bool yields False, which would assert a fact is not a total because we do not
    # know. They are populated here, so the guard is that they stay boolean-valued.
    assert balance["is_total"].isin([True, False]).all()


def test_projection_rejects_a_name_this_configuration_does_not_emit(stitched):
    """Which names were valid used to depend on which rows came back."""
    with pytest.raises(KeyError):
        stitched.query().to_dataframe("concept", "no_such_column")

    projected = stitched.query().to_dataframe("concept", "period_start")
    assert list(projected.columns) == ["concept", "period_start"]


def test_source_filing_index_is_present_even_when_nothing_populates_it(stitched):
    """The field is declared public; dropna deleted it whenever it was all-null.

    That is why edgartools-qbm7 was reported as "source_filing_index is None on
    all 215 rows" when the column was in fact absent entirely.
    """
    df = stitched.query().to_dataframe()
    assert "source_filing_index" in df.columns
    assert str(df["source_filing_index"].dtype) == "Int64"
