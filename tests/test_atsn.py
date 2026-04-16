"""Verification tests for ATS-N (Alternative Trading System) data objects.

Ground truth filings:
  - BofA Instinct X initial ATS-N — accession 0001675365-19-000012
  - Goldman Sigma X2 ATS-N/UA      — accession 0000950123-23-009133
  - J.P. Morgan JPB-X withdrawal   — accession 0000019617-24-000664
"""
from pathlib import Path

import pytest

try:
    import vcr
except ImportError:
    vcr = None

from edgar import get_by_accession_number
from edgar.ats import (
    ATS_N_ALL_FORMS,
    ATS_N_AMENDMENT_FORMS,
    ATS_N_FORMS,
    ATS_N_WITHDRAWAL_FORMS,
    AlternativeTradingSystem,
    AlternativeTradingSystemWithdrawal,
)

pytestmark = pytest.mark.network

CASSETTES_DIR = Path(__file__).parent / "cassettes"
my_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTES_DIR),
    record_mode="once",
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["User-Agent", "Authorization"],
    decode_compressed_response=True,
) if vcr else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bofa_initial():
    """BofA Securities Instinct X — the first initial ATS-N ever filed (2019)."""
    with my_vcr.use_cassette("test_atsn_bofa_initial.yaml"):
        filing = get_by_accession_number("0001675365-19-000012")
        return filing.obj()


@pytest.fixture(scope="module")
def gs_amendment():
    """Goldman Sachs Sigma X2 — ATS-N/UA with oversized-field PDFs."""
    with my_vcr.use_cassette("test_atsn_gs_ua.yaml"):
        filing = get_by_accession_number("0000950123-23-009133")
        return filing.obj()


@pytest.fixture(scope="module")
def jpm_withdrawal():
    """JPM JPB-X withdrawal — ATS-N-W with atsncw namespace, empty formData."""
    with my_vcr.use_cassette("test_atsn_jpm_withdrawal.yaml"):
        filing = get_by_accession_number("0000019617-24-000664")
        return filing.obj()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:

    def test_ats_n_forms(self):
        assert ATS_N_FORMS == ["ATS-N"]

    def test_ats_n_amendment_forms(self):
        assert ATS_N_AMENDMENT_FORMS == ["ATS-N/MA", "ATS-N/UA", "ATS-N/CA"]

    def test_ats_n_withdrawal_forms(self):
        assert ATS_N_WITHDRAWAL_FORMS == ["ATS-N-W"]

    def test_ats_n_all_forms(self):
        assert ATS_N_ALL_FORMS == [
            "ATS-N", "ATS-N/MA", "ATS-N/UA", "ATS-N/CA", "ATS-N-W",
        ]


# ---------------------------------------------------------------------------
# BofA Securities initial ATS-N (Instinct X)
# ---------------------------------------------------------------------------

class TestBofAInitial:

    def test_is_ats_object(self, bofa_initial):
        assert isinstance(bofa_initial, AlternativeTradingSystem)

    def test_form_type(self, bofa_initial):
        assert bofa_initial.form_type == "ATS-N"

    def test_is_not_amendment(self, bofa_initial):
        assert bofa_initial.is_amendment is False

    def test_amended_accession_number_absent(self, bofa_initial):
        # Initial filings have no accession-being-amended reference
        assert bofa_initial.amended_accession_number is None

    def test_amendment_statement_absent(self, bofa_initial):
        assert bofa_initial.amendment_statement is None

    def test_cik(self, bofa_initial):
        assert bofa_initial.cik == "1675365"

    def test_mpid(self, bofa_initial):
        # Ground-truth: BofA Instinct X MPID published by SEC as MLIX
        assert bofa_initial.mpid == "MLIX"

    def test_ats_name(self, bofa_initial):
        assert bofa_initial.ats_name == "Instinct X"

    def test_operator_name_exact(self, bofa_initial):
        # XML stores operator name in upper case verbatim
        assert bofa_initial.operator_name == "BOFA SECURITIES, INC."

    # ---- Part I identity ----

    def test_sro_is_finra(self, bofa_initial):
        assert bofa_initial.identifying_info.sro_name == "FINRA"

    def test_bd_file_number(self, bofa_initial):
        assert bofa_initial.identifying_info.bd_file_number == "008-69787"

    def test_bd_crd_number(self, bofa_initial):
        assert bofa_initial.identifying_info.bd_crd_number == "000283942"

    def test_supersedes_prior_form_ats_no(self, bofa_initial):
        # BofA Instinct X was new — did not operate under prior Form ATS
        assert bofa_initial.identifying_info.supersedes_prior_form_ats is False

    def test_ats_names_repeating(self, bofa_initial):
        names = [n.ats_name for n in bofa_initial.identifying_info.ats_names]
        assert "Instinct X" in names

    def test_primary_site_populated(self, bofa_initial):
        site = bofa_initial.identifying_info.primary_site
        assert site is not None
        assert site.city == "Secaucus"
        assert site.zip_code == "07094"
        assert site.state_or_country == "US-NY"

    # ---- Part III — subscriber types (ground-truth enumeration) ----

    def test_subscriber_types_include_asset_managers(self, bofa_initial):
        assert "Asset Managers" in bofa_initial.subscriber_types

    def test_subscriber_types_include_principal_trading_firms(self, bofa_initial):
        assert "Principal Trading Firms" in bofa_initial.subscriber_types

    def test_subscriber_types_include_hedge_funds(self, bofa_initial):
        assert "Hedge Funds" in bofa_initial.subscriber_types

    # ---- Part III — key regulatory flags ----

    def test_exceeds_fair_access_threshold_false(self, bofa_initial):
        # Item 25: BofA Instinct X reported N (does not exceed 5% ADV threshold)
        assert bofa_initial.operations.exceeds_fair_access_threshold is False

    def test_publishes_execution_stats_false(self, bofa_initial):
        assert bofa_initial.operations.publishes_execution_stats is False

    def test_has_segmentation(self, bofa_initial):
        assert bofa_initial.operations.has_segmentation is True

    def test_order_types_non_empty(self, bofa_initial):
        assert bofa_initial.operations.order_types
        assert len(bofa_initial.operations.order_types) > 100

    def test_nms_matching_rules_non_empty(self, bofa_initial):
        assert bofa_initial.operations.nms_matching_rules
        assert len(bofa_initial.operations.nms_matching_rules) > 100

    def test_fees_direct_non_empty(self, bofa_initial):
        assert bofa_initial.operations.fees_direct
        assert "per share" in bofa_initial.operations.fees_direct.lower()

    def test_no_oversized_pdf_attachments(self, bofa_initial):
        # BofA's initial filing fits within XML size limits — no ITM PDFs
        assert bofa_initial.operations.order_types_pdf_url is None
        assert bofa_initial.operations.conditional_orders_pdf_url is None


