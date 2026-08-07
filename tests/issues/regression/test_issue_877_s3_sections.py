"""
Regression test for Issue #877: Expose .sections on S-3 registration statements.

GitHub Issue: https://github.com/dgunning/edgartools/issues/877

Bug (FIXED): RegistrationS3 lacked the ``.sections`` accessor that
RegistrationS1 and Prospectus424B already expose, so S-3 shelf registrations
could not be section-scoped (Risk Factors, Use of Proceeds, Plan of
Distribution, ...) for RAG/NLP workflows. The root cause was two-fold:
  1. S-3 had no title-based FormSchema, so the parser did not route S-3 filings
     through the title-based section engine used for S-1 / 424B.
  2. RegistrationS3 did not extend ProspectusSectionsMixin and exposed no
     ``_document`` for the mixin to read.

Fix: Registered a title-based ``S3_SCHEMA`` (reusing the shared prospectus
section vocabulary) for S-3 / S-3/A / S-3ASR in ``edgar.documents.form_schema``,
and made ``RegistrationS3`` extend ``ProspectusSectionsMixin`` with a
``_document`` property, mirroring ``RegistrationS1`` exactly.
"""
import pytest

from edgar._filings import Filing
from edgar.documents.form_schema import get_form_schema
from edgar.offerings.prospectus._sections import ProspectusSectionsMixin
from edgar.offerings.prospectus.registration_s3 import RegistrationS3


class TestS3FormSchema:
    """Network-free checks that S-3 routes through the title-based engine."""

    def test_s3_variants_are_title_based(self):
        for form in ("S-3", "S-3/A", "S-3ASR"):
            assert get_form_schema(form).title_based is True, form

    def test_item_based_forms_unchanged(self):
        # No regression: item-based forms stay item-based.
        assert get_form_schema("8-K").title_based is False
        assert get_form_schema("10-K").title_based is False

    def test_registration_s3_exposes_sections_api(self):
        assert issubclass(RegistrationS3, ProspectusSectionsMixin)
        assert hasattr(RegistrationS3, "sections")
        assert hasattr(RegistrationS3, "section")


class TestS3SectionsGroundTruth:
    """Ground truth: a real S-3 resolves labelled Reg S-K sections.

    Vigil Neuroscience, Inc. S-3 filed 2025-03-31 (accession
    0001193125-25-067858). Verified by hand against the SEC EDGAR filing.
    """

    @pytest.mark.vcr
    def test_s3_sections_ground_truth(self):
        # Construct the Filing directly (not find()) to keep the cassette small.
        filing = Filing(
            form="S-3",
            company="Vigil Neuroscience, Inc.",
            cik=1827087,
            filing_date="2025-03-31",
            accession_no="0001193125-25-067858",
        )
        s3 = RegistrationS3.from_filing(filing)
        keys = set(s3.sections.keys())

        # Labelled prospectus sections resolved, not the single 'full' fallback.
        assert "full" not in keys
        assert {"risk_factors", "use_of_proceeds", "plan_of_distribution"} <= keys

        # Section text is real, non-trivial content.
        risk_factors = s3.section("risk_factors")
        assert risk_factors is not None
        assert len(risk_factors.text()) > 500

        # Silence check: an absent section returns None, not a crash.
        assert s3.section("this_section_does_not_exist") is None
