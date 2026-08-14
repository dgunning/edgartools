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

        # Check known BDC - Main Street Capital Corp. (Ares Capital, the former
        # anchor, was dropped from the SEC's 2026 BDC report; MAIN is a stable,
        # large BDC present across report years.)
        main = next((b for b in bdcs if b.cik == 1396440), None)
        assert main is not None
        assert 'Main Street' in main.name
        assert main.file_number == '814-00746'

    @pytest.mark.network
    def test_get_active_bdc_ciks(self):
        """Test getting active BDC CIKs."""
        ciks = get_active_bdc_ciks(min_year=2023)

        # Should have many active BDCs
        assert len(ciks) > 50

        # Known active BDC should be included
        assert 1396440 in ciks  # MAIN (Main Street Capital)

    @pytest.mark.network
    def test_is_bdc_cik(self):
        """Test BDC CIK detection."""
        # Known BDCs
        assert is_bdc_cik(17313)    # CSWC (Capital Southwest)
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

        # Known BDC - Main Street Capital
        main = bdcs.get_by_cik(1396440)
        assert main is not None
        assert 'Main Street' in main.name
        assert main.cik == 1396440

        # Non-existent CIK
        none_result = bdcs.get_by_cik(999999999)
        assert none_result is None

    @pytest.mark.network
    def test_bdc_entities_get_by_ticker(self):
        """Test getting BDC by ticker symbol."""
        bdcs = get_bdc_list()

        # Known BDC tickers
        main = bdcs.get_by_ticker('MAIN')
        assert main is not None
        assert 'Main Street' in main.name

        htgc = bdcs.get_by_ticker('HTGC')
        assert htgc is not None
        assert 'Hercules' in htgc.name

        # Lowercase should work too
        main_lower = bdcs.get_by_ticker('main')
        assert main_lower is not None
        assert main_lower.cik == main.cik

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
        # Get a BDC 10-K filing (Blue Owl Credit Income Corp)
        blue_owl = Company(1812554)
        filings = blue_owl.get_filings(form="10-K")

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
        main = next((b for b in bdcs if b.cik == 1396440), None)
        assert main is not None

        company = main.get_company()
        assert company.cik == 1396440
        assert 'MAIN STREET' in company.name.upper()

    @pytest.mark.network
    def test_bdc_entity_get_filings(self):
        """Test BDCEntity.get_filings() method."""
        bdcs = get_bdc_list()
        main = next((b for b in bdcs if b.cik == 1396440), None)
        assert main is not None

        filings = main.get_filings(form='10-K')
        assert len(filings) > 0

    @pytest.mark.network
    def test_bdc_entity_schedule_of_investments(self):
        """Test BDCEntity.schedule_of_investments() method."""
        bdcs = get_bdc_list()
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        soi = blue_owl.schedule_of_investments()
        # Blue Owl should have a Schedule of Investments
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

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Wingspire Capital Holdings LLC | Specialty finance equity investment | Affiliated',
                ('specialty finance',),
                'Wingspire Capital Holdings LLC',
                'Equity',
            ),
            (
                'Wingspire Capital Holdings LLC | Specialty finance equity investment 1',
                ('specialty finance',),
                'Wingspire Capital Holdings LLC',
                'Equity',
            ),
            (
                'AAM Series 2.1 Aviation Feeder, LLC | Specialty finance debt investment | Affiliated',
                ('specialty finance',),
                'AAM Series 2.1 Aviation Feeder, LLC',
                'Debt',
            ),
            (
                'Controlled/affiliated - debt commitments, First lien senior secured revolving loan',
                ('debt commitment',),
                'Controlled/affiliated - debt commitments',
                'First lien senior secured revolving loan',
            ),
            (
                'DTE Enterprises, LLC | Class AA Preferred Member Units (non-voting)',
                ('class aa',),
                'DTE Enterprises, LLC',
                'Class AA Preferred Member Units (non-voting)',
            ),
        ],
    )
    def test_parse_cross_issuer_regressions(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        'descriptor',
        ['equity investment', 'Equity Investment', 'EQUITY INVESTMENT'],
    )
    def test_descriptor_type_is_canonically_cased(self, descriptor):
        """However the filer cased the label, the type comes back one way.

        The match is case-insensitive, so returning the captured span verbatim
        made the filer's typography part of the value — OBDC's lowercase
        "equity" became a bucket of its own next to 'Preferred Equity' from
        every other branch, and grouping by investment_type split the concept
        in two.
        """
        _, _company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: Some Holdings LLC | Specialty finance {descriptor}',
            member_candidates=('specialty finance',),
        )
        assert investment_type == 'Equity'

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
        assert inv_type == 'First lien senior secured loan'

    def test_parse_complex_company_name(self):
        """Test parsing with complex company names containing commas."""
        # Company name with ampersand
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Smith & Jones LLC, Equity'
        )
        assert company == 'Smith & Jones LLC'
        assert inv_type == 'Equity'

    def test_parse_fdus_first_lien_debt_format(self):
        """Test parsing FDUS prose identifier with industry label."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investments Donovan Food Brokerage, LLC '
            'Business Services First Lien Debt Variable Index Spread (S + 6.00%) Variable Index Floor (2.00%) '
            'Rate Cash 10.29% Rate PIK 0.00% Investment date 2/23/2024 Maturity 2/23/2029'
        )
        assert company == 'Donovan Food Brokerage, LLC'
        assert inv_type == 'First Lien Debt'

    def test_parse_fdus_with_plain_inc_suffix(self):
        """Test parsing FDUS prose identifier when the company ends with Inc."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investments Quest Software US Holdings Inc. '
            'Information Technology Services First Lien Debt Variable Index Spread (S + 1.00%) Variable Index '
            'Floor (0.50%) Rate Cash 15.31% Rate PIK 6.75% Investment date 8/11/2025 Maturity 2/1/2030'
        )
        assert company == 'Quest Software US Holdings Inc.'
        assert inv_type == 'First Lien Debt'

    def test_parse_fdus_affiliate_with_parenthetical_alias(self):
        """Test parsing FDUS affiliate identifier with a parenthetical alias."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Affiliate Investments Spectra A&D Acquisition, Inc. '
            '(fka FDS Avionics Corp.) Aerospace & Defense Manufacturing First Lien Debt Variable Index Spread '
            '(S + 6.00%) Variable Index Floor(1.00%) Rate Cash 10.26% Rate PIK 0.00% Investment date 2/12/2021 '
            'Maturity 2/11/2026'
        )
        assert company == 'Spectra A&D Acquisition, Inc. (fka FDS Avionics Corp.)'
        assert inv_type == 'First Lien Debt'

    def test_parse_fdus_common_equity_format(self):
        """Test parsing FDUS affiliate identifier with equity instrument."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Affiliate Investments Pfanstiehl Inc Health Products '
            'Common Equity (2,550 units) Investment date 3/29/2013'
        )
        assert company == 'Pfanstiehl Inc'
        assert inv_type == 'Common Equity'

    def test_parse_fdus_subordinated_without_debt_suffix(self):
        """Test parsing FDUS subordinated instrument labels that omit 'Debt'."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investments Pinnergy, Ltd. '
            'Oil & Gas Services Subordinated Rate Cash 10.00% Rate PIK 0.00% '
            'Investment date 6/30/2022 Maturity 6/30/2027'
        )
        assert company == 'Pinnergy, Ltd.'
        assert inv_type == 'Subordinated'

    def test_parse_fdus_without_investments_in_prefix(self):
        """Test parsing FDUS labels whose relationship prefix omits 'Investments'."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate AMOpportunities, Inc. '
            'Information Technology Services First Lien Debt Cash 12.50% Rate PIK 0.00% '
            'Investment date 3/12/2025 Maturity 3/12/2029'
        )
        assert company == 'AMOpportunities, Inc.'
        assert inv_type == 'First Lien Debt'

    def test_parse_fdus_revolving_loan_with_parenthetical_alias(self):
        """Test parsing FDUS revolving loan labels with a parenthetical alias."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investments Ad Info Parent, Inc. '
            '(dba MediaRadar) Information Technology Services Revolving Loan ($1,442 unfunded commitment) '
            'Variable Index Spread (S + 5.25%) Variable Index Floor (1.00%) Rate Cash 9.25% Rate PIK 0.00% '
            'Investment date 11/1/2023 Maturity 9/16/2029'
        )
        assert company == 'Ad Info Parent, Inc. (dba MediaRadar)'
        assert inv_type == 'Revolving Loan'

    def test_parse_fdus_warrant_label(self):
        """Test parsing FDUS warrant labels with unit counts."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investments United Biologics, LLC '
            'Healthcare Services Warrant (57,469 units) Investment date 3/5/2012'
        )
        assert company == 'United Biologics, LLC'
        assert inv_type == 'Warrant'

    def test_parse_fdus_control_common_equity_label(self):
        """Test parsing FDUS control investment labels."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Control Investments US GreenFiber LLC '
            'Building Products Manufacturing Common Equity (2,522 units) Investment Date 7/3/2014'
        )
        assert company == 'US GreenFiber LLC'
        assert inv_type == 'Common Equity'

    def test_parse_fdus_duplicate_instrument_after_company(self):
        """Test parsing FDUS labels that repeat the instrument after an unfunded commitment."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investments Detechtion Holdings, LLC '
            'First Lien Debt ($1,250 unfunded commitments) Information Technology Services First Lien Debt '
            'Variable Index Spread (S + 5.75%) Variable Index Floor (2.25%) Rate Cash 10.04% Rate PIK 2.50% '
            'Investment date 6/21/2023 Maturity 6/21/2028'
        )
        assert company == 'Detechtion Holdings, LLC'
        assert inv_type == 'First Lien Debt'

    def test_parse_fdus_truncated_investments_prefix_typo(self):
        """Test parsing a leaked/truncated relationship prefix in the company name."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Non-control/Non-affiliate Investmnts Suited Connector LLC '
            'Information Technology Services Common Equity (97,808 units) Investment date 12/1/2021'
        )
        assert company == 'Suited Connector LLC'
        assert inv_type == 'Common Equity'

    def test_parse_fdus_leaked_affiliate_prefix_fragment(self):
        """Test parsing a leaked prefix fragment before the company name."""
        identifier, company, inv_type = _parse_investment_identifier(
            'us-gaap:InvestmentIdentifierAxis: Affiliate InvesAffiliate Investments Medsurant Holdings LLC '
            'Healthcare Services Preferred Equity (84,997 units) Investment date 4/12/2011'
        )
        assert company == 'Medsurant Holdings LLC'
        assert inv_type == 'Preferred Equity'

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'Debt Investments Business Services Alpha Midco, Inc. Investment First-lien loan '
                '($69,624 par, due 8/2028) Initial Acquisition Date 08/15/2019 Reference Rate and '
                'Spread SOFR + 6.88% Interest Rate 11.20%',
                ('alpha midco inc', 'business service'),
                'Alpha Midco, Inc.',
                'First-lien loan',
                id='tslx',
            ),
            pytest.param(
                'Investments\u2014non-controlled/non-affiliated Debt Investments Professional Services '
                'KWOR Acquisition, Inc. Investment First Lien Debt Reference Rate and Spread '
                'S + 6.25% Interest Rate 10.07% Maturity Date 02/28/2030 One',
                ('professional service',),
                'KWOR Acquisition, Inc.',
                'First Lien Debt',
                id='msdl',
            ),
            pytest.param(
                'Investments-non-controlled/non-affiliated Debt Investments Commercial Services '
                '& Supplies Hercules Borrower, LLC Investment C26First Lien Debt Reference Rate '
                'and Spread C + 4.75% Interest Rate 7.04% Maturity Date 12/15/2028',
                ('commercial service supplie',),
                'Hercules Borrower, LLC',
                'First Lien Debt',
                id='msdl-concatenated-member-code',
            ),
            pytest.param(
                'vInvestments-non-controlled/non-affiliated Debt Investments Food Products AMCP '
                'Pet Holdings, Inc. (Brightpet) Investment First Lien Debt Reference Rate and '
                'Spread S + 7.00% (incl. 3.00% PIK) Interest Rate 10.99% Maturity Date 01/04/2028',
                ('food product',),
                'AMCP Pet Holdings, Inc. (Brightpet)',
                'First Lien Debt',
                id='msdl-leaked-prefix-character',
            ),
            pytest.param(
                'Investments-non-controlled/non-affiliated Debt Investments-non-controlled/'
                'non-affiliated Debt Investments Professional Services Deerfield Dakota Holding, '
                'LLC Investment First Lien Debt Reference Rate and Spread S + 5.75% (incl. 2.75% '
                'PIK) Interest Rate 9.42% Maturity Date 09/13/2032 One Professional Services '
                'Deerfield Dakota Holding, LLC Investment First Lien Debt Reference Rate and '
                'Spread S + 5.75% (incl. 2.75% PIK) Interest Rate 9.42% Maturity Date 09/13/2032 One',
                ('professional service',),
                'Deerfield Dakota Holding, LLC',
                'First Lien Debt',
                id='msdl-duplicated-investment-path',
            ),
            pytest.param(
                'Investment Debt Investments - 216.4% United States - 205.6% 1st Lien/Senior '
                'Secured Debt - 195.3% AAG KP Borrower LLC (dba KUIU) Industry Textiles, Apparel '
                '& Luxury Goods Interest Rate 8.76% Reference Rate and Spread S + 5.00% Maturity 12/05/31',
                ('aag kp borrower llc dba kuiu',),
                'AAG KP Borrower LLC (dba KUIU)',
                '1st Lien/Senior Secured Debt',
                id='gsbd',
            ),
            pytest.param(
                'Advertising Printing & Publishing Accelerate360 Accelerate360 Holdings, LLC First '
                'Lien Secured Debt - Term Loan SOFR+600, 1.00% Floor Maturity Date 02/11/27',
                ('accelerate360 holding llc',),
                'Accelerate360 Holdings, LLC',
                'First Lien Secured Debt - Term Loan',
                id='mfic',
            ),
            pytest.param(
                'Aerospace & Defense ATS First Lien Senior Secured Loan SOFR Spread 5.75% '
                'Interest Rate 10.05% Maturity Date 7/12/2029',
                ('ats',),
                'ATS',
                'First Lien Senior Secured Loan',
                id='bcsf',
            ),
            pytest.param(
                'Equity Securities Issuer Name 48Forty Intermediate Holdings, Inc. - Common Equity '
                'Acquisition 11/5/2024 Industry Containers and Packaging',
                (),
                '48Forty Intermediate Holdings, Inc.',
                'Common Equity',
                id='pflt',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies First Lien '
                'Secured Debt Marketplace Events Acquisition, LLC Acquisition 12/19/2024 '
                'Maturity 12/19/2030',
                (),
                'Marketplace Events Acquisition, LLC',
                'First Lien Secured Debt',
                id='pflt-category-first',
            ),
            pytest.param(
                'CLO Equity BABSN 2018-4A SUB Industry Structured Subordinated Note '
                'Maturity Date 10/15/2030',
                ('babsn 2018 4a sub',),
                'BABSN 2018-4A SUB',
                'Subordinated Note',
                id='psbd',
            ),
            pytest.param(
                'Non-Control/Non-Affiliate Investments Debt Investments Systems Software '
                '3PL Central LLC (dba Extensiv) Investment Type Senior Secured Interest Rate '
                'SOFR+7.00%, 9.00% floor, 5.00% ETP Initial Acquisition Date 11/9/2022 '
                'Maturity Date 6/30/2026',
                ('system software',),
                '3PL Central LLC (dba Extensiv)',
                'Senior Secured',
                id='rway',
            ),
            pytest.param(
                'First Lien Senior Secured Canadian Debt Information Tulip.io Inc. Facility Type '
                'Term Loan All in Rate 15.00% Benchmark P Spread 4.00% PIK 3.00% Floor 8.00% '
                'Initial Acquisition Date 11/4/2024 Maturity 11/4/2028',
                ('tulip io inc',),
                'Tulip.io Inc.',
                'Term Loan',
                id='lien',
            ),
            pytest.param(
                'First Lien Secured Debt Issuer Name Kinetic Purchaser, LLC Acquisition 07/24/23 '
                'Maturity 11/10/27 Industry Consumer Products Current Coupon 10.15%',
                (),
                'Kinetic Purchaser, LLC',
                'First Lien Secured Debt',
                id='pnnt',
            ),
            pytest.param(
                'Controlled investments ProAir Holdco, LLC Type of Investment Common Stock and '
                'Membership Units Industry Classification Trading Companies & Distributors',
                ('proair holdco llc',),
                'ProAir Holdco, LLC',
                'Common Stock and Membership Units',
                id='bcic',
            ),
            pytest.param(
                'American Coastal Insurance Corp. Industry Insurance Security Unsecured Bond '
                'Interest Rate 7.25% Initial Acquisition Date 12/20/2022 Maturity 12/15/2027',
                ('american coastal insurance corp',),
                'American Coastal Insurance Corp.',
                'Unsecured Bond',
                id='gecc',
            ),
            pytest.param(
                '12 Interactive, LLC (D/B/A PerkSpot) | First Lien Debt (Revolver)',
                (),
                '12 Interactive, LLC (D/B/A PerkSpot)',
                'First Lien Debt (Revolver)',
                id='ofs',
            ),
            pytest.param(
                'Portfolio Company Debt Securities- United States Supply Chain Technology '
                'Inktavo, LLC Type of Investment Secured Loan Investment Date October 15, 2025 '
                'Maturity Date October 15, 2031 Interest Rate Variable interest rate SOFR 3 Month '
                'Term + 6.8%; EOT 0.0%',
                ('supply chain technology',),
                'Inktavo, LLC',
                'Secured Loan',
                id='trin',
            ),
        ],
    )
    def test_parse_structured_investment_formats(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        """Parse structured investment labels used by the Format 1 tickers."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'Other Investments Apidos CLO, Series 2015-23A Investment Structured Credit '
                '($4,000 par, due 10/2038) Initial Acquisition Date 9/3/2025 Reference Rate and '
                'Spread SOFR + 5.20% Interest Rate 9.10%',
                (),
                'Apidos CLO, Series 2015-23A',
                'Structured Credit',
                id='structured-credit-with-investment-anchor',
            ),
            pytest.param(
                'Other Investments CIFC Funding Ltd, Series 2020 -4A Structured Credit '
                '($4,000 par, due 1/2040) Initial Acquisition Date 7/29/2025 Reference Rate and '
                'Spread SOFR + 4.90% Interest Rate 8.80%',
                (),
                'CIFC Funding Ltd, Series 2020 -4A',
                'Structured Credit',
                id='structured-credit-without-investment-anchor',
            ),
            pytest.param(
                'Debt Investments Business Services BCTO Ignition Purchaser, Inc Investment '
                'First-lien holdco loan ($54,435 par, due 10/2030) Initial Acquisition Date '
                '4/18/2023 Reference Rate and Spread SOFR + 7.50% Interest Rate 11.37% PIK',
                ('business service',),
                'BCTO Ignition Purchaser, Inc',
                'First-lien holdco loan',
                id='first-lien-holdco-loan',
            ),
            pytest.param(
                'Debt Investments Education Astra Acquisition Corp. Investment Second-lien loan '
                '($40,804 par, due 10/2029) Initial Acquisition Date 10/22/2021 Reference Rate and '
                'Spread P + 9.88% Interest Rate 16.63%',
                ('education',),
                'Astra Acquisition Corp.',
                'Second-lien loan',
                id='second-lien-loan',
            ),
            pytest.param(
                'Debt Investments Financial Services Passport Labs, Inc. Investment Convertible '
                'Promissory Note A ($1,086 par, due 8/2026) Initial Acquisition Date 3/2/2023 '
                'Reference Rate and Spread 8.00% Interest Rate 8.00%',
                ('financial service',),
                'Passport Labs, Inc.',
                'Convertible Promissory Note A',
                id='convertible-promissory-note',
            ),
            pytest.param(
                'Debt Investments Financial Services Payroc Buyer, LLC Investment Promissory Note '
                '($6,000 par, due 9/2030) Initial Acquisition Date 9/30/2025 Reference Rate and '
                'Spread 5.50% Interest Rate 5.50%',
                ('financial service',),
                'Payroc Buyer, LLC',
                'Promissory Note',
                id='promissory-note',
            ),
            pytest.param(
                'Debt Investments Manufacturing ASP Unifrax Holdings, Inc. Second-lien note '
                '($2,024 par, due 9/2029) Initial Acquisition Date 8/31/2023 Reference Rate and '
                'Spread 7.10% Interest Rate 7.10% (incl. 1.25% PIK)',
                ('manufacturing',),
                'ASP Unifrax Holdings, Inc.',
                'Second-lien note',
                id='second-lien-note',
            ),
            pytest.param(
                'Debt Investments Other Boréal Bidco First-lien note (EUR 13,605 par, due 3/2032) '
                'Initial Acquisition Date 3/24/2025 Reference Rate and Spread E + 7.25% Interest '
                'Rate 9.27% (inclu. 5.75% PIK)',
                ('other',),
                'Boréal Bidco',
                'First-lien note',
                id='first-lien-note',
            ),
            pytest.param(
                'Equity and Other Investments Business Services Newark FP Co-Invest, L.P. '
                'Partnership (2,527,719 units) Initial Acquisition Date 11/8/2023',
                ('business service',),
                'Newark FP Co-Invest, L.P.',
                'Partnership',
                id='partnership',
            ),
            pytest.param(
                'Equity and Other Investments Financial Services TS Imagine, Inc. Class AA Units '
                '(19,093 units) Initial Acquisition Date 11/1/2024 Reference Rate and Spread '
                '20.00% Interest Rate 20.00%',
                ('financial service',),
                'TS Imagine, Inc.',
                'Class AA Units',
                id='class-aa-units',
            ),
            pytest.param(
                'Equity and Other Investments Hotel, Gaming and Leisure IRGSE Holding Corp. '
                'Class C-1 Units (8,800,000 units) Initial Acquisition Date 12/21/2018',
                ('hotel gaming and leisure',),
                'IRGSE Holding Corp.',
                'Class C-1 Units',
                id='class-c1-units',
            ),
            pytest.param(
                'Equity and Other Investments Internet Services Khoros, LLC Earnout Interests '
                'Initial Acquisition Date 5/23/2025',
                ('internet service',),
                'Khoros, LLC',
                'Earnout Interests',
                id='earnout-interests',
            ),
            pytest.param(
                'Equity and Other Investments Pharmaceuticals Elysium BidCo Limited Convertible '
                'Preference Shares (4,976,563 Shares) Initial Acquisition Date 12/11/2024',
                ('pharmaceutical',),
                'Elysium BidCo Limited',
                'Convertible Preference Shares',
                id='convertible-preference-shares',
            ),
            pytest.param(
                'Equity and Other Investments Financial Services Passport Labs, Inc. Warrants '
                '(17,534 warrants) Initial Acquisition Date 4/28/2021',
                ('financial service',),
                'Passport Labs, Inc.',
                'Warrants',
                id='warrant-quantity-is-not-company',
            ),
            pytest.param(
                'Equity and Other Investments Retail and Consumer Products Copper Bidco, LLC '
                'Trust Certificates (996,958 Certificates) Initial Acquisition Date 1/30/2021',
                ('retail and consumer product',),
                'Copper Bidco, LLC',
                'Trust Certificates',
                id='certificate-quantity-is-not-company',
            ),
        ],
    )
    def test_parse_tslx_additional_structured_types(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        """Parse additional TSLX structured instrument variants."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            pytest.param(
                '2.9% Canada - 0.0% Common Stock - 0.0% Prairie Provident Resources, Inc.',
                'Prairie Provident Resources, Inc.',
                'Common Stock',
                id='common-stock',
            ),
            pytest.param(
                '2.9% United States - 2.9% Preferred Stock - 1.9% CloudBees, Inc.',
                'CloudBees, Inc.',
                'Preferred Stock',
                id='preferred-stock',
            ),
            pytest.param(
                '226.3% United States \u2013 214.3% 1st Lien/Senior Secured Debt \u2013 200.8% '
                'A Place For Mom, Inc.',
                'A Place For Mom, Inc.',
                '1st Lien/Senior Secured Debt',
                id='first-lien-senior-secured',
            ),
            pytest.param(
                '226.3% United States \u2013 214.3% 2nd Lien/Senior Secured Debt - 3.4% '
                'MPI Engineered Technologies, LLC',
                'MPI Engineered Technologies, LLC',
                '2nd Lien/Senior Secured Debt',
                id='second-lien-senior-secured',
            ),
            pytest.param(
                '226.3% United States \u2013 214.3% Unsecured Debt - 0.6% Wine.com, Inc.',
                'Wine.com, Inc.',
                'Unsecured Debt',
                id='unsecured-debt',
            ),
            pytest.param(
                'Investment Debt Investments \u2013 226.3% United States \u2013 214.3% '
                '1st Lien/Last-Out Unitranche (14) - 9.5% EDB Parent, LLC '
                '(dba Enterprise DB) Industry Software Interest Rate 10.84% Reference Rate and '
                'Spread S + 7.00% Maturity 07/07/28 Two',
                'EDB Parent, LLC (dba Enterprise DB)',
                '1st Lien/Last-Out Unitranche',
                id='last-out-unitranche',
            ),
        ],
    )
    def test_parse_gsbd_percentage_hierarchy(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        """Parse GSBD hierarchy paths without retaining percentage rollups."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    def test_parse_gsbd_percentage_hierarchy_uses_company_member_boundary(self):
        """Stop the company before an unlabeled industry and rate fields."""
        raw_identifier = (
            'Investment Debt Investments - 226.3% United States - 214.3% '
            '1st Lien/Senior Secured Debt - 200.8% Rotation Buyer, LLC '
            '(dba Rotating Machinery Services) Machinery Interest Rate 8.47% '
            'Reference Rate and Spread S + 4.75% Maturity 12/02/31'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('rotation buyer llc dba rotating machinery service',),
        )
        assert company == 'Rotation Buyer, LLC (dba Rotating Machinery Services)'
        assert investment_type == '1st Lien/Senior Secured Debt'

    def test_parse_gsbd_percentage_hierarchy_handles_joined_industry_field(self):
        """Handle source labels that omit whitespace after the Industry field."""
        raw_identifier = (
            'Investment Debt Investments - 226.3% United States - 214.3% '
            '1st Lien/Senior Secured Debt - 200.8% Vardiman Black Holdings, LLC '
            '(dba Specialty Dental Brands) IndustryHealth Care Providers & Services '
            'Reference Rate and Spread S + 7.00% PIK Maturity 03/18/27'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == 'Vardiman Black Holdings, LLC (dba Specialty Dental Brands)'
        assert investment_type == '1st Lien/Senior Secured Debt'

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'Trading Companies & Distributors Banner Solutions Banner Parent Holdings, Inc. '
                'Common Equity - Common Stock',
                ('trading companie distributor', 'banner solution'),
                'Banner Parent Holdings, Inc.',
                'Common Equity - Common Stock',
                id='common-equity-with-portfolio-alias',
            ),
            pytest.param(
                'Trading Companies & Distributors ORS Nasco WC ORS Holdings, L.P. '
                'Common Equity - Common Stock',
                ('trading companie distributor', 'ors nasco'),
                'WC ORS Holdings, L.P.',
                'Common Equity - Common Stock',
                id='company-with-commas',
            ),
            pytest.param(
                'Pharmaceuticals Alcresta Therapeutics Inc. Alcresta Holdings, LP '
                'Preferred Equity - Preferred Equity',
                ('pharmaceutical', 'alcresta therapeutic inc'),
                'Alcresta Holdings, LP',
                'Preferred Equity - Preferred Equity',
                id='preferred-equity',
            ),
            pytest.param(
                'Passenger Airlines Merx Aviation Finance, LLC Merx Aviation Finance, LLC '
                'Common Equity - Membership Interests',
                ('passenger airline',),
                'Merx Aviation Finance, LLC',
                'Common Equity - Membership Interests',
                id='duplicated-company',
            ),
            pytest.param(
                'Chemicals Carbonfree Chemicals SPE I LLC '
                '(f/k/a Maxus Capital Carbon SPE I LLC) FC2 LLC Secured Debt - Promissory Note '
                'Maturity Date 10/14/27',
                ('chemical', 'carbonfree chemical spe i llc'),
                'FC2 LLC',
                'Secured Debt - Promissory Note',
                id='company-after-former-name',
            ),
            pytest.param(
                'Consumer Finance US Auto Auto Pool 2023 Trust (Del. Stat. Trust) '
                'Structured Products and Other - Membership Interests Maturity Date 02/28/29',
                ('consumer finance', 'us auto'),
                'Auto Pool 2023 Trust (Del. Stat. Trust)',
                'Structured Products and Other - Membership Interests',
                id='structured-products',
            ),
            pytest.param(
                'Ground Transportation Third Lane Mobility Inc. Warrants – Warrants',
                ('ground transportation',),
                'Third Lane Mobility Inc.',
                'Warrants – Warrants',
                id='unicode-type-separator',
            ),
            pytest.param(
                'Commercial Services & Supplies Jacent Jacent Strategic Merchandising, LLC '
                'Common Equity - Common Stock',
                (
                    'commercial service supplie',
                    'jacent',
                    'jacent strategic merchandising',
                ),
                'Jacent Strategic Merchandising, LLC',
                'Common Equity - Common Stock',
                id='prefer-complete-company-member',
            ),
            pytest.param(
                'Software Asure Software Asure Software, Inc. First Lien Secured Debt - Term Loan '
                'SOFR+500, 2.00% Floor Maturity Date 04/01/30',
                ('software', 'asure software', 'inc'),
                'Asure Software, Inc.',
                'First Lien Secured Debt - Term Loan',
                id='ignore-generic-company-member',
            ),
        ],
    )
    def test_parse_mfic_paired_investment_type(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        """Parse MFIC industry, portfolio company, issuer, and paired type paths."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            (
                'Controlled Investments Merx Aviation Finance, LLC, Membership Interests',
                'Merx Aviation Finance, LLC',
                'Membership Interests',
            ),
            (
                'Affiliated Investments Arrivia, Inc. '
                '(International Cruise & Excursion Gallery, Inc),Membership Interests',
                'Arrivia, Inc. (International Cruise & Excursion Gallery, Inc)',
                'Membership Interests',
            ),
        ],
    )
    def test_parse_mfic_relationship_investment(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        """Parse MFIC relationship-prefixed comma labels with legal-name commas."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'U.S. Dollar Automotive Cardo First Lien Senior Secured Loan SOFR Spread 5.25% '
                'Interest Rate 8.98% Maturity Date 5/12/2028',
                ('automotive',),
                'Cardo',
                'First Lien Senior Secured Loan',
                id='us-dollar-debt',
            ),
            pytest.param(
                'European Currency Healthcare & Pharmaceuticals Mertus 522. GmbH First Lien '
                'Senior Secured Loan EURIBOR Spread 4.00% (3.00% PIK) Interest Rate 9.12% '
                'Maturity Date 5/28/2028',
                ('healthcare pharmaceutical',),
                'Mertus 522. GmbH',
                'First Lien Senior Secured Loan',
                id='european-currency-debt',
            ),
            pytest.param(
                'British Pound Services: Business Parcel2Go Equity Interest',
                ('service business',),
                'Parcel2Go',
                'Equity Interest',
                id='british-pound-equity',
            ),
            pytest.param(
                'Australian Dollar Media: Advertising, Printing & Publishing T G I Sport Bidco '
                'Pty Ltd First Lien Senior Secured Loan BBSY Spread 7.00% Interest Rate 10.60% '
                'Maturity Date 4/30/2026',
                ('media advertising printing publishing',),
                'T G I Sport Bidco Pty Ltd',
                'First Lien Senior Secured Loan',
                id='australian-dollar-debt',
            ),
            pytest.param(
                'New Zealand Dollar Beverage, Food & Tobacco Hellers First Lien Senior Secured '
                'Loan - Delayed Draw BBKM Spread 3.63% (1.88% PIK) Interest Rate 9.29% '
                'Maturity Date 9/27/2030',
                ('beverage food tobacco',),
                'Hellers',
                'First Lien Senior Secured Loan - Delayed Draw',
                id='new-zealand-dollar-delayed-draw',
            ),
            pytest.param(
                'Non-Controlled/Affiliate Investments Aerospace & Defense Ansett Aviation '
                'Training Equity Interest',
                ('aerospace defense',),
                'Ansett Aviation Training',
                'Equity Interest',
                id='non-controlled-affiliate-equity',
            ),
            pytest.param(
                'Non-controlled/Non-Affiliated Investments High Tech Industries Applitools '
                'Equity Interest One',
                ('high tech industrie',),
                'Applitools',
                'Equity Interest',
                id='non-affiliated-equity-suffix',
            ),
            pytest.param(
                'Controlled Affiliate Investments Investment Vehicles Bain Capital Senior Loan '
                'Program, LLC Preferred Equity Interest Investment Vehicles',
                ('investment vehicle',),
                'Bain Capital Senior Loan Program, LLC',
                'Preferred Equity Interest',
                id='controlled-affiliate-preferred-equity-interest',
            ),
            pytest.param(
                'Non-controlled/Non-Affiliated Investments Automotive Gills Point S First Lien '
                'Senior Secured Loan - Revolver Maturity Date 5/17/2029',
                ('automotive',),
                'Gills Point S',
                'First Lien Senior Secured Loan - Revolver',
                id='relationship-prefixed-revolver',
            ),
            pytest.param(
                'High Tech Industries Govineer Solutions (fka Black Mountain) First Lien Senior '
                'Secured Loan SOFR Spread 5.00% Interest Rate 8.67% Maturity Date 10/7/2030',
                ('high tech industrie', 'govineer solution', 'black mountain'),
                'Govineer Solutions (fka Black Mountain)',
                'First Lien Senior Secured Loan',
                id='former-name-is-not-company',
            ),
            pytest.param(
                'European Currency Services: Business Fiduciaire Jean-Marc Faber (FJMF) First '
                'Lien Senior Secured Loan - Delayed Draw EURIBOR Spread 5.50% Interest Rate '
                '7.58% Maturity Date 4/3/2032',
                ('service business', 'fiduciaire jean marc faber', 'fjmf'),
                'Fiduciaire Jean-Marc Faber (FJMF)',
                'First Lien Senior Secured Loan - Delayed Draw',
                id='parenthetical-abbreviation-is-not-company',
            ),
        ],
    )
    def test_parse_bcsf_structured_investment(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        """Parse BCSF currency and relationship-prefixed investment paths."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'in Non-Controlled, Non-Affiliated Portfolio Companies Common Equity/Warrants '
                'Magnolia Topco, LP -',
                'Magnolia Topco, LP',
                'Common Equity/Warrants',
                id='truncated-prefix-common-equity-warrants',
            ),
            pytest.param(
                'in Non-Controlled, Non-Affiliated Portfolio Companies Preferred Equity '
                'Accounting Platform Holdings, Inc. -',
                'Accounting Platform Holdings, Inc.',
                'Preferred Equity',
                id='preferred-equity',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Subordinate '
                'Debt ORL Holdco, Inc. - Unfunded Convertible Notes Acquisition 8/2/2024 '
                'Maturity 03/8/2028 Industry Consumer Finance',
                'ORL Holdco, Inc.',
                'Subordinate Debt - Unfunded Convertible Notes',
                id='subordinate-debt-detail',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Subordinate '
                'Debt Wash & Wax Systems, LLC - Subordinate Debt Acquisition 4/30/2025 '
                'Maturity 07/30/2028 Industry Consumer Services Current Coupon 12.00%',
                'Wash & Wax Systems, LLC',
                'Subordinate Debt',
                id='repeated-subordinate-debt-detail',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Preferred '
                'Equity Magnolia Topco, LP - Preferred Equity - Class A Acquisition 7/25/2023 '
                'Industry Automobiles',
                'Magnolia Topco, LP',
                'Preferred Equity - Class A',
                id='repeated-preferred-equity-prefix',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies First Lien '
                'Secured Debt North American Rail Solutions, LLC - Funded Revolver Acquisitions '
                '8/29/2025 Maturity 08/29/2031 Industry Manufacturing/Basic Industry',
                'North American Rail Solutions, LLC',
                'First Lien Secured Debt - Funded Revolver',
                id='plural-acquisitions',
            ),
            pytest.param(
                'Investments in Controlled, Affiliated Portfolio Companies Equity Interests '
                'PennantPark Senior Secured Loan Fund I LLC - Common Equity Acquisition '
                '6/16/2017 Industry Financial Services',
                'PennantPark Senior Secured Loan Fund I LLC',
                'Equity Interests - Common Equity',
                id='plural-equity-interests',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Preferred '
                'Equity AFC Acquisitions, Inc. Preferred Equity - Series F-2 Acquisition '
                '12/7/2023 Industry Distributors',
                'AFC Acquisitions, Inc.',
                'Preferred Equity - Series F-2',
                id='repeated-type-without-company-delimiter',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies First Lien '
                'Secured Debt GGG Midco, LLC – Unfunded Revolver Acquisition 09/27/2024 '
                'Maturity 09/27/2030 Industry Diversified Consumer Services',
                'GGG Midco, LLC',
                'First Lien Secured Debt - Unfunded Revolver',
                id='unicode-facility-delimiter',
            ),
            pytest.param(
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies First Lien '
                'Secured Debt Meadowlark Acquirer, LLC- Funded Revolver Acquisition 12/9/2021 '
                'Maturity 12/10/2027 Industry Professional Services',
                'Meadowlark Acquirer, LLC',
                'First Lien Secured Debt - Funded Revolver',
                id='unspaced-facility-delimiter',
            ),
            pytest.param(
                '/Warrants Kentucky Racing Holdco, LLC - Warrants',
                'Kentucky Racing Holdco, LLC',
                'Warrants',
                id='truncated-warrants',
            ),
        ],
    )
    def test_parse_pflt_category_first_investment(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        """Parse PFLT category-first labels and optional security details."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    def test_parse_pflt_issuer_name_before_facility_type(self):
        raw_identifier = (
            'First Lien Secured Debt Issuer Name Paving Lessor Corp. First Lien -Term Loan '
            'Acquisition 8/28/2025 Maturity 7/1/2031 Industry Business Services'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == 'Paving Lessor Corp.'
        assert investment_type == 'Term Loan'

    @pytest.mark.parametrize(
        'company_name',
        [
            'Fidelity Investments Money Market Government Portfolio - Institutional Class',
            'Morgan Stanley Liquidity Funds US Dollar Treasury Liquidity Fund - Institutional Class',
        ],
    )
    def test_parse_psbd_short_term_investment(self, company_name):
        raw_identifier = f'Short-Term Investments {company_name}'
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == company_name
        assert investment_type == 'Short-Term Investments'

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'CLO Mezzanine AIMCO 2015-AA FR4 Industry Structured Note Interest Rate 11.41% '
                '(S + 7.18%) Maturity Date 10/17/2038',
                'AIMCO 2015-AA FR4',
                'Structured Note',
                id='clo-mezzanine',
            ),
            pytest.param(
                'Debt Investments Corporate Bonds Altice Financing S.A. Industry Diversified '
                'Telecommunication Services Interest Rate 0.05 Maturity Date 1/15/2028',
                'Altice Financing S.A.',
                'Corporate Bonds',
                id='corporate-bonds',
            ),
            pytest.param(
                'Equity Investments Aimbridge Acquisition Co., Inc. Industry Hotels, Restaurants '
                'and Leisure',
                'Aimbridge Acquisition Co., Inc.',
                'Equity',
                id='equity-investments',
            ),
        ],
    )
    def test_parse_psbd_category_prefixed_investment(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        """Parse PSBD category-prefixed CLO, bond, and equity labels."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            pytest.param(
                'Warrant Application Software 3DNA Corp. (dba NationBuilder)',
                ('application software',),
                '3DNA Corp. (dba NationBuilder)',
                'Warrant',
                id='singular-warrant',
            ),
            pytest.param(
                'Warrants Application Software Piano Software, Inc.',
                ('application software',),
                'Piano Software, Inc.',
                'Warrants',
                id='plural-warrants',
            ),
            pytest.param(
                'Warrant Technology Hardware & Equipment Brivo, Inc.Investment',
                ('technology hardware equipment',),
                'Brivo, Inc.',
                'Warrant',
                id='attached-investment-token',
            ),
            pytest.param(
                'Warrant Technology Hardware & Equipment Linxup,',
                ('technology hardware equipment',),
                'Linxup',
                'Warrant',
                id='trailing-comma',
            ),
        ],
    )
    def test_parse_rway_leading_warrant(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        """Parse RWAY warrant labels with an industry before the company."""
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    def test_parse_rway_full_warrant_identifier(self):
        raw_identifier = (
            'Non-Control/Non-Affiliate Investments Warrant Application Software 3DNA Corp. '
            '(dba NationBuilder) Investment Type Warrants Series C-1 Preferred Stock Initial '
            'Acquisition Date 12/28/2018 Maturity Date 12/28/2028'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('application software',),
        )
        assert company == '3DNA Corp. (dba NationBuilder)'
        assert investment_type == 'Warrants'

    def test_parse_rway_attached_investment_type_field(self):
        raw_identifier = (
            'Non-Control/Non-Affiliate Investments Warrant Technology Hardware & Equipment '
            'Linxup, LLCInvestment Type Warrants Success fee Initial Acquisition Date 11/3/2023 '
            'Maturity Date 11/3/2033'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('technology hardware equipment',),
        )
        assert company == 'Linxup, LLC'
        assert investment_type == 'Warrants'

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Control Investments Equity Investments Runway-Cadma I LLC',
                (),
                'Runway-Cadma I LLC',
                'Equity',
            ),
            (
                'Affiliate Investments Debt Investments Senior Secured Gynesonics, Inc.',
                (),
                'Gynesonics, Inc.',
                'Senior Secured',
            ),
            (
                'Control Investments Equity Investments Multi-Sector Holdings Runway-Cadma I LLC '
                'Investment Type Equity 50% Equity Interest Initial Acquisition Date 3/6/2024',
                ('multi sector holding',),
                'Runway-Cadma I LLC',
                'Equity',
            ),
        ],
    )
    def test_parse_rway_relationship_category(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    def test_parse_rway_revolver_metadata(self):
        raw_identifier = (
            'Non-Control/Non-Affiliate Investments Debt Investments Systems Software Digicert, '
            'Inc. (Revolver) Investment Type Senior Secured Interest Rate SOFR+5.75%, 6.50% '
            'floor Initial Acquisition Date 7/30/2025 Maturity Date 7/30/2030'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('system software', 'revolver'),
        )
        assert company == 'Digicert, Inc.'
        assert investment_type == 'Senior Secured - Revolver'

    def test_parse_rway_revolver_after_company_alias(self):
        raw_identifier = (
            'Non-Control/Non-Affiliate Investments Debt Investments Commercial & Professional '
            'Services Shepherd Intermediate, LLC (dba FHAS) (Revolver) Investment Type Senior '
            'Secured Interest Rate SOFR+7.25%, 8.25% floor, Initial Acquisition Date 7/10/2025 '
            'Maturity Date 7/10/2030'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=(
                'commercial professional service',
                'shepherd intermediate llc dba fha',
            ),
        )
        assert company == 'Shepherd Intermediate, LLC (dba FHAS)'
        assert investment_type == 'Senior Secured - Revolver'

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_type'),
        [
            (
                'U.S. Preferred Stock Real Estate and Rental and Leasing Workbox Holdings Inc. '
                'A-1 Preferred Initial Acquisition Date 5/20/2024',
                'A-1 Preferred',
            ),
            (
                'U.S. Warrants Real Estate and Rental and Leasing Workbox Holdings Inc. A-4 '
                'Warrants Initial Acquisition Date 5/20/2024',
                'A-4 Warrants',
            ),
        ],
    )
    def test_parse_lien_us_equity(self, raw_identifier, expected_type):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=(
                'real estate and rental and leasing',
                'workbox holding inc member',
            ),
        )
        assert company == 'Workbox Holdings Inc.'
        assert investment_type == expected_type

    def test_parse_lien_second_lien_debt(self):
        raw_identifier = (
            'US Corporate Debt Second Lien Senior Secured Cannabis Remedy - Maryland Wellness, '
            'LLC Facility Type Delayed Draw Term Loan All in Rate 20.25% Benchmark P Spread 9.00% '
            'PIK 3.50% Floor 7.75% Initial Acquisition Date 10/1/2024 Maturity 8/1/2028'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('cannabi', 'remedy maryland wellness llc member'),
        )
        assert company == 'Remedy - Maryland Wellness, LLC'
        assert investment_type == 'Delayed Draw Term Loan'

    def test_parse_lien_company_field_delimiter(self):
        raw_identifier = (
            'US Corporate Debt First Lien Senior Secured U.S. Debt Information Protect Animals '
            'With Satellites LLC (Halo Collar) - Facility Type Incremental Term Loan All in Rate '
            '13.25% Initial Acquisition Date 10/1/2024 Maturity 11/1/2026'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('information',),
        )
        assert company == 'Protect Animals With Satellites LLC (Halo Collar)'
        assert investment_type == 'Incremental Term Loan'

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            (
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Second Lien '
                'Secured Debt of Net Assets Issuer Name Burgess Point Purchaser Corporation '
                'Acquisition 07/26/2022 Maturity 07/28/2030 Industry Auto Sector Current Coupon '
                '12.77% Basis Point Spread Above Index 3M SOFR+910',
                'Burgess Point Purchaser Corporation',
                'Second Lien Secured Debt',
            ),
            (
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Subordinate '
                'Debt/Corporate Notes of Net Assets Issuer Name Beacon Behavioral Holdings, LLC '
                'Acquisition 06/21/2024 Maturity 06/21/2030 Industry Healthcare, Education and '
                'Childcare Current Coupon PIK 15.00%',
                'Beacon Behavioral Holdings, LLC',
                'Subordinate Debt/Corporate Notes',
            ),
            (
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Preferred '
                'Equity/Partnership Interests of Net Assets Issuer Name AFC Acquisitions, Inc. '
                '(F-2 Series) Acquisition 12/07/2023 Industry Distribution',
                'AFC Acquisitions, Inc.',
                'Preferred Equity/Partnership Interests - F-2 Series',
            ),
            (
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies Common Equity/'
                'Partnership Interests/Warrants of Net Assets Issuer Name Kentucky Racing Holdco, '
                'LLC (Warrants) Acquisition 04/16/2019 Industry Hotels, Motels, Inns and Gaming',
                'Kentucky Racing Holdco, LLC',
                'Common Equity/Partnership Interests/Warrants',
            ),
            (
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies US Government '
                'Securities of Net Assets Issuer Name U.S. Treasury Bill Acquisition 01/02/2026 '
                'Maturity 01/27/2026 Industry Short-Term U.S. Government Securities Current Coupon '
                '3.98%',
                'U.S. Treasury Bill',
                'US Government Securities',
            ),
            (
                'Equity Securities Issuer Name Wash & Wax Group, LP - Common Equity - Common '
                'Equity Acquisition 04/30/25 Industry Business Services',
                'Wash & Wax Group, LP',
                'Common Equity - Common Equity',
            ),
            (
                'Investments in Non-Controlled, Non-Affiliated Portfolio Companies First Lien '
                'Secured Debt Issuer PCS MIDCO, Inc. - Unfunded Term Loan - Third Amendment '
                'Acquisition 03/01/2024 Maturity 03/24/2028 Industry Financial Services',
                'PCS MIDCO, Inc.',
                'First Lien Secured Debt - Unfunded Term Loan - Third Amendment',
            ),
        ],
    )
    def test_parse_pnnt_issuer_path(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies Common Stock and '
                'Membership Units AAPC Holdings, LLC Health Care Providers & Services',
                ('health care provider service',),
                'AAPC Holdings, LLC',
                'Common Stock and Membership Units',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies Common Stock and '
                'Membership Units BGPT Maverick, L.P. (Metric Inc.) Communications Equipment',
                ('communication equipment',),
                'BGPT Maverick, L.P. (Metric Inc.)',
                'Common Stock and Membership Units',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies Preferred Stock '
                'and Units Prosper Marketplace Household Products',
                ('household product',),
                'Prosper Marketplace',
                'Preferred Stock and Units',
            ),
        ],
    )
    def test_parse_bcic_continuation_units(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Investments in Affiliate Portfolio Companies Collateralized Loan Obligations '
                'JMP Credit Advisors CLO IV LTD CLO Fund Securities Maturity 07/17/29',
                (),
                'JMP Credit Advisors CLO IV LTD',
                'CLO Fund Securities',
            ),
            (
                'Investments in Affiliate Portfolio Companies Derivatives Princeton Medspa '
                'Partners, LLC Diversified Consumer Services',
                ('diversified consumer service',),
                'Princeton Medspa Partners, LLC',
                'Derivatives',
            ),
            (
                'Investments in Affiliate Portfolio Companies Joint Ventures Series B-Great '
                'Lakes Funding II LLC Joint Venture',
                (),
                'Series B-Great Lakes Funding II LLC',
                'Joint Venture',
            ),
            (
                'Investments in Controlled Afilliated Portfolio Companies Asset Manager '
                'Affiliates Asset Management Company Asset Management Company',
                (),
                'Asset Management Company',
                'Asset Manager Affiliates',
            ),
        ],
    )
    def test_parse_bcic_portfolio_category(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        'raw_identifier',
        [
            'Non Controlled Affiliated Investments [Member]',
            'Non Controlled Affiliated and Controlled Investments [Member]',
        ],
    )
    def test_parse_bcic_relationship_rollup(self, raw_identifier):
        _, _, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert investment_type == 'Unknown'

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien /Senior '
                'Secured Debt Keg Logistics LLC Diversified Consumer Services Interest Rate '
                '10.73% Reference Rate and Spread SOFR + 6.75%, 0.50% PIK Floor 1.00% Maturity '
                '11/23/27',
                ('diversified consumer service',),
                'Keg Logistics LLC',
                'First Lien/Senior Secured Debt',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien /Senior '
                'Secured Debt Florida Food Products, LLC First Lien, Term Loan A Food Products '
                'Interest Rate 9.43% Reference Rate and Spread SOFR + 5.50% Floor 2.00% Maturity '
                '10/15/30',
                ('food product',),
                'Florida Food Products, LLC',
                'First Lien/Senior Secured Debt - First Lien, Term Loan A',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien /Senior '
                'Secured Debt Morae Global Corporation (Revolver) IT Services Interest Rate '
                '12.04% Reference Rate and Spread SOFR + 8.00% Floor 2.00% Maturity 10/31/28',
                ('it service',),
                'Morae Global Corporation',
                'First Lien/Senior Secured Debt - Revolver',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien/Senior '
                'Secured Debt Bradshaw International Parent Corp. (Revolver) Specialty Retail '
                'Reference Rate and Spread SOFR + 5.75% Floor 1.00% Maturity 10/21/26',
                ('specialty retail',),
                'Bradshaw International Parent Corp.',
                'First Lien/Senior Secured Debt - Revolver',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien/Senior '
                'Secured Debt Anthem Sports & Entertainment Inc. (2025 Delayed Draw Term Loan) '
                'Media Interest Rate 9.43% Reference Rate and Spread SOFR + 5.50%, 9.43% PIK '
                'Floor 1.00% Maturity 11/15/27',
                ('media',),
                'Anthem Sports & Entertainment Inc.',
                'First Lien/Senior Secured Debt - 2025 Delayed Draw Term Loan',
            ),
            (
                'Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien/Senior '
                'Secured Debt Dodge Data & Analytics LLC (Second Out) Professional Services '
                'Interest Rate 8.75% Reference Rate and Spread SOFR + 4.75% Floor 0.50% Maturity '
                '02/28/29',
                ('professional service',),
                'Dodge Data & Analytics LLC',
                'First Lien/Senior Secured Debt - Second Out',
            ),
        ],
    )
    def test_parse_bcic_lien_category(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Non-controlled affiliated investments GreenPark Infrastructure, LLC - Series A '
                'Type of Investment Preferred Stock and Units Industry Classification Commercial '
                'Services & Supplies',
                ('greenpark infrastructure llc',),
                'GreenPark Infrastructure, LLC',
                'Preferred Stock and Units - Series A',
            ),
            (
                'Non-controlled affiliated investments Princeton Medspa Partners, LLC - Put '
                'Option Type of Investment Derivatives Industry Classification Diversified '
                'Consumer Services',
                ('princeton medspa partner llc',),
                'Princeton Medspa Partners, LLC',
                'Derivatives - Put Option',
            ),
        ],
    )
    def test_parse_bcic_security_detail(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            (
                'Advancion Industry Chemicals Security 1st Lien, Secured Loan Interest Rate 1M '
                'SOFR + 4.00% (7.82%) Initial Acquisition Date 08/26/2025 Maturity 11/24/2027',
                'Advancion',
                '1st Lien, Secured Loan',
            ),
            (
                'Blackstone Secured Lending Fund Industry Closed-End Fund Security Common Equity '
                'Initial Acquisition Date 09/25/2024',
                'Blackstone Secured Lending Fund',
                'Common Equity',
            ),
            (
                'Commercial Vehicle Group, Inc. Industry Transportation Equipment Manufacturing '
                'Security Tranche 1 Warrants Initial Acquisition Date 07/31/2025',
                'Commercial Vehicle Group, Inc.',
                'Tranche 1 Warrants',
            ),
            (
                'Ryan, LLC Industry Business Services Security 1st Lien, Secured Loan 1M SOFR + '
                '3.50% (7.22%) Initial Acquisition Date 11/05/2025 Maturity 11/05/2032',
                'Ryan, LLC',
                '1st Lien, Secured Loan',
            ),
            (
                'Trident TPI Holding, Inc. Industry Packaging Unsecured Bond Interest Rate 12.75 '
                'Initial Acquisition Date 11/26/2025 Maturity 12/31/2028',
                'Trident TPI Holding, Inc.',
                'Unsecured Bond',
            ),
            (
                'MFB Northern Inst Funds Treas Portfolio Premier CL Short-Term Investments Money '
                'Market Interest Rate 4.16%%',
                'MFB Northern Inst Funds Treas Portfolio Premier CL',
                'Short-Term Investments - Money Market',
            ),
            (
                'CLO Formation JV, LLC CLO Subordinated Notes Apex Credit CLO 2025-12 Ltd',
                'CLO Formation JV, LLC',
                'CLO Subordinated Notes - Apex Credit CLO 2025-12 Ltd',
            ),
        ],
    )
    def test_parse_gecc_labeled_security(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            (
                '12 Interactive, LLC | First Lien Debt 1',
                '12 Interactive, LLC',
                'First Lien Debt',
            ),
            (
                '12 Interactive, LLC (D/B/A PerkSpot) | First Lien Debt (Revolver)',
                '12 Interactive, LLC (D/B/A PerkSpot)',
                'First Lien Debt (Revolver)',
            ),
            (
                'RideNow Group, Inc. (F/K/A RumbleOn, Inc.) | Warrants',
                'RideNow Group, Inc. (F/K/A RumbleOn, Inc.)',
                'Warrants',
            ),
            (
                'Contract Datascan Holdings, Inc. | Preferred Equity 2',
                'Contract Datascan Holdings, Inc.',
                'Preferred Equity',
            ),
            (
                'Planet Bingo | LLC (F/K/A 3rd Rock Gaming Holdings, LLC), First Lien Debt',
                'Planet Bingo, LLC (F/K/A 3rd Rock Gaming Holdings, LLC)',
                'First Lien Debt',
            ),
            (
                'Battalion CLO XI Ltd. | Mezzanine Debt - Class E',
                'Battalion CLO XI Ltd.',
                'Mezzanine Debt - Class E',
            ),
        ],
    )
    def test_parse_ofs_pipe_identifier(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'member_candidates', 'expected_company', 'expected_type'),
        [
            (
                'Portfolio Company Equity Investments- Canada Supply Chain Technology GoFor '
                'Delivers, Inc. Type of Investment Equity Investment Date June 28, 2024 Series '
                'Preferred Series 2 Seed',
                ('supply chain technology',),
                'GoFor Delivers, Inc.',
                'Equity - Preferred Series 2 Seed',
            ),
            (
                'Portfolio Company Equity Investments- United States Multi-Sector Holdings '
                'Eagle Point Trinity Senior Secured Lending Company (fka EPT 16 LLC) Type of '
                'Investment Equity Investment Date June 28, 2024 Series Member Interest',
                ('multi sector holding',),
                'Eagle Point Trinity Senior Secured Lending Company (fka EPT 16 LLC)',
                'Equity - Member Interest',
            ),
            (
                'Portfolio Company Warrant Investments- United States Biotechnology Pendulum '
                'Therapeutics, Inc. One Type of Investment Warrant Investment Date June 1, 2020 '
                'Expiration Date July 15, 2030 Series Preferred Series B',
                ('biotechnology', 'one'),
                'Pendulum Therapeutics, Inc.',
                'Warrant - Preferred Series B',
            ),
            (
                'Portfolio Company Warrant Investments – Europe Consumer Products & Services '
                'Motorway Online, Ltd Type of Investment Warrant Investment Date December 23, '
                '2035 Expiration Date December 23, 2026 Ordinary',
                ('consumer product service',),
                'Motorway Online, Ltd',
                'Warrant - Ordinary',
            ),
        ],
    )
    def test_parse_trin_equity_and_warrant(
        self,
        raw_identifier,
        member_candidates,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=member_candidates,
        )
        assert company == expected_company
        assert investment_type == expected_type

    @pytest.mark.parametrize(
        ('raw_identifier', 'expected_company', 'expected_type'),
        [
            (
                'Control Investments Autonomy Data Services, Inc.',
                'Autonomy Data Services, Inc.',
                'Unknown',
            ),
            (
                'Affiliate Investments GoFor Delivers, Inc.',
                'GoFor Delivers, Inc.',
                'Unknown',
            ),
            (
                'Control and Affiliate Investments',
                'Control and Affiliate Investments',
                'Unknown',
            ),
            (
                'SOFR 3-Month Term Rate',
                'SOFR 3-Month Term Rate',
                'Unknown',
            ),
        ],
    )
    def test_parse_trin_relationship_member(
        self,
        raw_identifier,
        expected_company,
        expected_type,
    ):
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}'
        )
        assert company == expected_company
        assert investment_type == expected_type

    def test_parse_trin_quoted_industry_acronym(self):
        raw_identifier = (
            'Portfolio Company Debt Securities- United States Software as a Service ("SaaS") '
            'Hometown Ticketing, Inc. Type of Investment Secured Loan Investment Date November '
            '25, 2024 Maturity Date November 25, 2029 Variable interest rate SOFR 3 Month Term + '
            '7.7%; EOT 0.0%'
        )
        _, company, investment_type = _parse_investment_identifier(
            f'us-gaap:InvestmentIdentifierAxis: {raw_identifier}',
            member_candidates=('saa',),
        )
        assert company == 'Hometown Ticketing, Inc.'
        assert investment_type == 'Secured Loan'


class TestPortfolioInvestmentsIntegration:
    """Integration tests for portfolio investments."""

    @pytest.mark.network
    def test_bdc_entity_portfolio_investments(self):
        """Test BDCEntity.portfolio_investments() method."""
        bdcs = get_bdc_list()
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        investments = blue_owl.portfolio_investments()
        # Blue Owl should have portfolio investments
        assert investments is not None
        assert len(investments) > 100  # Blue Owl has hundreds of investments

    @pytest.mark.network
    def test_portfolio_investments_has_fair_values(self):
        """Test that portfolio investments have fair values."""
        bdcs = get_bdc_list()
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        investments = blue_owl.portfolio_investments()
        assert investments is not None

        # Total fair value should be significant (billions for Blue Owl)
        assert investments.total_fair_value > Decimal('1000000000')

    @pytest.mark.network
    def test_portfolio_investments_filter_by_type(self):
        """Test filtering portfolio investments by type."""
        bdcs = get_bdc_list()
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        investments = blue_owl.portfolio_investments()
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
        assert dq.interest_rate_coverage == 1.0  # 1 of 1 debt investments has rate
        assert dq.debt_count == 1
        assert dq.equity_count == 1

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
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        investments = blue_owl.portfolio_investments()
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
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        investments = blue_owl.portfolio_investments()
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
    def test_blue_owl_has_detailed_investments_with_quality(self):
        """Test that Blue Owl has detailed investment data."""
        bdcs = get_bdc_list()
        blue_owl = bdcs.get_by_cik(1812554)
        assert blue_owl is not None

        assert blue_owl.has_detailed_investments() is True

    @pytest.mark.network
    def test_htgc_has_detailed_investments(self):
        """Test that HTGC (Hercules) has detailed investment data.

        HTGC uses a different format: "Debt Investments [Industry] and [Company], Senior Secured, ..."
        The from_xbrl method extracts these by looking at dimensional facts.
        Note: The number of individually-tagged investments varies by filing period.
        """
        bdcs = get_bdc_list()
        htgc = next((b for b in bdcs if 'hercules' in b.name.lower()), None)
        assert htgc is not None

        assert htgc.has_detailed_investments() is True

        # Verify we can extract investments
        investments = htgc.portfolio_investments()
        assert investments is not None
        assert len(investments) > 0  # HTGC has individually-tagged investments

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

        results = find_bdc("Main Street")
        assert len(results) > 0
        # Should find Main Street Capital
        assert any("MAIN STREET" in r.name.upper() for r in results)

    @pytest.mark.network
    def test_find_bdc_by_ticker(self):
        """Test searching for BDC by ticker."""
        from edgar.bdc import find_bdc

        results = find_bdc("MAIN")
        assert len(results) > 0
        # First result should be Main Street Capital
        assert results[0].cik == 1396440

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

        results = find_bdc("MAIN")
        assert len(results) > 0
        entity = results[0]
        assert isinstance(entity, BDCEntity)
        assert entity.cik == 1396440

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
