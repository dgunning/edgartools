# AI Function Patterns for EdgarTools

## Overview

This document establishes standardized patterns for implementing AI-specific functions across the EdgarTools library, building on the existing `to_llm_context()` method in `FinancialFact`.

## Existing Implementation Analysis

The current `to_llm_context()` method in `edgar.entity.models.FinancialFact` provides a solid foundation:

### Strengths
1. **Human-readable formatting**: Converts numeric values to formatted strings with scale indicators
2. **Contextual information**: Includes period descriptions, data quality, and source information
3. **Structured output**: Returns a dictionary optimized for LLM consumption
4. **Quality indicators**: Includes confidence scores and audit status

### Areas for Enhancement
1. **Standardization**: Need consistent patterns across all classes
2. **Token optimization**: Consider token limits for LLM contexts
3. **Semantic enrichment**: Add more business context and relationships
4. **Multi-modal support**: Prepare for vision models (charts, tables)

## Standardized AI Function Patterns

### 1. Core AI Methods

Every major data class should implement these AI-specific methods:

```python
class AIEnabled:
    """Base mixin for AI-enabled classes"""
    
    def to_llm_context(self, 
                      detail_level: str = 'standard',
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Convert object to LLM-optimized context.
        
        Args:
            detail_level: 'minimal', 'standard', 'detailed'
            max_tokens: Optional token limit for the response
            
        Returns:
            Dictionary with formatted data and context
        """
        raise NotImplementedError
    
    def to_agent_tool(self) -> Dict[str, Any]:
        """
        Convert object to agent tool response format.
        
        Returns:
            Dictionary following MCP tool response schema
        """
        raise NotImplementedError
    
    def get_semantic_description(self) -> str:
        """
        Get natural language description of the object.
        
        Returns:
            Human-readable description with key insights
        """
        raise NotImplementedError
    
    def get_related_concepts(self) -> List[str]:
        """
        Get semantically related concepts for graph traversal.
        
        Returns:
            List of related concept identifiers
        """
        raise NotImplementedError
```

### 2. Implementation Pattern for Financial Objects

```python
@dataclass
class FinancialStatement(AIEnabled):
    """Example implementation for financial statements"""
    
    def to_llm_context(self, detail_level='standard', max_tokens=None):
        """Convert financial statement to LLM context"""
        
        # Base context always included
        context = {
            "type": self.__class__.__name__,
            "company": self.company_name,
            "period": self.period_description,
            "summary": self._generate_summary()
        }
        
        # Add detail based on level
        if detail_level in ['standard', 'detailed']:
            context["key_metrics"] = self._format_key_metrics()
            context["trends"] = self._describe_trends()
            
        if detail_level == 'detailed':
            context["line_items"] = self._format_line_items()
            context["notes"] = self._extract_relevant_notes()
            
        # Optimize for token limit if specified
        if max_tokens:
            context = self._optimize_for_tokens(context, max_tokens)
            
        return context
    
    def _generate_summary(self) -> str:
        """Generate executive summary"""
        return f"""
        {self.company_name} {self.statement_type} for {self.period_description}:
        - Total Revenue: ${self.total_revenue:,.0f}
        - Net Income: ${self.net_income:,.0f} ({self.net_margin:.1%} margin)
        - Key Insight: {self._identify_key_insight()}
        """
    
    def to_agent_tool(self) -> Dict[str, Any]:
        """Format for agent tool response"""
        return {
            "data": self.to_dict(),
            "context": self.to_llm_context(),
            "actions": self._get_available_actions(),
            "metadata": {
                "source": f"SEC {self.form_type}",
                "filed": self.filing_date.isoformat(),
                "confidence": self.data_quality.value
            }
        }
```

### 3. Token Optimization Strategies

```python
class TokenOptimizer:
    """Utilities for optimizing content for LLM token limits"""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough estimation: ~4 characters per token"""
        return len(text) // 4
    
    @staticmethod
    def optimize_for_tokens(content: Dict, max_tokens: int) -> Dict:
        """Progressively summarize content to fit token limit"""
        
        current_tokens = TokenOptimizer.estimate_tokens(str(content))
        
        if current_tokens <= max_tokens:
            return content
            
        # Priority order for content retention
        priority_keys = ['summary', 'key_metrics', 'company', 'period', 'type']
        
        # Start with high-priority content
        optimized = {k: content[k] for k in priority_keys if k in content}
        
        # Add remaining content that fits
        for key, value in content.items():
            if key not in optimized:
                test_content = {**optimized, key: value}
                if TokenOptimizer.estimate_tokens(str(test_content)) <= max_tokens:
                    optimized[key] = value
                else:
                    # Try to summarize the value
                    if isinstance(value, str) and len(value) > 100:
                        optimized[key] = value[:100] + "..."
                        
        return optimized
```

### 4. Semantic Enrichment Pattern

```python
class SemanticEnricher:
    """Add semantic context to financial concepts"""
    
    CONCEPT_DEFINITIONS = {
        "Revenue": "Total income from sales of goods or services",
        "NetIncome": "Profit after all expenses, taxes, and costs",
        "CurrentRatio": "Liquidity measure: current assets / current liabilities",
        # ... more definitions
    }
    
    CONCEPT_RELATIONSHIPS = {
        "Revenue": ["GrossProfit", "OperatingIncome", "NetIncome"],
        "Assets": ["CurrentAssets", "NonCurrentAssets", "TotalAssets"],
        # ... more relationships
    }
    
    @staticmethod
    def enrich_fact(fact: FinancialFact) -> Dict[str, Any]:
        """Add semantic context to a financial fact"""
        
        enriched = fact.to_llm_context()
        
        # Add definition
        concept_key = fact.concept.split(':')[-1]  # Remove namespace
        if concept_key in SemanticEnricher.CONCEPT_DEFINITIONS:
            enriched["definition"] = SemanticEnricher.CONCEPT_DEFINITIONS[concept_key]
            
        # Add relationships
        if concept_key in SemanticEnricher.CONCEPT_RELATIONSHIPS:
            enriched["related_concepts"] = SemanticEnricher.CONCEPT_RELATIONSHIPS[concept_key]
            
        # Add business interpretation
        enriched["interpretation"] = SemanticEnricher._interpret_value(fact)
        
        return enriched
    
    @staticmethod
    def _interpret_value(fact: FinancialFact) -> str:
        """Generate business interpretation of the value"""
        
        if fact.concept.endswith("Revenue"):
            if fact.numeric_value > 0:
                return "Positive revenue indicates active business operations"
            else:
                return "Zero or negative revenue may indicate business challenges"
                
        # Add more interpretations...
        return ""
```

