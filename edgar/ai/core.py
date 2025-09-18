"""
AI enhancements for EdgarTools entity models.

This module provides enhanced AI capabilities building on the existing
to_llm_context() implementation, adding token optimization, semantic
enrichment, and MCP compatibility.
"""

import json
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional, Union


class TokenOptimizer:
    """Utilities for optimizing content for LLM token limits."""

    @staticmethod
    def estimate_tokens(content: Union[str, dict]) -> int:
        """
        Estimate token count for content.

        Rough estimation: ~4 characters per token for English text.
        """
        if isinstance(content, dict):
            content = json.dumps(content)
        return len(content) // 4

    @staticmethod
    def optimize_for_tokens(content: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """
        Optimize content to fit within token limit.

        Uses progressive summarization to retain most important information.
        """
        current_tokens = TokenOptimizer.estimate_tokens(content)

        if current_tokens <= max_tokens:
            return content

        # Define priority order for content retention
        priority_keys = [
            'concept', 'value', 'period', 'context', 
            'quality', 'confidence', 'source'
        ]

        # Start with high-priority content
        optimized = {}
        for key in priority_keys:
            if key in content:
                optimized[key] = content[key]
                if TokenOptimizer.estimate_tokens(optimized) > max_tokens:
                    # Remove last added item if we exceed limit
                    optimized.pop(key)
                    break

        # Add truncation indicator
        if len(optimized) < len(content):
            optimized['_truncated'] = True

        return optimized


class SemanticEnricher:
    """Add semantic context and interpretations to financial data."""

    # Concept definitions for common financial terms
    CONCEPT_DEFINITIONS = {
        "Revenue": "Total income generated from normal business operations",
        "Revenues": "Total income generated from normal business operations",
        "NetIncome": "Company's total earnings after all expenses and taxes",
        "NetIncomeLoss": "Company's total earnings or losses after all expenses",
        "Assets": "Resources owned by the company with economic value",
        "Liabilities": "Company's financial debts or obligations",
        "StockholdersEquity": "Residual interest in assets after deducting liabilities",
        "CashAndCashEquivalents": "Highly liquid assets readily convertible to cash",
        "OperatingIncome": "Profit from core business operations before interest and taxes",
        "EarningsPerShare": "Company's profit divided by outstanding shares",
        "CurrentAssets": "Assets expected to be converted to cash within one year",
        "CurrentLiabilities": "Obligations due within one year",
    }

    # Relationships between concepts
    CONCEPT_RELATIONSHIPS = {
        "Revenue": ["GrossProfit", "OperatingIncome", "NetIncome"],
        "Assets": ["CurrentAssets", "NonCurrentAssets", "CashAndCashEquivalents"],
        "Liabilities": ["CurrentLiabilities", "LongTermDebt"],
        "NetIncome": ["Revenue", "OperatingExpenses", "TaxExpense"],
        "StockholdersEquity": ["Assets", "Liabilities", "RetainedEarnings"],
    }

    @classmethod
    def get_concept_definition(cls, concept: str) -> Optional[str]:
        """Get human-readable definition for a concept."""
        # Remove namespace prefix if present
        concept_key = concept.split(':')[-1]
        return cls.CONCEPT_DEFINITIONS.get(concept_key)

    @classmethod
    def get_related_concepts(cls, concept: str) -> List[str]:
        """Get semantically related concepts."""
        concept_key = concept.split(':')[-1]
        return cls.CONCEPT_RELATIONSHIPS.get(concept_key, [])

    @classmethod
    def interpret_value(cls, concept: str, value: Union[int, float], 
                       unit: str, period_type: str = None) -> str:
        """
        Generate business interpretation of a financial value.

        Args:
            concept: The financial concept (e.g., "Revenue")
            value: The numeric value
            unit: The unit of measurement (e.g., "USD")
            period_type: 'instant' or 'duration'

        Returns:
            Human-readable interpretation
        """
        concept_key = concept.split(':')[-1]

        # Revenue interpretations
        if concept_key in ["Revenue", "Revenues"]:
            if value > 1_000_000_000:
                scale = "billion-dollar"
            elif value > 100_000_000:
                scale = "multi-million dollar"
            else:
                scale = "smaller-scale"
            return f"The company is a {scale} business based on revenue"

        # Profitability interpretations
        elif concept_key in ["NetIncome", "NetIncomeLoss"]:
            if value > 0:
                return "The company is profitable"
            elif value == 0:
                return "The company broke even"
            else:
                return "The company reported a net loss"

        # Asset interpretations
        elif concept_key == "CashAndCashEquivalents":
            if value > 10_000_000_000:
                return "Very strong cash position providing significant financial flexibility"
            elif value > 1_000_000_000:
                return "Healthy cash reserves for operations and investments"
            elif value > 100_000_000:
                return "Adequate cash position for normal operations"
            else:
                return "Limited cash reserves may constrain growth opportunities"

        return ""


class AIEnabled(ABC):
    """
    Base mixin for AI-enabled EdgarTools classes.

    Provides standardized AI methods that all classes should implement.
    """

    @abstractmethod
    def to_llm_context(self, detail_level: str = 'standard', 
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Convert object to LLM-optimized context.

        Args:
            detail_level: Level of detail ('minimal', 'standard', 'detailed')
            max_tokens: Optional token limit for response optimization

        Returns:
            Dictionary optimized for LLM consumption
        """
        pass

    def to_agent_tool(self) -> Dict[str, Any]:
        """
        Convert object to MCP agent tool response format.

        Returns:
            Dictionary following MCP tool response schema
        """
        return {
            "data": self.to_dict() if hasattr(self, 'to_dict') else {},
            "context": self.to_llm_context(),
            "metadata": {
                "source": "SEC EDGAR",
                "object_type": self.__class__.__name__,
                "timestamp": date.today().isoformat()
            }
        }

    @abstractmethod
    def get_semantic_description(self) -> str:
        """
        Get natural language description of the object.

        Returns:
            Human-readable description with key insights
        """
        pass


def enhance_financial_fact_llm_context(fact, detail_level='standard', max_tokens=None):
    """
    Enhanced version of FinancialFact.to_llm_context() with new features.

    This function shows how to enhance the existing implementation while
    maintaining backward compatibility.

    Args:
        fact: FinancialFact instance
        detail_level: 'minimal', 'standard', or 'detailed'
        max_tokens: Optional token limit

    Returns:
        Enhanced LLM context dictionary
    """
    # Start with the existing implementation
    context = fact.to_llm_context()

    # Add semantic enrichment based on detail level
    if detail_level in ['standard', 'detailed']:
        # Add concept definition
        definition = SemanticEnricher.get_concept_definition(fact.concept)
        if definition:
            context['definition'] = definition

        # Add value interpretation
        interpretation = SemanticEnricher.interpret_value(
            fact.concept, 
            fact.numeric_value or fact.value,
            fact.unit,
            fact.period_type
        )
        if interpretation:
            context['interpretation'] = interpretation

    if detail_level == 'detailed':
        # Add related concepts
        related = SemanticEnricher.get_related_concepts(fact.concept)
        if related:
            context['related_concepts'] = related

        # Add additional metadata
        context['metadata'] = {
            'taxonomy': fact.taxonomy,
            'scale': fact.scale,
            'decimals': getattr(fact, 'decimals', None),
            'statement_type': fact.statement_type
        }

        # Add calculation context if available
        if hasattr(fact, 'calculation_context') and fact.calculation_context:
            context['calculation_context'] = fact.calculation_context

    # Optimize for token limit if specified
    if max_tokens:
        context = TokenOptimizer.optimize_for_tokens(context, max_tokens)

    return context


class FinancialFactAIWrapper:
    """
    Wrapper to add AI methods to existing FinancialFact instances.

    This demonstrates how to add AI capabilities without modifying
    the original class definition.
    """

    def __init__(self, fact):
        self.fact = fact

    def to_llm_context(self, detail_level='standard', max_tokens=None):
        """Enhanced LLM context with new features."""
        return enhance_financial_fact_llm_context(
            self.fact, detail_level, max_tokens
        )

    def to_agent_tool(self):
        """Convert to MCP tool response format."""
        return {
            "data": {
                "concept": self.fact.concept,
                "value": self.fact.value,
                "numeric_value": self.fact.numeric_value,
                "unit": self.fact.unit,
                "period_end": self.fact.period_end.isoformat() if self.fact.period_end else None,
                "fiscal_period": self.fact.fiscal_period,
                "fiscal_year": self.fact.fiscal_year
            },
            "context": self.to_llm_context(),
            "metadata": {
                "source": f"SEC {self.fact.form_type}",
                "filed": self.fact.filing_date.isoformat() if self.fact.filing_date else None,
                "quality": self.fact.data_quality.value,
                "confidence": self.fact.confidence_score
            }
        }

    def get_semantic_description(self):
        """Natural language description of the fact."""
        context = self.fact.to_llm_context()

        return (f"{context['concept']} of {context['value']} {context['unit']} "
                f"{context['period']} from {context['source']}")


def check_ai_capabilities():
    """
    Check which AI features are available based on installed dependencies.

    Returns:
        Dictionary with capability flags
    """
    capabilities = {
        'basic': True,  # Always available
        'mcp': False,
        'token_optimization': False,
        'semantic_enrichment': True,  # Works without external deps
    }

    try:
        import mcp  # noqa: F401
        capabilities['mcp'] = True
    except ImportError:
        pass

    try:
        import tiktoken  # noqa: F401
        capabilities['token_optimization'] = True
    except ImportError:
        pass

    return capabilities


# Example usage demonstrating the enhanced capabilities
if __name__ == "__main__":
    # This would be imported from edgar.entity.models
    from dataclasses import dataclass
    from enum import Enum

    class DataQuality(Enum):
        HIGH = "high"

    @dataclass
    class MockFinancialFact:
        """Mock class for demonstration"""
        concept: str = "us-gaap:Revenue"
        taxonomy: str = "us-gaap"
        value: float = 125_000_000_000
        numeric_value: float = 125_000_000_000
        unit: str = "USD"
        scale: int = 1
        period_end: date = date(2024, 3, 31)
        period_type: str = "duration"
        fiscal_period: str = "Q1"
        fiscal_year: int = 2024
        form_type: str = "10-Q"
        filing_date: date = date(2024, 4, 30)
        data_quality: DataQuality = DataQuality.HIGH
        confidence_score: float = 0.95
        statement_type: str = "IncomeStatement"

        def to_llm_context(self):
            # Simulate existing implementation
            return {
                "concept": "Revenue",
                "value": "125,000 million",
                "unit": "USD",
                "period": "for Q1 2024",
                "context": "",
                "quality": "high",
                "confidence": 0.95,
                "source": "10-Q filed 2024-04-30"
            }

    # Create a mock fact
    fact = MockFinancialFact()

    # Wrap it with AI enhancements
    ai_fact = FinancialFactAIWrapper(fact)

    # Test different detail levels




