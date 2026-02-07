"""
Tests for BDC (Business Development Company) functionality.
"""
import pytest
import pandas as pd

from edgar import Company
from decimal import Decimal

from edgar.bdc import (
    BDCEntities,
    BDCEntity,
    PortfolioInvestment,
    PortfolioInvestments,
    fetch_bdc_report,
    get_active_bdc_ciks,
    get_bdc_list,
    is_bdc_cik,
)
from edgar.bdc.investments import _parse_investment_identifier


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

    @pytest.mark.network
    def test_bdc_entities_get_by_cik(self):
        """Test getting BDC by CIK."""
        bdcs = get_bdc_list()

        # Known BDC - Ares Capital
        arcc = bdcs.get_by_cik(1287750)
        assert arcc is not None
        assert arcc.name == 'ARES CAPITAL CORP'
        assert arcc.cik == 1287750

        # Non-existent CIK
        none_result = bdcs.get_by_cik(999999999)
        assert none_result is None

    @pytest.mark.network
    def test_bdc_entities_get_by_ticker(self):
        """Test getting BDC by ticker symbol."""
        bdcs = get_bdc_list()

        # Known BDC tickers
        arcc = bdcs.get_by_ticker('ARCC')
        assert arcc is not None
        assert arcc.name == 'ARES CAPITAL CORP'

        main = bdcs.get_by_ticker('MAIN')
        assert main is not None
        assert 'Main Street' in main.name

        htgc = bdcs.get_by_ticker('HTGC')
        assert htgc is not None
        assert 'Hercules' in htgc.name

        # Lowercase should work too
        arcc_lower = bdcs.get_by_ticker('arcc')
        assert arcc_lower is not None
        assert arcc_lower.cik == arcc.cik

        # Non-BDC ticker
        aapl = bdcs.get_by_ticker('AAPL')
        assert aapl is None


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

    @pytest.mark.network
    def test_bdc_entity_get_company(self):
        """Test BDCEntity.get_company() method."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        company = arcc.get_company()
        assert company.cik == 1287750
        assert 'ARES' in company.name.upper()

    @pytest.mark.network
    def test_bdc_entity_get_filings(self):
        """Test BDCEntity.get_filings() method."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        filings = arcc.get_filings(form='10-K')
        assert len(filings) > 0

    @pytest.mark.network
    def test_bdc_entity_schedule_of_investments(self):
        """Test BDCEntity.schedule_of_investments() method."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        soi = arcc.schedule_of_investments()
        # ARCC should have a Schedule of Investments
        assert soi is not None
        assert hasattr(soi, 'to_dataframe')
        assert hasattr(soi, 'render')


class TestPortfolioInvestment:
    """Tests for PortfolioInvestment dataclass."""

    def test_portfolio_investment_creation(self):
        """Test creating PortfolioInvestment."""
        inv = PortfolioInvestment(
            identifier='Test Company, First lien senior secured loan',
            company_name='Test Company',
            investment_type='First lien senior secured loan',
            fair_value=Decimal('1000000'),
            cost=Decimal('950000'),
            interest_rate=0.095,
        )

        assert inv.company_name == 'Test Company'
        assert inv.investment_type == 'First lien senior secured loan'
        assert inv.fair_value == Decimal('1000000')
        assert inv.cost == Decimal('950000')
        assert inv.interest_rate == 0.095

    def test_portfolio_investment_unrealized_gain(self):
        """Test unrealized gain/loss calculation."""
        inv = PortfolioInvestment(
            identifier='Test Company, Equity',
            company_name='Test Company',
            investment_type='Equity',
            fair_value=Decimal('1200000'),
            cost=Decimal('1000000'),
        )

        assert inv.unrealized_gain_loss == Decimal('200000')

    def test_portfolio_investment_is_debt(self):
        """Test is_debt property."""
        loan = PortfolioInvestment(
            identifier='Test, First lien senior secured loan',
            company_name='Test',
            investment_type='First lien senior secured loan',
        )
        assert loan.is_debt is True
        assert loan.is_equity is False

    def test_portfolio_investment_is_equity(self):
        """Test is_equity property."""
        equity = PortfolioInvestment(
            identifier='Test, Common stock',
            company_name='Test',
            investment_type='Common stock',
        )
        assert equity.is_equity is True
        assert equity.is_debt is False

    def test_portfolio_investment_rich(self):
        """Test PortfolioInvestment __rich__ returns Panel."""
        from rich.panel import Panel

        inv = PortfolioInvestment(
            identifier='Test Company, First lien senior secured loan',
            company_name='Test Company',
            investment_type='First lien senior secured loan',
            fair_value=Decimal('1000000'),
            cost=Decimal('950000'),
        )

        rich_output = inv.__rich__()
        assert isinstance(rich_output, Panel)


class TestPortfolioInvestments:
    """Tests for PortfolioInvestments collection."""

    def test_portfolio_investments_totals(self):
        """Test total calculations."""
        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Company A, Loan',
                company_name='Company A',
                investment_type='Loan',
                fair_value=Decimal('1000000'),
                cost=Decimal('900000'),
            ),
            PortfolioInvestment(
                identifier='Company B, Equity',
                company_name='Company B',
                investment_type='Equity',
                fair_value=Decimal('500000'),
                cost=Decimal('400000'),
            ),
        ])

        assert investments.total_fair_value == Decimal('1500000')
        assert investments.total_cost == Decimal('1300000')
        assert investments.total_unrealized_gain_loss == Decimal('200000')

    def test_portfolio_investments_filter(self):
        """Test filtering investments."""
        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Company A, First lien loan',
                company_name='Company A',
                investment_type='First lien loan',
            ),
            PortfolioInvestment(
                identifier='Company B, Second lien loan',
                company_name='Company B',
                investment_type='Second lien loan',
            ),
            PortfolioInvestment(
                identifier='Company C, Equity',
                company_name='Company C',
                investment_type='Equity',
            ),
        ])

        # Filter by investment type
        loans = investments.filter(investment_type='lien')
        assert len(loans) == 2

        # Filter by company name
        company_a = investments.filter(company_name='Company A')
        assert len(company_a) == 1

    def test_portfolio_investments_to_dataframe(self):
        """Test converting to DataFrame."""
        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Test, Loan',
                company_name='Test',
                investment_type='Loan',
                fair_value=Decimal('1000000'),
            ),
        ])

        df = investments.to_dataframe()
        assert 'company_name' in df.columns
        assert 'investment_type' in df.columns
        assert 'fair_value' in df.columns
        assert len(df) == 1

    def test_portfolio_investments_rich(self):
        """Test PortfolioInvestments __rich__ returns Panel."""
        from rich.panel import Panel

        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Test, Loan',
                company_name='Test',
                investment_type='Loan',
                fair_value=Decimal('1000000'),
                cost=Decimal('900000'),
            ),
        ])

        rich_output = investments.__rich__()
        assert isinstance(rich_output, Panel)


class TestInvestmentIdentifierParsing:
    """Tests for investment identifier parsing."""

    def test_parse_first_lien_loan(self):
        """Test parsing first lien loan identifier."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Acme Corp, First lien senior secured loan'
        )
        assert company == 'Acme Corp'
        assert 'First lien' in inv_type

    def test_parse_equity(self):
        """Test parsing equity identifier."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Test Holdings LLC, Common stock'
        )
        assert company == 'Test Holdings LLC'
        assert inv_type == 'Common stock'

    def test_parse_numbered_loan(self):
        """Test parsing numbered loan identifier."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Big Company Inc., First lien senior secured loan 2'
        )
        assert company == 'Big Company Inc.'
        assert 'First lien' in inv_type

    def test_parse_complex_company_name(self):
        """Test parsing with complex company names containing commas."""
        # Company name with ampersand
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Smith & Jones LLC, Equity'
        )
        assert company == 'Smith & Jones LLC'
        assert inv_type == 'Equity'


