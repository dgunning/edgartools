# Create Plan

You are tasked with creating a detailed implementation plan based on research findings. This is Phase 2 of the Frequent Intentional Compaction (FIC) workflow.

## Initial Setup:

When this command is invoked, respond with:
```
📋 Starting implementation planning (Phase 2 of FIC workflow)

I'll create a detailed implementation plan based on the research findings.

Please provide either:
1. The path to your research document from Phase 1, or
2. A summary of what needs to be implemented
```

## Planning Process:

### 1. **Context Gathering**
If research document exists:
- Read the research document from Phase 1
- Extract key findings and open questions
- Identify components that need modification
- **For GitHub issues**: Extract reproduction steps and root cause

If starting fresh:
- Detect if input is a GitHub issue (#NNN)
- If issue: Read the issue research or fetch with `gh issue view`
- Otherwise: Conduct quick research using the codebase-locator agent
- Identify key files and patterns
- Understand current implementation

### 2. **Analyze Requirements**
- Clarify the desired outcome
- Identify constraints and dependencies
- Consider EdgarTools principles:
  - Simple yet powerful
  - Beginner-friendly
  - Accurate financials
  - Joyful UX with rich output

### Soft Fork Protocol (Required)
- `edgar/` is read-only; do not modify core files.
- Implement new behavior in `quant/` (e.g., `quant/core.py`, `quant/utils.py`).
- Extend core classes via inheritance (e.g., `class QuantCompany(Company)`) and use `super()`.
- Use relative imports inside `quant/` (e.g., `from .utils import TTMCalculator`).

### 3. **Design Solution**
Break down the implementation into logical phases:
- Each phase should be independently testable
- Phases should build on each other
- Include verification steps for each phase
- Consider rollback strategies if needed

### 4. **Create Detailed Plan Document**

Save to: `docs-internal/planning/active-tasks/YYYY-MM-DD-{topic}-plan.md`

Structure:
```markdown
# Implementation Plan: [Feature/Fix Name]

**Date Created**: [Current date]
**Planning Phase**: 2 of 3 (FIC Workflow)
**Based on Research**: [Link to research document if exists]
**Next Phase**: Implementation (`/implement`)

## Overview
[Brief description of what will be implemented and why]

## Current State Analysis
[Summary from research phase]
- What exists today
- Key files involved
- Current limitations

## Desired End State
[Clear description of success]
- Functional requirements
- Performance requirements
- User experience goals

## Out of Scope
[What will NOT be addressed]
- Future enhancements
- Unrelated improvements
- Items for separate tasks

## Implementation Approach

### Phase 1: [Descriptive Name] ⬜
**Goal**: [What this phase accomplishes]

**Changes**:
1. `quant/module.py`:
   - [ ] Add method `new_functionality()`
   - [ ] Update class initialization
   ```python
   # Example of key change
   def new_functionality(self):
       # Implementation approach
       pass
   ```

2. `quant/tests/test_module.py`:
   - [ ] Add test for new functionality
   - [ ] Update existing tests

**Verification**:
- [ ] Run: `python -m pytest tests/test_module.py`
- [ ] Check: New functionality works with sample data
- [ ] Verify: No regression in existing features

### Phase 2: [Descriptive Name] ⬜
**Goal**: [What this phase accomplishes]

**Changes**:
[Similar structure to Phase 1]

**Verification**:
[Specific tests and checks]

### Phase 3: [Integration and Polish] ⬜
**Goal**: Complete integration and user experience

**Changes**:
1. Documentation updates
2. Example scripts
3. Performance optimization
4. Rich output formatting

**Verification**:
- [ ] All tests pass: `python -m pytest`
- [ ] Documentation builds: `mkdocs build`
- [ ] Examples run successfully
- [ ] Performance meets requirements

## Testing Strategy

### Unit Tests
- New test files needed
- Existing tests to update
- Coverage requirements

### Integration Tests
- End-to-end scenarios
- Edge cases to handle
- Performance benchmarks

### Manual Verification
- User workflows to test
- Visual output checks (rich formatting)
- Error handling scenarios

## Risk Mitigation

### Potential Issues
1. **Issue**: [Potential problem]
   **Mitigation**: [How to handle]

2. **Issue**: [Another potential problem]
   **Mitigation**: [How to handle]

### Rollback Plan
- How to revert changes if needed
- Backup strategies for critical data

## Dependencies
- External libraries required
- Internal modules affected
- Documentation updates needed

## Success Criteria
- [ ] All functional requirements met
- [ ] Tests pass with >90% coverage for new code
- [ ] Documentation complete
- [ ] No performance regression
- [ ] Clean code following EdgarTools patterns

## Estimated Effort
- Phase 1: [Time estimate]
- Phase 2: [Time estimate]
- Phase 3: [Time estimate]
- Total: [Total estimate]

## Notes for Implementation
- Key EdgarTools patterns to follow
- Specific gotchas to watch for
- Performance considerations
- Security considerations (API keys, rate limits)
```

### 5. **Review and Refine**
Before finalizing:
- Verify plan aligns with EdgarTools principles
- Check that phases are properly sized
- Ensure verification steps are comprehensive
- Confirm all dependencies are identified

### 6. **Present Plan**
```
📋 Implementation plan created: docs-internal/planning/active-tasks/YYYY-MM-DD-{topic}-plan.md

Summary:
- [X phases planned]
- [Key components to modify]
- [Estimated total effort]

The plan is ready for implementation. You can:
1. Review and adjust the plan if needed
2. Proceed with implementation: `/implement [plan-file]`
3. Get human review before proceeding

What would you like to do?

## Important Principles:

### EdgarTools-Specific Considerations:
1. **SEC Data Accuracy**: Plans involving financial data must ensure accuracy
2. **Beginner-Friendly**: APIs should be intuitive and well-documented
3. **Rich Output**: Consider how data will be displayed with rich formatting
4. **Performance**: Batch operations should be optimized
5. **Testing**: Financial data needs comprehensive test coverage
6. **Cache Strategy**: Consider caching for expensive operations

### Planning Best Practices:
- **Incremental Progress**: Each phase should provide value
- **Testability**: Every change should be verifiable
- **Documentation**: Plan documentation updates alongside code
- **Patterns**: Follow existing EdgarTools patterns
- **Error Handling**: Plan for edge cases and failures

### FIC Workflow Benefits:
- **Clean Context**: Start with fresh context after research
- **Focused Planning**: Only planning concerns in context
- **Structured Handoff**: Plan document guides implementation
- **Progress Tracking**: Checkboxes track completion

## Interactive Planning:

If the user wants to refine the plan:
1. Discuss specific concerns
2. Adjust phases as needed
3. Update verification criteria
4. Revise estimates
5. Update the plan document

The plan should be thorough enough that implementation can proceed with minimal questions.

## Plan Templates for Common Tasks:

### New SEC Filing Parser:
- Phase 1: Basic parsing structure
- Phase 2: Field extraction and validation
- Phase 3: Integration with Filing class
- Phase 4: Rich output formatting
- Phase 5: Tests and documentation

### Bug Fix:
- Phase 1: Reproduce and isolate issue
- Phase 2: Implement fix
- Phase 3: Add regression tests
- Phase 4: Verify no side effects

### Performance Optimization:
- Phase 1: Benchmark current performance
- Phase 2: Implement optimization
- Phase 3: Verify improvements
- Phase 4: Add performance tests

### API Enhancement:
- Phase 1: Extend data model
- Phase 2: Update API methods
- Phase 3: Add validation and error handling
- Phase 4: Update documentation and examples

Remember: The plan is a living document. Mark phases with ⬜ initially, and they'll be checked off ✅ during implementation.
