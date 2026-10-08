"""
Regression test for GitHub Issue #1415:
edgar_read: 13F summary section is dropped unless sections=["all"].
"summary" is both the metadata-only mode and a section name.

Root cause:
In edgar/ai/mcp/tools/reader.py:
1. edgar_read had:
       if "summary" not in sections or len(sections) > 1:
   which caused sections=["summary"] to skip section extraction entirely (metadata-only mode).
2. _extract_sections had:
       sections_to_extract = [s for s in sections if s != "summary"]
   which unconditionally stripped "summary" from section extraction on multi-section requests.

For 13F-HR filings, "summary" is an actual section name containing management company,
report period, total holdings, and total portfolio value.

Fix:
Only treat "summary" as metadata-only if "summary" is not in available_sections for that form.
Similarly, in _extract_sections, retain "summary" if it is in available_sections for that form.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1415
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.reader import edgar_read, _extract_sections, _get_section_list


class FakeThirteenF:
    """Mock ThirteenF object matching 13F-HR structure."""
    management_company_name = "Test Manager LP"
    report_period = "2026-06-30"
    total_holdings = 3
    total_value = 299997

    def __init__(self):
        self.holdings = pd.DataFrame([
            {"Issuer": "ISSUER 0", "SharesPrnAmount": 1000, "Value": 100000},
            {"Issuer": "ISSUER 1", "SharesPrnAmount": 1000, "Value": 99999},
            {"Issuer": "ISSUER 2", "SharesPrnAmount": 1000, "Value": 99998},
        ])


class FakeTenK:
    """Mock TenK object matching 10-K structure."""
    def __init__(self):
        self.called_getitem = False

    def __getitem__(self, key):
        self.called_getitem = True
        if key in ("business", "Item 1"):
            return "Business overview content for TenK."
        return None


class FakeFiling:
    def __init__(self, form="13F-HR", typed_obj=None):
        self.form = form
        self._obj = typed_obj
        self.accession_no = "0001999371-26-017606"

    def obj(self):
        return self._obj


@pytest.mark.asyncio
class TestIssue1415EdgarRead13FSummary:
    """Verify 13F summary section extraction under all request modes."""

    async def test_13f_read_with_sections_summary(self):
        """Requesting sections=['summary'] on 13F-HR returns the summary section."""
        fake_filing = FakeFiling(form="13F-HR", typed_obj=FakeThirteenF())

        with patch.object(reader, "_get_filing", return_value=fake_filing), \
             patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
            resp = await edgar_read(accession_number="test", sections=["summary"])

            assert resp.success is True
            data = resp.data
            assert "sections" in data, "sections key must be present for 13F-HR with sections=['summary']"
            sections = data["sections"]
            assert "summary" in sections
            assert sections["summary"] is not None
            assert "Management Company: Test Manager LP" in sections["summary"]
            assert "Report Period: 2026-06-30" in sections["summary"]
            assert "Total Holdings: 3" in sections["summary"]
            assert "Total Value: $299,997" in sections["summary"]

            # Next steps should not hint that content was omitted
            hint = "Add sections like 'business'"
            assert not any(hint in step for step in resp.next_steps)

    async def test_13f_read_with_default_sections(self):
        """Calling edgar_read without sections on 13F-HR extracts summary section."""
        fake_filing = FakeFiling(form="13F-HR", typed_obj=FakeThirteenF())

        with patch.object(reader, "_get_filing", return_value=fake_filing), \
             patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
            # sections defaults to None -> ["summary"]
            resp = await edgar_read(accession_number="test")

            assert resp.success is True
            data = resp.data
            assert "sections" in data
            assert "summary" in data["sections"]
            assert "Total Value: $299,997" in data["sections"]["summary"]

    async def test_13f_read_with_sections_summary_and_holdings(self):
        """Requesting sections=['summary', 'holdings'] on 13F-HR returns both sections."""
        fake_filing = FakeFiling(form="13F-HR", typed_obj=FakeThirteenF())

        with patch.object(reader, "_get_filing", return_value=fake_filing), \
             patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
            resp = await edgar_read(accession_number="test", sections=["summary", "holdings"])

            assert resp.success is True
            data = resp.data
            assert "sections" in data
            sections = data["sections"]
            assert "summary" in sections
            assert "holdings" in sections
            assert "Total Holdings: 3" in sections["summary"]
            assert "Top holdings (3 of 3):" in sections["holdings"]

    async def test_13f_read_with_sections_all(self):
        """Requesting sections=['all'] on 13F-HR returns both holdings and summary."""
        fake_filing = FakeFiling(form="13F-HR", typed_obj=FakeThirteenF())

        with patch.object(reader, "_get_filing", return_value=fake_filing), \
             patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
            resp = await edgar_read(accession_number="test", sections=["all"])

            assert resp.success is True
            data = resp.data
            assert "sections" in data
            sections = data["sections"]
            assert "summary" in sections
            assert "holdings" in sections


@pytest.mark.asyncio
class TestMetadataOnlyModePreservedForOtherForms:
    """Verify non-13F forms preserve metadata-only mode when sections=['summary']."""

    async def test_10k_read_with_sections_summary_is_metadata_only(self):
        """Calling edgar_read(sections=['summary']) on 10-K does not call obj() or return sections."""
        tenk_mock = FakeTenK()
        filing_mock = MagicMock()
        filing_mock.form = "10-K"
        filing_mock.obj = MagicMock(return_value=tenk_mock)

        with patch.object(reader, "_get_filing", return_value=filing_mock), \
             patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
            resp = await edgar_read(accession_number="test", sections=["summary"])

            assert resp.success is True
            data = resp.data
            # sections must not be present in response
            assert "sections" not in data
            # filing.obj() must not be called in metadata-only mode
            filing_mock.obj.assert_not_called()
            # Next steps must suggest adding sections to read content
            assert any("Add sections like 'business'" in s for s in resp.next_steps)

    async def test_10k_read_with_summary_and_business(self):
        """Calling edgar_read(sections=['summary', 'business']) on 10-K filters out summary."""
        tenk_mock = FakeTenK()
        filing_mock = MagicMock()
        filing_mock.form = "10-K"
        filing_mock.obj = MagicMock(return_value=tenk_mock)

        with patch.object(reader, "_get_filing", return_value=filing_mock), \
             patch.object(reader, "format_filing_summary", return_value={"accession": "test"}):
            resp = await edgar_read(accession_number="test", sections=["summary", "business"])

            assert resp.success is True
            data = resp.data
            assert "sections" in data
            sections = data["sections"]
            assert "business" in sections
            assert "summary" not in sections
            assert "Business overview content" in sections["business"]


@pytest.mark.asyncio
class TestExtractSectionsDirect:
    """Direct unit tests for _extract_sections."""

    async def test_extract_sections_13f_includes_summary(self):
        fake_filing = FakeFiling(form="13F-HR", typed_obj=FakeThirteenF())
        extracted = await _extract_sections(fake_filing, ["summary"])
        assert "summary" in extracted
        assert "Total Value" in extracted["summary"]

    async def test_extract_sections_10k_excludes_summary(self):
        tenk_mock = FakeTenK()
        fake_filing = FakeFiling(form="10-K", typed_obj=tenk_mock)
        extracted = await _extract_sections(fake_filing, ["summary", "business"])
        assert "summary" not in extracted
        assert "business" in extracted