class TestPortfolioInvestmentsIntegration:
    """Integration tests for portfolio investments."""

    @pytest.mark.network
    def test_bdc_entity_portfolio_investments(self):
        """Test BDCEntity.portfolio_investments() method."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        investments = arcc.portfolio_investments()
        # ARCC should have portfolio investments
        assert investments is not None
        assert len(investments) > 100  # ARCC has hundreds of investments

    @pytest.mark.network
    def test_portfolio_investments_has_fair_values(self):
        """Test that portfolio investments have fair values."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        investments = arcc.portfolio_investments()
        assert investments is not None

        # Total fair value should be significant (billions for ARCC)
        assert investments.total_fair_value > Decimal('1000000000')

    @pytest.mark.network
    def test_portfolio_investments_filter_by_type(self):
        """Test filtering portfolio investments by type."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        investments = arcc.portfolio_investments()
        assert investments is not None

        # Filter to first lien loans
        first_lien = investments.filter(investment_type='First lien')
        assert len(first_lien) > 0
        assert len(first_lien) < len(investments)


class TestDataQuality:
    """Tests for DataQuality dataclass."""

    def test_data_quality_creation(self):
        """Test creating DataQuality."""
        from edgar.bdc import DataQuality

        dq = DataQuality(
            total_investments=100,
            fair_value_coverage=0.95,
            cost_coverage=0.94,
            principal_coverage=0.75,
            interest_rate_coverage=0.67,
            pik_rate_coverage=0.15,
            spread_coverage=0.67,
            debt_count=73,
            equity_count=22,
        )
        assert dq.total_investments == 100
        assert dq.fair_value_coverage == 0.95
        assert dq.debt_count == 73

    def test_data_quality_rich(self):
        """Test DataQuality __rich__ returns Panel."""
        from rich.panel import Panel
        from edgar.bdc import DataQuality

        dq = DataQuality(
            total_investments=100,
            fair_value_coverage=0.95,
            cost_coverage=0.94,
            principal_coverage=0.75,
            interest_rate_coverage=0.67,
            pik_rate_coverage=0.15,
            spread_coverage=0.67,
            debt_count=73,
            equity_count=22,
        )
        rich_output = dq.__rich__()
        assert isinstance(rich_output, Panel)


class TestPortfolioInvestmentsPeriodAndQuality:
    """Tests for period and data_quality properties."""

    def test_portfolio_investments_period(self):
        """Test period property."""
        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Test, Loan',
                company_name='Test',
                investment_type='Loan',
            ),
        ], period='2024-12-31')

        assert investments.period == '2024-12-31'

    def test_portfolio_investments_data_quality(self):
        """Test data_quality property."""
        from edgar.bdc import DataQuality

        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Company A, Loan',
                company_name='Company A',
                investment_type='Loan',
                fair_value=Decimal('1000000'),
                cost=Decimal('900000'),
                interest_rate=0.10,
            ),
            PortfolioInvestment(
                identifier='Company B, Equity',
                company_name='Company B',
                investment_type='Equity',
                fair_value=Decimal('500000'),
            ),
        ])

        dq = investments.data_quality
        assert isinstance(dq, DataQuality)
        assert dq.total_investments == 2
        assert dq.fair_value_coverage == 1.0  # Both have fair value
        assert dq.cost_coverage == 0.5  # Only one has cost
        assert dq.interest_rate_coverage == 0.5  # Only one has rate

    def test_empty_portfolio_data_quality(self):
        """Test data_quality for empty portfolio."""
        investments = PortfolioInvestments([])
        dq = investments.data_quality
        assert dq.total_investments == 0
        assert dq.fair_value_coverage == 0.0

    def test_filter_preserves_period(self):
        """Test that filter preserves period."""
        investments = PortfolioInvestments([
            PortfolioInvestment(
                identifier='Company A, Loan',
                company_name='Company A',
                investment_type='Loan',
            ),
            PortfolioInvestment(
                identifier='Company B, Equity',
                company_name='Company B',
                investment_type='Equity',
            ),
        ], period='2024-12-31')

        filtered = investments.filter(investment_type='Loan')
        assert filtered.period == '2024-12-31'

    @pytest.mark.network
    def test_portfolio_investments_period_from_xbrl(self):
        """Test that period is extracted from XBRL data."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        investments = arcc.portfolio_investments()
        assert investments is not None
        assert investments.period is not None
        # Period should be a date string like '2024-12-31'
        assert len(investments.period) == 10
        assert '-' in investments.period

    @pytest.mark.network
    def test_portfolio_investments_data_quality_from_xbrl(self):
        """Test data_quality from real XBRL data."""
        from edgar.bdc import DataQuality

        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        investments = arcc.portfolio_investments()
        assert investments is not None

        dq = investments.data_quality
        assert isinstance(dq, DataQuality)
        assert dq.total_investments > 100
        assert dq.fair_value_coverage > 0.9  # Most have fair value
        assert dq.debt_count > 0
        assert dq.equity_count > 0


