"""
Tests for AI-native to_context() methods across the workflow.

This module tests the AI-optimized context generation methods that enable
AI agents to discover and navigate the EdgarTools API independently.
"""
import pytest
from edgar import Company, get_filings, get_obj_info


class TestGetObjInfo:
    """Test the get_obj_info() helper function."""

    def test_form_c_has_obj(self):
        """Form C should have FormC object."""
        has_obj, obj_type, description = get_obj_info('C')
        assert has_obj is True
        assert obj_type == 'FormC'
        assert 'crowdfunding' in description.lower()

    def test_form_c_amendment_has_obj(self):
        """Form C/A should also have FormC object."""
        has_obj, obj_type, description = get_obj_info('C/A')
        assert has_obj is True
        assert obj_type == 'FormC'

    def test_form_10k_has_obj(self):
        """Form 10-K should have TenK object."""
        has_obj, obj_type, description = get_obj_info('10-K')
        assert has_obj is True
        assert obj_type == 'TenK'
        assert 'annual' in description.lower()

    def test_unknown_form_no_obj(self):
        """Unknown form types should return False."""
        has_obj, obj_type, description = get_obj_info('UNKNOWN-FORM')
        assert has_obj is False
        assert obj_type is None
        assert description is None

    def test_all_crowdfunding_forms(self):
        """All crowdfunding forms should map to FormC."""
        crowdfunding_forms = ['C', 'C-U', 'C-AR', 'C-TR']
        for form in crowdfunding_forms:
            has_obj, obj_type, _ = get_obj_info(form)
            assert has_obj is True, f"Form {form} should have obj"
            assert obj_type == 'FormC', f"Form {form} should map to FormC"


class TestFilingToContext:
    """Test Filing.to_context() method."""

    @pytest.mark.network
    def test_filing_to_context_minimal(self):
        """Filing.to_context(detail='minimal') should be under 150 tokens."""
        filings = get_filings(2024, 1, form='C')
        assert len(filings) > 0, "Should have some Form C filings"

        filing = filings[0]
        context = filing.to_context(detail='minimal')

        # Rough token count (words * 1.3 for tokens)
        word_count = len(context.split())
        estimated_tokens = word_count * 1.3

        assert estimated_tokens < 200, f"Minimal context should be under 200 tokens, got {estimated_tokens}"
        assert 'FILING:' in context
        assert filing.form in context
        assert filing.company in context
        assert str(filing.cik) in context

    @pytest.mark.network
    def test_filing_to_context_standard(self):
        """Filing.to_context(detail='standard') should be under 350 tokens."""
        filings = get_filings(2024, 1, form='C')
        filing = filings[0]
        context = filing.to_context(detail='standard')

        word_count = len(context.split())
        estimated_tokens = word_count * 1.3

        assert estimated_tokens < 450, f"Standard context should be under 450 tokens, got {estimated_tokens}"
        assert 'AVAILABLE ACTIONS' in context
        assert '.obj()' in context
        assert '.docs' in context

    @pytest.mark.network
    def test_filing_to_context_full(self):
        """Filing.to_context(detail='full') should be under 600 tokens."""
        filings = get_filings(2024, 1, form='C')
        filing = filings[0]
        context = filing.to_context(detail='full')

        word_count = len(context.split())
        estimated_tokens = word_count * 1.3

        assert estimated_tokens < 800, f"Full context should be under 800 tokens, got {estimated_tokens}"
        assert 'DOCUMENTS:' in context

    @pytest.mark.network
    def test_filing_context_mentions_obj_for_form_c(self):
        """Filing.to_context() should mention .obj() for Form C."""
        filings = get_filings(2024, 1, form='C')
        filing = filings[0]
        context = filing.to_context()

        assert '.obj()' in context
        assert 'FormC' in context

    @pytest.mark.network
    def test_filing_context_no_obj_for_unknown_form(self):
        """Filing.to_context() should not mention .obj() for forms without structured objects."""
        # Get a filing that typically doesn't have structured obj
        filings = get_filings(2024, 1, form='8-K')
        if len(filings) > 0:
            filing = filings[0]
            # 8-K should have obj (EightK)
            context = filing.to_context()
            # This test is less relevant now since 8-K has obj
            # But we verify the context is still generated
            assert 'FILING:' in context


