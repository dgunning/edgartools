"""Verification tests for EX-21 Subsidiaries parser."""
from pathlib import Path

import pytest

from edgar.company_reports.subsidiaries import Subsidiary, SubsidiaryList, parse_subsidiaries

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseAAPLSubsidiaries:
    """Test parsing Apple's EX-21 (simple 2-column, 19 subsidiaries)."""

    @pytest.fixture
    def aapl_subs(self):
        html = (FIXTURES / "ex21_aapl.html").read_text()
        return parse_subsidiaries(html)

    @pytest.mark.fast
    def test_count(self, aapl_subs):
        assert len(aapl_subs) == 19

    @pytest.mark.fast
    def test_first_subsidiary(self, aapl_subs):
        assert aapl_subs[0].name == "Apple Asia Limited"
        assert aapl_subs[0].jurisdiction == "Hong Kong"

    @pytest.mark.fast
    def test_last_subsidiary(self, aapl_subs):
        assert aapl_subs[-1].name == "iTunes K.K."
        assert aapl_subs[-1].jurisdiction == "Japan"

    @pytest.mark.fast
    def test_no_ownership_data(self, aapl_subs):
        assert all(s.ownership_pct is None for s in aapl_subs)

    @pytest.mark.fast
    def test_specific_subsidiary(self, aapl_subs):
        braeburn = [s for s in aapl_subs if "Braeburn" in s.name]
        assert len(braeburn) == 1
        assert braeburn[0].name == "Braeburn Capital, Inc."
        assert braeburn[0].jurisdiction == "Nevada, U.S."


class TestParseXOMSubsidiaries:
    """Test parsing ExxonMobil's EX-21 (3-column with ownership percentages, 3 tables)."""

    @pytest.fixture
    def xom_subs(self):
        html = (FIXTURES / "ex21_xom.html").read_text()
        return parse_subsidiaries(html)

    @pytest.mark.fast
    def test_count(self, xom_subs):
        assert len(xom_subs) > 100

    @pytest.mark.fast
    def test_has_ownership(self, xom_subs):
        with_ownership = [s for s in xom_subs if s.ownership_pct is not None]
        assert len(with_ownership) > 50

    @pytest.mark.fast
    def test_first_subsidiary(self, xom_subs):
        assert xom_subs[0].name == "AKG Marketing Company Limited"
        assert xom_subs[0].jurisdiction == "Bahamas"
        assert xom_subs[0].ownership_pct == 87.5

    @pytest.mark.fast
    def test_specific_subsidiary_with_ownership(self, xom_subs):
        imperial = [s for s in xom_subs if s.name == "Imperial Oil Limited"]
        assert len(imperial) == 1
        assert imperial[0].jurisdiction == "Canada"
        assert imperial[0].ownership_pct == 69.6

    @pytest.mark.fast
    def test_footnotes_stripped(self, xom_subs):
        """Footnote markers like (4) (5) should be stripped from names."""
        for s in xom_subs:
            assert "(4)" not in s.name
            assert "(5)" not in s.name


class TestParseJPMSubsidiaries:
    """Test parsing JPMorgan's EX-21 (header with date prefix)."""

    @pytest.fixture
    def jpm_subs(self):
        html = (FIXTURES / "ex21_jpm.html").read_text()
        return parse_subsidiaries(html)

    @pytest.mark.fast
    def test_count(self, jpm_subs):
        assert len(jpm_subs) == 18

    @pytest.mark.fast
    def test_header_filtered(self, jpm_subs):
        """The header row 'December 31, 2025Name' should not appear as a subsidiary."""
        names = [s.name for s in jpm_subs]
        assert not any("December" in n for n in names)

    @pytest.mark.fast
    def test_first_subsidiary(self, jpm_subs):
        assert jpm_subs[0].name == "JPMorgan Chase Bank, National Association"
        assert jpm_subs[0].jurisdiction == "United States"


class TestSubsidiaryList:
    """Test SubsidiaryList collection behavior."""

    @pytest.fixture
    def sub_list(self):
        subs = [
            Subsidiary(name="Alpha Corp", jurisdiction="Delaware"),
            Subsidiary(name="Beta Ltd", jurisdiction="UK", ownership_pct=80.0),
            Subsidiary(name="Gamma GmbH", jurisdiction="Germany"),
        ]
        return SubsidiaryList(subs)

    @pytest.mark.fast
    def test_len(self, sub_list):
        assert len(sub_list) == 3

    @pytest.mark.fast
    def test_iter(self, sub_list):
        names = [s.name for s in sub_list]
        assert names == ["Alpha Corp", "Beta Ltd", "Gamma GmbH"]

    @pytest.mark.fast
    def test_getitem(self, sub_list):
        assert sub_list[0].name == "Alpha Corp"
        assert sub_list[-1].name == "Gamma GmbH"

    @pytest.mark.fast
    def test_to_dataframe(self, sub_list):
        df = sub_list.to_dataframe()
        assert len(df) == 3
        assert list(df.columns) == ["name", "jurisdiction", "ownership"]
        assert df.iloc[1]["ownership"] == 80.0

    @pytest.mark.fast
    def test_to_dataframe_no_ownership(self):
        subs = SubsidiaryList([
            Subsidiary(name="A", jurisdiction="B"),
            Subsidiary(name="C", jurisdiction="D"),
        ])
        df = subs.to_dataframe()
        assert "ownership" not in df.columns

    @pytest.mark.fast
    def test_repr(self, sub_list):
        r = repr(sub_list)
        assert "3" in r
        assert "Alpha Corp" in r

    @pytest.mark.fast
    def test_rich(self, sub_list):
        panel = sub_list.__rich__()
        assert panel is not None


