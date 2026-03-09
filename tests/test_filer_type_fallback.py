"""
Tests for filer_type fallback when state_of_incorporation is missing.

Issue #562: When ~955 out of 7947 companies have no state_of_incorporation,
filer_type should fall back to inferring from filed form types.
"""

import pytest
from unittest.mock import patch


class TestFilerTypeFallback:
    """Test filer_type uses form-based fallback when state_of_incorporation is missing."""

    @pytest.mark.fast
    def test_filer_type_domestic_from_state(self):
        """Domestic company with state_of_incorporation returns 'Domestic'."""
        from edgar import Company
        company = Company("AAPL")
        assert company.filer_type == 'Domestic'

    @pytest.mark.fast
    def test_filer_type_foreign_from_state(self):
        """Foreign company with state_of_incorporation returns 'Foreign'."""
        from edgar import Company
        company = Company("BABA")
        assert company.filer_type == 'Foreign'

    @pytest.mark.fast
    def test_is_foreign_domestic_company(self):
        """Domestic company is not foreign."""
        from edgar import Company
        company = Company("AAPL")
        assert company.is_foreign is False

    @pytest.mark.fast
    def test_is_foreign_foreign_company(self):
        """Foreign company is foreign."""
        from edgar import Company
        company = Company("BABA")
        assert company.is_foreign is True

    @pytest.mark.fast
    def test_filer_type_fallback_to_10k(self):
        """When state_of_incorporation is empty, 10-K filings indicate Domestic."""
        from edgar import Company
        company = Company("AAPL")
        # Clear cached_property so it re-evaluates
        company.__dict__.pop('filer_type', None)
        # Simulate missing state_of_incorporation
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'10-K', '10-Q', '8-K'}):
                assert company.filer_type == 'Domestic'
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_filer_type_fallback_to_20f(self):
        """When state_of_incorporation is empty, 20-F filings indicate Foreign."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'20-F', '6-K'}):
                assert company.filer_type == 'Foreign'
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_filer_type_fallback_to_40f(self):
        """When state_of_incorporation is empty, 40-F filings indicate Canadian."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'40-F', '6-K'}):
                assert company.filer_type == 'Canadian'
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_filer_type_fallback_amended_forms(self):
        """Amended forms (20-F/A, 40-F/A, 10-K/A) also trigger fallback."""
        from edgar import Company
        company = Company("AAPL")
        original = company.data.state_of_incorporation

        for form, expected in [('20-F/A', 'Foreign'), ('40-F/A', 'Canadian'), ('10-K/A', 'Domestic')]:
            company.__dict__.pop('filer_type', None)
            company.data.state_of_incorporation = ''
            try:
                with patch.object(company, '_get_form_types', return_value={form, '8-K'}):
                    result = company.filer_type
                    assert result == expected, f"Expected {expected} for form {form}, got {result}"
            finally:
                company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_filer_type_fallback_returns_none_when_no_forms(self):
        """When no state and no recognizable forms, returns None."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'SC 13G', '4'}):
                assert company.filer_type is None
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_is_foreign_fallback_with_20f(self):
        """is_foreign returns True when state missing but 20-F filed."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'20-F', '6-K'}):
                assert company.is_foreign is True
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_is_foreign_fallback_with_10k(self):
        """is_foreign returns False when state missing but 10-K filed."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'10-K', '10-Q'}):
                assert company.is_foreign is False
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_filer_type_fallback_6k_means_foreign(self):
        """6-K (foreign current report) indicates Foreign even without 20-F."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'6-K', '8-K'}):
                assert company.filer_type == 'Foreign'
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_filer_type_fallback_10q_means_domestic(self):
        """10-Q (quarterly report) indicates Domestic even without 10-K."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'10-Q', '8-K'}):
                assert company.filer_type == 'Domestic'
        finally:
            company.data.state_of_incorporation = original

    @pytest.mark.fast
    def test_20f_takes_priority_over_10k(self):
        """If both 20-F and 10-K present, 20-F wins (Foreign)."""
        from edgar import Company
        company = Company("AAPL")
        company.__dict__.pop('filer_type', None)
        original = company.data.state_of_incorporation
        company.data.state_of_incorporation = ''
        try:
            with patch.object(company, '_get_form_types', return_value={'20-F', '10-K'}):
                assert company.filer_type == 'Foreign'
        finally:
            company.data.state_of_incorporation = original
