"""Regression test for GH #1960: to_dataframe() crashed under pandas 3 on a statement with no signs.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1960

``Statement._apply_presentation`` multiplied each period column by
``preferred_sign`` over a mask of rows that have one. When no row has a sign the
column is object dtype, the mask selects nothing, and the product is an empty
object Series. pandas 3 refuses to assign that into the float64 period column:
``TypeError: Invalid value '[]' for dtype 'float64'`` (the '[]' is the empty
slice, not a list in the data). The signs are now read as numbers and the
assignment runs only when some row has one.

Keysight's FY2020 10-K (0001601046-20-000154) has a presentation role
``PropertyPlantAndEquipmentNetLandSaleDetails`` that FilingSummary.xml does not
list and that has no facts: two concepts, no values. ``to_dataframe()`` on it
raised with the default ``presentation=True``, so walking the filing's notes
crashed. Ground truth for the signs still being applied, from the same filing's
R7.htm "Consolidated Statement of Cash Flows" ($ in millions, FY2020): gain on
insurance proceeds (32), accounts receivable 75.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from edgar import find
from edgar.xbrl.statements import Statement

LAND_SALE = "http://www.keysight.com/role/PropertyPlantAndEquipmentNetLandSaleDetails"


def _present(df, statement_type="BalanceSheet"):
    owner = SimpleNamespace(_presentation_sign_type=lambda: statement_type)
    return Statement._apply_presentation(owner, df)


@pytest.mark.fast
def test_no_row_with_a_sign_does_not_raise():
    df = pd.DataFrame({
        "concept": ["keys_Bindingcontracttosellland", "us-gaap_GainLossOnSaleOfPropertyPlantEquipment"],
        "label": ["Binding contract to sell land", "Gain (Loss) on Disposition of land"],
        "2020-10-31 (FY)": pd.Series([None, None], dtype=object),
        "preferred_sign": pd.Series([np.nan, np.nan], dtype=object),
    })
    out = _present(df)  # raised TypeError: Invalid value '[]' for dtype 'float64'
    assert out["2020-10-31 (FY)"].isna().all()
    assert list(out["label"]) == list(df["label"])


@pytest.mark.fast
def test_signs_still_apply_when_the_column_is_object_dtype():
    df = pd.DataFrame({
        "concept": ["a", "b", "c"],
        "label": ["a", "b", "c"],
        "2020-10-31 (FY)": pd.Series([32_000_000, -75_000_000, 5.0], dtype=object),
        "preferred_sign": pd.Series([-1, -1, None], dtype=object),
    })
    out = _present(df, "CashFlowStatement")
    assert list(out["2020-10-31 (FY)"]) == [-32_000_000.0, 75_000_000.0, 5.0]


@pytest.fixture(scope="module")
def keys_fy2020():
    return find("0001601046-20-000154").xbrl()


@pytest.mark.network
def test_keys_land_sale_details_to_dataframe(keys_fy2020):
    index = next(i for i, s in enumerate(keys_fy2020.get_all_statements()) if s["role"] == LAND_SALE)
    df = keys_fy2020.statements[index].to_dataframe()  # raised before the fix
    assert list(df["label"]) == ["Binding contract to sell land", "Gain (Loss) on Disposition of land"]
    assert df["2020-10-31 (FY)"].isna().all()


@pytest.mark.network
def test_keys_cash_flow_signs_match_the_filing(keys_fy2020):
    df = keys_fy2020.statements.cash_flow_statement().to_dataframe()
    face = df[df["dimension"] != True]  # noqa: E712

    def value(concept):
        return face[face["concept"] == concept].iloc[0]["2020-10-31 (FY)"]

    assert value("us-gaap_GainOnBusinessInterruptionInsuranceRecovery") == -32_000_000
    assert value("us-gaap_IncreaseDecreaseInAccountsReceivable") == 75_000_000
