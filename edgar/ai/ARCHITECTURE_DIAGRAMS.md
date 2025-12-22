# edgar.ai Architecture Diagrams

**Visual representations of the corrected parallel integration architecture**

---

## Diagram 1: Parallel Integration Pathways (Corrected)

```
                    ┌────────────────────────┐
                    │      AI Agent          │
                    │ (Claude Desktop, etc)  │
                    └───────────┬────────────┘
                                │
                                │ Agent chooses pathway
                                │
                      ┌─────────┴─────────┐
                      │                   │
            ┌─────────▼────────┐  ┌──────▼───────────┐
            │  Skills Package  │  │   MCP Server     │
            │  (documentation) │  │ (stdio protocol) │
            │  + Code Execution│  │  + Tool Calling  │
            └─────────┬────────┘  └──────┬───────────┘
                      │                   │
                      │  Both call directly
                      │                   │
            ┌─────────▼───────────────────▼────────────┐
            │      EdgarTools Core API                 │
            │      (edgar package)                     │
            │  Company(), get_filings(), XBRL()        │
            └─────────┬────────────────────────────────┘
                      │ HTTP requests
            ┌─────────▼────────┐
            │  SEC EDGAR APIs  │
            └──────────────────┘
```

**Key Point**: Skills and MCP are **peers**, not layers. Both integrate with EdgarTools API directly.

---

## Diagram 2: Skills Path (Primary - Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Agent Loads Skill                                   │
│ Claude Desktop startup → ~/.claude/skills/edgartools/       │
│                       → SKILL.md loaded                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Agent Learns Patterns                               │
│ Reads: quickstart-by-task.md (30s)                          │
│        ↓                                                    │
│ Reads: SKILL.md (5min)                                      │
│        ↓                                                    │
│ Reads: workflows.md (examples)                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Agent Writes Python Code                            │
│                                                             │
│ from edgar import Company                                   │
│                                                             │
│ company = Company("AAPL")                                   │
│ income = company.income_statement(periods=3)                │
│ balance = company.balance_sheet(periods=3)                  │
│                                                             │
│ # Variables, chaining, full composability                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Code Executes Directly                              │
│                                                             │
│ Python execution environment                                │
│   ↓ import edgar                                            │
│ EdgarTools Core API                                         │
│   ↓ HTTP requests                                           │
│ SEC EDGAR APIs                                              │
│   ↓ Data returned                                           │
│ Results displayed to user                                   │
└─────────────────────────────────────────────────────────────┘

**Advantages**:
- Zero protocol overhead (no JSON-RPC)
- Full composability (variables, chaining, loops)
- Agent learns patterns (not just tool schemas)
- Maximum performance
```

---

## Diagram 3: MCP Path (Alternative)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Agent Calls MCP Tool                                │
│ Claude Desktop → edgar_company_research("AAPL")             │
└─────────────────────────────────────────────────────────────┘
                            ↓ JSON-RPC over stdio
┌─────────────────────────────────────────────────────────────┐
│ Step 2: MCP Server Receives Request                         │
│ MCP Server (edgar/ai/mcp/server.py)                         │
│   ↓                                                         │
│ Tool Handler (company_research.py)                          │
│   ↓                                                         │
│ from edgar import Company  # Direct import!                 │
└─────────────────────────────────────────────────────────────┘
                            ↓ Direct API call
┌─────────────────────────────────────────────────────────────┐
│ Step 3: EdgarTools API Called Directly                      │
│                                                             │
│ company = Company("AAPL")                                   │
│ income = company.income_statement(periods=3)                │
│ # Same API calls as Skills path!                            │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP requests
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Results Returned via MCP Protocol                   │
│                                                             │
│ EdgarTools → MCP handler formats response                   │
│            → JSON-RPC over stdio                            │
│            → Claude Desktop receives text                   │
└─────────────────────────────────────────────────────────────┘

**Trade-offs**:
- Protocol overhead (~100-200ms per call)
- Limited composability (separate tool calls)
- Parameter validation via schemas
- Good for simple queries
```

---

## Diagram 4: COP Layered Architecture Mapping

