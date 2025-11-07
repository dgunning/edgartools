# edgar.ai Architecture

**High-level technical overview for architects and technical decision-makers**

## Executive Summary

`edgar.ai` provides two parallel pathways for AI agents to access SEC EDGAR filing data: **Skills** (documentation + code execution) and **MCP** (tool-based protocol). Both integrate directly with the EdgarTools API, optimized for LLM context windows and agent workflows.

**Primary Integration: Skills + Code Execution** (90% of use cases)
- Interactive analysis with Claude Desktop
- Learning EdgarTools patterns through progressive disclosure
- Direct Python code execution (zero protocol overhead)
- Full composability (variables, chaining, reusable objects)
- Ad-hoc research and exploratory analysis
- Context-Oriented Programming (COP) aligned architecture

**Specialized Integration: MCP Server** (10% - Complex Workflows Only)
- Batch processing across 100+ companies
- Automated filing monitoring pipelines
- Scheduled report generation
- Workflow orchestration (integration with n8n, Zapier, etc.)
- Production data pipelines requiring structured tool calling
- Parameter validation through JSON schemas

**Key Architectural Principles:**
- **Skills-first approach**: Documentation as primary integration for interactive use
- **MCP for automation**: Workflow orchestration and batch processing only
- **Don't install both**: Unless you specifically need both interactive analysis AND workflow automation
- **Progressive disclosure**: Layer complexity from quick patterns to comprehensive API reference
- **Token efficiency**: Optimize all outputs for LLM context window constraints
- **Direct API access**: Both pathways call EdgarTools directly (no abstraction layer)

---

## System Architecture

### Parallel Integration Pathways

**Critical Understanding**: MCP and Skills are **peer integration pathways**, not layered. Both call the EdgarTools API directly.

```
                    ┌────────────────────────┐
                    │      AI Agent          │
                    │ (Claude Desktop, etc)  │
                    └───────────┬────────────┘
                                │
                      ┌─────────┴─────────┐
                      │                   │
            ┌─────────▼────────┐  ┌───────▼───────────┐
            │  Skills Package  │  │   MCP Server      │
            │  (documentation) │  │ (stdio protocol)  │
            │  + Code Execution│  │  + Tool Calling   │
            └─────────┬────────┘  └───────┬───────────┘
                      │                   │
                      │  Both call directly
                      │                   │
            ┌─────────▼───────────────────▼───────────┐
            │      EdgarTools Core API                │
            │      (edgar package)                    │
            │  Company(), get_filings(), Filing.xbrl()│
            └─────────┬───────────────────────────────┘
                      │
            ┌─────────▼────────┐
            │  SEC EDGAR APIs  │
            └──────────────────┘
```

**Key Insight**: EdgarTools API is the actual integration layer. Skills and MCP are alternative ways to reach it.

---

## Integration Path 1: Skills + Code Execution (Primary)

### Purpose
Teach AI agents how to use EdgarTools through progressive disclosure documentation, enabling them to write and execute Python code directly.

### How It Works

**1. Agent Loads Skill Documentation**
```
Claude Desktop startup → Scans ~/.claude/skills/
                      → Finds edgartools/SKILL.md
                      → Loads metadata (name, description)
                      → Full docs loaded on-demand
```

**2. Agent Discovers Capabilities**
```markdown
# From SKILL.md
## Getting Filings (3 Approaches)
1. Published Filings - get_filings(year, quarter)
2. Current Filings - get_current_filings()
3. Company Filings - Company(ticker).get_filings()
```

**3. Agent Writes Python Code**
```python
# Agent composes code based on documentation
from edgar import Company

company = Company("AAPL")
income = company.income_statement(periods=3)
print(income)
```

**4. Code Executes Directly**
```
Python execution environment
  ↓ Imports edgar package
EdgarTools Core API
  ↓ HTTP requests
SEC EDGAR APIs
```

### Architecture Components

**Skills Package Structure:**
```
edgar/ai/skills/core/
├── SKILL.md                      # Main documentation (YAML + markdown)
├── quickstart-by-task.md         # Quick routing (Tier 0)
├── workflows.md                  # End-to-end examples
├── objects.md                    # Object reference + token costs
├── data-objects.md               # Form-specific objects
└── form-types-reference.md       # 311 SEC forms catalog
```