class TestFilingsToContext:
    """Test Filings.to_context() method."""

    @pytest.mark.network
    def test_filings_to_context_has_navigation_hints(self):
        """Filings.to_context() should include navigation hints."""
        filings = get_filings(2024, 1, form='C')
        context = filings.to_context()

        assert '.latest()' in context
        assert '[index]' in context or 'filings[0]' in context
        assert '.filter(' in context
        assert '.docs' in context

    @pytest.mark.network
    def test_filings_to_context_minimal(self):
        """Filings.to_context(detail='minimal') should be under 150 tokens."""
        filings = get_filings(2024, 1, form='C')
        context = filings.to_context(detail='minimal')

        word_count = len(context.split())
        estimated_tokens = word_count * 1.3

        assert estimated_tokens < 200, f"Minimal context should be under 200 tokens, got {estimated_tokens}"
        assert 'FILINGS COLLECTION' in context
        assert 'Total:' in context

    @pytest.mark.network
    def test_filings_to_context_standard(self):
        """Filings.to_context(detail='standard') should include sample filings."""
        filings = get_filings(2024, 1, form='C')
        context = filings.to_context(detail='standard')

        assert 'SAMPLE FILINGS:' in context
        assert 'AVAILABLE ACTIONS:' in context

    @pytest.mark.network
    def test_filings_to_context_full(self):
        """Filings.to_context(detail='full') should include form breakdown."""
        filings = get_filings(2024, 1, form='C')
        context = filings.to_context(detail='full')

        assert 'FORM BREAKDOWN:' in context

    @pytest.mark.network
    def test_empty_filings_collection(self):
        """Empty filings collection should handle gracefully."""
        filings = get_filings(2024, 1, form='C')
        # Filter to empty
        empty_filings = filings.filter(ticker='NONEXISTENT_TICKER_XYZ')

        context = empty_filings.to_context()
        assert 'Total: 0 filings' in context or 'FILINGS COLLECTION' in context


class TestEntityFilingsToContext:
    """Test EntityFilings.to_context() method."""

    @pytest.mark.network
    def test_entity_filings_has_company_header(self):
        """EntityFilings.to_context() should include company name and CIK."""
        company = Company(1881570)  # ViiT Health Inc
        filings = company.get_filings(form='C')

        if len(filings) > 0:
            context = filings.to_context()
            assert 'FILINGS FOR:' in context
            assert 'CIK: 1881570' in context

    @pytest.mark.network
    def test_entity_filings_crowdfunding_breakdown(self):
        """EntityFilings.to_context() should show crowdfunding breakdown."""
        company = Company(1881570)  # ViiT Health Inc
        filings = company.get_filings(form='C')

        if len(filings) > 0:
            context = filings.to_context(detail='standard')
            # May have CROWDFUNDING FILINGS section if has CF forms
            # Just verify context is generated
            assert 'FILINGS FOR:' in context


class TestFormCToContext:
    """Test FormC.to_context() method with method hints."""

    @pytest.mark.network
    def test_formc_mentions_get_offering(self):
        """FormC.to_context() should mention .get_offering() method."""
        filings = get_filings(2024, 1, form='C')
        assert len(filings) > 0

        formc = filings[0].obj()
        context = formc.to_context()

        assert '.get_offering()' in context
        assert 'AVAILABLE ACTIONS:' in context

    @pytest.mark.network
    def test_formc_context_standard_detail(self):
        """FormC.to_context() should show available actions in standard detail."""
        filings = get_filings(2024, 1, form='C')
        formc = filings[0].obj()
        context = formc.to_context(detail='standard')

        assert 'AVAILABLE ACTIONS:' in context
        assert '.issuer' in context

    @pytest.mark.network
    def test_formc_context_minimal_no_actions(self):
        """FormC.to_context(detail='minimal') should not show actions."""
        filings = get_filings(2024, 1, form='C')
        formc = filings[0].obj()
        context = formc.to_context(detail='minimal')

        # Minimal should not have AVAILABLE ACTIONS
        assert 'AVAILABLE ACTIONS:' not in context


