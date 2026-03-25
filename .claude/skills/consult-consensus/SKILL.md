---
name: consult-consensus
description: "Run a multi-model consensus session (GPT-5.4 + Gemini 3.1) via PAL MCP on a user-specified topic. Only trigger when the user explicitly says 'get consensus' followed by their topic. This is a manual-only skill — never trigger proactively or on behalf of the user."
allowed-tools: Read, Edit, Write, Bash(git log:*), Bash(git diff:*), Bash(mkdir:*), Bash(ls:*), Bash(date:*), Glob, Grep, mcp__pal__consensus, mcp__pal__chat, mcp__pal__listmodels
---

## Pre-computed Context

**Current system state:**
!`head -20 docs/autonomous-system/architecture.md 2>/dev/null | grep -A10 'Current State'`
**Pending milestones:**
!`grep '\- \[ \]' docs/autonomous-system/roadmap.md 2>/dev/null | head -10`
**Recent commits:**
!`git log --oneline -10 -- edgar/xbrl/standardization/ 2>/dev/null`
**Previous consensus sessions:**
!`ls docs/autonomous-system/consensus/ 2>/dev/null | tail -5`

---

# Multi-Model Consensus Session

You are running a structured consensus session that consults GPT-5.4 and Gemini 3.1 Pro via the PAL MCP `consensus` tool. The goal is to get outside perspective on the autonomous XBRL extraction system, synthesize it with your own analysis, and save the result for future reference.

This is NOT about blindly trusting what external models say. They provide brainstorming perspectives — you make the final diagnosis based on what you know about the codebase, the history, and the user's goals.

## Step 1: Collect Context

Read the current system state from these sources:

1. **Architecture**: `docs/autonomous-system/architecture.md` — current state numbers, key components, decisions
2. **Roadmap**: `docs/autonomous-system/roadmap.md` — pending milestones, recent run results, consensus history
3. **Recent changes**: `git log --oneline -10 -- edgar/xbrl/standardization/` and `git diff` if relevant
4. **User's specific concern**: If the user mentioned a specific issue, limitation, or question, that becomes the focus. If not, focus on the most impactful pending work.

Summarize what you found in 5-10 bullet points. This becomes the basis for the consultation prompt.

## Step 2: Formulate the Consultation

The user will provide the topic when they invoke the skill (e.g., "get consensus on whether LIS should be binary or continuous"). Use their topic as the anchor — don't invent a different question.

Determine the session number by checking existing files in `docs/autonomous-system/consensus/`. The next number is one higher than the highest existing session number.

Enrich the user's topic with the context you gathered in Step 1 — ground it with actual numbers, architecture details, and constraints. The user provides the *what*, you provide the *context*.

### Choose the Stance Pattern

The stance assignment shapes the kind of feedback you get. Pick the pattern that fits the question:

| Question Type | Pattern | GPT-5.4 Stance | Gemini 3.1 Stance | When to use |
|---|---|---|---|---|
| "Should we do X?" | **Dialectic** | for — "Argue what's achievable, propose concrete path" | against — "Challenge assumptions, identify gaps and risks" | Go/no-go decisions, proposals, feature additions |
| "X vs Y?" | **Champion** | neutral — "Evaluate option X as the stronger choice" | neutral — "Evaluate option Y as the stronger choice" | Comparing two approaches, tools, architectures |
| "How should we do X?" | **Exploratory** | neutral — "Propose the most practical approach" | neutral — "Propose the most robust approach" | Open-ended design questions, strategy |

Use Dialectic as the default. Switch to Champion when the user is comparing two named alternatives. Switch to Exploratory when there's no clear proposal to argue for or against.

### Preview

Show the user what you'll do before running:

```
Consensus Session NNN: [Topic]
Pattern: [Dialectic/Champion/Exploratory]

GPT-5.4: [stance] — [stance_prompt summary]
Gemini 3.1: [stance] — [stance_prompt summary]

Question:
[2-3 sentence summary]

Key context:
- [bullet 1]
- [bullet 2]
- ...

Proceed? (y/n)
```

Wait for confirmation, then proceed.

## Step 3: Run the PAL Consensus Tool

Use the `mcp__pal__consensus` tool. Set the models array based on the stance pattern chosen above.

**Dialectic example:**
```json
[
  {"model": "openai/gpt-5.4", "stance": "for", "stance_prompt": "Argue what's achievable and propose concrete improvements"},
  {"model": "google/gemini-3.1-pro-preview", "stance": "against", "stance_prompt": "Challenge assumptions, identify fundamental gaps and risks"}
]
```