**Helper Functions (Optional Convenience):**
```python
# edgar/ai/helpers.py
from edgar import get_filings, Company

def get_revenue_trend(ticker, periods=3, quarterly=False):
    """Convenience wrapper with clear parameter names"""
    company = Company(ticker)
    return company.income_statement(periods=periods, annual=not quarterly)
```

### Design Principles

1. **Progressive Disclosure**: 4-tier documentation hierarchy (30s → 5min → detailed → comprehensive)
2. **Self-Documenting**: APIs designed to be understood from usage examples
3. **Zero Protocol Overhead**: Direct Python imports, no RPC layer
4. **Full Composability**: Variables, chaining, reusable objects in single code block

### Advantages Over Tool-Calling

| Aspect | Skills + Code | MCP Tools |
|--------|---------------|-----------|
| **Token Overhead** | Documentation only (loaded once) | Tool schemas (every conversation) |
| **Composability** | Full (variables, chaining, loops) | Limited (separate tool calls) |
| **Learning** | Agent learns patterns | Agent follows schemas |
| **Flexibility** | Any Python code | Predefined tool contracts |
| **Maintenance** | Documentation only | Server + handlers + schemas |

### Installation

**Export to Claude Desktop:**
```python
from edgar.ai.skills import edgartools_skill

# Install to ~/.claude/skills/edgartools/
edgartools_skill.export(format="claude-skills")

# Or create portable ZIP
edgartools_skill.export(format="claude-desktop", create_zip=True)
```

**Manual Installation:**
```bash
# Copy skill directory
cp -r edgar/ai/skills/core ~/.claude/skills/edgartools/

# Restart Claude Desktop
# Skill automatically discovered
```

---

## Integration Path 2: MCP Server (Alternative)

### Purpose
Provide structured tool-based access to EdgarTools for AI agents that prefer tool calling over code execution, with parameter validation and standardized error handling.

### How It Works

**1. Agent Invokes MCP Tool**
```
Claude Desktop → Calls edgar_company_research("AAPL")
              → JSON-RPC over stdio
              → MCP Server receives request
```

**2. MCP Server Calls EdgarTools Directly**
```python
# edgar/ai/mcp/tools/company_research.py
from edgar import Company  # Direct import!

async def handle_company_research(args: dict):
    company = Company(args["identifier"])  # Direct API call
    income = company.income_statement(periods=3)
    return [TextContent(type="text", text=format_results(...))]
```

**3. Results Returned via MCP Protocol**
```
MCP Server → Formats response as TextContent
          → JSON-RPC over stdio
          → Claude Desktop receives text response
```

### Architecture Components

**MCP Server Entry Points:**
```python
# Python module
python -m edgar.ai

# Console script (post-install)
edgartools-mcp
```

**Tool Registry:**
```python
# edgar/ai/mcp/server.py
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="edgar_company_research",
             description="Get company profile and financials",
             inputSchema={...}),
        Tool(name="edgar_analyze_financials",
             description="Multi-period financial analysis",
             inputSchema={...}),
        Tool(name="edgar_industry_overview",
             description="Industry sector analysis",
             inputSchema={...}),
        Tool(name="edgar_compare_industry_companies",
             description="Compare companies in sector",
             inputSchema={...})
    ]
```

**Tool Handlers (All Call EdgarTools Directly):**
```
edgar/ai/mcp/tools/
├── company_research.py      # from edgar import Company
├── financial_analysis.py    # from edgar import Company
├── industry_analysis.py     # from edgar.reference import *
└── utils.py                 # Response formatting
```

### Configuration