```
┌──────────────────────────────────────────────────────────┐
│ Layer 5: Intent (what humans want)                       │
│ "Compare Apple and Microsoft's revenue trends"           │
└──────────────────────────────────────────────────────────┘
                       ↓ Claude interprets
┌──────────────────────────────────────────────────────────┐
│ Layer 4: Context/Approach (Skills)                       │
│ - Loads SKILL.md: "3 approaches to get filings"          │
│ - Loads workflows.md: "Workflow 1: Compare Revenue"      │
│ - Understands: Use Company.income_statement()            │
└──────────────────────────────────────────────────────────┘
                       ↓ Orchestrates approach
┌──────────────────────────────────────────────────────────┐
│ Layer 3: Execution (Code Generation + Execution)         │
│                                                          │
│ Agent chooses integration path:                          │
│                                                          │
│ PRIMARY (90%):          │  SPECIALIZED (10%):            │
│ Skills + Code           │  MCP for Complex Workflows     │
│ ─────────────────────   │  ─────────────────             │
│ from edgar import       │  # Complex multi-step:         │
│   Company               │  edgar_batch_analysis()        │
│ company = Company("A")  │  edgar_monitor_filings()       │
│ income = company.       │  edgar_workflow_orchestrate()  │
│   income_statement(3)   │    ↓ (MCP protocol)            │
│                         │  MCP Server handler            │
│ Interactive analysis,   │    ↓                           │
│ learning, exploration   │  from edgar import Company     │
│                         │  # Batch processing,           │
│                         │  # automation, pipelines       │
│                         │                                │
│ Both paths call EdgarTools Core API directly             │
└──────────────────────────────────────────────────────────┘
                       ↓ Direct API calls
┌──────────────────────────────────────────────────────────┐
│ Layer 2: EdgarTools Core API (edgar package)             │
│ - Company()                                              │
│ - get_filings()                                          │
│ - Filing.xbrl()                                          │
│ - Statement objects                                      │
└──────────────────────────────────────────────────────────┘
                       ↓ HTTP requests
┌──────────────────────────────────────────────────────────┐
│ Layer 1: External Systems (SEC EDGAR APIs)               │
│ - Company Facts API                                      │
│ - Entity Submissions API                                 │
│ - XBRL Filing Data                                       │
└──────────────────────────────────────────────────────────┘

**Key Insights**:
- EdgarTools API (Layer 2) is the actual integration layer
- Skills (PRIMARY) for 90% of use cases: interactive analysis, learning, exploration
- MCP (SPECIALIZED) for 10%: complex workflows, batch processing, orchestration
- Don't install both unless you specifically need workflow automation
```

---

## Diagram 5: Progressive Disclosure (4-Tier Hierarchy)

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 0: Quick Routing (30 seconds, ~50 tokens)              │
│                                                             │
│ quickstart-by-task.md                                       │
│ ├─ Section 1: Counting & Existence Queries                  │
│ ├─ Section 2: Discovery & Filtering Queries                 │
│ ├─ Section 3: Data Analysis Queries                         │
│ └─ Section 4: Multi-Company Queries                         │
│                                                             │
│ form-types-reference.md                                     │
│ └─ 311 SEC forms with natural language mapping              │
│    "crowdfunding" → Form C                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓ Decision made
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: Tutorial Level (5-10 minutes, ~2000 tokens)         │
│                                                             │
│ SKILL.md                                                    │
│ ├─ Quick Start                                              │
│ ├─ Core API Reference (3 approaches to get filings)         │
│ └─ Advanced Patterns                                        │
│                                                             │
│ workflows.md                                                │
│ └─ End-to-end workflow examples                             │
│                                                             │
│ objects.md                                                  │
│ └─ Core objects + token estimates                           │
│                                                             │
│ data-objects.md                                             │
│ └─ Form-specific objects (TenK, Form4, etc.)                │
└─────────────────────────────────────────────────────────────┘
                            ↓ Deep dive needed
