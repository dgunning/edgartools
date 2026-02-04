"""
Tests for entity classification (is_individual) logic.

Tests the shared _classify_is_individual function directly, which is the
single source of truth used by both EntityData.is_individual and
is_individual_from_json().
"""

import pytest

from edgar.entity.constants import _classify_is_individual, _name_suggests_company

# Each test case: (test_id, kwargs_dict, expected_is_individual)
CLASSIFICATION_TESTS = [

    # =========================================================================
    # Signal 1: insiderTransactionForIssuerExists (strongest -> company)
    # =========================================================================
    ("issuer_flag_true",
     dict(insider_transaction_for_issuer_exists=True),
     False),

    ("issuer_flag_overrides_owner",
     dict(insider_transaction_for_issuer_exists=True,
          insider_transaction_for_owner_exists=True,
          entity_type="other"),
     False),

    ("issuer_flag_overrides_all_individual_signals",
     dict(insider_transaction_for_issuer_exists=True,
          insider_transaction_for_owner_exists=True,
          entity_type="other",
          name="JOHN SMITH"),
     False),

    # =========================================================================
    # Signal 2: Tickers / exchanges (strong -> company)
    # =========================================================================
    ("single_ticker",
     dict(tickers=["AAPL"]),
     False),

    ("multiple_tickers",
     dict(tickers=["AAPL", "APPL"]),
     False),

    ("single_exchange",
     dict(exchanges=["Nasdaq"]),
     False),

    ("ticker_overrides_owner_flag",
     dict(tickers=["TSLA"],
          insider_transaction_for_owner_exists=True),
     False),

    ("empty_tickers_falls_through",
     dict(tickers=[]),
     True),

    ("none_tickers_falls_through",
     dict(tickers=None),
     True),

    # =========================================================================
    # Signal 3: State of incorporation (strong -> company, with exceptions)
    # =========================================================================
    ("state_de",
     dict(state_of_incorporation="DE"),
     False),

    ("state_foreign",
     dict(state_of_incorporation="X2"),
     False),

    ("state_overrides_owner_flag",
     dict(state_of_incorporation="DE",
          insider_transaction_for_owner_exists=True),
     False),

    ("reed_hastings_exception",
     dict(state_of_incorporation="CA", cik=1033331),
     True),

    ("state_empty_falls_through",
     dict(state_of_incorporation=""),
     True),

    ("state_whitespace_falls_through",
     dict(state_of_incorporation="   "),
     True),

    ("state_none_falls_through",
     dict(state_of_incorporation=None),
     True),

    # =========================================================================
    # Signal 4: Entity type (strong -> company)
    # =========================================================================
    ("entity_type_operating",
     dict(entity_type="operating"),
     False),

    ("entity_type_investment",
     dict(entity_type="investment"),
     False),

    ("entity_type_fund",
     dict(entity_type="fund"),
     False),

    ("entity_type_asset_backed",
     dict(entity_type="asset_backed"),
     False),

    ("entity_type_case_insensitive",
     dict(entity_type="OPERATING"),
     False),

    ("entity_type_other_falls_through",
     dict(entity_type="other"),
     True),

    ("entity_type_empty_falls_through",
     dict(entity_type=""),
     True),

    ("entity_type_none_falls_through",
     dict(entity_type=None),
     True),

    # =========================================================================
    # Signal 5: Company forms in filing history (strong -> company)
    # =========================================================================
    ("form_10k",
     dict(forms=["10-K"]),
     False),

    ("form_10q",
     dict(forms=["10-Q"]),
     False),

    ("form_8k",
     dict(forms=["8-K"]),
     False),

    ("form_8k_amendment",
     dict(forms=["8-K/A"]),
     False),

    ("form_def14a",
     dict(forms=["DEF 14A"]),
     False),

    ("form_s1",
     dict(forms=["S-1"]),
     False),

    ("form_ncsr",
     dict(forms=["N-CSR"]),
     False),

    ("form_n1a",
     dict(forms=["N-1A"]),
     False),

    ("form_20f",
     dict(forms=["20-F"]),
     False),

    ("form_20f_amendment",
     dict(forms=["20-F/A"]),
     False),

    ("form_10ksb_small_business",
     dict(forms=["10-KSB"]),
     False),

    ("form_10qsb_small_business",
     dict(forms=["10-QSB"]),
     False),

    ("form_485bpos_fund_prospectus",
     dict(forms=["485BPOS"]),
     False),

    ("form_497k_summary_prospectus",
     dict(forms=["497K"]),
     False),

    ("form_npx_proxy_voting",
     dict(forms=["N-PX"]),
     False),

    ("form_345_ambiguous_falls_through",
     dict(forms=["3", "4", "5"]),
     True),

    ("form_345_with_company_form",
     dict(forms=["3", "4", "10-K"]),
     False),

    ("forms_empty_falls_through",
     dict(forms=[]),
     True),

    ("warren_buffett_exception_on_forms",
     dict(forms=["10-K", "10-Q"], cik=315090),
     True),

    # =========================================================================
    # Signal 6: EIN (weak -> company, with exceptions)
    # =========================================================================
    ("valid_ein",
     dict(ein="123456789"),
     False),

    ("ein_placeholder_falls_through",
     dict(ein="000000000"),
     True),

    ("ein_empty_falls_through",
     dict(ein=""),
     True),

    ("ein_none_falls_through",
     dict(ein=None),
     True),

    ("warren_buffett_exception_on_ein",
     dict(ein="470539396", cik=315090),
     True),

    ("ein_overrides_owner_flag",
     dict(ein="123456789",
          insider_transaction_for_owner_exists=True),
     False),

    # =========================================================================
    # Signal 7: Name-based heuristics (fallback -> company)
    # =========================================================================

    # Loose keyword matches (substring - long/distinctive keywords)
    ("name_corporation",
     dict(name="MICROSOFT CORPORATION"),
     False),

    ("name_limited",
     dict(name="HSBC HOLDINGS LIMITED"),
     False),

    ("name_company",
     dict(name="FORD MOTOR COMPANY"),
     False),

    ("name_holdings",
     dict(name="BERKSHIRE HATHAWAY HOLDINGS"),
     False),

    ("name_partners",
     dict(name="KKR PARTNERS"),
     False),

    ("name_partnership",
     dict(name="CARLYLE PARTNERSHIP"),
     False),

    ("name_capital",
     dict(name="SEQUOIA CAPITAL"),
     False),

    ("name_ventures",
     dict(name="ANDREESSEN HOROWITZ VENTURES"),
     False),

    ("name_management",
     dict(name="BRIDGEWATER MANAGEMENT"),
     False),

    ("name_advisors",
     dict(name="WELLINGTON ADVISORS"),
     False),

    ("name_securities",
     dict(name="MERRILL LYNCH SECURITIES"),
     False),

    ("name_investment",
     dict(name="T ROWE PRICE INVESTMENT"),
     False),

    ("name_bank",
     dict(name="JPMORGAN CHASE BANK"),
     False),

    ("name_foundation",
     dict(name="BILL AND MELINDA GATES FOUNDATION"),
     False),

    ("name_association",
     dict(name="NATIONAL FOOTBALL LEAGUE ASSOCIATION"),
     False),

    ("name_technologies",
     dict(name="PALANTIR TECHNOLOGIES"),
     False),

    ("name_services",
     dict(name="FISERV FINANCIAL SERVICES"),
     False),

    ("name_international",
     dict(name="CATERPILLAR INTERNATIONAL"),
     False),

    ("name_industries",
     dict(name="DOVER INDUSTRIES"),
     False),

    ("name_enterprises",
     dict(name="ENTERPRISE PRODUCTS ENTERPRISES"),
     False),

    # Strict keyword matches (whole word only)
    ("name_co_whole_word",
     dict(name="STANDARD OIL CO"),
     False),

    ("name_co_not_substring",
     dict(name="SCOTT JOHNSON"),
     True),

    ("name_corp_whole_word",
     dict(name="GENERAL ELECTRIC CORP"),
     False),

    ("name_llc_whole_word",
     dict(name="SMITH CAPITAL LLC"),
     False),

    ("name_ltd_whole_word",
     dict(name="BARCLAYS LTD"),
     False),

    ("name_group_whole_word",
     dict(name="GOLDMAN SACHS GROUP"),
     False),

    ("name_trust_whole_word",
     dict(name="VANGUARD TRUST"),
     False),

    ("name_fund_whole_word",
     dict(name="FIDELITY GROWTH FUND"),
     False),

    ("name_bank_whole_word",
     dict(name="JPMORGAN CHASE BANK"),
     False),

    ("name_inc_whole_word",
     dict(name="ACME INC"),
     False),

    ("name_inc_not_substring",
     dict(name="LINCOLN SMITH"),
     True),

    ("name_lp_whole_word",
     dict(name="BLACKSTONE GROUP LP"),
     False),

    ("name_lp_not_substring",
     dict(name="ALPINE JOHN"),
     True),

    ("name_lp_not_in_ralph",
     dict(name="RALPH JONES"),
     True),

    ("name_lp_not_in_help",
     dict(name="HELP ANDERSON"),
     True),

    ("name_corp_not_substring",
     dict(name="CORPUZ MARIA"),
     True),

    ("name_bank_not_substring",
     dict(name="BANKS ROBERT"),
     True),

    ("name_fund_not_substring",
     dict(name="FUNDBERG OLAF"),
     True),

    ("name_trust_not_substring",
     dict(name="TRUSTER JANE"),
     True),

    ("name_group_not_substring",
     dict(name="GROUPER JAMES"),
     True),

    ("name_na_whole_word",
     dict(name="FIRST NATIONAL BANK NA"),
     False),

    ("name_plc_whole_word",
     dict(name="VODAFONE PLC"),
     False),

    ("name_sa_whole_word",
     dict(name="PETROBRAS SA"),
     False),

    # SEC filing suffixes
    ("name_adr_suffix",
     dict(name="TOYOTA MOTOR CORP /ADR/"),
     False),

    ("name_bd_suffix",
     dict(name="SMITH BARNEY /BD/"),
     False),

    ("name_ta_suffix",
     dict(name="COMPUTERSHARE /TA/"),
     False),

    # Space-separated variants (loose substring)
    ("name_l_l_c_spaced",
     dict(name="ACME HOLDINGS L L C"),
     False),

    ("name_l_p_spaced",
     dict(name="BLACKSTONE L P"),
     False),

    # Ampersand patterns — & usually indicates a company/partnership
    ("name_ampersand_company",
     dict(name="JOHNSON & JOHNSON"),
     False),

    ("name_ampersand_law_firm",
     dict(name="SKADDEN ARPS SLATE MEAGHER & FLOM"),
     False),

    ("name_ampersand_partnership",
     dict(name="PROCTER & GAMBLE"),
     False),

    # Ampersand exclusions — joint individual filers
    ("name_ampersand_mr_mrs_excluded",
     dict(name="MR & MRS JOHN SMITH"),
     True),

    ("name_ampersand_joint_filer_excluded",
     dict(name="SMITH JOHN & SMITH JANE"),
     True),

    # Plain individual names - no keywords
    ("name_plain_individual",
     dict(name="JOHN SMITH"),
     True),

    ("name_plain_individual_2",
     dict(name="MARY JANE WATSON"),
     True),

    ("name_none",
     dict(name=None),
     True),

    # =========================================================================
    # Signal 8: insiderTransactionForOwnerExists (weak -> individual)
    # =========================================================================
    ("owner_flag_alone",
     dict(insider_transaction_for_owner_exists=True),
     True),

    ("owner_flag_with_issuer_none",
     dict(insider_transaction_for_owner_exists=True,
          insider_transaction_for_issuer_exists=None),
     True),

    ("owner_flag_false_falls_through",
     dict(insider_transaction_for_owner_exists=False),
     True),

    # =========================================================================
    # Signal 9: Default (no signals -> individual)
    # =========================================================================
    ("no_signals_at_all",
     dict(),
     True),

    ("all_none",
     dict(name=None, entity_type=None, tickers=None, exchanges=None,
          state_of_incorporation=None, ein=None,
          insider_transaction_for_owner_exists=None,
          insider_transaction_for_issuer_exists=None,
          forms=None, cik=None),
     True),

    ("all_empty",
     dict(name="", entity_type="", tickers=[], exchanges=[],
          state_of_incorporation="", ein="",
          insider_transaction_for_owner_exists=False,
          insider_transaction_for_issuer_exists=False,
          forms=[], cik=None),
     True),

    # =========================================================================
    # Realistic entity profiles
    # =========================================================================

    # Public operating company
    ("real_apple",
     dict(name="APPLE INC", entity_type="operating",
          tickers=["AAPL"], exchanges=["Nasdaq"],
          state_of_incorporation="CA", ein="942404110",
          insider_transaction_for_issuer_exists=True,
          forms=["10-K", "10-Q", "8-K", "DEF 14A"],
          cik=320193),
     False),

    # Foreign private issuer
    ("real_toyota",
     dict(name="TOYOTA MOTOR CORP /ADR/", entity_type="operating",
          tickers=["TM"], exchanges=["NYSE"],
          state_of_incorporation="M0",
          insider_transaction_for_issuer_exists=True,
          forms=["20-F", "6-K"],
          cik=1094517),
     False),

    # Mutual fund
    ("real_vanguard_fund",
     dict(name="VANGUARD INDEX FUNDS", entity_type="fund",
          forms=["N-CSR", "N-CEN", "485BPOS", "497K"],
          cik=36405),
     False),

    # ETF
    ("real_spdr_etf",
     dict(name="SPDR S&P 500 ETF TRUST", entity_type="fund",
          tickers=["SPY"], exchanges=["NYSE Arca"],
          forms=["N-CSR", "497K"],
          cik=884394),
     False),

    # Insider individual - plain filer
    ("real_insider_individual",
     dict(name="COOK TIMOTHY D", entity_type="other",
          insider_transaction_for_owner_exists=True,
          insider_transaction_for_issuer_exists=False,
          forms=["3", "4"],
          cik=1214156),
     True),

    # Warren Buffett - has EIN + company forms but is individual
    ("real_warren_buffett",
     dict(name="BUFFETT WARREN E", entity_type="other",
          ein="470539396",
          insider_transaction_for_owner_exists=True,
          forms=["3", "4", "SC 13D", "SC 13D/A"],
          cik=315090),
     True),

    # Reed Hastings - has state of incorporation but is individual
    ("real_reed_hastings",
     dict(name="HASTINGS REED", entity_type="other",
          state_of_incorporation="CA",
          insider_transaction_for_owner_exists=True,
          forms=["3", "4"],
          cik=1033331),
     True),

    # Private company (no tickers, no forms, just state + EIN)
    ("real_private_company",
     dict(name="ACME HOLDINGS LLC", entity_type="operating",
          state_of_incorporation="DE", ein="831234567"),
     False),

    # Holding company filing as owner (SC 13D filer)
    ("real_holding_company_owner",
     dict(name="BLACKROCK CAPITAL MANAGEMENT",
          entity_type="other",
          insider_transaction_for_owner_exists=True,
          forms=["SC 13D", "SC 13G"]),
     False),

    # Old inactive company - no tickers, no state, entity_type=""
    # Only the name reveals it's a company
    ("real_old_inactive_company",
     dict(name="CONSOLIDATED MINING CORP",
          entity_type="",
          forms=["3"]),
     False),

    # Broker-dealer
    ("real_broker_dealer",
     dict(name="MORGAN STANLEY /BD/",
          entity_type="other",
          forms=["X-17A-5"]),
     False),

    # Pre-2008 small business
    ("real_small_business",
     dict(name="HOMETOWN SAVINGS BANK",
          entity_type="",
          forms=["10-KSB", "10-QSB"]),
     False),

    # Foreign institutional investor filing as owner
    ("real_foreign_institution_owner",
     dict(name="NORGES BANK INVESTMENT MANAGEMENT",
          entity_type="other",
          insider_transaction_for_owner_exists=True,
          forms=["SC 13G", "SC 13G/A"]),
     False),

    # Individual with no flags at all - just entity_type "other"
    ("real_minimal_individual",
     dict(name="GARCIA MARIA", entity_type="other"),
     True),

    # Foundation
    ("real_foundation",
     dict(name="BILL & MELINDA GATES FOUNDATION",
          entity_type="other"),
     False),

    # Transfer agent
    ("real_transfer_agent",
     dict(name="COMPUTERSHARE TRUST COMPANY NA",
          entity_type="other",
          forms=["TA-1", "TA-2"]),
     False),
]