class TestParseEdgeCases:
    """Test parser edge cases."""

    @pytest.mark.fast
    def test_empty_html(self):
        assert parse_subsidiaries("") == []

    @pytest.mark.fast
    def test_no_tables(self):
        html = "<html><body><p>No tables here</p></body></html>"
        assert parse_subsidiaries(html) == []

    @pytest.mark.fast
    def test_empty_table(self):
        html = "<html><body><table></table></body></html>"
        assert parse_subsidiaries(html) == []

    @pytest.mark.fast
    def test_single_row_table(self):
        html = """<html><body><table>
        <tr><td>Only one cell</td></tr>
        </table></body></html>"""
        assert parse_subsidiaries(html) == []

    @pytest.mark.fast
    def test_simple_two_column_table(self):
        html = """<html><body><table>
        <tr><td>Name of Subsidiary</td><td>Jurisdiction</td></tr>
        <tr><td>Acme Corp</td><td>Delaware</td></tr>
        <tr><td>Beta LLC</td><td>California</td></tr>
        </table></body></html>"""
        subs = parse_subsidiaries(html)
        assert len(subs) == 2
        assert subs[0].name == "Acme Corp"
        assert subs[0].jurisdiction == "Delaware"
        assert subs[1].name == "Beta LLC"
        assert subs[1].jurisdiction == "California"


class TestBugFixes:
    """Regression tests for specific bugs found during review."""

    @pytest.mark.fast
    def test_nested_tables_no_duplicates(self):
        """Nested layout tables should not cause duplicate subsidiaries."""
        html = """<html><body>
        <table>
          <tr><td>
            <table>
              <tr><td>Alpha Corp</td><td>Delaware</td></tr>
              <tr><td>Beta LLC</td><td>California</td></tr>
            </table>
          </td></tr>
        </table>
        </body></html>"""
        subs = parse_subsidiaries(html)
        names = [s.name for s in subs]
        assert names.count("Alpha Corp") == 1
        assert names.count("Beta LLC") == 1

    @pytest.mark.fast
    def test_name_with_jurisdiction_word_not_filtered(self):
        """A subsidiary named 'Jurisdiction Holdings' should not be dropped as a header."""
        html = """<html><body><table>
        <tr><td>Jurisdiction Holdings LLC</td><td>Delaware</td></tr>
        <tr><td>Normal Corp</td><td>California</td></tr>
        </table></body></html>"""
        subs = parse_subsidiaries(html)
        names = [s.name for s in subs]
        assert "Jurisdiction Holdings LLC" in names

    @pytest.mark.fast
    def test_name_with_ownership_word_not_filtered(self):
        """A subsidiary named 'National Ownership Corp' should not be dropped as a header."""
        html = """<html><body><table>
        <tr><td>National Ownership Corp</td><td>Delaware</td></tr>
        <tr><td>Normal Corp</td><td>California</td></tr>
        </table></body></html>"""
        subs = parse_subsidiaries(html)
        names = [s.name for s in subs]
        assert "National Ownership Corp" in names

    @pytest.mark.fast
    def test_footnote_pattern_preserves_mid_name_references(self):
        """Footnote stripping should not mangle mid-name references like 'Series [1]'."""
        html = """<html><body><table>
        <tr><td>Series [1] Holdings Trust</td><td>Delaware</td></tr>
        <tr><td>Phase (1) Clinical LLC</td><td>California</td></tr>
        <tr><td>Fund [2024]</td><td>New York</td></tr>
        <tr><td>Trailing Footnote Corp (3)</td><td>Texas</td></tr>
        </table></body></html>"""
        subs = parse_subsidiaries(html)
        names = [s.name for s in subs]
        assert "Series [1] Holdings Trust" in names
        assert "Phase (1) Clinical LLC" in names
        assert "Fund [2024]" in names
        # Trailing footnotes SHOULD be stripped
        assert "Trailing Footnote Corp" in names

    @pytest.mark.fast
    def test_zero_percent_ownership_parsed(self):
        """0% ownership should be parsed as 0.0, not None."""
        html = """<html><body><table>
        <tr><td>Active Corp</td><td>100</td><td>Delaware</td></tr>
        <tr><td>Dormant Corp</td><td>0</td><td>California</td></tr>
        <tr><td>Other Corp</td><td>50</td><td>Texas</td></tr>
        </table></body></html>"""
        subs = parse_subsidiaries(html)
        dormant = [s for s in subs if s.name == "Dormant Corp"]
        assert len(dormant) == 1
        assert dormant[0].ownership_pct == 0.0


class TestTenKSubsidiariesProperty:
    """Integration tests for TenK.subsidiaries property."""

    @pytest.mark.network
    def test_aapl_tenk_subsidiaries(self):
        from edgar import Company
        tenk = Company("AAPL").get_filings(form="10-K").latest().obj()
        subs = tenk.subsidiaries
        assert subs is not None
        assert len(subs) == 19
        assert subs[0].name == "Apple Asia Limited"

    @pytest.mark.network
    def test_xom_tenk_subsidiaries_with_ownership(self):
        from edgar import Company
        tenk = Company("XOM").get_filings(form="10-K").latest().obj()
        subs = tenk.subsidiaries
        assert subs is not None
        assert len(subs) > 100
        assert any(s.ownership_pct is not None for s in subs)

    @pytest.mark.network
    def test_subsidiaries_to_dataframe(self):
        from edgar import Company
        tenk = Company("AAPL").get_filings(form="10-K").latest().obj()
        df = tenk.subsidiaries.to_dataframe()
        assert len(df) == 19
        assert "name" in df.columns
        assert "jurisdiction" in df.columns