┌─────────────────────────────────────────────────────────────┐
│ Tier 2: API Reference (detailed, ~3000+ tokens)             │
│                                                             │
│ api-reference/Company.md      (~1,070 lines)                │
│ api-reference/EntityFiling.md (~557 lines)                  │
│ api-reference/XBRL.md         (~587 lines)                  │
│ api-reference/Statement.md    (~567 lines)                  │
│                                                             │
│ Complete method signatures, parameters, return types        │
└─────────────────────────────────────────────────────────────┘
                            ↓ Specific method needed
┌─────────────────────────────────────────────────────────────┐
│ Tier 3: On-Demand Resources (unlimited)                     │
│                                                             │
│ - EdgarTools source code (when needed)                      │
│ - SEC filing examples (when needed)                         │
│ - Advanced tutorials (when needed)                          │
└─────────────────────────────────────────────────────────────┘

**Example Navigation**:
Query: "How many crowdfunding filings in past week?"
  ↓ Load Tier 0 (50 tokens)
quickstart-by-task.md → Section 1: Counting
form-types-reference.md → "crowdfunding" → Form C
  ↓ Load pattern (200 tokens)
SKILL.md → Date filtering example
  ↓ Execute (no additional context)
Total: ~270 tokens vs loading full API reference (~5000 tokens)
= 95% token savings
```

---

## Diagram 6: Token Economics (Context as Resource)

```
┌─────────────────────────────────────────────────────────────┐
│ Context Window Budget: 200,000 tokens (Claude Sonnet)       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Skills Approach (Progressive Disclosure)                    │
│                                                             │
│ Initial Load:      ~2,000 tokens (SKILL.md)                 │
│ Per Query:         0 tokens (documentation cached)          │
│ ────────────────────────────────────────────────────────    │
│ Total (10 queries): ~2,000 tokens                           │
│                                                             │
│ Remaining budget: 198,000 tokens for conversation           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ MCP Approach (Tool Schemas)                                 │
│                                                             │
│ Initial Load:      ~400 tokens (tool schemas)               │
│ Per Query:         ~50 tokens (tool call overhead)          │
│ ────────────────────────────────────────────────────────    │
│ Total (10 queries): ~900 tokens                             │
│                                                             │
│ Remaining budget: 199,100 tokens for conversation           │
└─────────────────────────────────────────────────────────────┘

**Analysis**:
- Both approaches are token-efficient
- Skills: Better for <10 queries per conversation
- MCP: Slightly better for >20 queries per conversation
- Real winner: Skills for learning + composability
```

---

## Diagram 7: Skills vs MCP Decision Tree

```
                        Start: Need SEC Data
                                │
                    ┌───────────┴───────────┐
                    │                       │
        Interactive analysis?     Automated workflow?
        Learning EdgarTools?      Batch processing?
                    │                       │
                   Yes                      No
                    │                       │
          ┌─────────▼─────────┐            │
          │                   │            │
          │  Use Skills +     │     ┌──────▼──────────┐
          │  Code Execution   │     │                 │
          │                   │     │ Complex multi-  │
          │  PRIMARY PATH     │     │ step workflow?  │
          │  (90% of users)   │     │ (S&P 500 batch, │
          │                   │     │  monitoring,    │
          └───────────────────┘     │  orchestration) │
                    │               │                 │
                    │               └────────┬────────┘
                    │                        │
                    │                       Yes
                    │                        │
                    │               ┌────────▼────────┐
                    │               │                 │
                    │               │  Use MCP Tools  │
                    │               │                 │
                    │               │  SPECIALIZED    │
                    │               │  (10% of users) │
                    │               │                 │
                    │               └─────────────────┘
                    │                        │
                    ▼                        ▼
    from edgar import Company    edgar_batch_analysis()
    company = Company("AAPL")    edgar_monitor_filings()
    income = company.            edgar_workflow_orchestrate()
      income_statement(3)