**Champion example** (X vs Y):
```json
[
  {"model": "openai/gpt-5.4", "stance": "neutral", "stance_prompt": "Evaluate [Option X] as the stronger choice. Argue its merits and address its weaknesses."},
  {"model": "google/gemini-3.1-pro-preview", "stance": "neutral", "stance_prompt": "Evaluate [Option Y] as the stronger choice. Argue its merits and address its weaknesses."}
]
```

**Exploratory example:**
```json
[
  {"model": "openai/gpt-5.4", "stance": "neutral", "stance_prompt": "Propose the most practical, implementable approach. Prioritize speed and simplicity."},
  {"model": "google/gemini-3.1-pro-preview", "stance": "neutral", "stance_prompt": "Propose the most robust, future-proof approach. Prioritize correctness and scalability."}
]
```

**Relevant files** (always include):
- `/home/sangicook/projects/edgartools/docs/autonomous-system/architecture.md`
- `/home/sangicook/projects/edgartools/docs/autonomous-system/roadmap.md`

Add any other relevant files based on the topic (e.g., specific Python files if discussing implementation details).

**Step flow:**
- Step 1 (of 4): Your independent analysis — write the consultation prompt with full context
- Step 2: Process GPT-5.4's response — capture key points in findings
- Step 3: Process Gemini 3.1's response — capture key points in findings
- Step 4: Final synthesis — set `next_step_required: false`

After the consensus tool returns its synthesis, proceed to your own diagnosis.

## Step 4: Your Diagnosis

The PAL consensus tool will produce a synthesis. Now write YOUR diagnosis — the part that matters most. Structure it as:

### Agreements (what all parties converge on)
List the points where GPT-5.4, Gemini 3.1, and you agree. These are high-confidence action items.

### Disagreements + Your Resolution
Where the models disagree with each other or with you, explain why you side with one perspective. Include the reasoning, not just the conclusion.

### Action Items
Concrete next steps, ordered by priority. Each should be specific enough to implement in one session.

### What We Learned
Any new insight that should inform future work — a pattern, a risk, a constraint we hadn't considered.

## Step 5: Save the Consensus

Create a file at `docs/autonomous-system/consensus/NNN-YYYY-MM-DD-topic.md` with this structure:

```markdown
# Consensus Session NNN: [Topic]

**Date:** YYYY-MM-DD
**Pattern:** [Dialectic/Champion/Exploratory]
**Models:** GPT-5.4 ([stance]), Gemini 3.1 Pro ([stance]), Claude Opus 4.6 (moderator)
**Continuation ID:** [from PAL response]
**Trigger:** [What prompted this session — implementation, issue, eval results, etc.]

## Context
[2-3 paragraph summary of system state and the specific question]

## GPT-5.4 (For Stance)
[Key points from their response — 5-10 bullets, preserving their specific recommendations]

## Gemini 3.1 (Against Stance)
[Key points from their response — 5-10 bullets, preserving their specific concerns]

## Our Diagnosis
[Your synthesis from Step 4 — agreements, disagreements + resolutions, action items]

## Key Decisions
[Numbered list of decisions made in this session — these may be referenced by future sessions]

## Action Items
- [ ] [Specific actionable item 1]
- [ ] [Specific actionable item 2]
- ...
```

## Step 6: Update Cross-References

After saving the consensus:

1. **Update roadmap.md** — Add a row to the Consensus Sessions table:
   ```
   | NNN | YYYY-MM-DD | GPT-5.4 + Gemini 3.1 | [Topic] | [Status] |
   ```

2. **Update roadmap.md Continuation IDs** — Add the new continuation ID.

3. **If key decisions were made** — Update `architecture.md` Key Decisions section if any new persistent decisions emerged.

4. **Inform the user** — Show a summary of:
   - The consensus file location
   - 3-5 most important takeaways
   - The action items
   - The continuation ID (for resuming this thread later)

## Notes

- **Continuation IDs**: Always save these. They let us resume the conversation with the same models later, preserving full context.
- **Session numbering**: Continues from the roadmap. Sessions 001-004 already exist. Check `docs/autonomous-system/consensus/` and the roadmap for the latest number.
- **Don't over-consult**: Not every small decision needs a consensus session. Reserve this for architectural decisions, strategy shifts, or when we've genuinely hit a wall.
- **History is valuable**: The consensus docs are a decision log. Write them for future-you who needs to understand WHY a decision was made, not just WHAT was decided.