class TestHasDetailedInvestments:
    """Tests for has_detailed_investments method."""

    @pytest.mark.network
    def test_arcc_has_detailed_investments(self):
        """Test that ARCC has detailed investment data."""
        bdcs = get_bdc_list()
        arcc = next((b for b in bdcs if b.cik == 1287750), None)
        assert arcc is not None

        assert arcc.has_detailed_investments() is True

    @pytest.mark.network
    def test_htgc_has_detailed_investments(self):
        """Test that HTGC (Hercules) has detailed investment data.

        HTGC uses a different format: "Debt Investments [Industry] and [Company], Senior Secured, ..."
        The from_xbrl method extracts these by looking at dimensional facts.
        """
        bdcs = get_bdc_list()
        htgc = next((b for b in bdcs if 'hercules' in b.name.lower()), None)
        assert htgc is not None

        assert htgc.has_detailed_investments() is True

        # Verify we can extract investments
        investments = htgc.portfolio_investments()
        assert investments is not None
        assert len(investments) > 50  # HTGC has ~116 investments

    @pytest.mark.network
    def test_blue_owl_has_detailed_investments(self):
        """Test that Blue Owl has detailed investment data.

        Blue Owl's investment data is in dimensional facts (dim_us-gaap_InvestmentIdentifierAxis)
        rather than in the Statement presentation hierarchy. The from_xbrl method extracts these.
        """
        bdcs = get_bdc_list()
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        assert blue_owl.has_detailed_investments() is True

        # Verify we can extract investments
        investments = blue_owl.portfolio_investments()
        assert investments is not None
        assert len(investments) > 100  # Blue Owl has ~468 investments


