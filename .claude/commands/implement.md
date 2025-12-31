# Implement Plan

You are tasked with implementing a plan step-by-step, following the phases outlined in the planning document. This is Phase 3 of the Frequent Intentional Compaction (FIC) workflow.

## Initial Setup:

When this command is invoked, respond with:
```
🚀 Starting implementation (Phase 3 of FIC workflow)

I'll implement the plan phase by phase, verifying each step before proceeding.

Please provide the path to your implementation plan from Phase 2.
```

## Soft Fork Protocol (Required)
- `edgar/` is read-only; do not modify core files.
- Implement new behavior in `quant/` (e.g., `quant/core.py`, `quant/utils.py`).
- Extend core classes via inheritance (e.g., `class QuantCompany(Company)`) and use `super()`.
- Use relative imports inside `quant/` (e.g., `from .utils import TTMCalculator`).

## Implementation Process:

### 1. **Load and Review Plan**
- Read the entire plan document
- Identify all phases and their checkboxes (⬜)
- Note which phases are already complete (✅)
- Create a TodoWrite list matching the plan phases
- Understand success criteria and verification steps

### 2. **Pre-Implementation Checks**
```bash
# Ensure clean working state
git status
git diff

# Run existing tests to ensure baseline
python -m pytest quant/tests

# Check current branch
git branch --show-current
```

If not on a feature branch, suggest creating one:
```bash
git checkout -b feature/{description}
```

### 3. **Phase-by-Phase Implementation**

For each phase marked ⬜ in the plan:

#### A. Start Phase
1. Update plan to mark phase as in-progress:
   - Change `### Phase N: [Name] ⬜` to `### Phase N: [Name] 🔄`
2. Update TodoWrite to mark phase as in_progress
3. Announce what you're implementing

#### B. Implement Changes
- Follow the plan's specified changes exactly
- Use the Edit or MultiEdit tool for modifications
- Create new files with Write when needed
- Implement in the order specified in the plan

#### C. Verify Implementation
Run the verification steps from the plan:
```bash
# Run specific tests
python -m pytest tests/test_module.py::TestClass -xvs

# Check functionality
python -c "from edgar import Module; Module().test_new_feature()"

# Verify no regressions
python -m pytest tests/ -x
```

#### D. Handle Issues
If verification fails:
1. **Stop and analyze** the discrepancy
2. **Document the issue**:
   ```
   ⚠️ Issue in Phase N:
   Expected: [what plan said]
   Found: [actual situation]
   Attempting fix: [your solution]
   ```
3. **Fix and re-verify**
4. If unable to fix, ask user for guidance

#### E. Complete Phase
1. Update plan to mark phase complete:
   - Change `### Phase N: [Name] 🔄` to `### Phase N: [Name] ✅`
2. Update TodoWrite to mark phase as completed
3. Save the updated plan document
4. Brief summary of what was accomplished

### 4. **Context Management (FIC)**

**After completing each major phase:**
1. Update the plan document with progress
2. If context is getting large (>60% usage):
   ```
   📊 Context usage high. Compacting progress into plan...

   Completed:
   ✅ Phase 1: [Summary]
   ✅ Phase 2: [Summary]

   Continuing with Phase 3...
   ```
3. Consider suggesting a context reset if beneficial

### 5. **Final Verification**

After all phases complete:

```bash
# Run full test suite
python -m pytest quant/tests

# Check code quality
ruff check quant/
mypy quant/

# Verify examples work
python examples/relevant_example.py

# Build documentation
mkdocs build --strict
```

### 6. **Completion Report**

```markdown
✅ Implementation Complete!

## Summary
- All [N] phases implemented successfully
- [X] files modified
- [Y] tests added/updated
- Documentation updated

## Verification Results
- ✅ All tests passing
- ✅ Code quality checks pass
- ✅ Examples run successfully
- ✅ Documentation builds

## Changes Made
[List key files changed with brief descriptions]

## Next Steps
1. Review changes: `git diff`
2. Run final tests: `python -m pytest`
3. Create commit: `git add -A && git commit -m "feat: [description]"`
4. Create PR if needed

Plan document updated: [path to plan with all ✅]
```

## Implementation Guidelines:

### EdgarTools-Specific Patterns:

1. **Rich Output Formatting**:
   ```python
   # Use rich for beautiful console output
   from rich.console import Console
   from rich.table import Table
   console = Console()
   ```

2. **Error Handling**:
   ```python
   # Handle SEC API errors gracefully
   try:
       filing = company.get_filing()
   except EdgarException as e:
       console.print(f"[red]Error: {e}[/red]")
   ```

3. **Test Patterns**:
   ```python
   # Use fixtures for SEC data
   @pytest.fixture
   def sample_xbrl():
       return Path("tests/fixtures/xbrl/sample.xml").read_text()
   ```

### Following the Plan's Intent:

- **Trust the plan** but adapt to reality
- **Document deviations** when necessary
- **Maintain quality** - don't skip verification
- **Keep progress visible** - update plan and todos

### When Plans Don't Match Reality:

If the plan doesn't align with what you find:
1. **Stop and document** the mismatch
2. **Explain clearly** what's different
3. **Propose adjustment** if minor
4. **Ask for guidance** if major

Example:
```
⚠️ Plan Mismatch in Phase 2:
- Plan expects: Method `parse_filing()` in parser.py
- Found: Method is actually `parse_document()` in document.py
- Proceeding with actual method name
```

### Incremental Progress:

- After each phase, the code should be functional
- Tests should pass after each phase
- Documentation updates alongside code changes
- Commit opportunities at phase boundaries

## Special Considerations:

### Performance-Critical Changes:
- Benchmark before and after
- Document performance improvements
- Add performance tests

### Financial Data Changes:
- Extra verification for accuracy
- Test with multiple filing examples
- Verify GAAP compliance

### API Changes:
- Update type hints
- Maintain backward compatibility
- Update documentation examples

### Cache-Related Changes:
- Test cache hit/miss scenarios
- Verify TTL behavior
- Check memory usage

## Recovery from Issues:

If implementation gets stuck:
1. Save current progress to plan
2. Document the blocker clearly
3. Suggest options:
   - Skip to next phase
   - Research the issue
   - Get human help
   - Rollback changes

## FIC Workflow Benefits:

This implementation phase:
- **Starts with clear plan** from Phase 2
- **Tracks progress** with checkboxes
- **Allows context resets** between major phases
- **Maintains state** in the plan document
- **Enables resumption** from any checkpoint

Remember: The plan is your guide, but adapt intelligently to what you discover during implementation. Document all progress in the plan file with ✅ markers.
