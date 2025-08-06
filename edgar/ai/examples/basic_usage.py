#!/usr/bin/env python3
"""
Basic usage examples for EdgarTools AI features.

This script demonstrates how to use the AI capabilities including
LLM context generation and MCP server functionality.
"""

import json
from datetime import date

# Check if AI features are available
try:
    from edgar.ai import (
        AI_AVAILABLE,
        MCP_AVAILABLE,
        get_ai_info,
        enhance_financial_fact_llm_context,
        check_ai_capabilities
    )
except ImportError:
    print("EdgarTools AI features not available.")
    print("Install with: pip install edgartools[llm]")
    exit(1)


def demonstrate_ai_capabilities():
    """Show available AI capabilities."""
    print("=== AI Capabilities ===")
    info = get_ai_info()
    print(f"AI Available: {info['ai_available']}")
    print(f"MCP Available: {info['mcp_available']}")
    print(f"Token Optimization: {info['tiktoken_available']}")
    
    if info['missing_dependencies']:
        print(f"\nMissing dependencies: {', '.join(info['missing_dependencies'])}")
        print(f"Install with: {info['install_command']}")
    
    print("\nDetailed capabilities:")
    capabilities = check_ai_capabilities()
    for capability, available in capabilities.items():
        status = "✓" if available else "✗"
        print(f"  {status} {capability}")


def demonstrate_financial_fact_enhancement():
    """Demonstrate enhancing financial facts for LLM consumption."""
    print("\n=== Financial Fact Enhancement ===")
    
    # Create a mock financial fact (in real usage, this would come from EdgarTools)
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
            """Basic LLM context (existing in EdgarTools)."""
            return {
                "concept": self.label,
                "value": f"{self.value:,.0f}",
                "unit": self.unit,
                "period": f"for {self.fiscal_period} {self.fiscal_year}",
                "quality": self.data_quality.value,
                "confidence": self.confidence_score,
                "source": f"{self.form_type} filed {self.filing_date}"
            }
    
    fact = MockFinancialFact()
    
    # Show different detail levels
    print("\nMinimal context:")
    minimal = enhance_financial_fact_llm_context(fact, detail_level='minimal')
    print(json.dumps(minimal, indent=2))
    
    print("\nStandard context (with semantic enrichment):")
    standard = enhance_financial_fact_llm_context(fact, detail_level='standard')
    print(json.dumps(standard, indent=2))
    
    print("\nToken-limited context (100 tokens):")
    limited = enhance_financial_fact_llm_context(fact, detail_level='detailed', max_tokens=100)
    print(json.dumps(limited, indent=2))


def demonstrate_mcp_server():
    """Demonstrate MCP server setup."""
    print("\n=== MCP Server Setup ===")
    
    if not MCP_AVAILABLE:
        print("MCP not available. Install with: pip install edgartools[llm]")
        return
    
    try:
        from edgar.ai.mcp import get_simple_server
        
        server = get_simple_server()
        print("MCP Server created successfully!")
        print(f"Server name: {server.name}")
        
        print("\nTo run the server:")
        print("  python edgar/ai/run_mcp_server.py")
        
        print("\nOr use in Claude Desktop config:")
        print("""  {
    "tools": [
      {
        "type": "mcp",
        "name": "edgartools",
        "config": {
          "command": "python",
          "args": ["edgar/ai/run_mcp_server.py"]
        }
      }
    ]
  }""")
        
    except ImportError as e:
        print(f"Error creating MCP server: {e}")


def demonstrate_usage_with_company():
    """Demonstrate AI features with real EdgarTools objects."""
    print("\n=== Usage with EdgarTools Company ===")
    
    try:
        from edgar import Company
        
        # Get a company
        company = Company("AAPL")
        print(f"Company: {company.name} ({company.get_ticker()})")
        
        # If the company has a to_llm_context method (future enhancement)
        if hasattr(company, 'to_llm_context'):
            context = company.to_llm_context()
            print("\nLLM Context:")
            print(json.dumps(context, indent=2))
        else:
            print("\nNote: Company.to_llm_context() will be available in future versions")
            print("For now, use the AI wrapper functions to enhance EdgarTools objects")
            
    except Exception as e:
        print(f"Error demonstrating company usage: {e}")
        print("This example requires a working internet connection and valid SEC API access")


def main():
    """Run all demonstrations."""
    print("EdgarTools AI Features Demonstration")
    print("=" * 50)
    
    # Check capabilities
    demonstrate_ai_capabilities()
    
    # Show financial fact enhancement
    demonstrate_financial_fact_enhancement()
    
    # Show MCP server setup
    demonstrate_mcp_server()
    
    # Show usage with real EdgarTools objects
    demonstrate_usage_with_company()
    
    print("\n" + "=" * 50)
    print("For more examples, see the documentation in edgar/ai/docs/")


if __name__ == "__main__":
    main()