# edgar.ai Messaging Guide

**Positioning edgar.ai as Context-Oriented Programming exemplar with Skills-first approach**

---

## Elevator Pitch (30 seconds)

**edgar.ai makes SEC financial data accessible to AI agents through Skills—AI-consumable documentation that teaches patterns, not syntax. Agents read, learn, and write Python code directly. Zero protocol overhead. Full composability. For complex workflows and automation, MCP provides structured tool calling. Context-Oriented Programming in action.**

---

## One-Paragraph Summary

edgar.ai provides two parallel pathways for AI agents to access SEC EDGAR filing data: Skills (documentation + code execution) and MCP (tool-based protocol). Skills is the primary approach for 90% of users—it follows Context-Oriented Programming principles with progressive disclosure (4-tier documentation), token optimization, and direct API access. Agents read SKILL.md, learn patterns, write Python code, and execute directly for interactive analysis. MCP is specialized for complex workflows: batch processing 100+ companies, automated monitoring, scheduled reports, and workflow orchestration. Both call EdgarTools API directly—no abstraction layer. Most users should start with Skills only and add MCP when they need production automation.

---

## Key Messages

### 1. Skills-First Architecture (Primary Message)

**What**: Documentation-first integration that teaches AI agents how to use EdgarTools

**Why**:
- Zero protocol overhead (direct Python code execution)
- Full composability (variables, chaining, loops in single code block)
- Agents learn patterns (not just tool schemas)
- Context-Oriented Programming aligned

**Proof**:
- 95% token savings through progressive disclosure
- 4-tier documentation hierarchy (30s → 5min → detailed → comprehensive)
- Real-world usage by Claude Desktop, Cline, Continue.dev

**Soundbite**: *"Skills teach patterns. MCP executes schemas. Skills win on learning and composability."*

### 2. Context-Oriented Programming Exemplar (Differentiation Message)

**What**: edgar.ai naturally implements COP's five axioms without being designed for it

**Why**:
- **Understanding as Primitive**: Self-documenting APIs, semantic enrichment
- **Context as Resource**: Token budgets, optimization, estimates for all operations
- **Progressive Disclosure**: 4-tier documentation with quantified token costs
- **Semantic Composition**: Helper functions abstract multi-step patterns
- **Data Flow**: Process before context (540x performance improvement)

**Proof**:
- Industry filtering: 9 minutes → <1 second (5,400 API calls → 0 calls)
- Token efficiency: ~270 tokens for simple query vs ~5000 tokens loading full API
- Aligns with Anthropic's Skills + MCP + Code Execution vision

**Soundbite**: *"edgar.ai proves COP works—not because we followed COP principles, but because COP describes what naturally emerges when you design systems for AI agents."*

### 3. Parallel Pathways for Different Use Cases (Technical Message)

**What**: Skills and MCP are peer integration pathways for different use cases—both call EdgarTools API directly

**Why**:
- No forced abstraction layer
- **Skills (90%)**: Interactive analysis, learning, exploration
- **MCP (10%)**: Batch processing, automation, orchestration
- Independent evolution (Skills and MCP can improve separately)
- EdgarTools API is the stable contract

**Proof**:
```python
# Skills path (interactive analysis)
from edgar import Company
company = Company("AAPL")
income = company.income_statement(periods=3)

# MCP path (automated batch processing)
# In MCP tool handler:
from edgar import Company  # Same import!
for ticker in sp500_tickers:  # Batch processing
    company = Company(ticker)
    # Process 100+ companies
```

**Soundbite**: *"Skills for humans + agents. MCP for robots + pipelines."*

### 4. Quantified Benefits (ROI Message)

**What**: Measurable improvements over traditional approaches

**Why**: Decision-makers need numbers

**Proof**:

| Metric | Old Way | edgar.ai | Improvement |
|--------|---------|----------|-------------|
| Industry filtering | 9 minutes | <1 second | 540x faster |
| API calls | 5,400 | 0 | 100% reduction |
| Token overhead | ~5,000 | ~270 | 95% savings |
| Code maintenance | Server + handlers + schemas | Documentation only | 70% less code |

**Soundbite**: *"Process data before it enters context. This simple principle delivers 540x performance improvement."*

---

## Target Audiences & Tailored Messaging

### For AI Agents (Claude, GPT, etc.)