### 5. Multi-Modal Support

```python
class MultiModalFormatter:
    """Format data for multi-modal AI models"""
    
    @staticmethod
    def to_markdown_table(statement: FinancialStatement) -> str:
        """Convert to markdown table for vision models"""
        
        lines = ["| Item | Value | % of Revenue |", "|------|-------|-------------|"]
        
        for item in statement.line_items:
            pct = (item.value / statement.revenue * 100) if statement.revenue else 0
            lines.append(f"| {item.label} | ${item.value:,.0f} | {pct:.1f}% |")
            
        return "\n".join(lines)
    
    @staticmethod
    def to_chart_description(trends: List[float]) -> str:
        """Describe chart trends for vision models"""
        
        if not trends:
            return "No trend data available"
            
        direction = "increasing" if trends[-1] > trends[0] else "decreasing"
        volatility = np.std(trends) / np.mean(trends) if np.mean(trends) else 0
        
        return f"Trend: {direction}, Volatility: {'high' if volatility > 0.2 else 'low'}"
```

## Integration with MCP

### Updating Classes Across EdgarTools

1. **Company Class**
```python
class Company(AIEnabled):
    def to_llm_context(self, detail_level='standard', max_tokens=None):
        return {
            "name": self.name,
            "ticker": self.ticker,
            "industry": self.industry,
            "description": self.business_description,
            "key_metrics": self._get_key_metrics(),
            "recent_performance": self._summarize_performance(),
            "risk_factors": self._get_top_risks(5)
        }
```

2. **Filing Class**
```python
class Filing(AIEnabled):
    def to_llm_context(self, detail_level='standard', max_tokens=None):
        return {
            "form_type": self.form,
            "company": self.company,
            "filed_date": self.filing_date.isoformat(),
            "period": self.period_of_report,
            "summary": self._generate_filing_summary(),
            "key_sections": self._extract_key_sections(detail_level),
            "notable_items": self._identify_notable_items()
        }
```

3. **Filings Collection**
```python
class Filings(AIEnabled):
    def to_llm_context(self, detail_level='standard', max_tokens=None):
        return {
            "total_filings": len(self),
            "date_range": f"{self.earliest_date} to {self.latest_date}",
            "form_types": self._count_by_form_type(),
            "companies": self._count_unique_companies(),
            "recent_filings": [f.to_llm_context('minimal') for f in self.latest(5)],
            "summary": self._generate_collection_summary()
        }
```

## Best Practices

### 1. Consistent Naming
- Use `to_llm_context()` for LLM-optimized output
- Use `to_agent_tool()` for MCP tool responses
- Use `get_semantic_*()` for semantic enrichment methods

### 2. Progressive Detail
- Always support detail levels: minimal, standard, detailed
- Start with essential information, add detail progressively
- Consider token limits at each level

### 3. Context Preservation
- Include source information (filing, date, form type)
- Add confidence scores and data quality indicators
- Preserve relationships between concepts

### 4. Error Handling
```python
def to_llm_context(self, detail_level='standard', max_tokens=None):
    try:
        # Main implementation
        return context
    except Exception as e:
        # Return graceful degradation
        return {
            "error": "Unable to generate full context",
            "partial_data": self._get_minimal_context(),
            "reason": str(e)
        }
```

### 5. Testing AI Functions
```python
def test_llm_context_generation():
    """Test that LLM context is properly formatted"""
    
    fact = FinancialFact(
        concept="us-gaap:Revenue",
        value=1000000,
        period_end=date(2024, 3, 31)
    )
    
    context = fact.to_llm_context()
    
    # Test required fields
    assert "concept" in context
    assert "value" in context
    assert "period" in context
    
    # Test formatting
    assert "million" in context["value"]  # Check scale formatting
    assert "Q1 2024" in context["period"]  # Check period formatting
    
    # Test token optimization
    minimal = fact.to_llm_context(max_tokens=100)
    assert len(str(minimal)) < len(str(context))
```

## Migration Strategy

### Phase 1: Enhance Existing
- Update `FinancialFact.to_llm_context()` with new patterns
- Add token optimization
- Add semantic enrichment

### Phase 2: Core Classes
- Implement in Company, Filing, Filings classes
- Add to Statement classes (BalanceSheet, IncomeStatement, etc.)
- Ensure consistency across implementations

### Phase 3: Collections and Aggregates
- Add to collection classes (CurrentFilings, FactSet, etc.)
- Implement for comparison and analysis results
- Add multi-object context generation

### Phase 4: MCP Integration
- Add `to_agent_tool()` methods
- Implement streaming support
- Add conversation context management

## Conclusion

By standardizing AI-specific functions across EdgarTools, we create a consistent, powerful interface for AI agents and LLMs to interact with SEC data. The existing `to_llm_context()` method provides a solid foundation that we'll extend with token optimization, semantic enrichment, and MCP compatibility.