class TestIsActive:
    """Tests for is_active property and active filtering."""

    def test_is_active_with_recent_filing(self):
        """Test that BDC with recent filing is active."""
        from datetime import date
        from dateutil.relativedelta import relativedelta

        # Filed 6 months ago - should be active
        recent_date = date.today() - relativedelta(months=6)
        bdc = BDCEntity(
            file_number='814-00001',
            cik=1234567,
            name='TEST ACTIVE BDC',
            last_filing_date=recent_date,
            last_filing_type='10-K',
        )
        assert bdc.is_active is True

    def test_is_active_with_old_filing(self):
        """Test that BDC with old filing is inactive."""
        from datetime import date
        from dateutil.relativedelta import relativedelta

        # Filed 2 years ago - should be inactive
        old_date = date.today() - relativedelta(months=24)
        bdc = BDCEntity(
            file_number='814-00002',
            cik=7654321,
            name='TEST INACTIVE BDC',
            last_filing_date=old_date,
            last_filing_type='10-K',
        )
        assert bdc.is_active is False

    def test_is_active_with_no_filing_date(self):
        """Test that BDC with no filing date is inactive."""
        bdc = BDCEntity(
            file_number='814-00003',
            cik=1111111,
            name='TEST NO DATE BDC',
        )
        assert bdc.is_active is False

    def test_is_active_returns_bool(self):
        """Test that is_active returns Python bool, not numpy bool."""
        from datetime import date

        bdc = BDCEntity(
            file_number='814-00004',
            cik=2222222,
            name='TEST BOOL BDC',
            last_filing_date=date.today(),
            last_filing_type='10-Q',
        )
        assert type(bdc.is_active) is bool

    @pytest.mark.network
    def test_filter_active_bdcs(self):
        """Test filtering to active BDCs."""
        bdcs = get_bdc_list()
        active = bdcs.filter(active=True)
        inactive = bdcs.filter(active=False)

        # Should have both active and inactive
        assert len(active) > 0
        assert len(inactive) > 0
        assert len(active) + len(inactive) == len(bdcs)

        # All in active should have is_active True
        assert all(bdc.is_active for bdc in active)
        # All in inactive should have is_active False
        assert all(not bdc.is_active for bdc in inactive)

    @pytest.mark.network
    def test_dataframe_includes_is_active(self):
        """Test that to_dataframe includes is_active column."""
        bdcs = get_bdc_list()
        df = bdcs.to_dataframe()

        assert 'is_active' in df.columns
        # Should have both True and False values
        assert df['is_active'].sum() > 0  # Some active
        assert (~df['is_active']).sum() > 0  # Some inactive

    def test_rich_display_shows_status(self):
        """Test that __rich__ shows status indicator."""
        from datetime import date

        active_bdc = BDCEntity(
            file_number='814-00005',
            cik=3333333,
            name='TEST ACTIVE DISPLAY',
            last_filing_date=date.today(),
            last_filing_type='10-K',
        )
        inactive_bdc = BDCEntity(
            file_number='814-00006',
            cik=4444444,
            name='TEST INACTIVE DISPLAY',
            last_filing_date=date(2020, 1, 1),
            last_filing_type='10-K',
        )

        active_repr = repr(active_bdc)
        inactive_repr = repr(inactive_bdc)

        assert 'Active' in active_repr
        assert 'Inactive' in inactive_repr


