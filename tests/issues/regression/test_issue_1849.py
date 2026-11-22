"""NM / N/A table cells export as NaN, not 0.0.

JPMorgan Chase 10-K for FY2024 (accession 0000019617-25-000270, fixture
tests/fixtures/html/jpm/10k/jpm-10-k-2025-02-14.html): the firmwide reconciliation
row "Overhead ratio" reports 52% Reported, NM for the fully taxable-equivalent
adjustment, 51% Managed basis. NM is "not meaningful", not a zero rate.
Dashes keep their historical value of 0.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1849
"""
import math
from pathlib import Path

import pytest

from edgar.documents import parse_html
from edgar.documents.table_nodes import Cell

FIXTURE = Path(__file__).parents[2] / "fixtures/html/jpm/10k/jpm-10-k-2025-02-14.html"


@pytest.mark.fast
@pytest.mark.parametrize("token", ["NM", "nm", "N/A", "n/a"])
def test_not_meaningful_cell_is_numeric_like_but_nan(token):
    cell = Cell(content=token)
    assert cell.is_numeric
    assert math.isnan(cell.numeric_value)


@pytest.mark.fast
@pytest.mark.parametrize("token", ["-", "—", "–", "--"])
def test_dash_cell_still_zero(token):
    cell = Cell(content=token)
    assert cell.is_numeric
    assert cell.numeric_value == 0.0


@pytest.mark.fast
def test_jpm_overhead_ratio_nm_is_nan_in_dataframe():
    document = parse_html(FIXTURE.read_text(encoding="utf-8"))
    for table in document.tables:
        row = next((r for r in table.rows if r.cells and r.cells[0].text().strip() == "Overhead ratio"
                    and any(c.text().strip() == "NM" for c in r.cells)), None)
        if row is None:
            continue
        nm_cell = next(c for c in row.cells if c.text().strip() == "NM")
        assert nm_cell.is_numeric
        assert math.isnan(nm_cell.numeric_value)
        values = table.to_dataframe().loc[["Overhead ratio"]].iloc[0].tolist()
        assert 52.0 in values and 51.0 in values
        assert any(isinstance(v, float) and math.isnan(v) for v in values)
        assert 0.0 not in values
        return
    pytest.fail("Overhead ratio row with an NM cell not found in the JPM fixture")