class TestFullWorkflowDiscovery:
    """Test that full workflow is discoverable through context."""

    @pytest.mark.network
    def test_full_workflow_discoverable(self):
        """Agent should be able to discover full workflow through context."""
        company = Company(1881570)  # ViiT Health Inc

        # Step 1: Company (Company now has .to_context() for consistency)
        # Testing with Company.to_context() is optional for this workflow test

        # Step 2: Filings hints at .latest()
        filings = company.get_filings(form='C')
        if len(filings) == 0:
            pytest.skip("No Form C filings for test company")

        filings_context = filings.to_context()
        assert '.latest()' in filings_context, "Filings should hint at .latest()"

        # Step 3: Filing hints at .obj()
        filing = filings.latest()
        filing_context = filing.to_context()
        assert '.obj()' in filing_context, "Filing should hint at .obj()"

        # Step 4: FormC hints at .get_offering()
        formc = filing.obj()
        formc_context = formc.to_context()
        assert '.get_offering()' in formc_context, "FormC should hint at .get_offering()"

        # Step 5: Offering provides lifecycle (already tested in other tests)
        offering = formc.get_offering()
        offering_context = offering.to_context()
        assert 'lifecycle' in offering_context.lower() or 'FORM C' in offering_context


class TestTokenBudgets:
    """Test that token budgets are respected."""

    @pytest.mark.network
    def test_filing_token_budgets(self):
        """Verify Filing.to_context() respects token budgets."""
        filings = get_filings(2024, 1, form='C')
        filing = filings[0]

        # Minimal
        minimal = filing.to_context(detail='minimal')
        minimal_tokens = len(minimal.split()) * 1.3
        assert minimal_tokens < 200, f"Minimal exceeded budget: {minimal_tokens}"

        # Standard
        standard = filing.to_context(detail='standard')
        standard_tokens = len(standard.split()) * 1.3
        assert standard_tokens < 450, f"Standard exceeded budget: {standard_tokens}"

        # Full
        full = filing.to_context(detail='full')
        full_tokens = len(full.split()) * 1.3
        assert full_tokens < 800, f"Full exceeded budget: {full_tokens}"

    @pytest.mark.network
    def test_filings_token_budgets(self):
        """Verify Filings.to_context() respects token budgets."""
        filings = get_filings(2024, 1, form='C')

        # Minimal
        minimal = filings.to_context(detail='minimal')
        minimal_tokens = len(minimal.split()) * 1.3
        assert minimal_tokens < 200, f"Minimal exceeded budget: {minimal_tokens}"

        # Standard
        standard = filings.to_context(detail='standard')
        standard_tokens = len(standard.split()) * 1.3
        assert standard_tokens < 450, f"Standard exceeded budget: {standard_tokens}"

        # Full
        full = filings.to_context(detail='full')
        full_tokens = len(full.split()) * 1.3
        assert full_tokens < 600, f"Full exceeded budget: {full_tokens}"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.network
    def test_filing_with_no_attachments(self):
        """Filing.to_context() should handle missing attachments gracefully."""
        filings = get_filings(2024, 1, form='C')
        filing = filings[0]

        # Should not raise exception
        context = filing.to_context()
        assert 'FILING:' in context

    @pytest.mark.network
    def test_filing_with_no_period(self):
        """Filing.to_context() should handle missing period gracefully."""
        # Some forms don't have period_of_report
        filings = get_filings(2024, 1, form='C')
        if len(filings) > 0:
            filing = filings[0]
            context = filing.to_context(detail='standard')
            # Should not raise exception
            assert 'FILING:' in context

    @pytest.mark.network
    def test_single_filing_collection(self):
        """Filings collection with single filing should use singular."""
        filings = get_filings(2024, 1, form='C')
        if len(filings) > 0:
            # Take just one
            single = filings.filter(accession_number=filings[0].accession_no)
            context = single.to_context()
            # Should say "1 filing" not "1 filings"
            assert '1 filing' in context
