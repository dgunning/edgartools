"""
Regression test for GitHub Issue #1416:
edgar_read: opt-in ``limit`` so a full 13F portfolio can be read.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1416

Before the fix, the ``holdings`` section of a 13F-HR was hard-capped at 30 rows
in ``_extract_13f_section``, and ``_extract_sections`` then cut every section to
6,000 characters. A caller could not read a whole portfolio, or check it against
the filing's total value: a 211-row fixture returned 30 rows worth 29,565,000 of
188,845,000.

Fix: ``edgar_read`` takes an optional ``limit`` (default 30, so existing callers
see no change; ``0`` means every row). It is threaded through ``_extract_sections``,
``_extract_section`` and ``_extract_13f_section``. The 13F ``holdings`` section no
longer goes through the 6,000-character cap, because ``limit`` already bounds it;
every other section keeps the cap. ``limit`` is validated for every form and
applied only to 13F holdings: a negative or non-integer value is an
``INVALID_ARGUMENTS`` error, while an integral float such as ``30.0`` is accepted
because JSON Schema counts it as an integer.

The fixture is synthetic, so the totals asserted here are computed from it
rather than taken from a filing.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.base import TOOLS
from edgar.ai.mcp.tools.reader import edgar_read

ROWS = 211


def _holdings_frame(rows=ROWS) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Issuer": f"ISSUER {i:03d}", "SharesPrnAmount": 1000 + i, "Value": 1_000_000 - i * 1_000}
            for i in range(rows)
        ]
    )


FILED_TOTAL = int(_holdings_frame()["Value"].sum())


class FakeThirteenF:
    management_company_name = "Test Manager LP"
    report_period = "2026-06-30"
    total_holdings = ROWS
    total_value = FILED_TOTAL

    def __init__(self, holdings=None):
        self.holdings = _holdings_frame() if holdings is None else holdings


class FakeLongTenK:
    """A 10-K whose business section is far longer than the 6,000-character cap."""

    def __getitem__(self, key):
        return "x" * 20_000 if key == "business" else None


class FakeFiling:
    def __init__(self, form="13F-HR", typed_obj=None):
        self.form = form
        self._obj = typed_obj if typed_obj is not None else FakeThirteenF()
        self.accession_no = "0001999371-26-017606"

    def obj(self):
        return self._obj


async def _read(filing, **kwargs):
    with patch.object(reader, "_get_filing", return_value=filing), \
         patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
        return await edgar_read(accession_number="test", **kwargs)


async def _holdings(limit="unset", form="13F-HR", typed_obj=None) -> str:
    kwargs = {} if limit == "unset" else {"limit": limit}
    resp = await _read(FakeFiling(form=form, typed_obj=typed_obj), sections=["holdings"], **kwargs)
    assert resp.success is True
    return resp.data["sections"]["holdings"]


def _rows(text: str) -> list[str]:
    return text.splitlines()[1:]


@pytest.mark.asyncio
class TestHoldingsLimit:
    async def test_default_is_unchanged(self):
        text = await _holdings()

        assert text.splitlines()[0] == "Top holdings (30 of 211):"
        assert len(_rows(text)) == 30
        assert _rows(text)[0] == "  ISSUER 000 | 1,000 shares | $1,000,000"
        assert _rows(text)[-1] == "  ISSUER 029 | 1,029 shares | $971,000"
        # Passing the default explicitly, or None, is the same call.
        assert await _holdings(30) == text
        assert await _holdings(None) == text

    async def test_limit_zero_returns_every_row_and_reconciles_to_total(self):
        text = await _holdings(0)

        rows = _rows(text)
        assert text.splitlines()[0] == "Top holdings (211 of 211):"
        assert len(rows) == ROWS
        assert rows[-1] == "  ISSUER 210 | 1,210 shares | $790,000"
        # The point of the issue: the listed rows add up to the filing total,
        # and the output (well past 6,000 characters) is not cut off.
        assert sum(int(row.rsplit("$", 1)[1].replace(",", "")) for row in rows) == FILED_TOTAL == 188_845_000
        assert len(text) > 6000
        assert "truncated" not in text

    async def test_limit_smaller_than_default(self):
        assert (await _holdings(1)).splitlines() == [
            "Top holdings (1 of 211):",
            "  ISSUER 000 | 1,000 shares | $1,000,000",
        ]

    async def test_limit_larger_than_holdings_returns_them_all(self):
        assert (await _holdings(5000)).splitlines()[0] == "Top holdings (211 of 211):"
        short = FakeThirteenF(_holdings_frame(3))
        assert (await _holdings(0, typed_obj=short)).splitlines()[0] == "Top holdings (3 of 3):"

    async def test_header_counts_the_rows_actually_listed(self):
        # A row with no usable cell is skipped, so it must not be counted as shown.
        frame = _holdings_frame(3)
        frame.loc[1] = {"Issuer": None, "SharesPrnAmount": None, "Value": None}

        text = await _holdings(0, typed_obj=FakeThirteenF(frame))

        assert text.splitlines() == [
            "Top holdings (2 of 3):",
            "  ISSUER 000 | 1,000 shares | $1,000,000",
            "  ISSUER 002 | 1,002 shares | $998,000",
        ]

    async def test_amended_13f_honours_limit(self):
        assert (await _holdings(0, form="13F-HR/A")).splitlines()[0] == "Top holdings (211 of 211):"

    async def test_limit_leaves_the_summary_section_alone(self):
        default = await _read(FakeFiling(), sections=["summary"])
        both = await _read(FakeFiling(), sections=["summary", "holdings"], limit=0)

        summary = both.data["sections"]["summary"]
        assert summary == default.data["sections"]["summary"]
        assert f"Total Value: ${FILED_TOTAL:,}" in summary
        assert len(_rows(both.data["sections"]["holdings"])) == ROWS


@pytest.mark.asyncio
class TestLimitOutsideHoldings:
    async def test_other_forms_still_get_the_char_cap(self):
        resp = await _read(FakeFiling(form="10-K", typed_obj=FakeLongTenK()), sections=["business"], limit=0)

        text = resp.data["sections"]["business"]
        assert text.endswith("... (truncated)")
        assert len(text) < 6100


@pytest.mark.asyncio
class TestLimitValidation:
    @pytest.mark.parametrize("bad", [-1, "10", 2.5, True])
    async def test_invalid_values_are_an_error_and_fetch_nothing(self, bad):
        with patch.object(reader, "_get_filing") as get_filing:
            resp = await edgar_read(accession_number="test", sections=["holdings"], limit=bad)

        assert resp.success is False
        assert resp.error_code == "INVALID_ARGUMENTS"
        assert "limit" in resp.error
        get_filing.assert_not_called()

    async def test_integral_floats_are_accepted_like_integers(self):
        # JSON Schema counts 30.0 as an integer, so the schema accepts it.
        assert await _holdings(30.0) == await _holdings(30)
        assert (await _holdings(0.0)).splitlines()[0] == "Top holdings (211 of 211):"


class TestToolSchema:
    def test_limit_is_advertised_as_an_optional_integer(self):
        schema = TOOLS["edgar_read"]["schema"]

        assert schema["properties"]["limit"]["type"] == "integer"
        assert schema["properties"]["limit"]["default"] == 30
        assert schema["properties"]["limit"]["minimum"] == 0
        assert "limit" not in schema["required"]
