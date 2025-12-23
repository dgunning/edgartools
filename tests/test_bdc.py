"""
Tests for BDC (Business Development Company) functionality.
"""
import pytest

from edgar import Company
from edgar.bdc import (
    BDCEntities,
    BDCEntity,
    fetch_bdc_report,
    get_active_bdc_ciks,
    get_bdc_list,
    is_bdc_cik,
)


class TestBDCReference:
    """Tests for BDC reference data functions."""

    @pytest.mark.network
    def test_fetch_bdc_report(self):
        """Test fetching SEC BDC Report as DataFrame."""
        df = fetch_bdc_report(year=2024)

        # Should have expected columns
        assert 'file_number' in df.columns
        assert 'cik' in df.columns
        assert 'registrant_name' in df.columns

        # Should have 100+ BDCs
        assert len(df) > 100

        # All file numbers should start with 814-
        assert all(str(fn).startswith('814-') for fn in df['file_number'] if fn)

    @pytest.mark.network
    def test_get_bdc_list(self):
        """Test getting list of BDC entities."""
        bdcs = get_bdc_list()

        # Should have 100+ BDCs
        assert len(bdcs) > 100

        # All should be BDCEntity instances
        assert all(isinstance(bdc, BDCEntity) for bdc in bdcs)

        # Check known BDC - Ares Capital Corp
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None
        assert arcc.name == 'ARES CAPITAL CORP'
        assert arcc.file_number == '814-00663'

    @pytest.mark.network
    def test_get_active_bdc_ciks(self):
        """Test getting active BDC CIKs."""
        ciks = get_active_bdc_ciks(min_year=2023)

        # Should have many active BDCs
        assert len(ciks) > 50

        # Known active BDC should be included
        assert 1287750 in ciks  # ARCC

    @pytest.mark.network
    def test_is_bdc_cik(self):
        """Test BDC CIK detection."""
        # Known BDCs
        assert is_bdc_cik(1287750)  # ARCC (Ares Capital)
        assert is_bdc_cik(1396440)  # MAIN (Main Street Capital)
        assert is_bdc_cik(1280784)  # HTGC (Hercules Capital)

        # Known non-BDCs
        assert not is_bdc_cik(320193)   # AAPL
        assert not is_bdc_cik(1318605)  # TSLA
        assert not is_bdc_cik(789019)   # MSFT


class TestBDCEntity:
    """Tests for BDCEntity dataclass."""

    def test_bdc_entity_creation(self):
        """Test creating BDCEntity."""
        bdc = BDCEntity(
            file_number='814-00663',
            cik=1287750,
            name='ARES CAPITAL CORP',
            city='NEW YORK',
            state='NY',
        )

        assert bdc.file_number == '814-00663'
        assert bdc.cik == 1287750
        assert bdc.name == 'ARES CAPITAL CORP'
        assert bdc.city == 'NEW YORK'
        assert bdc.state == 'NY'

    def test_bdc_entity_repr(self):
        """Test BDCEntity repr shows rich panel."""
        bdc = BDCEntity(
            file_number='814-00663',
            cik=1287750,
            name='ARES CAPITAL CORP',
            city='NEW YORK',
            state='NY',
        )

        repr_str = repr(bdc)
        assert 'ARES CAPITAL CORP' in repr_str
        assert '1287750' in repr_str
        assert '814-00663' in repr_str
        assert 'Business Development Company' in repr_str

    def test_bdc_entity_rich(self):
        """Test BDCEntity __rich__ returns Panel."""
        from datetime import date
        from rich.panel import Panel

        bdc = BDCEntity(
            file_number='814-00663',
            cik=1287750,
            name='ARES CAPITAL CORP',
            city='NEW YORK',
            state='NY',
            last_filing_date=date(2024, 5, 15),
            last_filing_type='10-K',
        )

        rich_output = bdc.__rich__()
        assert isinstance(rich_output, Panel)


class TestBDCEntities:
    """Tests for BDCEntities collection class."""

    @pytest.mark.network
    def test_get_bdc_list_returns_bdc_entities(self):
        """Test that get_bdc_list returns BDCEntities."""
        bdcs = get_bdc_list()
        assert isinstance(bdcs, BDCEntities)
        assert len(bdcs) > 100

    @pytest.mark.network
    def test_bdc_entities_indexing(self):
        """Test BDCEntities indexing."""
        bdcs = get_bdc_list()

        # Test positive index
        first = bdcs[0]
        assert isinstance(first, BDCEntity)

        # Test negative index
        last = bdcs[-1]
        assert isinstance(last, BDCEntity)

    @pytest.mark.network
    def test_bdc_entities_iteration(self):
        """Test BDCEntities iteration."""
        bdcs = get_bdc_list()

        count = 0
        for bdc in bdcs:
            assert isinstance(bdc, BDCEntity)
            count += 1
            if count >= 5:
                break

        assert count == 5

    @pytest.mark.network
    def test_bdc_entities_filter_by_state(self):
        """Test filtering BDCs by state."""
        bdcs = get_bdc_list()
        ny_bdcs = bdcs.filter(state='NY')

        assert len(ny_bdcs) > 0
        assert len(ny_bdcs) < len(bdcs)
        assert all(bdc.state == 'NY' for bdc in ny_bdcs)

    @pytest.mark.network
    def test_bdc_entities_filter_active(self):
        """Test filtering active BDCs."""
        bdcs = get_bdc_list()
        active = bdcs.filter(active=True)

        assert len(active) > 0
        assert len(active) < len(bdcs)

    @pytest.mark.network
    def test_bdc_entities_to_dataframe(self):
        """Test converting to DataFrame."""
        bdcs = get_bdc_list()
        df = bdcs.to_dataframe()

        assert 'name' in df.columns
        assert 'cik' in df.columns
        assert 'file_number' in df.columns
        assert len(df) == len(bdcs)

    @pytest.mark.network
    def test_bdc_entities_rich(self):
        """Test BDCEntities __rich__ returns Panel."""
        from rich.panel import Panel

        bdcs = get_bdc_list()
        rich_output = bdcs.__rich__()
        assert isinstance(rich_output, Panel)


class TestCompanyIsBDC:
    """Tests for Company.is_bdc property."""

    @pytest.mark.network
    def test_bdc_company_is_bdc(self):
        """Test that BDC companies have is_bdc=True."""
        # Ares Capital Corp - largest BDC
        arcc = Company(1287750)
        assert arcc.data.is_bdc is True

    @pytest.mark.network
    def test_regular_company_is_not_bdc(self):
        """Test that regular companies have is_bdc=False."""
        # Apple - definitely not a BDC
        aapl = Company("AAPL")
        assert aapl.data.is_bdc is False

    @pytest.mark.network
    def test_main_street_capital_is_bdc(self):
        """Test another known BDC."""
        # Main Street Capital
        main = Company("MAIN")
        assert main.data.is_bdc is True


class TestBDCIntegration:
    """Integration tests for BDC functionality."""

    @pytest.mark.network
    def test_bdc_has_schedule_of_investments(self):
        """Test that BDC filings have Schedule of Investments."""
        # Get a BDC 10-K filing
        arcc = Company(1287750)
        filings = arcc.get_filings(form="10-K")

        if len(filings) > 0:
            tenk = filings[0]
            xbrl = tenk.xbrl()

            if xbrl:
                # Try to access schedule of investments
                soi = xbrl.statements.schedule_of_investments()
                # SOI may or may not be present depending on the filing
                # This test just ensures the method works without error
                assert soi is None or hasattr(soi, 'render')