**Claude Desktop:**
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python3",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
```

### When to Use MCP (vs Skills)

**Use Skills + Code (PRIMARY - 90% of users):**
- ✅ Interactive analysis with Claude Desktop or similar AI tools
- ✅ Learning EdgarTools patterns and capabilities
- ✅ Ad-hoc research and exploratory data analysis
- ✅ Single-company deep dives
- ✅ Complex multi-step workflows with variable reuse
- ✅ Want to chain operations in single code block
- ✅ Maximum performance (zero protocol overhead)

**Use MCP Tools (SPECIALIZED - 10% for complex workflows):**
- ✅ Batch processing across 100+ companies (e.g., "analyze all S&P 500 financials")
- ✅ Automated filing monitoring pipelines (e.g., "alert when Form 4 filed for pharma companies")
- ✅ Scheduled report generation (e.g., "weekly revenue trends for portfolio")
- ✅ Workflow orchestration with tools like n8n, Zapier, Make
- ✅ Production data pipelines requiring structured tool calling
- ✅ Parameter validation before execution (for automation safety)

**Don't Install Both Unless:**
- You specifically need interactive analysis (Skills) AND workflow automation (MCP)
- Most users should start with Skills only

### Technical Constraints

- **Protocol Overhead**: ~100-200ms per tool call (JSON-RPC)
- **Stateless**: No state sharing between tool calls
- **Token Cost**: Tool schemas loaded in every conversation (~400 tokens)
- **Rate Limiting**: Inherits SEC API limits (10 req/sec)
- **Response Size**: Capped at ~2000 tokens (configurable)

---

## Core AI Infrastructure (Shared by Both Paths)

### Purpose

Provide foundational AI capabilities used by both Skills and MCP pathways for token optimization, semantic enrichment, and LLM-friendly output formatting.

### Components

#### 1. Token Management (`edgar/ai/core.py`)

```python
class TokenOptimizer:
    @staticmethod
    def estimate_tokens(content: Union[str, dict]) -> int:
        """~4 characters per token estimation"""

    @staticmethod
    def optimize_for_tokens(content: Dict, max_tokens: int) -> Dict:
        """Progressive summarization for context limits"""
```

**Token Budget Strategy:**
- Default tool response: 2,000 tokens
- Financial statements: 3,000 tokens (larger allowance)
- Truncation with ellipsis if exceeded
- Priority order: concept, value, period, context, quality

#### 2. Semantic Enrichment

```python
class SemanticEnricher:
    CONCEPT_DEFINITIONS = {
        "Revenue": "Total income from normal business operations",
        "NetIncome": "Company's earnings after all expenses",
        ...
    }

    CONCEPT_RELATIONSHIPS = {
        "Revenue": ["GrossProfit", "OperatingIncome", "NetIncome"],
        ...
    }

    @classmethod
    def interpret_value(cls, concept, value, unit) -> str:
        """Generate business interpretation"""
```

**Capabilities:**
- Concept definitions (human-readable explanations)
- Related concepts (semantic relationships)
- Value interpretation (business context)

#### 3. AI-Enabled Base Class

```python
class AIEnabled(ABC):
    @abstractmethod
    def to_llm_context(self, detail_level='standard',
                      max_tokens=None) -> Dict[str, Any]:
        """Convert to LLM-optimized format"""

    def to_agent_tool(self) -> Dict[str, Any]:
        """Convert to MCP tool response format"""

    @abstractmethod
    def get_semantic_description(self) -> str:
        """Natural language description"""
```

**Integration Pattern:**
```python
# Enhanced context generation
def enhance_financial_fact_llm_context(fact, detail_level='standard',
                                      max_tokens=None):
    context = fact.to_llm_context()  # Existing implementation

    if detail_level in ['standard', 'detailed']:
        context['definition'] = SemanticEnricher.get_concept_definition(fact.concept)
        context['interpretation'] = SemanticEnricher.interpret_value(...)

    if max_tokens:
        context = TokenOptimizer.optimize_for_tokens(context, max_tokens)

    return context
```

#### 4. Helper Functions (`edgar/ai/helpers.py`)

**Purpose**: Simplify common workflows with clear parameter names

```python
# Instead of: get_filings(2023, 1, form="10-K")
# More clear: get_filings_by_period(year=2023, quarter=1, form="10-K")

def get_filings_by_period(year, quarter, form=None, filing_date=None):
    """Get published filings with clear parameter names"""

def get_today_filings():
    """Get current filings (last ~24 hours)"""

def get_revenue_trend(ticker, periods=3, quarterly=False):
    """Get multi-period income statement"""

def compare_companies_revenue(tickers, periods=3):
    """Compare revenue trends across companies"""

# Industry filtering (100x faster than old implementation)
def filter_by_industry(filings, sic=None, sic_range=None, ...):
    """Filter using comprehensive company dataset (zero API calls)"""
```

**Performance Optimization:**
- Old industry filtering: ~9 minutes (5,400 API calls)
- New industry filtering: <1 second (zero API calls, uses local dataset)

---

## Data Flow Patterns

### Pattern 1: MCP Tool Request

```
AI Agent
    │
    ├─> edgar_company_research(identifier="AAPL")
    │
    ▼