@pytest.mark.parametrize(
    "test_id, kwargs, expected",
    CLASSIFICATION_TESTS,
    ids=[t[0] for t in CLASSIFICATION_TESTS],
)
def test_is_individual(test_id, kwargs, expected):
    """Parametrized entity classification test."""
    result = _classify_is_individual(**kwargs)
    assert result is expected, (
        f"{test_id}: expected is_individual={expected}, got {result} "
        f"with inputs {kwargs}"
    )


class TestNameSuggestsCompany:
    """Tests for the _name_suggests_company helper function."""

    def test_none_name(self):
        assert _name_suggests_company(None) is False

    def test_empty_name(self):
        assert _name_suggests_company("") is False

    def test_loose_keyword(self):
        assert _name_suggests_company("ACME CORPORATION") is True

    def test_strict_keyword_co(self):
        assert _name_suggests_company("STANDARD OIL CO") is True

    def test_strict_keyword_not_substring(self):
        assert _name_suggests_company("SCOTT JOHNSON") is False

    def test_sec_suffix(self):
        assert _name_suggests_company("TOYOTA MOTOR CORP /ADR/") is True

    def test_individual_name(self):
        assert _name_suggests_company("JOHN SMITH") is False

    def test_case_insensitive(self):
        assert _name_suggests_company("acme inc") is True
