"""
Tests for Company.business_category classification.

Tests the multi-signal classification approach that determines
company business categories based on SIC codes, form types,
entity type, and name patterns.
"""

import pytest

from edgar import Company
from edgar.entity.categorization import (
    BusinessCategory,
    classify_business_category,
    SIC_CODES_REIT,
    SIC_CODES_BANK,
    SIC_CODES_INSURANCE,
    SIC_CODES_SPAC,
    SIC_CODES_INVESTMENT_MANAGER,
)


class TestBusinessCategoryEnum:
    """Test BusinessCategory enum."""

    def test_business_category_values(self):
        """Test that all expected categories exist."""
        assert BusinessCategory.OPERATING_COMPANY.value == "Operating Company"
        assert BusinessCategory.ETF.value == "ETF"
        assert BusinessCategory.MUTUAL_FUND.value == "Mutual Fund"
        assert BusinessCategory.CLOSED_END_FUND.value == "Closed-End Fund"
        assert BusinessCategory.BDC.value == "BDC"
        assert BusinessCategory.REIT.value == "REIT"
        assert BusinessCategory.INVESTMENT_MANAGER.value == "Investment Manager"
        assert BusinessCategory.BANK.value == "Bank"
        assert BusinessCategory.INSURANCE_COMPANY.value == "Insurance Company"
        assert BusinessCategory.SPAC.value == "SPAC"
        assert BusinessCategory.HOLDING_COMPANY.value == "Holding Company"
        assert BusinessCategory.UNKNOWN.value == "Unknown"


class TestSICCodeConstants:
    """Test SIC code constant sets."""

    def test_reit_sic_codes(self):
        """Test REIT SIC codes."""
        assert 6798 in SIC_CODES_REIT

    def test_bank_sic_codes(self):
        """Test Bank SIC codes."""
        assert 6021 in SIC_CODES_BANK
        assert 6022 in SIC_CODES_BANK
        assert 6029 in SIC_CODES_BANK

    def test_insurance_sic_codes(self):
        """Test Insurance SIC codes."""
        assert 6311 in SIC_CODES_INSURANCE
        assert 6331 in SIC_CODES_INSURANCE

    def test_spac_sic_codes(self):
        """Test SPAC SIC codes."""
        assert 6770 in SIC_CODES_SPAC

    def test_investment_manager_sic_codes(self):
        """Test Investment Manager SIC codes."""
        assert 6211 in SIC_CODES_INVESTMENT_MANAGER
        assert 6282 in SIC_CODES_INVESTMENT_MANAGER