class TestBDCSearch:
    """Tests for BDC search functionality."""

    @pytest.mark.network
    def test_find_bdc_by_name(self):
        """Test searching for BDC by name."""
        from edgar.bdc import find_bdc

        results = find_bdc("Ares")
        assert len(results) > 0
        # Should find Ares Capital
        assert any("ARES" in r.name for r in results)

    @pytest.mark.network
    def test_find_bdc_by_ticker(self):
        """Test searching for BDC by ticker."""
        from edgar.bdc import find_bdc

        results = find_bdc("ARCC")
        assert len(results) > 0
        # First result should be Ares Capital
        assert results[0].cik == 1287750

    @pytest.mark.network
    def test_find_bdc_fuzzy_match(self):
        """Test fuzzy matching on BDC names."""
        from edgar.bdc import find_bdc

        # Search with partial name
        results = find_bdc("Main Street")
        assert len(results) > 0
        # Should find Main Street Capital
        assert any("MAIN STREET" in r.name.upper() for r in results)

    @pytest.mark.network
    def test_search_results_indexing(self):
        """Test indexing into search results returns BDCEntity."""
        from edgar.bdc import find_bdc, BDCEntity

        results = find_bdc("ARCC")
        assert len(results) > 0
        entity = results[0]
        assert isinstance(entity, BDCEntity)
        assert entity.cik == 1287750

    @pytest.mark.network
    def test_search_results_iteration(self):
        """Test iterating over search results."""
        from edgar.bdc import find_bdc, BDCEntity

        results = find_bdc("Capital", top_n=5)
        entities = list(results)
        assert len(entities) <= 5
        assert all(isinstance(e, BDCEntity) for e in entities)

    @pytest.mark.network
    def test_search_results_properties(self):
        """Test search results properties."""
        from edgar.bdc import find_bdc

        results = find_bdc("Hercules")
        assert not results.empty
        assert len(results.ciks) == len(results)
        assert len(results.tickers) == len(results)

    @pytest.mark.network
    def test_bdcentities_search_method(self):
        """Test search method on BDCEntities."""
        bdcs = get_bdc_list()
        results = bdcs.search("Blue Owl")
        assert len(results) > 0
        assert any("BLUE OWL" in r.name.upper() for r in results)

    @pytest.mark.network
    def test_search_results_display(self):
        """Test that search results can be displayed."""
        from edgar.bdc import find_bdc

        results = find_bdc("MAIN")
        # Should be able to get rich representation
        rich_repr = results.__rich__()
        assert rich_repr is not None
        # Should be able to get string repr
        str_repr = repr(results)
        assert "MAIN" in str_repr


