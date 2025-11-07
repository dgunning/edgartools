Carlos E Perez 
I just spent a week deriving the formalization of Context-Oriented Programming.

What I found isn't just a new way to build AI systems.

It's a complete paradigm with axioms, a calculus, composition laws, and resource economics.

Let me show you the foundation. 🧵

Here's what seemed strange:

When Anthropic published their MCP + code execution article, they described:

* Progressive disclosure
* Context as scarce resource
* Filesystem as architecture
* Skills as reusable units

These aren't random design choices.

They're implementing a formal framework without naming it.

Axiom 1: Understanding as Primitive (UAP)

In Context-Oriented Programming:

∀ specification S, ∃ understanding U such that:
 U(S) → behavior B

Understanding is not a feature. Understanding is the atomic computational operation.

Everything else derives from this.

Traditional computing: Parse → Execute Context-Oriented: Understand → Emerge

Axiom 2: Context as Resource (CAR)

Context C is finite: |C| ≤ C_max
∀ operation O: O consumes context budget

This is profound.

Context isn't just "what the model sees."

Context is to COP what memory is to traditional computing—the fundamental scarce resource that constrains everything.

Every design decision flows from this constraint.

Axiom 3: Progressive Disclosure (PD)

∀ information I, ∃ hierarchy H = {h₁, h₂, ..., hₙ} where:
 |h₁| << |h₂| << ... << |hₙ|
 Load(hᵢ) → Decision → Load(hᵢ₊₁) | Terminate

You can't load everything upfront (violates Axiom 2).

So you build an information hierarchy:

Level 1: Index (50 tokens)
Level 2: Synopsis (200 tokens)
Level 3: Full spec (2000 tokens)
Level 4: Resources (on-demand)

This isn't a pattern. It's a mathematical necessity.

Axiom 4: Semantic Composition (SC)

∀ components C₁, C₂, ∃ composition C₁ ⊕ C₂ where:
 ⊕ is semantic (understanding-based)
 NOT syntactic (interface-based)

Traditional systems: Components must match rigid interfaces

COP systems: Components compose through understanding their purposes

This is why you don't need explicit integration code. The system understands how things fit together.

Axiom 5: Temporal Locality (TL)
∀ specialized behavior B, ∃ scope S such that:
 B is active within S
 B is automatically removed outside S
 Context_pollution(B, t > t_end) = 0

Specialized contexts have lifetimes.
They load, do their job, and self-cleanup.
This prevents context pollution—the deadly accumulation of irrelevant information that would violate Axiom 2.

These five axioms aren't arbitrary.

They form a closed mathematical system:

Axiom 1 (Understanding) enables semantic composition (Axiom 4)
Axiom 2 (Context scarcity) necessitates progressive disclosure (Axiom 3)
Axiom 3 (Progressive disclosure) requires temporal cleanup (Axiom 5)
Axiom 5 (Temporal locality) protects the resource constraint (Axiom 2)

It's self-consistent. Elegant. Inevitable.

From these axioms, a layered architecture emerges:

Layer 5: Intent (what humans want)
   ↓ semantic interpretation
Layer 4: Context (how to approach)
   ↓ orchestration
Layer 3: Execution (how to compute)
   ↓ tool invocation
Layer 2: Integration (MCP)
   ↓ system calls
Layer 1: Systems (external world)

Each layer communicates through understanding, not protocols. (Is this Abductive Coupling?)

This is why MCP + Skills + Code Execution work together—they're implementing this architecture.

Execution follows a four-phase model:

Phase 1: SEMANTIC INTERPRETATION
 (Understanding → Plan)

Phase 2: PLAN COMPOSITION
 (Compose operations, generate code)

Phase 3: DETERMINISTIC EXECUTION
 (Run code, filter data, invoke tools)

Phase 4: SEMANTIC INTEGRATION
 (Interpret results, respond)

Notice: Phases 1, 2, 4 are semantic. Only Phase 3 is deterministic.

Understanding bookends execution.

The system maintains three orthogonal state spaces:

Conversation Context (Epistemic):

What the system knows
Dialogue history
Loaded specifications

Execution Context (Deontic):

What the system can do
Tool permissions
Resource quotas

Application Context (Domain):
External world state
Databases, filesystems
Lives outside the system

These are independent dimensions that must stay synchronized.
Critical insight: Process data before it enters context.

External System (1M rows)
 ↓ Query via MCP
Execution Environment
 ↓ Filter (Status == "pending")
Filtered Data (1000 rows)
 ↓ Aggregate
Summary (10 data points)
 ↓ Load into Context
Result (200 tokens)

Data flows through execution environment. Only results enter context.

This is architectural privacy and efficiency.

COP relates to existing paradigms:

### vs. Object-Oriented:

**OOP**: Type-based polymorphism
**COP**: Semantic polymorphism

### vs. Functional:

**FP**: Function composition via types
**COP**: Context composition via understanding

### vs. Declarative:

Declarative: Specify what, not how
**COP**: Specify intent and approach
**COP** is "declarative at the semantic level"

For systems architects:
### Before (Traditional):

**Integration layer**: 500 lines of mapping code
**Orchestration**: Hardcoded workflow logic
**Configuration**: Cryptic YAML files
**Authorization**: 200 granular permissions

### After (COP):

**Integration**: Semantic description (50 lines)
**Orchestration**: Intent specification
**Configuration**: Self-documenting natural language
**Authorization**: Contextual policy (100 lines)

80% of accidental complexity disappears.

COP systems have standard structure:

- `/contexts`      # Behavioral specifications
- `/servers`       # MCP tool definitions
- `/skills`        # Learned patterns
- `/code`          # Traditional code (when needed)
- `/config`        # System configuration

This structure emerges from the axioms.
It's not arbitrary—it's the optimal information architecture for progressive disclosure.

Here's what blows my mind:

Anthropic built:

- MCP (integration layer)
- Code execution (efficiency layer)
- Skills (reusability layer)

They created the complete infrastructure for COP without calling it that.

When systems understand, description suffices.

But here's the deeper impact:

COP democratizes system architecture.

Domain experts can:

- Write contexts (behavioral specs)
- Compose workflows
- Define policies
- Create integrations
- Without writing code.

The compliance officer can write policies that enforce themselves. The business analyst can encode business rules directly.

This isn't about replacing engineers. It's about amplifying domain expertise.

Here's my prediction:

In 5 years, enterprise systems will be:
- 70% contexts and skills (COP)
- 20% traditional code (critical paths)
- 10% configuration

Most business logic will be specified in natural language following COP principles.

Code will be reserved for:

- Security-critical operations
- Performance-critical paths
- Complex algorithms requiring determinism