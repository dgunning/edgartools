"""Regression: text facts on a primary statement leave its value columns numeric.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1995
Bead: edgartools-auvk1.24

Zimmer Biomet's 2018 income statement (0001564590-19-004283) presents
TypeOfRevenueExtensibleList and TypeOfCostGoodOrServiceExtensibleList on its
face, each filed as us-gaap:ProductMember. In 6.0 to_dataframe() coerced the
value columns of the four primary statements to numbers, so those cells were
NaN. edgartools-auvk1.13 (#1975) kept any column holding text as text, to keep
note narrative (Issue #762), so 6.2 left 'us-gaap:ProductMember' beside floats
and pyarrow/polars refused the frame (ArrowInvalid). A primary statement's
value columns are numeric again, whether it is reached by name or by role.
"""
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest

from edgar.xbrl import XBRL

pytestmark = pytest.mark.fast

ZBH_2018 = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "zbh" / "10k_2018"
ENUMERATIONS = ["us-gaap_TypeOfRevenueExtensibleList", "us-gaap_TypeOfCostGoodOrServiceExtensibleList"]


@pytest.fixture(scope="module")
def zbh():
    return XBRL.from_directory(ZBH_2018)


def _value_columns(df):
    return [c for c in df.columns if str(c)[:4].isdigit()]


def _check(df):
    columns = _value_columns(df)
    assert columns == ["2018-12-31 (FY)", "2017-12-31 (FY)", "2016-12-31 (FY)"]
    for column in columns:
        assert pd.api.types.is_float_dtype(df[column]), column
    rows = df.set_index("concept")
    # Printed income statement: Net sales $7,932.9 million (2018), $7,803.3 million (2017)
    net_sales = rows.loc["us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"]
    assert net_sales["2018-12-31 (FY)"] == 7_932_900_000
    assert net_sales["2017-12-31 (FY)"] == 7_803_300_000
    for concept in ENUMERATIONS:
        assert rows.loc[concept, columns].isna().all()
    pa.Table.from_pandas(df[columns])  # raised ArrowInvalid on 'us-gaap:ProductMember'


def test_income_statement_value_columns_are_numeric(zbh):
    _check(zbh.statements.income_statement().to_dataframe(view="standard"))


def test_same_statement_reached_by_role_is_numeric_too(zbh):
    role = zbh.statements.income_statement().role_or_type
    statement = zbh.statements[role]
    assert statement.canonical_type is None
    _check(statement.to_dataframe(view="standard"))