MCP Server (edgar/ai/mcp/server.py)
    │
    ├─> handle_company_research(args)
    │
    ▼
Tool Handler (edgar/ai/mcp/tools/company_research.py)
    │
    ├─> Company("AAPL")
    ├─> company.income_statement(periods=3, concise_format=True)
    ├─> company.get_filings(limit=5)
    │
    ▼
Utility Functions (edgar/ai/mcp/tools/utils.py)
    │
    ├─> build_company_profile()
    ├─> check_output_size() [token management]
    │
    ▼
Response Assembly
    │
    └─> TextContent(type="text", text="...")
```

### Pattern 2: Skills Export & Consumption

```
Skill Definition (edgar/ai/skills/core/__init__.py)
    │
    ├─> EdgarToolsSkill instance
    │
    ▼
Export Request
    │
    ├─> skill.export(format="claude-skills")
    │
    ▼
Exporter (edgar/ai/exporters/claude_skills.py)
    │
    ├─> Copy SKILL.md + supporting docs
    ├─> Copy api-reference/ from centralized locations
    ├─> Validate YAML frontmatter
    │
    ▼
Installation
    │
    └─> ~/.claude/skills/edgartools/
            ├── SKILL.md
            ├── workflows.md
            ├── objects.md
            └── api-reference/
                └── *.md
```

### Pattern 3: Helper Function Usage

```
AI Agent reads skill documentation
    │
    ├─> "I need to compare revenue across AAPL, MSFT, GOOGL"
    │
    ▼
Agent generates code using helper
    │
    ├─> from edgar.ai.helpers import compare_companies_revenue
    ├─> results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)
    │
    ▼
Helper implementation
    │
    ├─> for ticker in tickers:
    │       company = Company(ticker)
    │       results[ticker] = company.income_statement(periods=3)
    │
    ▼
Returns
    │
    └─> Dict[str, MultiPeriodStatement]
```

---

## Integration Points

### MCP Integration

**Client Configuration Locations:**
- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
- **Cline**: `.vscode/cline_mcp_settings.json`
- **Continue.dev**: `~/.continue/config.json`

**Protocol:**
- Transport: stdio (stdin/stdout)
- Format: JSON-RPC
- Lifecycle: Client spawns server process, maintains connection
- Shutdown: SIGTERM on client disconnect

**Security:**
- No authentication (local subprocess)
- Inherits user's file system permissions
- Environment isolation via client config

### Skills Integration

**Discovery Mechanism:**
- Claude Desktop scans `~/.claude/skills/` for SKILL.md files
- Each subdirectory is a separate skill
- YAML frontmatter provides metadata

**Loading Process:**
1. Scan for SKILL.md in each subdirectory
2. Parse YAML frontmatter for name/description
3. Load markdown content as knowledge base
4. Make available to AI agent during conversations

**Format Compatibility:**
- Follows Anthropic's Claude Skills specification
- Compatible with future Claude Desktop versions
- Extensible via additional markdown files

---

## Performance Characteristics

### MCP Server

**Startup Time:**
- Cold start: ~1-2 seconds (Python import overhead)
- Warm start: <100ms (already running)

**Response Times:**
```
edgar_company_research:      2-5 seconds  (Entity Facts API call)
edgar_analyze_financials:    3-8 seconds  (Multiple periods, statements)
edgar_industry_overview:     1-3 seconds  (Local dataset + light API)
edgar_compare_companies:     5-15 seconds (N companies × API calls)
```

**Bottlenecks:**
1. SEC API rate limits (10 req/sec)
2. Network latency to SEC servers
3. XBRL parsing for complex statements
4. Multiple sequential API calls

**Optimization Strategies:**
- Use Entity Facts API (single call for multi-period data)
- Local company dataset (zero API calls for filtering)
- Concise format flag for smaller responses
- Response caching (future enhancement)

### Skills

**Export Time:**
```
claude-skills format:   <100ms (file copy operations)
claude-desktop format:  <200ms (includes ZIP compression)
```

**Load Time (in Claude Desktop):**
- Initial scan: ~50ms per skill
- Documentation parsing: Lazy (on first use)
- Helper function import: Only when code execution enabled

**Memory Footprint:**
- SKILL.md: ~50-100 KB (main documentation)
- Supporting docs: ~200-500 KB total
- API reference: ~300-500 KB (centralized docs)
- Total per skill: ~500 KB - 1 MB

---

## Extensibility Architecture

### Creating Custom Skills

**Step 1: Define Skill Class**
```python
from edgar.ai.skills.base import BaseSkill
from pathlib import Path

