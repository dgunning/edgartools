"""
Tests for the ``max_chars`` parameter of the ``edgar_read`` MCP tool.

``max_chars`` caps the characters returned per text section (default 6,000).
13F-HR holdings are bounded by ``limit`` instead and ignore it. Like ``limit``,
it takes an integer of at least 1: integral floats are accepted, ``True`` and
non-numbers are rejected with INVALID_ARGUMENTS.

The tests use a fake filing, so they need no network.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.reader import DEFAULT_MAX_CHARS, edgar_read

LONG_TEXT = "x" * 20_000


class FakeTenK:
    """Mock TenK whose sections hold far more text than any cap."""

    def __getitem__(self, key):
        return LONG_TEXT if key == "risk_factors" else None


class FakeThirteenF:
    management_company_name = "Test Manager LP"
    report_period = "2026-06-30"
    total_holdings = 40
    total_value = 1000

    def __init__(self):
        self.holdings = pd.DataFrame([
            {"Issuer": f"ISSUER {i:02d}", "SharesPrnAmount": 1000, "Value": 25}
            for i in range(40)
        ])


class FakeFiling:
    def __init__(self, form="10-K", typed_obj=None):
        self.form = form
        self._obj = typed_obj
        self.accession_no = "0000000000-26-000001"

    def obj(self):
        return self._obj


async def _read(filing, **kwargs):
    with patch.object(reader, "_get_filing", return_value=filing), \
         patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
        return await edgar_read(accession_number="test", **kwargs)


@pytest.mark.asyncio
class TestEdgarReadMaxChars:

    async def test_default_cuts_at_6000(self):
        """With no max_chars the section is cut at 6,000 characters, as before."""
        assert DEFAULT_MAX_CHARS == 6000
        resp = await _read(FakeFiling(typed_obj=FakeTenK()), sections=["risk_factors"])
        assert resp.success is True
        text = resp.data["sections"]["risk_factors"]
        assert text.startswith("x" * 6000)
        assert "x" * 6001 not in text
        assert text.endswith("... (truncated)")

    async def test_small_max_chars_returns_shorter_section(self):
        """A small max_chars returns a shorter section than the default."""
        filing = FakeFiling(typed_obj=FakeTenK())
        default = (await _read(filing, sections=["risk_factors"])).data["sections"]["risk_factors"]
        short = (await _read(filing, sections=["risk_factors"], max_chars=100)).data["sections"]["risk_factors"]
        assert short.startswith("x" * 100)
        assert "x" * 101 not in short
        assert short.endswith("... (truncated)")
        assert len(short) < len(default)

    async def test_larger_max_chars_returns_more_text(self):
        """A max_chars above the default returns more than 6,000 characters."""
        resp = await _read(FakeFiling(typed_obj=FakeTenK()), sections=["risk_factors"], max_chars=10_000)
        text = resp.data["sections"]["risk_factors"]
        assert text.startswith("x" * 10_000)
        assert "x" * 10_001 not in text

    async def test_text_shorter_than_max_chars_is_not_truncated(self):
        resp = await _read(FakeFiling(typed_obj=FakeTenK()), sections=["risk_factors"], max_chars=50_000)
        assert resp.data["sections"]["risk_factors"] == LONG_TEXT

    @pytest.mark.parametrize("value", [None, 6000.0, 100.0])
    async def test_accepted_values(self, value):
        """None means the default; integral floats count as integers."""
        resp = await _read(FakeFiling(typed_obj=FakeTenK()), sections=["risk_factors"], max_chars=value)
        assert resp.success is True

    @pytest.mark.parametrize("value", [0, -1, True, False, "abc", 1.5])
    async def test_invalid_max_chars_is_rejected(self, value):
        resp = await _read(FakeFiling(typed_obj=FakeTenK()), sections=["risk_factors"], max_chars=value)
        assert resp.success is False
        assert resp.error_code == "INVALID_ARGUMENTS"
        assert "max_chars" in resp.error

    async def test_13f_holdings_ignore_max_chars(self):
        """Holdings stay bounded by ``limit`` only, even with a tiny max_chars."""
        filing = FakeFiling(form="13F-HR", typed_obj=FakeThirteenF())
        resp = await _read(filing, sections=["holdings"], limit=40, max_chars=10)
        assert resp.success is True
        text = resp.data["sections"]["holdings"]
        assert "ISSUER 00" in text
        assert "ISSUER 39" in text
        assert "truncated" not in text