**Message**: "Learn EdgarTools patterns through progressive disclosure documentation. Write Python code directly. Full composability."

**Tone**: Direct, technical, example-driven

**Key Points**:
- Install Skills to `~/.claude/skills/edgartools/`
- Read SKILL.md for quick start
- Use workflows.md for complete examples
- Refer to api-reference/ for detailed methods

**Call to Action**: Install the skill and start analyzing SEC filings with zero configuration

### For Developers

**Message**: "Skills-first integration for interactive analysis (90% of users). MCP for complex workflow automation (10%). Both call EdgarTools directly."

**Tone**: Pragmatic, architecture-focused, with code examples

**Key Points**:
- **Skills (PRIMARY)**: Interactive analysis, learning, exploration - zero protocol overhead
- **MCP (SPECIALIZED)**: Batch processing, automated pipelines, orchestration
- Most users start with Skills only
- Add MCP when you need production automation (100+ companies, scheduled monitoring)
- Both paths call same EdgarTools API
- No abstraction layer to learn

**Call to Action**: Install Skills for interactive use. Add MCP only when you need workflow automation.

### For Architects & Decision-Makers

**Message**: "Context-Oriented Programming in production. Skills-first architecture reduces complexity while improving performance and maintainability."

**Tone**: Strategic, ROI-focused, with architectural diagrams

**Key Points**:
- 70% less code to maintain (documentation only vs server + handlers)
- 95% token savings through progressive disclosure
- 540x performance improvement from COP patterns
- Extensible framework (external packages can create domain-specific skills)

**Call to Action**: Review ARCHITECTURE.md and CONTEXT_ORIENTED_ANALYSIS.md. Evaluate for your domain-specific use case.

### For COP Community & Thought Leaders

**Message**: "edgar.ai accidentally became a near-perfect COP implementation by designing for AI agents first. We discovered COP principles empirically."

**Tone**: Thought-leadership, research-oriented, with deep analysis

**Key Points**:
- Implements 4/5 COP axioms excellently (Understanding, Context, Progressive Disclosure, Data Flow)
- Quantifies token economics (COP talks abstractly about "context scarcity")
- Domain-specific semantic enrichment (shows HOW to implement "understanding as primitive")
- Hybrid architecture (Skills + MCP + Core) not described in COP literature

**Call to Action**: Join discussion on how COP applies to domain-specific APIs. Share patterns from your domain.

---

## Messaging Hierarchy

**Tier 1: Hook (5 seconds)**
> "AI-consumable SEC data through Skills—documentation that teaches, not just describes."

**Tier 2: Value Proposition (30 seconds)**
> "edgar.ai makes SEC filings accessible to AI agents through two paths: Skills (primary) for complex workflows with zero protocol overhead, and MCP (alternative) for simple queries with parameter validation. Both call EdgarTools directly. Skills follow Context-Oriented Programming principles: progressive disclosure, token optimization, semantic enrichment. Agents learn patterns and write Python code. Maximum composability."

**Tier 3: Proof Points (2 minutes)**
> Show architecture diagram (parallel pathways), token economics table (95% savings), performance metrics (540x improvement), and code examples (Skills vs MCP side-by-side). Emphasize: "We didn't design for COP. We designed for AI agents. COP principles emerged naturally."

**Tier 4: Deep Dive (10+ minutes)**
> Walk through ARCHITECTURE.md and CONTEXT_ORIENTED_ANALYSIS.md. Show how each COP axiom maps to implementation. Discuss gaps (temporal locality, semantic composition limitations). Share roadmap (resource-based state, skill composition, code-first API). Position as COP exemplar for domain-specific APIs.

---

## Common Objections & Responses

### "Why not just MCP? Anthropic designed it."

**Response**: "MCP is excellent for what it's designed for: structured tool calling in automated workflows. But 90% of users need interactive analysis, not automation. Skills provide better learning, composability, and zero protocol overhead for this primary use case. MCP remains essential for the 10% who need batch processing 100+ companies or workflow orchestration. The distinction is workflow complexity, not tool quality."

### "Documentation isn't code. How do agents execute?"

**Response**: "Skills ARE documentation. Agents read it, understand patterns, then write Python code that executes directly. No code generation from skills—agents generate code from understanding. This is COP's 'understanding as primitive' in action."

