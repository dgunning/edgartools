# AI/MCP Package Structure Plan for EdgarTools

## Recommendation: `edgar.ai` Package

After analyzing the current EdgarTools structure, I recommend creating an `edgar.ai` package for the following reasons:

### 1. Package Naming Decision

**Recommended: `edgar.ai`**
- **Clear Purpose**: Immediately communicates AI capabilities
- **Future-Proof**: Covers MCP, LLM integrations, and future AI features
- **Marketing Value**: "EdgarTools AI" is compelling for users
- **Scope**: Broader than just MCP - includes all AI enhancements

**Alternative Considered:**
- `edgar.mcp`: Too specific to one protocol
- `edgar.tools`: Too generic, could be confused with utility functions
- `edgar.llm`: Too narrow, doesn't cover agent protocols

### 2. Package Structure

```
edgar/
├── ai/                          # Main AI package
│   ├── __init__.py             # Public API exports
│   ├── core.py                 # AIEnabled mixin, base classes
│   ├── context.py              # LLM context generation
│   ├── semantic.py             # Semantic enrichment
│   ├── optimization.py         # Token optimization utilities
│   ├── mcp/                    # MCP-specific implementation
│   │   ├── __init__.py
│   │   ├── server.py           # MCP server implementation
│   │   ├── tools.py            # Tool definitions
│   │   └── handlers.py         # Request handlers
│   ├── agents/                 # Agent interfaces
│   │   ├── __init__.py
│   │   ├── langchain.py        # LangChain integration
│   │   ├── openai.py           # OpenAI function calling
│   │   └── claude.py           # Claude-specific features
│   └── templates/              # Prompt templates
│       ├── analysis.jinja2
│       └── research.jinja2
```

### 3. Conditional Dependencies in pyproject.toml

```toml
[project]
# Core dependencies remain unchanged
dependencies = [
    "httpx>=0.25.0",
    "pandas>=2.0.0",
    # ... existing dependencies
]

[project.optional-dependencies]
# AI/MCP features as optional to keep core library lightweight
ai = [
    "mcp>=0.1.0",              # Model Context Protocol
    "tiktoken>=0.5.0",         # Token counting for OpenAI models
    "anthropic>=0.25.0",       # For Claude-specific features
    "jinja2>=3.1.0",           # Already in core, but ensure version
]

# Full AI stack with all integrations
ai-full = [
    "mcp>=0.1.0",
    "tiktoken>=0.5.0",
    "anthropic>=0.25.0",
    "langchain>=0.1.0",
    "openai>=1.0.0",
    "chromadb>=0.4.0",         # Vector store for semantic search
]

# Development dependencies for AI features
ai-dev = [
    "pytest-mock>=3.12.0",     # For mocking AI responses
    "responses>=0.24.0",       # HTTP response mocking
]
```

### 4. Import Strategy

```python
# Core functionality always available
from edgar import Company, get_filings

# AI features with graceful degradation
try:
    from edgar.ai import to_llm_context, MCPServer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    
    # Provide helpful error message
    def to_llm_context(*args, **kwargs):
        raise ImportError(
            "AI features require additional dependencies. "
            "Install with: pip install edgartools[ai]"
        )
```

### 5. Migration Path for Existing Code

The existing `to_llm_context()` in `FinancialFact` should be enhanced:

```python
# edgar/entity/models.py
class FinancialFact:
    def to_llm_context(self, detail_level='standard', max_tokens=None):
        """Enhanced version with optional AI features"""
        
        # Basic implementation always available
        context = self._basic_llm_context()
        
        # Enhanced features if AI package is available
        if AI_AVAILABLE:
            from edgar.ai import enhance_context
            context = enhance_context(self, context, detail_level, max_tokens)
            
        return context
    
    def _basic_llm_context(self):
        """Current implementation - no AI dependencies"""
        # Existing code here
```

### 6. Installation Instructions

```bash
# Basic EdgarTools
pip install edgartools

# With AI/MCP support
pip install edgartools[ai]

# Full AI stack
pip install edgartools[ai-full]

# For development
pip install -e ".[ai,ai-dev]"
```

### 7. Feature Detection

```python
# edgar/ai/__init__.py
def check_ai_capabilities():
    """Check which AI features are available"""
    capabilities = {
        'basic': True,  # Always available
        'mcp': False,
        'token_optimization': False,
        'semantic_enrichment': True,  # Can work without external deps
        'langchain': False,
        'openai': False,
    }
    
    try:
        import mcp
        capabilities['mcp'] = True
    except ImportError:
        pass
        
    try:
        import tiktoken
        capabilities['token_optimization'] = True
    except ImportError:
        pass
        
    # ... check other capabilities
    
    return capabilities
```

### 8. Documentation Strategy

```python
# edgar/ai/core.py
class AIEnabled:
    """
    Mixin for AI-enabled EdgarTools classes.
    
    This class provides AI capabilities when the AI package is installed.
    If not installed, methods will raise helpful ImportError messages.
    
    Installation:
        pip install edgartools[ai]
    
    Example:
        >>> company = Company("AAPL")
        >>> # Works without AI package
        >>> data = company.get_filings()
        >>> 
        >>> # Requires AI package
        >>> context = company.to_llm_context()
    """
```

### 9. Testing Strategy

```python
# tests/test_ai_features.py
import pytest

def test_ai_import_error_without_package(monkeypatch):
    """Test graceful degradation without AI package"""
    monkeypatch.setattr('edgar.ai.AI_AVAILABLE', False)
    
    from edgar import Company
    company = Company("AAPL")
    
    with pytest.raises(ImportError, match="pip install edgartools\\[ai\\]"):
        company.to_llm_context()

@pytest.mark.ai  # Mark tests that require AI dependencies
def test_llm_context_with_ai_package():
    """Test enhanced features with AI package"""
    from edgar.ai import enhance_context
    # ... test implementation
```

### 10. Benefits of This Approach

1. **Backward Compatibility**: Core EdgarTools remains unchanged
2. **Lightweight Core**: Users who don't need AI features don't pay for them
3. **Clear Upgrade Path**: Easy to add AI features when needed
4. **Flexible Integration**: Support multiple AI providers/protocols
5. **Future-Proof**: Room for new AI capabilities
6. **Developer Friendly**: Clear error messages and documentation

## Implementation Timeline

1. **Phase 1**: Create `edgar.ai` package structure
2. **Phase 2**: Move `ai_enhancements.py` content to new package
3. **Phase 3**: Update pyproject.toml with optional dependencies
4. **Phase 4**: Implement MCP server in `edgar.ai.mcp`
5. **Phase 5**: Add integration tests and documentation

## Conclusion

The `edgar.ai` package approach provides the best balance of:
- Clear organization and naming
- Optional dependencies for lightweight core
- Room for growth and new AI features
- Backward compatibility
- Developer experience

This structure positions EdgarTools as a modern, AI-ready financial data platform while maintaining its core simplicity for traditional use cases.