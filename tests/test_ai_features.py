"""
Tests for EdgarTools AI features.

These tests verify the AI functionality including LLM context generation,
token optimization, and MCP server capabilities.
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch

# Test imports with graceful handling
try:
    from edgar.ai import (
        AIEnabled,
        TokenOptimizer,
        SemanticEnricher,
        enhance_financial_fact_llm_context,
        check_ai_capabilities,
        AI_AVAILABLE,
        MCP_AVAILABLE
    )
    AI_IMPORTED = True
except ImportError:
    AI_IMPORTED = False


@pytest.mark.skipif(not AI_IMPORTED, reason="AI package not available")
class TestTokenOptimizer:
    """Test token optimization functionality."""
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        # Test string estimation
        text = "This is a test string with some content."
        tokens = TokenOptimizer.estimate_tokens(text)
        assert tokens > 0
        assert tokens == len(text) // 4
        
        # Test dict estimation
        data = {"key": "value", "number": 123}
        tokens = TokenOptimizer.estimate_tokens(data)
        assert tokens > 0
        
    def test_optimize_for_tokens(self):
        """Test content optimization for token limits."""
        content = {
            "concept": "Revenue",
            "value": "125,000 million",
            "unit": "USD",
            "period": "for Q1 2024",
            "context": "Product sales revenue",
            "quality": "high",
            "confidence": 0.95,
            "source": "10-Q filed 2024-04-30",
            "extra_data": "This is additional data that might be truncated"
        }
        
        # Test no optimization needed
        result = TokenOptimizer.optimize_for_tokens(content, 1000)
        assert result == content
        
        # Test optimization required
        result = TokenOptimizer.optimize_for_tokens(content, 50)
        assert len(str(result)) < len(str(content))
        assert "_truncated" in result
        assert "concept" in result  # High priority fields retained


@pytest.mark.skipif(not AI_IMPORTED, reason="AI package not available")
class TestSemanticEnricher:
    """Test semantic enrichment functionality."""
    
    def test_get_concept_definition(self):
        """Test concept definition retrieval."""
        # Test known concept
        definition = SemanticEnricher.get_concept_definition("Revenue")
        assert definition is not None
        assert "income" in definition.lower()
        
        # Test with namespace
        definition = SemanticEnricher.get_concept_definition("us-gaap:Revenue")
        assert definition is not None
        
        # Test unknown concept
        definition = SemanticEnricher.get_concept_definition("UnknownConcept")
        assert definition is None
        
    def test_get_related_concepts(self):
        """Test related concept retrieval."""
        # Test known concept
        related = SemanticEnricher.get_related_concepts("Revenue")
        assert isinstance(related, list)
        assert len(related) > 0
        assert "NetIncome" in related
        
        # Test unknown concept
        related = SemanticEnricher.get_related_concepts("UnknownConcept")
        assert related == []
        
    def test_interpret_value(self):
        """Test value interpretation."""
        # Test revenue interpretation
        interpretation = SemanticEnricher.interpret_value(
            "Revenue", 125_000_000_000, "USD"
        )
        assert "billion-dollar" in interpretation
        
        # Test net income interpretation
        interpretation = SemanticEnricher.interpret_value(
            "NetIncome", -1_000_000, "USD"
        )
        assert "loss" in interpretation
        
        # Test cash interpretation
        interpretation = SemanticEnricher.interpret_value(
            "CashAndCashEquivalents", 50_000_000_000, "USD"
        )
        assert "strong" in interpretation.lower()


@pytest.mark.skipif(not AI_IMPORTED, reason="AI package not available")
class TestAIEnabled:
    """Test AIEnabled mixin functionality."""
    
    def test_ai_enabled_abstract_methods(self):
        """Test that AIEnabled enforces abstract methods."""
        with pytest.raises(TypeError):
            # Should not be able to instantiate without implementing abstract methods
            AIEnabled()


@pytest.mark.skipif(not AI_IMPORTED, reason="AI package not available")
class TestEnhanceFinancialFact:
    """Test financial fact enhancement."""
    
    def test_enhance_financial_fact_minimal(self):
        """Test minimal enhancement."""
        # Create mock fact
        mock_fact = Mock()
        mock_fact.to_llm_context.return_value = {
            "concept": "Revenue",
            "value": "125,000 million",
            "unit": "USD",
            "period": "for Q1 2024"
        }
        mock_fact.concept = "us-gaap:Revenue"
        mock_fact.numeric_value = 125_000_000_000
        mock_fact.unit = "USD"
        mock_fact.period_type = "duration"
        
        result = enhance_financial_fact_llm_context(mock_fact, detail_level='minimal')
        assert "concept" in result
        assert "definition" not in result  # Minimal doesn't include definition
        
    def test_enhance_financial_fact_standard(self):
        """Test standard enhancement."""
        mock_fact = Mock()
        mock_fact.to_llm_context.return_value = {
            "concept": "Revenue",
            "value": "125,000 million",
            "unit": "USD",
            "period": "for Q1 2024"
        }
        mock_fact.concept = "us-gaap:Revenue"
        mock_fact.numeric_value = 125_000_000_000
        mock_fact.unit = "USD"
        mock_fact.period_type = "duration"
        
        result = enhance_financial_fact_llm_context(mock_fact, detail_level='standard')
        assert "definition" in result
        assert "interpretation" in result
        assert "related_concepts" not in result  # Standard doesn't include related
        
    def test_enhance_financial_fact_detailed(self):
        """Test detailed enhancement."""
        mock_fact = Mock()
        mock_fact.to_llm_context.return_value = {
            "concept": "Revenue",
            "value": "125,000 million",
            "unit": "USD",
            "period": "for Q1 2024"
        }
        mock_fact.concept = "us-gaap:Revenue"
        mock_fact.numeric_value = 125_000_000_000
        mock_fact.unit = "USD"
        mock_fact.period_type = "duration"
        mock_fact.taxonomy = "us-gaap"
        mock_fact.scale = 1
        mock_fact.statement_type = "IncomeStatement"
        
        result = enhance_financial_fact_llm_context(mock_fact, detail_level='detailed')
        assert "definition" in result
        assert "interpretation" in result
        assert "related_concepts" in result
        assert "metadata" in result


@pytest.mark.skipif(not AI_IMPORTED, reason="AI package not available")
def test_check_ai_capabilities():
    """Test AI capability checking."""
    capabilities = check_ai_capabilities()
    
    assert isinstance(capabilities, dict)
    assert capabilities['basic'] is True
    assert capabilities['semantic_enrichment'] is True
    assert 'mcp' in capabilities
    assert 'token_optimization' in capabilities


# Test without AI package installed
class TestWithoutAIPackage:
    """Test behavior when AI package is not installed."""
    
    def test_import_error_message(self):
        """Test helpful error messages when AI not available."""
        # This test is tricky since AI is actually available
        # Test that we get helpful messages in the info function
        from edgar.ai import get_ai_info
        info = get_ai_info()
        
        # Should have install command if any deps are missing
        if info['missing_dependencies']:
            assert "pip install edgartools[ai]" in info['install_command']


# Integration test for MCP server (if available)
@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP not available")
@pytest.mark.integration
class TestMCPServer:
    """Test MCP server functionality."""
    
    def test_edgar_tools_server_creation(self):
        """Test creating EdgarTools MCP server."""
        # Test that the server module can be imported
        try:
            import edgar.ai.edgartools_mcp_server as server_module
            assert hasattr(server_module, 'app'), "Server should have app instance"
            assert hasattr(server_module, 'main'), "Server should have main function"
        except ImportError as e:
            pytest.skip(f"MCP server not available: {e}")


# Fixture for financial fact testing
@pytest.fixture
def sample_financial_fact():
    """Create a sample financial fact for testing."""
    from dataclasses import dataclass
    from enum import Enum
    
    class DataQuality(Enum):
        HIGH = "high"
    
    @dataclass
    class MockFinancialFact:
        concept: str = "us-gaap:Revenue"
        taxonomy: str = "us-gaap"
        label: str = "Revenue"
        value: float = 125_000_000_000
        numeric_value: float = 125_000_000_000
        unit: str = "USD"
        scale: int = 1
        period_end: date = date(2024, 3, 31)
        period_type: str = "duration"
        fiscal_period: str = "Q1"
        fiscal_year: int = 2024
        filing_date: date = date(2024, 4, 30)
        form_type: str = "10-Q"
        data_quality: DataQuality = DataQuality.HIGH
        confidence_score: float = 0.95
        statement_type: str = "IncomeStatement"
        
        def to_llm_context(self):
            return {
                "concept": self.label,
                "value": f"{self.value:,.0f}",
                "unit": self.unit,
                "period": f"for {self.fiscal_period} {self.fiscal_year}",
                "quality": self.data_quality.value,
                "confidence": self.confidence_score,
                "source": f"{self.form_type} filed {self.filing_date}"
            }
    
    return MockFinancialFact()