class CustomSkill(BaseSkill):
    name = "Custom SEC Analysis"
    description = "Domain-specific analysis patterns"
    content_dir = Path(__file__).parent / "docs"

    def get_helpers(self):
        return {
            'custom_workflow': self.custom_workflow
        }

    def get_object_docs(self):
        # Optional: reference EdgarTools centralized docs
        return [Path("path/to/relevant/docs.md")]
```

**Step 2: Create Documentation**
```
my_skill/
├── __init__.py              # CustomSkill definition
└── docs/
    ├── SKILL.md            # Required: main documentation
    ├── workflows.md        # Optional: examples
    └── reference.md        # Optional: detailed API
```

**Step 3: Export**
```python
from my_package.skills import custom_skill

# Install to Claude Desktop
custom_skill.export(format="claude-skills")

# Or create portable ZIP
custom_skill.export(format="claude-desktop", create_zip=True)
```

### Extending MCP Tools

**Add new tool to server.py:**
```python
@app.list_tools()
async def list_tools():
    return [
        # Existing tools...
        Tool(
            name="edgar_custom_analysis",
            description="Custom domain-specific analysis",
            inputSchema={...}
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "edgar_custom_analysis":
        from edgar.ai.mcp.tools.custom import handle_custom_analysis
        return await handle_custom_analysis(arguments)
```

**Tool handler pattern:**
```python
# edgar/ai/mcp/tools/custom.py
async def handle_custom_analysis(args: dict) -> list[TextContent]:
    identifier = args.get("identifier")

    try:
        # Use EdgarTools API
        result = perform_custom_analysis(identifier)

        # Format response
        response_text = format_output(result)

        # Token management
        response_text = check_output_size(response_text, max_tokens=2000)

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        return [TextContent(
            type="text",
            text=format_error_with_suggestions(e)
        )]
```

---

## Security Considerations

### MCP Server

**Threat Model:**
- **Subprocess Execution**: Server runs as user subprocess with full permissions
- **No Network Exposure**: stdio transport only, no network sockets
- **Input Validation**: Limited - trusts client to provide valid parameters
- **SEC API Identity**: Required, prevents abuse tracking

**Mitigations:**
- Run with least privilege (user-level, not root)
- Environment isolation via client config
- Rate limiting inherited from SEC API
- No persistent state or data storage

### Skills

**Threat Model:**
- **Documentation Injection**: Malicious markdown in skill docs
- **Code Execution**: Helper functions execute arbitrary Python
- **File System Access**: Skills can read arbitrary files via Path

**Mitigations:**
- Skills installed to user directory (~/.claude/skills/)
- No automatic code execution (user must enable)
- YAML frontmatter validation
- Read-only documentation (no write operations)

### Best Practices

1. **EDGAR_IDENTITY**: Always set, required by SEC
2. **Rate Limiting**: Respect SEC's 10 req/sec limit
3. **Error Handling**: Never expose internal paths or secrets
4. **Token Limits**: Prevent context overflow attacks
5. **Input Validation**: Sanitize company identifiers, form types

---

## Deployment Scenarios

### Scenario 1: Individual Developer with Claude Desktop

**Setup:**
```bash
pip install edgartools[ai]
```

**MCP Configuration:**
```json
{
  "mcpServers": {
    "edgartools": {
      "command": "python3",
      "args": ["-m", "edgar.ai"],
      "env": {"EDGAR_IDENTITY": "..."}
    }
  }
}
```

**Skills Installation:**
```python
from edgar.ai.skills import edgartools_skill
edgartools_skill.export(format="claude-skills")
# → ~/.claude/skills/edgartools/
```

**Usage Pattern:**
- Ask Claude to research companies
- Claude uses MCP tools for real-time data
- Claude references skill documentation for patterns
- User can execute helper functions if code execution enabled

### Scenario 2: Enterprise with Custom Skills

**Custom Skill Package:**
```python
# enterprise_sec_analysis/skills/compliance.py
class ComplianceSkill(BaseSkill):
    name = "SEC Compliance Analysis"
    description = "Regulatory compliance checks for public companies"

    def get_helpers(self):
        return {
            'check_sox_compliance': self.check_sox_compliance,
            'audit_financial_controls': self.audit_controls,
            'generate_compliance_report': self.generate_report,
        }
```

**Distribution:**
1. Package as Python library: `pip install enterprise-sec-analysis`
2. Export skills: `compliance_skill.export(format="claude-skills")`
3. Deploy to team via shared config or automation
4. Document custom workflows in skill markdown

### Scenario 3: Research Platform with API Integration

**Architecture:**
```
Research Platform
    ├─> Custom MCP Server (extends edgar.ai)
    ├─> Custom Skills (domain-specific)
    ├─> API Gateway (exposes to web clients)
    └─> Database (caches SEC data)
```

**Custom MCP Server:**
```python
# Extend base server with additional tools
from edgar.ai.mcp.server import app

@app.list_tools()
async def list_tools():
    tools = await original_list_tools()
    tools.append(Tool(
        name="edgar_research_custom",
        description="Platform-specific analysis",
        inputSchema={...}
    ))
    return tools
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_ai_features.py
def test_token_optimizer():
    content = {"key": "value" * 1000}
    optimized = TokenOptimizer.optimize_for_tokens(content, max_tokens=100)
    assert TokenOptimizer.estimate_tokens(optimized) <= 100

def test_semantic_enricher():
    definition = SemanticEnricher.get_concept_definition("Revenue")
    assert "income" in definition.lower()
```

### Integration Tests

```python
# tests/test_mcp_tools.py
@pytest.mark.network
async def test_company_research_tool():
    args = {"identifier": "AAPL", "include_financials": True}
    result = await handle_company_research(args)
    assert isinstance(result, list)
    assert result[0].type == "text"
```

### Skills Export Tests

```python
# tests/test_ai_skill_export.py
def test_export_claude_skills():
    skill = EdgarToolsSkill()
    path = skill.export(format="claude-skills", output_dir=temp_dir)
    assert (path / "SKILL.md").exists()
    assert (path / "api-reference").exists()
```

### End-to-End Tests

**MCP Server:**
```bash
# Start server
python -m edgar.ai &

# Send tool call via stdio
echo '{"method":"tools/list"}' | python -m edgar.ai

# Verify response
```

**Skills:**
```python
# Export skill
skill.export(format="claude-skills")

# Verify structure
assert Path.home() / ".claude/skills/edgartools/SKILL.md" exists()

# Validate frontmatter
content = read_file("SKILL.md")
assert "name: EdgarTools" in content
```

---

## Monitoring & Observability

### Logging

**MCP Server Logs:**
```python
import logging

logger = logging.getLogger("edgartools-mcp")
logger.setLevel(logging.INFO)

# Logs to stderr (captured by Claude Desktop)
logger.info("Starting EdgarTools MCP Server v4.26.0")
logger.warning("EDGAR_IDENTITY not set")
logger.error("Error in tool edgar_company_research: %s", e)
```

**Log Locations:**
- **Claude Desktop**: `~/Library/Logs/Claude/mcp-server-edgartools.log` (macOS)
- **Cline**: VS Code output panel
- **Continue.dev**: `~/.continue/logs/`

### Metrics

**Key Metrics to Track:**
1. Tool call latency (by tool name)
2. Tool call success/failure rate
3. Token usage per response
4. SEC API rate limit hits
5. Error types and frequency

**Future Enhancement:**
```python
class Metrics:
    @staticmethod
    def record_tool_call(tool_name, latency_ms, success):
        # Send to metrics backend
        pass

    @staticmethod
    def record_token_usage(tool_name, tokens):
        # Track context window usage
        pass
```

### Debugging

**Enable Debug Logging:**
```python
# In MCP server startup
logging.basicConfig(level=logging.DEBUG)
```

**MCP Inspector Tool:**
```bash
# Test MCP server without client
python -m edgar.ai --test
```

**Skill Validation:**
```python
from edgar.ai.skills import edgartools_skill

# Validate structure
docs = edgartools_skill.get_documents()
print(f"Documents: {docs}")

helpers = edgartools_skill.get_helpers()
print(f"Helpers: {list(helpers.keys())}")
```

---

## Future Enhancements

### Short-Term (3-6 months)

1. **Response Caching**
   - Cache Entity Facts API responses
   - TTL-based invalidation
   - Reduces latency for repeated queries

2. **Streaming Support**
   - Stream large responses in chunks
   - Improves UX for slow API calls
   - MCP supports SSE streaming

3. **Advanced Token Management**
   - Integrate tiktoken for accurate counts
   - Smart summarization (not just truncation)
   - Priority-based content selection

4. **More Skills**
   - Insider Trading Skill (Form 4 analysis)
   - Crowdfunding Skill (Form C/D analysis)
   - Fund Analysis Skill (N-CSR, NPORT)

### Medium-Term (6-12 months)

1. **Multi-Agent Collaboration**
   - Agents share context via resources
   - Coordinated multi-company analysis
   - Parallel execution optimization

2. **Vector Embeddings**
   - Semantic search across filings
   - Similar company discovery
   - Document similarity matching

3. **Fine-Tuned Models**
   - Domain-specific SEC terminology
   - Financial statement understanding
   - Form type classification

4. **Web Interface**
   - Visual dashboard for MCP server
   - Skill marketplace
   - Interactive documentation

### Long-Term (12+ months)

1. **Distributed Skills**
   - Skills hosted on remote servers
   - Automatic updates and versioning
   - Community-contributed skills

2. **Advanced Analytics**
   - Fraud detection patterns
   - Risk assessment models
   - Predictive financial analysis

3. **Cross-Source Integration**
   - Combine SEC data with market data
   - News sentiment analysis
   - Social media signals

---

## Technical Decisions & Rationale

### Why MCP + Skills (not just one)?

**Decision**: Provide both real-time (MCP) and knowledge-based (Skills) integration

**Rationale:**
- **MCP**: Best for real-time queries requiring current data
- **Skills**: Best for teaching patterns, workflows, API usage
- **Combined**: Agents can use tools for data, reference docs for patterns
- **Flexibility**: Clients can use one or both depending on needs

### Why stdio transport (not HTTP)?

**Decision**: Use stdio for MCP communication

**Rationale:**
- **Security**: No network exposure, local only
- **Simplicity**: No port management, firewall issues
- **Standard**: Follows MCP spec, works with all clients
- **Performance**: Lower latency than HTTP localhost

### Why progressive disclosure documentation?

**Decision**: Multi-tier documentation (Quick → Tutorial → Reference)

**Rationale:**
- **Token Efficiency**: Don't load full API reference for simple queries
- **Learning Curve**: Start simple, layer complexity
- **Task-Oriented**: Quick routing by what user wants to accomplish
- **Context Window**: Fit maximum useful info in minimum tokens

### Why BaseSkill abstract class?

**Decision**: Provide extensible skill framework

**Rationale:**
- **Ecosystem**: Enable external packages to create skills
- **Standardization**: Consistent structure across skills
- **Reusability**: Share export, validation logic
- **Discoverability**: Standard interface for tooling

### Why centralized API docs (not inline)?

**Decision**: Reference centralized markdown docs from main library

**Rationale:**
- **Single Source of Truth**: Docs maintained in core library
- **Consistency**: Same docs across all interfaces
- **Maintainability**: Update once, reflects everywhere
- **Completeness**: Full method signatures, parameters, examples

---

## Dependencies

### Core Dependencies

```toml
[tool.hatch.envs.default.dependencies]
# Core EdgarTools (no AI dependencies)
pandas = "*"
pyarrow = "*"
requests = "*"
rich = "*"

[project.optional-dependencies]
ai = [
    "mcp>=0.9.0",           # Model Context Protocol SDK
]

ai-dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21", # For async MCP tests
]
```

### Optional Dependencies

- **tiktoken**: Accurate token counting (OpenAI tokenizer)
- **yaml**: YAML frontmatter parsing (future: strict validation)

### Dependency Strategy

**Core Library**: No AI dependencies
- Keeps EdgarTools lightweight for non-AI users
- AI features are strictly optional

**AI Package**: Minimal dependencies
- Only MCP SDK required for server
- Skills work with just stdlib (no external deps)

**Future**: Consider bundling tiktoken for better token estimation

---

## Versioning & Compatibility

### Version Numbers

Format: `MAJOR.MINOR.PATCH`

**MCP Server**: Syncs with EdgarTools package version
```python
from edgar.__about__ import __version__
# Server reports version in InitializationOptions
```

**Skills**: Independent versioning in YAML frontmatter
```yaml
---
name: EdgarTools
version: 1.0.0
description: ...
---
```

### Compatibility Matrix

| EdgarTools | MCP SDK | Claude Desktop | Skills Format |
|------------|---------|----------------|---------------|
| 4.26.0+    | 0.9.0+  | 0.7.0+        | 1.0           |

### Breaking Changes

**MCP Server:**
- Tool schema changes (input/output format)
- Tool additions/removals
- Protocol version updates

**Skills:**
- YAML frontmatter structure
- Document organization
- Helper function signatures

**Mitigation:**
- Semantic versioning (MAJOR for breaking changes)
- Deprecation warnings (1 version ahead)
- Changelog documentation

---

## Documentation & Resources

### For Architects

- **This document**: High-level technical overview
- `edgar/ai/README.md`: Package overview and installation
- `edgar/ai/mcp/docs/MCP_QUICKSTART.md`: MCP setup guide

### For Developers

- `edgar/ai/skills/base.py`: BaseSkill API reference
- `edgar/ai/core.py`: AI infrastructure components
- `edgar/ai/helpers.py`: Helper function implementations

### For End Users

- `edgar/ai/skills/core/SKILL.md`: EdgarTools skill documentation
- `edgar/ai/skills/core/workflows.md`: End-to-end examples
- `edgar/ai/skills/core/quickstart-by-task.md`: Quick routing guide

### External Resources

- **MCP Specification**: https://spec.modelcontextprotocol.io/
- **Claude Skills**: https://www.anthropic.com/claude-skills
- **SEC EDGAR**: https://www.sec.gov/edgar/

---

## Appendix: Code Organization

```
edgar/ai/
├── __init__.py                 # Package exports, capability detection
├── __main__.py                 # Entry point: python -m edgar.ai
├── ARCHITECTURE.md             # This document
├── README.md                   # User-facing overview
│
├── core.py                     # AI infrastructure
│   ├── TokenOptimizer          # Token estimation & optimization
│   ├── SemanticEnricher        # Business context enrichment
│   ├── AIEnabled               # Base class for AI-aware objects
│   └── enhance_financial_fact_llm_context()
│
├── helpers.py                  # Convenience wrappers
│   ├── get_filings_by_period()
│   ├── get_revenue_trend()
│   ├── compare_companies_revenue()
│   └── filter_by_industry()
│
├── formats.py                  # Format utilities (future)
│
├── mcp/                        # Model Context Protocol
│   ├── __init__.py
│   ├── server.py               # MCP server implementation
│   ├── tools/                  # Tool handlers
│   │   ├── company_research.py
│   │   ├── financial_analysis.py
│   │   ├── industry_analysis.py
│   │   └── utils.py
│   └── docs/
│       └── MCP_QUICKSTART.md
│
├── skills/                     # Skills infrastructure
│   ├── __init__.py
│   ├── base.py                 # BaseSkill abstract class
│   └── core/                   # EdgarTools skill
│       ├── __init__.py         # EdgarToolsSkill implementation
│       ├── SKILL.md            # Main skill documentation
│       ├── readme.md           # Skill overview
│       ├── workflows.md        # End-to-end examples
│       ├── objects.md          # Object reference
│       ├── data-objects.md     # Form-specific objects
│       ├── form-types-reference.md  # SEC forms catalog
│       └── quickstart-by-task.md    # Task routing
│
├── exporters/                  # Skill export formats
│   ├── __init__.py
│   ├── claude_skills.py        # Official Claude Skills format
│   └── claude_desktop.py       # Portable/ZIP format
│
└── examples/                   # Usage examples
    └── basic_usage.py
```

---

## Contact & Contribution

**Maintainer**: EdgarTools Development Team

**Repository**: https://github.com/dgunning/edgartools

**Issues**: https://github.com/dgunning/edgartools/issues

**Discussions**: https://github.com/dgunning/edgartools/discussions

**Contributing**:
1. Fork repository
2. Create feature branch
3. Add tests for new features
4. Submit pull request with clear description

**Architectural Questions**: Open a discussion on GitHub with tag `architecture`

---

*Last Updated: 2025-01-05*
*Version: 1.0*
*EdgarTools: 4.26.0+*