class TestBDCDatasets:
    """Tests for SEC DERA BDC Data Sets."""

    @pytest.mark.network
    def test_fetch_bdc_dataset(self):
        """Test fetching a BDC dataset from SEC DERA."""
        from edgar.bdc import fetch_bdc_dataset

        # Fetch Q4 2024 dataset (should exist)
        dataset = fetch_bdc_dataset(2024, 4)

        # Should have all components
        assert dataset is not None
        assert dataset.year == 2024
        assert dataset.quarter == 4
        assert dataset.period == "2024Q4"

        # Should have DataFrames for each file
        assert hasattr(dataset, 'submissions')
        assert hasattr(dataset, 'numbers')
        assert hasattr(dataset, 'presentation')
        assert hasattr(dataset, 'soi')

        # Submissions should have expected structure
        if not dataset.submissions.empty:
            assert 'adsh' in dataset.submissions.columns
            assert 'cik' in dataset.submissions.columns

    @pytest.mark.network
    def test_fetch_bdc_dataset_invalid_quarter(self):
        """Test that invalid quarter raises ValueError."""
        from edgar.bdc import fetch_bdc_dataset

        with pytest.raises(ValueError, match="Quarter must be 1, 2, 3, or 4"):
            fetch_bdc_dataset(2024, 5)

    @pytest.mark.network
    def test_bdc_dataset_properties(self):
        """Test BDCDataset computed properties."""
        from edgar.bdc import fetch_bdc_dataset

        dataset = fetch_bdc_dataset(2024, 4)

        # Test properties
        assert dataset.num_submissions >= 0
        assert dataset.num_facts >= 0
        assert dataset.num_soi_entries >= 0
        assert dataset.num_companies >= 0

    @pytest.mark.network
    def test_bdc_dataset_get_methods(self):
        """Test BDCDataset getter methods."""
        from edgar.bdc import fetch_bdc_dataset

        dataset = fetch_bdc_dataset(2024, 4)

        # Test getting facts for a submission
        if not dataset.submissions.empty:
            adsh = dataset.submissions.iloc[0]['adsh']
            facts = dataset.get_facts_for_submission(adsh)
            assert isinstance(facts, pd.DataFrame)

            soi = dataset.get_soi_for_submission(adsh)
            assert isinstance(soi, pd.DataFrame)

    @pytest.mark.network
    def test_bdc_dataset_summary_by_company(self):
        """Test BDCDataset summary by company."""
        from edgar.bdc import fetch_bdc_dataset

        dataset = fetch_bdc_dataset(2024, 4)

        summary = dataset.summary_by_company()
        assert isinstance(summary, pd.DataFrame)

        if not summary.empty:
            assert 'cik' in summary.columns
            assert 'name' in summary.columns

    @pytest.mark.network
    def test_bdc_dataset_rich_display(self):
        """Test BDCDataset rich display."""
        from rich.panel import Panel
        from edgar.bdc import fetch_bdc_dataset

        dataset = fetch_bdc_dataset(2024, 4)

        rich_output = dataset.__rich__()
        assert isinstance(rich_output, Panel)

        str_repr = str(dataset)
        assert "2024Q4" in str_repr

    @pytest.mark.network
    def test_list_bdc_datasets(self):
        """Test listing available BDC datasets."""
        from edgar.bdc import list_bdc_datasets

        df = list_bdc_datasets(max_years_back=2)
        assert isinstance(df, pd.DataFrame)

        if not df.empty:
            assert 'year' in df.columns
            assert 'quarter' in df.columns
            assert 'period' in df.columns
            assert 'url' in df.columns

    def test_bdc_dataset_dataclass(self):
        """Test BDCDataset can be created directly for unit testing."""
        from edgar.bdc import BDCDataset
        import pandas as pd

        # Create empty dataset for testing
        dataset = BDCDataset(
            year=2024,
            quarter=3,
            submissions=pd.DataFrame({'adsh': ['test-123'], 'cik': [1234]}),
            numbers=pd.DataFrame(),
            presentation=pd.DataFrame(),
            soi=pd.DataFrame(),
        )

        assert dataset.period == "2024Q3"
        assert dataset.num_submissions == 1
        assert dataset.num_facts == 0
        assert dataset.num_soi_entries == 0

    @pytest.mark.network
    def test_soi_search(self):
        """Test searching for portfolio companies across BDCs."""
        from edgar.bdc import fetch_bdc_dataset

        dataset = fetch_bdc_dataset(2024, 3)
        soi = dataset.schedule_of_investments

        # Search for a known company
        results = soi.search("software", top_n=10)
        assert isinstance(results, pd.DataFrame)
        assert len(results) <= 10

        if not results.empty:
            assert 'company' in results.columns
            assert 'bdc_name' in results.columns
            assert 'bdc_cik' in results.columns

    @pytest.mark.network
    def test_soi_top_companies(self):
        """Test getting top portfolio companies across BDCs."""
        from edgar.bdc import fetch_bdc_dataset

        dataset = fetch_bdc_dataset(2024, 3)
        soi = dataset.schedule_of_investments

        top = soi.top_companies(n=10)
        assert isinstance(top, pd.DataFrame)
        assert len(top) <= 10

        if not top.empty:
            assert 'company' in top.columns
            assert 'num_bdcs' in top.columns
            # Companies should be held by at least 1 BDC
            assert top['num_bdcs'].min() >= 1