class TestClassifyBusinessCategory:
    """Test the classify_business_category function directly."""

    def test_classify_reit_by_sic(self):
        """Test REIT classification via SIC code."""
        result = classify_business_category(
            sic=6798,
            entity_type='operating',
            name='Some Realty Trust',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'REIT'

    def test_classify_bank_by_sic(self):
        """Test Bank classification via SIC code."""
        result = classify_business_category(
            sic=6021,
            entity_type='operating',
            name='National Bank Corp',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'Bank'

    def test_classify_insurance_by_sic(self):
        """Test Insurance classification via SIC code."""
        result = classify_business_category(
            sic=6331,
            entity_type='operating',
            name='Insurance Corp',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'Insurance Company'

    def test_classify_spac_by_sic(self):
        """Test SPAC classification via SIC code."""
        result = classify_business_category(
            sic=6770,
            entity_type='operating',
            name='Acquisition Corp IV',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'SPAC'

    def test_classify_investment_company_as_etf(self):
        """Test ETF classification via investment company forms."""
        result = classify_business_category(
            sic=None,
            entity_type='investment',
            name='iShares Core S&P 500 ETF',
            form_types={'N-CSR', 'NPORT-P'}
        )
        assert result == 'ETF'

    def test_classify_investment_company_as_mutual_fund(self):
        """Test Mutual Fund classification."""
        result = classify_business_category(
            sic=None,
            entity_type='investment',
            name='Vanguard Index Fund',
            form_types={'N-CSR', 'NPORT-P'}
        )
        assert result == 'Mutual Fund'

    def test_classify_bdc_by_forms(self):
        """Test BDC classification via N-2 forms."""
        result = classify_business_category(
            sic=None,
            entity_type='operating',
            name='Ares Capital Corp',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'BDC'

    def test_classify_bdc_requires_forms(self):
        """Test BDC classification requires BDC forms, not just name pattern."""
        result = classify_business_category(
            sic=None,
            entity_type='operating',
            name='Main Street Capital Corporation',
            form_types={'10-K', '10-Q'}
        )
        # Without N-2 forms, "Capital Corporation" alone is no longer sufficient
        assert result == 'Operating Company'

    def test_classify_investment_manager(self):
        """Test Investment Manager classification."""
        result = classify_business_category(
            sic=6282,
            entity_type='operating',
            name='Asset Management Inc',
            form_types={'10-K', '10-Q', '13F-HR'}
        )
        assert result == 'Investment Manager'

    def test_classify_operating_company_default(self):
        """Test default Operating Company classification."""
        result = classify_business_category(
            sic=3571,  # Electronic computers
            entity_type='operating',
            name='Apple Inc',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'Operating Company'

    def test_classify_holding_company(self):
        """Test Holding Company classification."""
        result = classify_business_category(
            sic=6719,
            entity_type='operating',
            name='Holdings Inc',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'Holding Company'


class TestCompanyBusinessCategoryProperty:
    """Integration tests for Company.business_category property."""

    @pytest.mark.network
    def test_apple_operating_company(self):
        """Test Apple is classified as Operating Company."""
        company = Company("AAPL")
        assert company.business_category == "Operating Company"

    @pytest.mark.network
    def test_microsoft_operating_company(self):
        """Test Microsoft is classified as Operating Company."""
        company = Company("MSFT")
        assert company.business_category == "Operating Company"

    @pytest.mark.network
    def test_realty_income_reit(self):
        """Test Realty Income is classified as REIT."""
        company = Company("O")
        assert company.business_category == "REIT"

    @pytest.mark.network
    def test_jpmorgan_bank(self):
        """Test JPMorgan is classified as Bank."""
        company = Company("JPM")
        assert company.business_category == "Bank"

    @pytest.mark.network
    def test_bank_of_america_bank(self):
        """Test Bank of America is classified as Bank."""
        company = Company("BAC")
        assert company.business_category == "Bank"

    @pytest.mark.network
    def test_allstate_insurance(self):
        """Test Allstate is classified as Insurance Company."""
        company = Company("ALL")
        assert company.business_category == "Insurance Company"

    @pytest.mark.network
    def test_progressive_insurance(self):
        """Test Progressive is classified as Insurance Company."""
        company = Company("PGR")
        assert company.business_category == "Insurance Company"

    @pytest.mark.network
    def test_blackrock_investment_manager(self):
        """Test BlackRock is classified as Investment Manager."""
        company = Company("BLK")
        assert company.business_category == "Investment Manager"

    @pytest.mark.network
    def test_ares_capital_bdc(self):
        """Test Ares Capital is classified as BDC."""
        company = Company("ARCC")
        assert company.business_category == "BDC"

    @pytest.mark.network
    def test_main_street_capital_bdc(self):
        """Test Main Street Capital is classified as BDC."""
        company = Company("MAIN")
        assert company.business_category == "BDC"


class TestCompanyBusinessCategoryHelpers:
    """Test helper methods for business category."""

    @pytest.mark.network
    def test_is_fund_false_for_operating_company(self):
        """Test is_fund() returns False for operating company."""
        company = Company("AAPL")
        assert company.is_fund() is False

    @pytest.mark.network
    def test_is_financial_institution_true_for_bank(self):
        """Test is_financial_institution() returns True for bank."""
        company = Company("JPM")
        assert company.is_financial_institution() is True

    @pytest.mark.network
    def test_is_financial_institution_true_for_insurance(self):
        """Test is_financial_institution() returns True for insurance."""
        company = Company("ALL")
        assert company.is_financial_institution() is True

    @pytest.mark.network
    def test_is_financial_institution_false_for_operating(self):
        """Test is_financial_institution() returns False for operating company."""
        company = Company("AAPL")
        assert company.is_financial_institution() is False

    @pytest.mark.network
    def test_is_operating_company_true(self):
        """Test is_operating_company() returns True for operating company."""
        company = Company("AAPL")
        assert company.is_operating_company() is True

    @pytest.mark.network
    def test_is_operating_company_false_for_bank(self):
        """Test is_operating_company() returns False for bank."""
        company = Company("JPM")
        assert company.is_operating_company() is False


class TestBusinessCategoryCaching:
    """Test that business_category is properly cached."""

    @pytest.mark.network
    def test_business_category_is_cached(self):
        """Test business_category property is cached."""
        company = Company("AAPL")

        # Access business_category twice
        category1 = company.business_category
        category2 = company.business_category

        # Both should return the same value
        assert category1 == category2
        assert category1 == "Operating Company"


class TestBusinessCategoryParametrized:
    """Parametrized tests covering multiple company types."""

    @pytest.mark.network
    @pytest.mark.parametrize("ticker,expected_category", [
        ("AAPL", "Operating Company"),
        ("O", "REIT"),
        ("JPM", "Bank"),
        ("ALL", "Insurance Company"),
        ("BLK", "Investment Manager"),
        ("ARCC", "BDC"),
    ])
    def test_business_category_by_ticker(self, ticker, expected_category):
        """Test that companies are classified correctly by ticker."""
        company = Company(ticker)
        assert company.business_category == expected_category, \
            f"{ticker} expected {expected_category}, got {company.business_category}"


class TestIssue561Misclassifications:
    """Regression tests for issue #561 — business_category misclassifications.

    Four categories of fixes:
    1. ETFs with "ETF" in name but no investment company forms → ETF
    2. Commodity trusts/funds with SIC 6200s → ETF
    3. SPACs with non-6770 SIC codes → SPAC (by name pattern)
    4. Churchill Capital Corp IX → not BDC (removed "CAPITAL CORP" name pattern)
    """

    # Issue 1: ETFs with "ETF" in name, no investment company forms
    @pytest.mark.parametrize("name,sic", [
        ("Goldman Sachs Physical Gold ETF", 6211),
        ("ARK 21Shares Bitcoin ETF", 6211),
        ("Bitwise Bitcoin ETF", 6211),
        ("Grayscale Bitcoin Mini Trust ETF", 6211),
        ("Invesco Galaxy Bitcoin ETF", 6211),
    ])
    def test_crypto_commodity_etf_by_name(self, name, sic):
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q'}
        )
        assert result == 'ETF'

    # Issue 2: Commodity trusts/funds, SIC 6200s
    @pytest.mark.parametrize("name,sic", [
        ("GraniteShares Gold Trust", 6211),
        ("Grayscale Bitcoin Cash Trust BCH", 6211),
        ("United States Brent Oil Fund LP", 6221),
        ("WisdomTree Bitcoin Fund", 6211),
        ("Teucrium Commodity Trust", 6221),
    ])
    def test_commodity_trust_fund_by_name_and_sic(self, name, sic):
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q'}
        )
        assert result == 'ETF'

    # Issue 2b: Royalty trusts should NOT be classified as ETF
    def test_royalty_trust_stays_operating_company(self):
        result = classify_business_category(
            sic=6211, entity_type='operating',
            name='BP Prudhoe Bay Royalty Trust',
            form_types={'10-K', '10-Q'}
        )
        assert result == 'Operating Company'

    # Issue 3: SPACs with non-6770 SIC
    @pytest.mark.parametrize("name,sic", [
        ("Altenergy Acquisition Corp", 3711),
        ("Alpha Star Acquisition Corp", 7389),
        ("Athena Technology Acquisition Corp II", 4911),
        ("Best SPAC I Acquisition Corp", 8200),
        ("Greenfield Acquisition Company", 5411),    # "Acquisition Co" variant
        ("Vertex Acquisition Inc", 3674),             # "Acquisition Inc" variant
    ])
    def test_spac_by_name(self, name, sic):
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q'}
        )
        assert result == 'SPAC'

    # Issue 4: Churchill Capital Corp IX should NOT be BDC
    def test_churchill_capital_not_bdc(self):
        result = classify_business_category(
            sic=6770, entity_type='operating',
            name='Churchill Capital Corp IX Cayman',
            form_types={'10-K', '10-Q'}
        )
        # SIC 6770 → SPAC (caught by step 1, not BDC)
        assert result == 'SPAC'

    def test_churchill_capital_non_spac_sic_not_bdc(self):
        """If Churchill had a non-SPAC SIC, still shouldn't be BDC."""
        result = classify_business_category(
            sic=6199, entity_type='operating',
            name='Churchill Capital Corp IX Cayman',
            form_types={'10-K', '10-Q'}
        )
        assert result != 'BDC'

    # Verify existing BDC detection still works (forms-based)
    def test_real_bdc_with_forms(self):
        result = classify_business_category(
            sic=None, entity_type='operating',
            name='Ares Capital Corporation',
            form_types={'10-K', '10-Q', 'N-2'},
        )
        assert result == 'BDC'

    def test_real_bdc_main_street(self):
        result = classify_business_category(
            sic=None, entity_type='operating',
            name='Main Street Capital Corporation',
            form_types={'10-K', '10-Q', 'N-2'},
        )
        assert result == 'BDC'

    # Guard: Investment manager with "ETF" in name is NOT classified as ETF
    def test_etf_manager_stays_investment_manager(self):
        result = classify_business_category(
            sic=6211, entity_type='operating',
            name='ETF Managers Group',
            form_types={'10-K', '10-Q', '13F-HR'}
        )
        assert result == 'Investment Manager'

    # Guard: operating companies with "Trust" outside SIC 6200s are NOT affected
    def test_operating_trust_outside_broker_sic(self):
        result = classify_business_category(
            sic=3571, entity_type='operating',
            name='Northern Trust Corporation',
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == 'Operating Company'

    # Guard: "Fund" in name with non-broker SIC stays Operating Company
    def test_fund_name_non_broker_sic(self):
        result = classify_business_category(
            sic=5411, entity_type='operating',
            name='FundTech Solutions Inc',
            form_types={'10-K', '10-Q'}
        )
        assert result == 'Operating Company'

    # Guard: broker-dealer with "Trust" in legal name
    def test_broker_trust_subsidiary(self):
        """A broker-dealer trust subsidiary should not become ETF."""
        result = classify_business_category(
            sic=6211, entity_type='operating',
            name='Morgan Stanley Securities Trust',
            form_types={'10-K', '10-Q', '13F-HR'}
        )
        # SIC 6211 + 13F → Investment Manager (caught before fund/trust heuristic)
        assert result == 'Investment Manager'
