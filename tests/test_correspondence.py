"""
Verification tests for SEC Correspondence (CORRESP / UPLOAD) support.

Tests use VCR cassettes to replay network requests deterministically.
"""

import pytest
from edgar import get_by_accession_number, get_obj_info
from edgar.correspondence import (
    Correspondence,
    CorrespondenceThread,
    CorrespondenceType,
    _extract_file_number,
    _extract_referenced_form,
    _classify_correspondence,
)


# ---------------------------------------------------------------------------
# Unit tests: metadata extraction (no network)
# ---------------------------------------------------------------------------

class TestMetadataExtraction:
    """Test regex-based extraction from correspondence text."""

    def test_extract_file_number_standard(self):
        text = "Re: Apple Inc.\nFile No. 001-36743\n"
        assert _extract_file_number(text) == "001-36743"

    def test_extract_file_number_with_colon(self):
        text = "Re: SomeCompany\nFile No.: 333-293459\n"
        assert _extract_file_number(text) == "333-293459"

    def test_extract_file_number_no_period(self):
        text = "Re: SomeCompany\nFile No 001-12345\n"
        assert _extract_file_number(text) == "001-12345"

    def test_extract_file_number_missing(self):
        text = "Dear Sir,\nPlease find enclosed.\n"
        assert _extract_file_number(text) is None

    def test_extract_referenced_form_10k(self):
        text = "Re: Apple Inc.\nForm 10-K for the fiscal year ended\n"
        assert _extract_referenced_form(text) == "10-K"

    def test_extract_referenced_form_s3(self):
        text = "Re: BAM Finance LLC\nRegistration Statement on Form F-3\n"
        assert _extract_referenced_form(text) == "F-3"

    def test_extract_referenced_form_s1(self):
        text = "Re: SomeCompany\nForm S-1 Registration\n"
        assert _extract_referenced_form(text) == "S-1"


class TestClassification:
    """Test correspondence type classification."""

    def test_review_complete(self):
        result = _classify_correspondence("UPLOAD", "We have completed our review of your filing.")
        assert result == CorrespondenceType.REVIEW_COMPLETE

    def test_no_review(self):
        result = _classify_correspondence(
            "UPLOAD",
            "This is to advise you that we have not reviewed and will not review your registration statement."
        )
        assert result == CorrespondenceType.NO_REVIEW

    def test_sec_comment_numbered(self):
        result = _classify_correspondence("UPLOAD", "We have the following comments.\n\n1. Please explain")
        assert result == CorrespondenceType.SEC_COMMENT

    def test_sec_comment_please_explain(self):
        result = _classify_correspondence("UPLOAD", "Please describe further the qualitative factors")
        assert result == CorrespondenceType.SEC_COMMENT

    def test_acceleration_request_rule461(self):
        result = _classify_correspondence(
            "CORRESP", "pursuant to Rule 461 of the General Rules"
        )
        assert result == CorrespondenceType.ACCELERATION_REQUEST

    def test_company_response(self):
        result = _classify_correspondence(
            "CORRESP", "provides the following response to the comments"
        )
        assert result == CorrespondenceType.COMPANY_RESPONSE

    def test_company_letter_fallback(self):
        result = _classify_correspondence("CORRESP", "Dear Sir, Please find enclosed documents.")
        assert result == CorrespondenceType.COMPANY_LETTER

    def test_sec_letter_fallback(self):
        result = _classify_correspondence("UPLOAD", "Dear Sir, Please find enclosed documents.")
        assert result == CorrespondenceType.SEC_LETTER


# ---------------------------------------------------------------------------
# Network tests: real filing parsing
# ---------------------------------------------------------------------------