```

**Guidelines**:
- **Use Skills (PRIMARY)**: Interactive analysis, learning, exploration, ad-hoc research
- **Use MCP (SPECIALIZED)**: Batch processing 100+ companies, automated pipelines, scheduled monitoring
- **Don't install both**: Unless you specifically need workflow orchestration + interactive analysis

---

## Diagram 8: Data Flow - Process Before Context (COP Pattern)

```
┌─────────────────────────────────────────────────────────────┐
│ External System: SEC EDGAR Database                         │
│ - 50,000 filings in Q4 2023                                 │
│ - Each filing: ~1MB of data                                 │
│ - Total: ~50GB of data                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓ Query via EdgarTools
┌─────────────────────────────────────────────────────────────┐
│ Execution Environment (Python)                              │
│                                                             │
│ filings = get_filings(2023, 4)  # 50,000 filings            │
│                                                             │
│ # Filter in execution (NOT in context)                      │
│ pharma_companies = get_pharmaceutical_companies()           │
│ pharma_ciks = pharma_companies['cik'].tolist()              │
│ pharma_filings = filings.filter(cik=pharma_ciks)            │
│                                                             │
│ # Result: 127 pharmaceutical filings                        │
└─────────────────────────────────────────────────────────────┘
                            ↓ Summary only
┌─────────────────────────────────────────────────────────────┐
│ Context Window (Agent Memory)                               │
│                                                             │
│ result = "Found 127 pharmaceutical 10-K filings in Q4 2023" │
│                                                             │
│ Token cost: ~15 tokens (vs 50,000 if loaded into context)   │
└─────────────────────────────────────────────────────────────┘

**Key Principle**: Process data in execution environment.
Only results enter context window.

**Old Way (Anti-Pattern)**:
50,000 filings → Load all into context → Filter in context
= Context overflow!

**New Way (COP Pattern)**:
50,000 filings → Filter in execution → Load results into context
= Efficient!
```

---

## Diagram 9: Skill Composition (Future Enhancement)

```
┌─────────────────────────────────────────────────────────────┐
│ Agent Task: "Detect insider trading patterns for            │
│              pharmaceutical companies"                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ System Understands: Needs 3 domain skills                   │
│                                                             │
│ 1. EdgarToolsSkill → Get pharmaceutical companies           │
│ 2. EdgarToolsSkill → Get Form 4 filings                     │
│ 3. InsiderTradingSkill → Analyze trading patterns           │
└─────────────────────────────────────────────────────────────┘
                            ↓ Semantic composition
┌─────────────────────────────────────────────────────────────┐
│ Composed Workflow (Generated by Agent)                      │
│                                                             │
│ from edgar.ai.helpers import get_pharmaceutical_companies   │
│ from edgar import Company                                   │
│ from insider_trading_skill import analyze_trading_patterns  │
│                                                             │
│ # Step 1: Get pharmaceutical companies                      │
│ pharma_cos = get_pharmaceutical_companies()                 │
│                                                             │
│ # Step 2: Get Form 4 filings for each                       │
│ for ticker in pharma_cos['ticker']:                         │
│     company = Company(ticker)                               │
│     form4s = company.get_filings(form="4")                  │
│                                                             │
│     # Step 3: Analyze trading patterns                      │
│     patterns = analyze_trading_patterns(form4s)             │
│     if patterns.is_unusual():                               │
│         report(ticker, patterns)                            │
└─────────────────────────────────────────────────────────────┘

**Future Vision**: Skills compose semantically through understanding,
not through rigid API contracts.
```

---

## Summary: Why Parallel Pathways?

```
Traditional (Layered) Architecture:
User → Application Layer → Business Logic → Data Access → Database
      (each layer abstracts the next)

edgar.ai (Parallel) Architecture:
User → Skills (Documentation)  ┐
    → MCP (Protocol)          ├─→ EdgarTools API → SEC APIs
    → Direct Code             ┘
      (all three reach same integration point)

**Benefits**:
1. User choice (tool calling vs code execution)
2. No forced abstraction layer
3. Skills and MCP can evolve independently
4. EdgarTools API remains stable contract

**Key Insight**: Integration layer (EdgarTools API) is separate
from access patterns (Skills vs MCP). This is the correct architecture.
```

---

*For more details, see ARCHITECTURE.md and CONTEXT_ORIENTED_ANALYSIS.md*