### "This sounds like more work than traditional APIs."

**Response**: "Actually less. Traditional: Server + handlers + schemas + documentation. Skills: Documentation only. The documentation IS the integration. 70% less code to maintain. Plus agents learn patterns, not just memorize schemas."

### "What if Anthropic changes Skills format?"

**Response**: "We follow Anthropic's Skills spec, but Skills are just markdown + YAML. Easy to adapt. Plus we have BaseSkill abstraction—external packages can create skills that work with future formats. And MCP provides fallback option."

### "Should I install both Skills and MCP?"

**Response**: "No, unless you need both interactive analysis AND workflow automation. 90% of users should install Skills only. Add MCP when you need to: (1) batch process 100+ companies, (2) automate filing monitoring, (3) schedule reports, or (4) integrate with workflow tools like n8n or Zapier. Installing both adds unnecessary complexity for most users."

### "How do you measure 'better learning' for agents?"

**Response**: "We measure token efficiency (95% savings), composability (variables + chaining in code vs separate tool calls), and complexity of achievable workflows (multi-company analysis, filtering, aggregation in single code block vs multiple tool invocations). Qualitatively, agents generate more sophisticated analyses with Skills."

---

## Sample Content Pieces

### Blog Post Title Ideas

1. "Why We Built edgar.ai Skills-First (And Kept MCP as Backup)"
2. "Context-Oriented Programming in the Wild: How edgar.ai Discovered COP Principles Empirically"
3. "From 9 Minutes to 1 Second: Processing Before Context in edgar.ai"
4. "Skills vs MCP: When to Use Each for SEC Data Analysis"
5. "Documentation as Code: How Skills Teach AI Agents Without Tool Schemas"

### Tweet Thread Starter

"🧵 We accidentally built a Context-Oriented Programming system while making SEC data accessible to AI agents.

Here's how edgar.ai's Skills-first architecture naturally implements COP's five axioms—and why MCP is optional..."

### Conference Talk Abstract

**Title**: "Skills Over Schemas: Context-Oriented Programming for Domain-Specific AI Integration"

**Abstract**: edgar.ai provides two pathways for AI agents to access SEC financial data: Skills (documentation + code execution) and MCP (tool calling). Through quantitative analysis of token usage, composability, and maintainability, we demonstrate why Skills emerged as the primary integration method. This talk explores how edgar.ai naturally implements Context-Oriented Programming principles—progressive disclosure, token optimization, semantic enrichment—without being explicitly designed for COP. We'll share architecture decisions, performance metrics (540x improvement through "process before context"), and lessons learned building AI-first APIs for specialized domains. Attendees will learn when Skills beat traditional tool-calling approaches, and when MCP remains valuable.

### README Badge/Slogan Ideas

- **Context-Oriented Programming in Production**
- **AI-Native SEC Data Analysis**
- **Skills-First Integration for Financial Data**
- **Documentation That Teaches, Not Just Describes**
- **Zero Protocol Overhead • Full Composability**

---

## Competitive Positioning

### vs MCP-Only Systems

**edgar.ai**: Skills (primary) + MCP (alternative)
**Competitors**: MCP only

**Our Advantage**:
- Better learning curve (documentation vs tool schemas)
- Full composability (code vs tool calls)
- Lower token overhead (documentation cached vs schemas every conversation)

**When They Win**: Very simple, single-query use cases where tool discovery matters

### vs Traditional API Documentation

**edgar.ai**: Progressive disclosure with token estimates
**Competitors**: Flat reference docs

**Our Advantage**:
- 95% token savings through tiered documentation
- Task-oriented routing (not just alphabetical methods)
- Token cost transparency (agents can optimize)

**When They Win**: When humans need comprehensive reference (we have that too at Tier 2)

### vs LangChain/LlamaIndex Wrappers

**edgar.ai**: Direct API access with Skills
**Competitors**: Framework abstraction layers

**Our Advantage**:
- Zero abstraction overhead
- No framework lock-in
- Agents write pure Python (not framework-specific code)

**When They Win**: When orchestration framework needed (we focus on data access)

---

## Visual Identity Concepts

### Color Palette Ideas

**Primary**: Deep blue (SEC official, trust, authority)
**Secondary**: Bright green (growth, financial data)
**Accent**: Gold (value, insights, intelligence)

