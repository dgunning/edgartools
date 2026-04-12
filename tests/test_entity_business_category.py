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


# =============================================================================
# Issue #774 Regression Tests
# =============================================================================

class TestIssue774BDCFalsePositives:
    """Regression tests for GH #774 patterns 1-2: BDC false positives.

    Pattern 1: Major alt asset managers (BX, KKR) that manage BDC subsidiaries
    were classified as BDC because 814- file numbers bled from subsidiaries.

    Pattern 2: Non-financial companies (NEE, RCAT) with definitive SIC codes
    were classified as BDC for the same reason.

    The classifier (not the is_bdc short-circuit) should never return BDC
    for entities whose SIC definitively indicates another category.
    """

    # Pattern 1: Alt asset managers with SIC 6282 should be Investment Manager
    @pytest.mark.parametrize("name,sic,expected", [
        ("Blackstone Inc", 6282, "Investment Manager"),
        ("KKR & Co Inc", 6282, "Investment Manager"),
        ("Brookfield Oaktree Holdings LLC", 6282, "Investment Manager"),
        ("Brookfield Asset Management Ltd", 6282, "Investment Manager"),
    ])
    def test_alt_asset_managers_not_bdc(self, name, sic, expected):
        """SIC 6282 entities that manage BDCs are not BDCs themselves."""
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == expected

    # Pattern 2: Non-financial companies should never be BDC
    @pytest.mark.parametrize("name,sic,expected", [
        ("NextEra Energy Inc", 4911, "Operating Company"),
        ("Seaboard Corp", 5150, "Operating Company"),
        ("Red Cat Holdings", 7372, "Operating Company"),
        ("Silo Pharma Inc", 2834, "Operating Company"),
        ("United Health Products", 3842, "Operating Company"),
        ("Onassis Holdings", 4412, "Operating Company"),
        ("Great Elm Group", 7372, "Operating Company"),
        ("Newtekone Inc", 6021, "Bank"),
        ("Prudential Financial", 6311, "Insurance Company"),
        ("Assured Guaranty", 6351, "Insurance Company"),
        ("Mackenzie Realty Capital", 6798, "REIT"),
    ])
    def test_non_financial_not_bdc(self, name, sic, expected):
        """Companies with definitive non-BDC SIC codes must not be BDC."""
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == expected

    def test_bdc_forms_blocked_by_non_financial_sic(self):
        """Even with N-2 forms, a non-financial SIC should block BDC."""
        result = classify_business_category(
            sic=4911, entity_type='operating', name='NextEra Energy Inc',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'Operating Company'

    def test_bdc_forms_blocked_by_bank_sic(self):
        """A bank SIC should override BDC forms."""
        result = classify_business_category(
            sic=6021, entity_type='operating', name='Newtekone Inc',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'Bank'


class TestIssue774BDCGuards:
    """Ensure legitimate BDCs are still classified correctly after #774 fixes."""

    def test_real_bdc_with_n2_no_sic(self):
        """BDC with N-2 forms and no SIC → BDC."""
        result = classify_business_category(
            sic=None, entity_type='operating', name='Ares Capital Corporation',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'BDC'

    def test_real_bdc_main_street(self):
        """Main Street Capital with N-2 → BDC."""
        result = classify_business_category(
            sic=None, entity_type='operating', name='Main Street Capital Corporation',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'BDC'

    def test_real_bdc_financial_sic_no_override(self):
        """A BDC with a generic financial SIC (not bank/insurance/REIT/investment manager)
        should still be BDC — sic_overrides_bdc only blocks definitive non-BDC SICs."""
        result = classify_business_category(
            sic=6199, entity_type='operating', name='Some Capital Corp',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'BDC'

    def test_sic_6282_with_n2_becomes_investment_manager(self):
        """SIC 6282 + N-2 → Investment Manager, not BDC.
        This is the correct behavior: SIC 6282 entities with N-2 forms are
        asset managers that manage BDC subsidiaries, not BDCs themselves."""
        result = classify_business_category(
            sic=6282, entity_type='operating', name='Owl Rock Capital Corp',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'Investment Manager'

    def test_holding_company_with_n2_stays_bdc(self):
        """SIC 6719 (Holding Company) + N-2 → BDC.
        Holding companies are not blocked by sic_overrides_bdc."""
        result = classify_business_category(
            sic=6719, entity_type='operating', name='Some Holdings',
            form_types={'10-K', '10-Q', 'N-2'}
        )
        assert result == 'BDC'


class TestIssue774InvestmentManagerFalseNegatives:
    """Regression tests for GH #774 pattern 3: Investment Manager false negatives.

    SIC 6282 (Investment Advice) and SIC 6211 (Security Brokers/Dealers)
    companies were classified as Operating Company because the classifier
    required both 13F filing AND investment SIC. SIC alone should suffice.
    """

    # Pattern 3a: SIC 6282 investment advisers — no 13F needed
    @pytest.mark.parametrize("name,sic", [
        ("Apollo Global Management", 6282),
        ("Ares Management Corp", 6282),
        ("Blue Owl Capital Inc", 6282),
        ("TPG Inc", 6282),
        ("Affiliated Managers Group", 6282),
        ("T. Rowe Price Group", 6282),
        ("Hamilton Lane Inc", 6282),
        ("StepStone Group Inc", 6282),
        ("Artisan Partners Asset Management", 6282),
        ("Virtus Investment Partners", 6282),
    ])
    def test_sic_6282_classified_as_investment_manager(self, name, sic):
        """SIC 6282 (Investment Advice) → Investment Manager even without 13F."""
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == "Investment Manager"

    # Pattern 3b: SIC 6211 broker-dealers / investment banks — no 13F needed
    @pytest.mark.parametrize("name,sic", [
        ("Goldman Sachs Group", 6211),
        ("Morgan Stanley", 6211),
        ("Charles Schwab Corp", 6211),
        ("Interactive Brokers Group", 6211),
    ])
    def test_sic_6211_classified_as_investment_manager(self, name, sic):
        """SIC 6211 (Security Brokers/Dealers) → Investment Manager even without 13F."""
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q', '8-K'}
        )
        assert result == "Investment Manager"

    # Guard: SIC 6211 commodity trusts must NOT become Investment Manager
    @pytest.mark.parametrize("name,sic", [
        ("GraniteShares Gold Trust", 6211),
        ("Grayscale Bitcoin Cash Trust BCH", 6211),
        ("WisdomTree Bitcoin Fund", 6211),
    ])
    def test_sic_6211_commodity_trust_stays_etf(self, name, sic):
        """SIC 6211 + 'Trust'/'Fund' in name → ETF, not Investment Manager."""
        result = classify_business_category(
            sic=sic, entity_type='operating', name=name,
            form_types={'10-K', '10-Q'}
        )
        assert result == 'ETF'

    def test_sic_6211_etf_in_name_stays_etf(self):
        """SIC 6211 + 'ETF' in name → ETF, not Investment Manager."""
        result = classify_business_category(
            sic=6211, entity_type='operating',
            name='Goldman Sachs Physical Gold ETF',
            form_types={'10-K', '10-Q'}
        )
        assert result == 'ETF'

    def test_sic_6211_with_13f_and_trust_stays_investment_manager(self):
        """SIC 6211 + 13F + 'Trust' in name → Investment Manager (13F wins)."""
        result = classify_business_category(
            sic=6211, entity_type='operating',
            name='Morgan Stanley Securities Trust',
            form_types={'10-K', '10-Q', '13F-HR'}
        )
        assert result == 'Investment Manager'


class TestIssue774UnknownReduction:
    """Regression tests for GH #774 pattern 4: high Unknown rate.

    Foreign/Canadian filers with entity_type='other' and valid SIC codes
    were classified as Unknown because Step 9 only accepted
    entity_type in ('operating', '', None).
    """

    @pytest.mark.parametrize("name,sic,entity_type,expected", [
        # Foreign manufacturer
        ("Toyota Motor Corp", 3711, "other", "Operating Company"),
        # Foreign pharma
        ("Novo Nordisk A/S", 2834, "other", "Operating Company"),
        # Foreign bank
        ("HSBC Holdings plc", 6022, "other", "Bank"),
        # Foreign insurer
        ("AXA SA", 6311, "other", "Insurance Company"),
        # Foreign REIT
        ("Brookfield Real Estate Partners", 6798, "other", "REIT"),
        # Foreign investment manager
        ("Man Group plc", 6282, "other", "Investment Manager"),
        # Foreign with no SIC → still Unknown
        ("Unknown Foreign Corp", None, "other", "Unknown"),
    ])
    def test_foreign_filers_classified_by_sic(self, name, sic, entity_type, expected):
        """Foreign filers (entity_type='other') should use SIC-based classification."""
        result = classify_business_category(
            sic=sic, entity_type=entity_type, name=name,
            form_types={'20-F', '6-K'}
        )
        assert result == expected

    def test_domestic_no_sic_still_operating(self):
        """Domestic filer with no SIC → Operating Company (not Unknown)."""
        result = classify_business_category(
            sic=None, entity_type='operating', name='Some Corp',
            form_types={'10-K', '10-Q'}
        )
        assert result == 'Operating Company'


class TestIssue774NetworkIntegration:
    """Network tests verifying real SEC data classifications for GH #774."""

    @pytest.mark.network
    @pytest.mark.parametrize("ticker,expected", [
        # Pattern 1: Alt asset managers (were BDC, should be Investment Manager)
        ("BX", "Investment Manager"),
        ("KKR", "Investment Manager"),
        # Pattern 2: Non-financial (were BDC, should be correct category)
        ("NEE", "Operating Company"),
        # Pattern 3: Investment advisers (were Operating, should be Investment Manager)
        ("APO", "Investment Manager"),
        ("TROW", "Investment Manager"),
        ("GS", "Investment Manager"),
        ("MS", "Investment Manager"),
        # Guards: existing correct classifications unchanged
        ("AAPL", "Operating Company"),
        ("JPM", "Bank"),
        ("O", "REIT"),
        ("ALL", "Insurance Company"),
        ("ARCC", "BDC"),
        ("BLK", "Investment Manager"),
    ])
    def test_issue_774_classification(self, ticker, expected):
        """Verify business_category against live SEC data."""
        company = Company(ticker)
        assert company.business_category == expected, \
            f"{ticker} (SIC {company.sic}): expected {expected}, got {company.business_category}"
