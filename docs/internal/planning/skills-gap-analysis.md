# Skills Architecture Gap Analysis

**Date:** 2026-01-19
**Branch:** feature/enhanced-skills-architecture
**Status:** In Progress

## Current State

### YAML Skills (6 files, ~4,130 tokens total)

| Skill | Tokens | Purpose |
|-------|-------:|---------|
| core | ~1,396 | Entry point, routing, common patterns |
| financials | ~710 | Financial statements, metrics |
| reports | ~554 | 10-K/Q/8-K sections |
| holdings | ~372 | 13F institutional holdings |
| ownership | ~639 | Form 4/3/5 insider transactions |
| xbrl | ~458 | Low-level XBRL facts access |

### Old MD Files (9 files, ~33,130 tokens total)

The YAML approach is **87% more token-efficient** than the old markdown approach.

## Covered in YAML Skills ✅

- Company lookup (find, Company)
- Filing selection (get_filings, get_current_filings, date ranges)
- Working with filings (.obj(), .xbrl(), .document())
- filing.search() for content search
- Financial statements (get_financials, statements, quick metrics)
- Report sections (TenK, TenQ, EightK items)
- 13F institutional holdings
- Form 4/3/5 insider transactions with TransactionSummary
- XBRL facts access
- str() vs to_context() guidance
- Local storage for batch processing
- view parameter (standard/detailed/summary)

## Gaps to Address

### High Priority

1. **.docs property for API discovery**
   - Source: SKILL.md, objects.md
   - Pattern: `obj.docs.search("filter")`
   - Critical for LLM self-discovery of available methods

2. **Common anti-patterns section**
   - Source: quickstart-by-task.md
   - Examples: Don't use .text() for counting, don't parse financials from text
   - Add to core skill avoid section

3. **describe_form() for form type lookup**
   - Source: form-types-reference.md
   - Maps natural language to form codes
   - `describe_form("C")` → "Offering statement (crowdfunding)"

### Medium Priority

4. **FormC crowdfunding**
   - Source: data-objects.md
   - `formc.to_context(detail='minimal|standard|full')`
   - Offering lifecycle, campaign status

5. **Error handling patterns**
   - Source: workflows.md
   - try/except, check data availability, graceful degradation

6. **Token efficiency tips**
   - Source: objects.md
   - .head(N), filter before retrieve, prefer MultiPeriodStatement

### Low Priority (Can Skip)

- **FormD private placements** - Niche use case
- **Industry filtering** - get_pharmaceutical_companies(), filter_by_industry()
- **Helper functions** - Syntactic sugar (compare_companies_revenue, etc.)
- **Configuration** - EDGAR_IDENTITY env var (one-time setup, in CLAUDE.md)
- **Troubleshooting** - Errors are self-explanatory
- **include_dimensions parameter** - to_dataframe(include_dimensions=False)

## Next Steps

1. [x] Add .docs property pattern to core skill ✓
2. [ ] ~~Expand avoid section with common anti-patterns~~ (skipped)
3. [ ] ~~Add describe_form() pattern for form type lookup~~ (skipped)
4. [ ] Consider FormC skill if crowdfunding use cases emerge
5. [ ] Consider merging back to main when stable

## Token Budget Analysis

Current total: ~4,130 tokens (6 skills)
Target: Keep under 5,000 tokens for all skills combined

Room for additions:
- ~200 tokens for .docs patterns
- ~150 tokens for anti-patterns
- ~100 tokens for describe_form()
- Total headroom: ~620 tokens before hitting 5K limit

## Related Files

- `edgar/ai/skills/core/skill.yaml` - Main entry point
- `edgar/ai/skills/*/skill.yaml` - Sub-skills
- `edgar/ai/skills/core/SKILL.md` - Old comprehensive guide (reference)
- `edgar/ai/skills/core/*.md` - Old supporting docs (reference)