### Logo Concepts

1. **Interconnected nodes** - representing parallel pathways (Skills + MCP)
2. **Layered document** - representing progressive disclosure
3. **Code + document merge** - representing Skills approach
4. **Rising graph line** - representing financial analysis + AI

### Tagline Options

- "AI-Native SEC Data Analysis"
- "Context-Oriented Programming for Finance"
- "Skills That Teach. Code That Composes."
- "From Filings to Insights, Instantly"
- "SEC Data, AI-Ready"

---

## Launch Strategy

### Phase 1: Soft Launch (Internal + Early Adopters)

**Audiences**: EdgarTools community, AI enthusiast developers
**Channels**: GitHub, EdgarTools docs, developer Slack/Discord
**Content**:
- Updated README.md with Skills-first messaging
- ARCHITECTURE.md explaining parallel pathways
- CONTEXT_ORIENTED_ANALYSIS.md for technical deep-dive
- Example workflows in docs

**Goal**: Gather feedback, measure Skills vs MCP adoption

### Phase 2: Technical Community Launch

**Audiences**: AI engineers, MCP developers, COP community
**Channels**: Hacker News, Reddit (r/MachineLearning, r/LangChain), Twitter/X
**Content**:
- Blog post: "Why We Built edgar.ai Skills-First"
- Architecture diagrams
- Performance benchmarks
- COP principles analysis

**Goal**: Establish thought leadership, drive GitHub stars

### Phase 3: Industry Launch

**Audiences**: Fintech developers, financial analysts, quant researchers
**Channels**: Financial tech blogs, conferences, LinkedIn
**Content**:
- Use case examples (insider trading detection, competitive analysis)
- ROI metrics (time savings, API cost reduction)
- Industry-specific skills (crowdfunding, institutional holdings)

**Goal**: Drive adoption in financial services sector

### Phase 4: Academic/Research Launch

**Audiences**: COP researchers, AI research community, academic conferences
**Channels**: Research papers, conference talks, academic Twitter
**Content**:
- Formal analysis of COP implementation
- Quantitative study: Skills vs MCP effectiveness
- Framework for domain-specific COP applications

**Goal**: Contribute to COP formalization, establish credibility

---

## Metrics for Success

### Adoption Metrics

- **Skills installations**: Number of `edgartools_skill.export()` calls
- **MCP connections**: Number of active MCP server instances
- **Skills vs MCP ratio**: Percentage using each pathway
- **GitHub stars**: Community interest indicator
- **Documentation views**: Which tier gets most traffic?

### Performance Metrics

- **Token efficiency**: Average tokens per query (Skills vs MCP)
- **Query complexity**: Average lines of code per workflow
- **Workflow success rate**: Percentage of successful multi-step analyses
- **Response times**: Latency comparison (Skills vs MCP)

### Engagement Metrics

- **Blog post views**: Thought leadership reach
- **Conference talk attendees**: Industry awareness
- **Community contributions**: External skills created (BaseSkill extensions)
- **Support questions**: Skills vs MCP confusion points

### Business Metrics (if applicable)

- **Enterprise inquiries**: Companies interested in custom skills
- **Consulting engagements**: Help with COP implementation
- **Training sessions**: Teaching Skills-first architecture
- **License upgrades**: Commercial use of edgar.ai features

---

## Next Steps

1. **Publish updated documentation**: README.md, ARCHITECTURE.md, CONTEXT_ORIENTED_ANALYSIS.md
2. **Create visual assets**: Diagrams for blog posts, conference talks
3. **Draft initial blog post**: "Why We Built edgar.ai Skills-First"
4. **Engage COP community**: Share analysis with Carlos Perez, Anthropic researchers
5. **Measure adoption**: Track Skills vs MCP usage over 3 months
6. **Iterate messaging**: Based on feedback and usage patterns
7. **Plan conference talks**: Submit to PyCon, FinTech conferences, AI events

---

*"When systems understand, description suffices."* — Context-Oriented Programming

*"edgar.ai didn't adopt COP. We discovered it by building for AI agents first."* — This Project

---

*Last Updated: 2025-01-05*
*Version: 1.0*
*For architecture details, see ARCHITECTURE.md and CONTEXT_ORIENTED_ANALYSIS.md*