# ---------------------------------------------------------------------------
# Goldman Sachs Sigma X2 amendment (ATS-N/UA)
# ---------------------------------------------------------------------------

class TestGSAmendment:

    def test_is_ats_object(self, gs_amendment):
        assert isinstance(gs_amendment, AlternativeTradingSystem)

    def test_form_type(self, gs_amendment):
        assert gs_amendment.form_type == "ATS-N/UA"

    def test_is_amendment(self, gs_amendment):
        assert gs_amendment.is_amendment is True

    def test_amended_accession_number_present(self, gs_amendment):
        # Amendments reference the prior filing being amended
        assert gs_amendment.amended_accession_number is not None
        assert gs_amendment.amended_accession_number != gs_amendment._filing.accession_no

    def test_amendment_statement_present(self, gs_amendment):
        assert gs_amendment.amendment_statement is not None
        assert len(gs_amendment.amendment_statement) > 50

    def test_cik(self, gs_amendment):
        assert gs_amendment.cik == "42352"

    def test_mpid(self, gs_amendment):
        assert gs_amendment.mpid == "SGMT"

    def test_ats_name(self, gs_amendment):
        assert gs_amendment.ats_name == "Sigma X2"

    def test_supersedes_prior_form_ats_yes(self, gs_amendment):
        # GSCO operated Sigma X2 under a prior Form ATS before ATS-N existed
        assert gs_amendment.identifying_info.supersedes_prior_form_ats is True

    # ---- Oversized-field PDF attachments ----

    def test_order_types_pdf_url_present(self, gs_amendment):
        # GS Item 7A narrative overflows XML → PDF attachment
        url = gs_amendment.operations.order_types_pdf_url
        assert url is not None
        assert url.endswith(".pdf")

    def test_nms_matching_rules_pdf_url_present(self, gs_amendment):
        # GS Item 11C narrative overflows → PDF attachment
        url = gs_amendment.operations.nms_matching_rules_pdf_url
        assert url is not None
        assert url.endswith(".pdf")

    def test_segmentation_description_pdf_url_present(self, gs_amendment):
        # GS Item 13A narrative overflows → PDF attachment
        url = gs_amendment.operations.segmentation_description_pdf_url
        assert url is not None
        assert url.endswith(".pdf")


# ---------------------------------------------------------------------------
# J.P. Morgan JPB-X withdrawal (ATS-N-W)
# ---------------------------------------------------------------------------

class TestJPMWithdrawal:

    def test_is_withdrawal_object(self, jpm_withdrawal):
        assert isinstance(jpm_withdrawal, AlternativeTradingSystemWithdrawal)

    def test_not_ats_object(self, jpm_withdrawal):
        # Withdrawal is a sibling class, not a subclass of AlternativeTradingSystem
        assert not isinstance(jpm_withdrawal, AlternativeTradingSystem)

    def test_form_type(self, jpm_withdrawal):
        assert jpm_withdrawal.form_type == "ATS-N-W"

    def test_cik(self, jpm_withdrawal):
        assert jpm_withdrawal.cik == "782124"

    def test_mpid(self, jpm_withdrawal):
        assert jpm_withdrawal.mpid == "JPBX"

    def test_ats_name(self, jpm_withdrawal):
        assert jpm_withdrawal.ats_name == "JPB-X"

    def test_withdrawn_accession_number(self, jpm_withdrawal):
        # Withdrawals reference the original filing being withdrawn
        assert jpm_withdrawal.withdrawn_accession_number is not None

    def test_contact_name_present(self, jpm_withdrawal):
        # Unlike primary ATS-N filings, withdrawals carry contact info in headerData
        assert jpm_withdrawal.filer.contact_name is not None


# ---------------------------------------------------------------------------
# Filing.obj() dispatch
# ---------------------------------------------------------------------------

class TestDispatch:

    def test_initial_dispatches_to_alternative_trading_system(self, bofa_initial):
        assert isinstance(bofa_initial, AlternativeTradingSystem)

    def test_updating_amendment_dispatches_to_alternative_trading_system(self, gs_amendment):
        assert isinstance(gs_amendment, AlternativeTradingSystem)

    def test_withdrawal_dispatches_to_withdrawal(self, jpm_withdrawal):
        assert isinstance(jpm_withdrawal, AlternativeTradingSystemWithdrawal)
