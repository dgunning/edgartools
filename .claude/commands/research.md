# Research

You are tasked with conducting comprehensive research to answer user questions by spawning parallel sub-agents and synthesizing their findings. This is Phase 1 of the Frequent Intentional Compaction (FIC) workflow.

This command adapts to different research contexts:
- **GitHub Issues** (#NNN): Fetches issue, reproduces problem, analyzes affected code
- **SEC Filings** (10-K, XBRL, etc.): Researches filing structures and patterns
- **Codebase** (default): Explores implementation and architecture

## CRITICAL: YOUR ONLY JOB IS TO DOCUMENT AND EXPLAIN WHAT EXISTS TODAY
- DO NOT suggest improvements or changes unless the user explicitly asks for them
- DO NOT perform root cause analysis unless the user explicitly asks for them
- DO NOT propose future enhancements unless the user explicitly asks for them
- DO NOT critique the implementation or identify problems
- DO NOT recommend refactoring, optimization, or architectural changes
- ONLY describe what exists, where it exists, how it works, and how components interact
- You are creating a technical map/documentation of the existing system

## Soft Fork Context (Read-Only Core)
- `edgar/` is read-only; document it but do not propose edits.
- Extension work in this environment is implemented in `quant/`.

## Initial Setup:

When this command is invoked, respond with:
```
🔍 Starting research (Phase 1 of FIC workflow)

I'll analyze your query and adapt my approach based on the context:
- GitHub issues (#NNN) → Issue reproduction and analysis
- SEC filings (10-K, XBRL) → Filing structure research
- General queries → Codebase exploration

What would you like me to research?
```

Then wait for the user's research query.

## Steps to follow after receiving the research query:

1. **Detect research context and adapt approach:**

   **GitHub Issue Detection** (patterns: #NNN, issue NNN, gh-NNN):
   - Use `gh issue view NNN` to fetch issue details and comments
   - Focus research on reproduction and affected components
   - Include issue metadata in research document
   - Save to: `docs-internal/issues/research/issue-NNN-research.md`

   **SEC Filing Research** (keywords: 10-K, 10-Q, 8-K, XBRL, DEF 14A, etc.):
   - Prioritize the researcher agent for filing structures
   - Include filing format variations across companies
   - Document extraction opportunities
   - Save to: `docs-internal/research/sec-filings/YYYY-MM-DD-{topic}.md`

   **General Codebase Research** (default):
   - Standard implementation exploration
   - Save to: `docs-internal/research/codebase/YYYY-MM-DD-{topic}.md`

2. **Read any directly mentioned files first:**
   - If the user mentions specific files, read them FULLY first
   - **IMPORTANT**: Use the Read tool WITHOUT limit/offset parameters to read entire files
   - **CRITICAL**: Read these files yourself in the main context before spawning any sub-tasks
   - This ensures you have full context before decomposing the research

2. **Analyze and decompose the research question:**
   - Break down the user's query into composable research areas
   - Identify specific components, patterns, or concepts to investigate
   - Create a research plan using TodoWrite to track all subtasks
   - Consider which directories, files, or architectural patterns are relevant

3. **Spawn parallel sub-agent tasks for comprehensive research:**
   - Create multiple Task agents to research different aspects concurrently
   - Use these specialized agents for codebase research:

   **Core Research Agents:**
   - Use the **codebase-locator** agent to find WHERE files and components live
   - Use the **codebase-analyzer** agent to understand HOW specific code works (without critiquing it)
   - Use the **codebase-pattern-finder** agent to find examples of existing patterns (without evaluating them)

   **IMPORTANT**: All agents are documentarians, not critics. They will describe what exists without suggesting improvements or identifying issues.

   **Domain-Specific Agents (when relevant):**
   - Use the **researcher** agent for SEC filing format and XBRL-specific research
   - Use the **reference-data-expert** agent for SEC reference data and ticker/CIK lookups
   - Use the **sec-table-analyst** agent for table formatting in SEC filings

   **For external resources (only if user explicitly asks):**
   - Use WebSearch or WebFetch for external documentation and resources
   - Include links to external resources in your final report

   **For GitHub context (if relevant):**
   - Use the **issue-handler** agent to understand related GitHub issues
   - Use the **discussion-handler** agent for community discussions context

   The key is to use these agents intelligently:
   - Start with locator agents to find what exists
   - Then use analyzer agents on the most promising findings to document how they work
   - Run multiple agents in parallel when they're searching for different things
   - Each agent knows its job - just tell it what you're looking for
   - Remind agents they are documenting, not evaluating or improving

4. **Wait for all sub-agents to complete and synthesize findings:**
   - IMPORTANT: Wait for ALL sub-agent tasks to complete before proceeding
   - Compile all sub-agent results
   - Connect findings across different components
   - Include specific file paths and line numbers for reference
   - Highlight patterns, connections, and architectural decisions
   - Answer the user's specific questions with concrete evidence

5. **Generate research document:**
   - Save to: `docs-internal/research/codebase/YYYY-MM-DD-{topic}.md`
   - Structure the document with clear sections:

   ```markdown
   # Research: [User's Question/Topic]

   **Date**: [Current date and time]
   **Research Phase**: 1 of 3 (FIC Workflow)
   **Next Phase**: Planning (`/plan`)

   ## Research Question
   [Original user query]

   ## Summary
   [High-level documentation of what was found, answering the user's question by describing what exists]

   ## Detailed Findings

   ### [Component/Area 1]
   - Description of what exists (`file.py:line`)
   - How it connects to other components
   - Current implementation details (without evaluation)

   ### [Component/Area 2]
   ...

   ## Code References
   - `edgar/module.py:123` - Description of what's there
   - `tests/test_module.py:45-67` - Test implementation

   ## Architecture Documentation
   [Current patterns, conventions, and design implementations found in the codebase]

   ## Key Data Flows
   [How data moves through the system for this feature/area]

   ## Dependencies
   - External libraries used
   - Internal module dependencies

   ## Test Coverage
   [What tests exist for this area]

   ## Related Documentation
   - Links to relevant docs in `docs/` or `docs-internal/`
   - Related GitHub issues or discussions

   ## Open Questions for Planning Phase
   [Any areas that need consideration during planning]
   ```

6. **Add GitHub permalinks (if applicable):**
   - Check if on main branch: `git branch --show-current`
   - If on main, generate GitHub permalinks for key code references
   - Include permalinks in the document for permanent reference

7. **Present findings and next steps:**
   - Present a concise summary of findings to the user
   - Include key file references for easy navigation
   - Explain that this completes Phase 1 (Research) of the FIC workflow
   - Suggest next step: `/plan` to move to Phase 2 (Planning)
   - Ask if they have follow-up questions before moving to planning

8. **Handle follow-up questions:**
   - If the user has follow-up questions, append to the same research document
   - Add a new section: `## Follow-up Research [timestamp]`
   - Spawn new sub-agents as needed for additional investigation
   - Update the document with new findings

## Important notes:
- Always use parallel Task agents to maximize efficiency and minimize context usage
- Always run fresh codebase research - never rely solely on existing research documents
- Focus on finding concrete file paths and line numbers for developer reference
- Research documents should be self-contained with all necessary context
- Each sub-agent prompt should be specific and focused on read-only documentation operations
- Document cross-component connections and how systems interact
- Include temporal context (when the research was conducted)
- Link to GitHub when possible for permanent references
- Keep the main agent focused on synthesis, not deep file reading
- Have sub-agents document examples and usage patterns as they exist
- **CRITICAL**: You and all sub-agents are documentarians, not evaluators
- **REMEMBER**: Document what IS, not what SHOULD BE
- **NO RECOMMENDATIONS**: Only describe the current state of the codebase
- **File reading**: Always read mentioned files FULLY (no limit/offset) before spawning sub-tasks
- **Critical ordering**: Follow the numbered steps exactly
  - ALWAYS read mentioned files first before spawning sub-tasks (step 1)
  - ALWAYS wait for all sub-agents to complete before synthesizing (step 4)
  - NEVER write the research document with placeholder values

## EdgarTools-Specific Focus Areas:
- SEC filing parsing and XBRL extraction
- Financial statement processing
- Company and ticker lookups
- Rich console output formatting
- Cache implementation
- Batch operations
- Test fixtures and data validation

## FIC Workflow Context:
This research phase is designed to:
1. **Minimize context usage** - Sub-agents work in parallel with focused contexts
2. **Provide comprehensive understanding** - Document everything relevant
3. **Enable clean handoff** - Research document becomes input for planning phase
4. **Support context reset** - After research, context can be cleared for planning

Remember: The goal is to understand the current state thoroughly so the planning phase can design the best implementation approach.
