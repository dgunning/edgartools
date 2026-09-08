"""
Tests for FilerCategory enum and Entity filer category properties.
"""
import pytest

from edgar.enums import FilerCategory, FilerQualification, FilerStatus


class TestFilerStatus:
    """Tests for FilerStatus enum."""

    def test_filer_status_values(self):
        """Test FilerStatus enum values match SEC terminology."""
        assert FilerStatus.LARGE_ACCELERATED.value == "Large accelerated filer"
        assert FilerStatus.ACCELERATED.value == "Accelerated filer"
        assert FilerStatus.NON_ACCELERATED.value == "Non-accelerated filer"

    def test_filer_status_from_string(self):
        """Test parsing FilerStatus from string."""
        assert FilerStatus.from_string("Large accelerated filer") == FilerStatus.LARGE_ACCELERATED
        assert FilerStatus.from_string("Accelerated filer") == FilerStatus.ACCELERATED
        assert FilerStatus.from_string("Non-accelerated filer") == FilerStatus.NON_ACCELERATED

    def test_filer_status_from_string_case_insensitive(self):
        """Test FilerStatus parsing is case insensitive."""
        assert FilerStatus.from_string("LARGE ACCELERATED FILER") == FilerStatus.LARGE_ACCELERATED
        assert FilerStatus.from_string("large accelerated filer") == FilerStatus.LARGE_ACCELERATED

    def test_filer_status_from_string_unknown(self):
        """Test FilerStatus returns None for unknown values."""
        assert FilerStatus.from_string("Unknown filer") is None
        assert FilerStatus.from_string("") is None
        assert FilerStatus.from_string(None) is None


class TestFilerQualification:
    """Tests for FilerQualification enum."""

    def test_filer_qualification_values(self):
        """Test FilerQualification enum values."""
        assert FilerQualification.SMALLER_REPORTING_COMPANY.value == "Smaller reporting company"
        assert FilerQualification.EMERGING_GROWTH_COMPANY.value == "Emerging growth company"


class TestFilerCategory:
    """Tests for FilerCategory parsing class."""

    def test_parse_large_accelerated(self):
        """Test parsing large accelerated filer."""
        fc = FilerCategory.from_string("Large accelerated filer")
        assert fc.status == FilerStatus.LARGE_ACCELERATED
        assert fc.is_large_accelerated_filer is True
        assert fc.is_accelerated_filer is False
        assert fc.is_non_accelerated_filer is False
        assert fc.is_smaller_reporting_company is False
        assert fc.is_emerging_growth_company is False

    def test_parse_accelerated(self):
        """Test parsing accelerated filer."""
        fc = FilerCategory.from_string("Accelerated filer")
        assert fc.status == FilerStatus.ACCELERATED
        assert fc.is_accelerated_filer is True

    def test_parse_non_accelerated(self):
        """Test parsing non-accelerated filer."""
        fc = FilerCategory.from_string("Non-accelerated filer")
        assert fc.status == FilerStatus.NON_ACCELERATED
        assert fc.is_non_accelerated_filer is True

    def test_parse_with_smaller_reporting_company(self):
        """Test parsing filer with SRC qualification."""
        fc = FilerCategory.from_string("Accelerated filer | Smaller reporting company")
        assert fc.status == FilerStatus.ACCELERATED
        assert fc.is_smaller_reporting_company is True
        assert fc.is_emerging_growth_company is False

    def test_parse_with_emerging_growth_company(self):
        """Test parsing filer with EGC qualification."""
        fc = FilerCategory.from_string("Accelerated filer | Emerging growth company")
        assert fc.status == FilerStatus.ACCELERATED
        assert fc.is_smaller_reporting_company is False
        assert fc.is_emerging_growth_company is True

    def test_parse_with_both_qualifications(self):
        """Test parsing filer with both SRC and EGC."""
        fc = FilerCategory.from_string(
            "Non-accelerated filer | Smaller reporting company | Emerging growth company"
        )
        assert fc.status == FilerStatus.NON_ACCELERATED
        assert fc.is_smaller_reporting_company is True
        assert fc.is_emerging_growth_company is True
        assert len(fc.qualifications) == 2

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        fc = FilerCategory.from_string("")
        assert fc.status is None
        assert fc.is_smaller_reporting_company is False
        assert fc.is_emerging_growth_company is False
        assert bool(fc) is False

    def test_parse_none(self):
        """Test parsing None."""
        fc = FilerCategory.from_string(None)
        assert fc.status is None
        assert bool(fc) is False

    def test_parse_egc_only(self):
        """Test parsing EGC without base status (edge case)."""
        fc = FilerCategory.from_string(" | Emerging growth company")
        assert fc.status is None
        assert fc.is_emerging_growth_company is True

    def test_str_representation(self):
        """Test string representation preserves original."""
        original = "Accelerated filer | Smaller reporting company"
        fc = FilerCategory.from_string(original)
        assert str(fc) == original

    def test_repr(self):
        """Test repr output."""
        fc = FilerCategory.from_string("Large accelerated filer")
        assert "FilerCategory" in repr(fc)
        assert "Large accelerated filer" in repr(fc)

    def test_bool_true_with_status(self):
        """Test bool is True when status is present."""
        fc = FilerCategory.from_string("Large accelerated filer")
        assert bool(fc) is True

    def test_bool_true_with_qualification_only(self):
        """Test bool is True when only qualification is present."""
        fc = FilerCategory.from_string(" | Smaller reporting company")
        assert bool(fc) is True

    def test_qualifications_property(self):
        """Test qualifications property returns list."""
        fc = FilerCategory.from_string(
            "Non-accelerated filer | Smaller reporting company | Emerging growth company"
        )
        quals = fc.qualifications
        assert FilerQualification.SMALLER_REPORTING_COMPANY in quals
        assert FilerQualification.EMERGING_GROWTH_COMPANY in quals


class TestEntityFilerCategory:
    """Integration tests for Entity filer category properties."""

    def test_apple_large_accelerated(self):
        """Test Apple is large accelerated filer."""
        from edgar import Company

        aapl = Company("AAPL")
        assert aapl.is_large_accelerated_filer is True
        assert aapl.is_accelerated_filer is False
        assert aapl.is_non_accelerated_filer is False
        assert aapl.is_smaller_reporting_company is False
        assert aapl.is_emerging_growth_company is False

    def test_filer_category_property(self):
        """Test filer_category property returns FilerCategory."""
        from edgar import Company

        aapl = Company("AAPL")
        fc = aapl.filer_category
        assert isinstance(fc, FilerCategory)
        assert fc.status == FilerStatus.LARGE_ACCELERATED

    def test_microsoft_large_accelerated(self):
        """Test Microsoft is large accelerated filer."""
        from edgar import Company

        msft = Company("MSFT")
        assert msft.is_large_accelerated_filer is True

    def test_filer_category_cached(self):
        """Test filer_category is cached."""
        from edgar import Company

        aapl = Company("AAPL")
        fc1 = aapl.filer_category
        fc2 = aapl.filer_category
        assert fc1 is fc2  # Same object due to caching