class TestCorrespondenceFromFiling:
    """Verify Correspondence.from_filing() parses real filings correctly."""

    @pytest.mark.vcr
    def test_apple_corresp_is_company_response(self):
        """Apple CORRESP filing classified as company_response with correct metadata."""
        filing = get_by_accession_number('0000320193-24-000061')
        corresp = Correspondence.from_filing(filing)
        assert isinstance(corresp, Correspondence)
        assert corresp.correspondence_type == CorrespondenceType.COMPANY_RESPONSE
        assert corresp.referenced_file_number == "001-36743"
        assert corresp.referenced_form == "10-K"
        assert corresp.sender == "company"
        assert corresp.fiscal_year_end == "September 30, 2023"
        assert corresp.response_date == "March 20, 2024"

    @pytest.mark.vcr
    def test_apple_upload_is_sec_comment(self):
        """Apple UPLOAD filing classified as sec_comment."""
        filing = get_by_accession_number('0000000000-24-003505')
        corresp = Correspondence.from_filing(filing)
        assert isinstance(corresp, Correspondence)
        assert corresp.correspondence_type == CorrespondenceType.SEC_COMMENT
        assert corresp.referenced_file_number == "001-36743"
        assert corresp.sender == "sec"

    @pytest.mark.vcr
    def test_apple_review_complete(self):
        """Apple UPLOAD with 'completed our review' classified correctly."""
        filing = get_by_accession_number('0000000000-24-005673')
        corresp = Correspondence.from_filing(filing)
        assert corresp.correspondence_type == CorrespondenceType.REVIEW_COMPLETE
        assert corresp.sender == "sec"
        assert corresp.referenced_file_number == "001-36743"

    @pytest.mark.vcr
    def test_acceleration_request(self):
        """Nuvectis CORRESP Rule 461 acceleration request."""
        filing = get_by_accession_number('0001104659-26-017097')
        corresp = Correspondence.from_filing(filing)
        assert corresp.correspondence_type == CorrespondenceType.ACCELERATION_REQUEST
        assert corresp.sender == "company"
        assert corresp.referenced_file_number == "333-293459"

    @pytest.mark.vcr
    def test_no_review_notice(self):
        """Nuvectis UPLOAD 'will not review' classified as NO_REVIEW."""
        filing = get_by_accession_number('0000000000-26-001655')
        corresp = Correspondence.from_filing(filing)
        assert corresp.correspondence_type == CorrespondenceType.NO_REVIEW
        assert corresp.sender == "sec"
        assert corresp.referenced_file_number == "333-293459"
        assert corresp.referenced_form == "S-3"


class TestObjDispatch:
    """Verify filing.obj() returns Correspondence for CORRESP/UPLOAD."""

    @pytest.mark.vcr
    def test_corresp_returns_correspondence(self):
        filing = get_by_accession_number('0000320193-24-000061')
        result = filing.obj()
        assert isinstance(result, Correspondence)
        assert result.correspondence_type == CorrespondenceType.COMPANY_RESPONSE

    @pytest.mark.vcr
    def test_upload_returns_correspondence(self):
        filing = get_by_accession_number('0000000000-24-005673')
        result = filing.obj()
        assert isinstance(result, Correspondence)
        assert result.correspondence_type == CorrespondenceType.REVIEW_COMPLETE

    def test_get_obj_info_corresp(self):
        has_obj, class_name, desc = get_obj_info('CORRESP')
        assert has_obj is True
        assert class_name == 'Correspondence'

    def test_get_obj_info_upload(self):
        has_obj, class_name, desc = get_obj_info('UPLOAD')
        assert has_obj is True
        assert class_name == 'Correspondence'


class TestCorrespondenceDisplay:
    """Verify Rich display renders without errors."""

    @pytest.mark.vcr
    def test_correspondence_repr_succeeds(self):
        filing = get_by_accession_number('0000320193-24-000061')
        corresp = Correspondence.from_filing(filing)
        text = repr(corresp)
        assert "Apple" in text
        assert "Company Response" in text

    @pytest.mark.vcr
    def test_correspondence_str(self):
        filing = get_by_accession_number('0000320193-24-000061')
        corresp = Correspondence.from_filing(filing)
        text = str(corresp)
        assert "CORRESP" in text
        assert "company_response" in text

    @pytest.mark.vcr
    def test_correspondence_to_context(self):
        filing = get_by_accession_number('0000320193-24-000061')
        corresp = Correspondence.from_filing(filing)
        ctx = corresp.to_context()
        assert "CORRESPONDENCE" in ctx
        assert "001-36743" in ctx
        assert "10-K" in ctx


class TestCorrespondenceType:
    """Verify CorrespondenceType enum."""

    def test_display_names(self):
        assert CorrespondenceType.COMPANY_RESPONSE.display_name == "Company Response"
        assert CorrespondenceType.ACCELERATION_REQUEST.display_name == "Acceleration Request"
        assert CorrespondenceType.SEC_COMMENT.display_name == "SEC Comment Letter"
        assert CorrespondenceType.REVIEW_COMPLETE.display_name == "Review Complete"
        assert CorrespondenceType.NO_REVIEW.display_name == "No Review Notice"

    def test_string_enum(self):
        assert CorrespondenceType.COMPANY_RESPONSE == "company_response"
        assert CorrespondenceType.SEC_COMMENT == "sec_comment"
