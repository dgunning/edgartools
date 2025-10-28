# EdgarTools Product Roadmap

- **Last Updated**: 2025-10-28 (v4.22.0 released)
- **Next Review**: 2025-11-04

This roadmap shows planned features, enhancements, and major bug fixes for EdgarTools. For current development priorities and immediate work, see [PRIORITIES.md](PRIORITIES.md).

---

## Legend

- 🚀 **IN PROGRESS** - Currently being implemented
- 📋 **PLANNED** - Scheduled for implementation
- ✅ **DONE** - Completed and released
- 🐛 **BUG FIX** - Bug fix pending release
- 💭 **CONSIDERING** - Under evaluation, not committed

**Status Indicators**:
- `(Est: 2d)` - Estimated implementation time with AI agents
- `(v4.20.0)` - Target release version

---

## Recently Completed

### v4.22.0 (Oct 27, 2025) - AI-Native Features Release

**Theme**: Making EdgarTools the most AI-friendly SEC data library

**Major Features Shipped**:

1. **AI-Native Object Documentation** (3,450+ lines of docs)
   - `.docs` property on all major objects (Company, Filing, XBRL, Statement)
   - Rich, searchable documentation with BM25 search algorithm
   - `.text()` methods for token-efficient AI agent context
   - Progressive disclosure: minimal/standard/detailed levels
   - Markdown-KV format for optimal LLM comprehension (60.7% accuracy, 25% token savings)
   - **User Value**: Documentation always at your fingertips, optimized for both humans and AI
   - **Implementation**: ~20-25 hours (Phase 1-3 complete)

2. **AI Skills Infrastructure** (2,500+ line skill system)
   - BaseSkill abstract class for extensible skill packaging
   - SEC Filing Analysis skill with curated workflows
   - Anthropic Claude Desktop Skills format export
   - Helper functions for common analysis patterns
   - Two-tier documentation (tutorial + API reference)
   - **User Value**: Enables specialized SEC analysis packages for AI agents
   - **Ecosystem Impact**: Foundation for third-party skill development
   - **Implementation**: ~15-18 hours (complete framework)

3. **MCP Server Consolidation** (-1,544 lines duplicate code)
   - Unified `edgar/ai/mcp/` architecture (single source of truth)
   - Removed 3 duplicate MCP implementations
   - Backward-compatible deprecation stubs
   - Cleaner codebase, easier maintenance
   - **User Value**: Clearer MCP integration, single implementation to understand
   - **Technical Debt**: Major cleanup reducing maintenance burden
   - **Implementation**: ~6-8 hours (refactoring + testing)

**Bug Fixes**:
- ✅ **Issue #459**: XBRLS Pre-XBRL Filing Handling - Fixed crash when stitching includes pre-2009 filings without XBRL
  - Simple defensive None filtering in period extraction
  - Enables historical analysis back to 2001
  - **Implementation**: 1-2 hours (XS feature, on target)

- ✅ **XBRLS filter_amendments Fix**: Corrected parameter handling in statement stitching

**Documentation**:
- New comprehensive AI Integration Guide (docs/ai-integration.md)
- Updated README.md with AI-Native Integration section
- Created examples/ai/ directory with practical examples
- API documentation for .docs property and .text() methods

**Total Effort**: ~42-53 hours over 5 days (Oct 22-27)
**Breaking Changes**: None - all additive features with backward compatibility
**User Impact**: Major capability expansion for AI agent integration, zero disruption to existing workflows

**Strategic Achievement**: Positioned EdgarTools as the most learner-friendly and AI-agent-friendly SEC data library in the Python ecosystem.

---

### v4.21.3 (Oct 23, 2025) - Current Filings Module Bug Fixes

- ✅ **Current Filings Parser Fix** - Handle company names with dashes correctly
- ✅ **PyArrow Optimization** - Performance improvements for current filings data processing
- **User Impact**: More robust real-time filing monitoring
- **Implementation**: ~2-3 hours

### v4.21.2 (Oct 22, 2025) - Critical Point Release

- ✅ **Issue #466**: Fixed dimension column always showing False in XBRL statement DataFrames
  - Root cause: Key name mismatch in Issue #463 refactoring
  - Fixed in 1 hour (on target with XS estimate)
  - Un-skipped Issue #416 regression tests
  - **Timeline**: Fixed within 5 hours of classification

### v4.21.1 (Oct 21, 2025) - Technical Debt & Documentation Cleanup

- ✅ **Issue #462: 8-K Items Documentation** - Documentation enhancement for EntityFiling
  - Added comprehensive docstring to `EntityFiling.items` attribute in `edgar/entity/filings.py`
  - Documented that `items` field sources from SEC metadata, not parsed content
  - Documented legacy SGML filings (1999-2001) metadata limitations
  - Noted modern XML filings (2005+) have accurate metadata
  - Provided workaround guidance for legacy filings (reference to GitHub Issue #462)
  - **Implementation**: ~20 minutes (on target with 30 min estimate)
  - **User Value**: Clarifies common misunderstanding, prevents confusion about legacy filing data
  - **Risk**: Zero - documentation only, no code changes

- ✅ **XBRL Dead Code Cleanup** - Removed 1,988 lines of dead code
  - Deleted `edgar/xbrl/parser.py` (1,903 lines - completely unused legacy monolithic parser)
  - Deleted `edgar/xbrl/parsers/calculation.py::apply_calculation_weights()` method (~85 lines)
  - **Implementation**: ~1.5-2 hours (on target with 1-2h estimate)
  - **User Value**: Technical debt cleanup, cleaner codebase
  - **Risk**: Zero - code was never imported or executed
  - **Breaking Changes**: None - purely internal cleanup
  - **Reference**: `docs-internal/planning/dead-code/DEAD-CODE-REPORT-2025-10-20.md`

- ✅ **XBRL Linting Improvements** - Fixed 38 linting issues
  - Improved code quality in XBRL package
  - Part of cleanup work
  - **User Value**: Better code maintainability

**Total Release Time**: ~2 hours (perfect estimation!)
**Release Type**: Point release (technical debt & documentation)
**User Impact**: None - purely internal improvements
**Breaking Changes**: None
**All Tests**: 846 passing

### v4.21.0 (Oct 20, 2025) - XBRL Value Transformations & Period Selection Fixes

- ✅ **Issue #463: XBRL Value Transformations and Metadata Columns** - Major enhancement to XBRL statement handling
  - Added metadata columns (`balance`, `weight`, `preferred_sign`) to all statement DataFrames
  - Raw XBRL instance values preserved by default (no transformation during parsing)
  - Added optional `presentation=True` parameter for HTML-matching transformations
  - Removed normalization mode after proving it unnecessary
  - Simplified from three-layer to two-layer system (raw/presentation)
  - Comprehensive documentation updates
  - **Implementation**: 3 days (Oct 17-20, 2025)
  - **User Value**: Data accuracy and transparency for financial analysis

- ✅ **Issue #464: Missing Comparative Periods in 10-Q Statements** - Fixed incomplete period selection
  - Fixed COIN 10-Q Q3 2024 missing 26-34 Cash Flow values and 15-16 Income Statement values
  - Expanded duration period candidates from ~4 to 12 periods
  - Return max_periods × 3 candidates for better coverage
  - Quarterly statements now reliably show year-over-year comparative periods
  - Reduced missing values to < 20 for Cash Flow, < 30 for Income
  - **Implementation**: 2 days (Oct 17-18, 2025)
  - **User Value**: Enables quarter-over-quarter and year-over-year analysis

### v4.20.0 (Oct 15, 2025) - Data Completeness & MCP Excellence

- ✅ **FEAT-449: XBRL DataFrame Unit & Point-in-Time Support** - Enhanced XBRL DataFrame exports with comprehensive unit and temporal information
  - Added `unit` column showing measurement units (USD, shares, pure numbers, etc.)
  - Added `point_in_time` boolean column to distinguish instant facts from duration facts
  - Enables precise financial analysis and data quality validation
  - **Implementation**: 2-3 days (on target with M estimate)
  - **User Value**: Direct user request, enables unit-aware visualizations and safe quarterly calculations

- ✅ **MCP Server Token Efficiency** - Optimized financial statement display for AI agents
  - 8-12% token reduction per statement (53-73 tokens saved on average)
  - New `to_llm_string()` method for plain text, borderless output
  - AAPL statements: 607→544 tokens (10.4%), TSLA: 627→574 tokens (8.4%), COIN: 587→514 tokens (12.4%)
  - 100% numeric value preservation with no ellipsis or truncation
  - **Implementation**: 1 day (faster than S estimate)

- ✅ **MCP Tool Clarity and Focus** - Streamlined MCP server to 2 core workflow-oriented tools
  - Removed legacy tools in favor of workflow-focused approach
  - Enhanced parameter descriptions with concrete examples
  - Inline guidance for statement types, period recommendations
  - Improved LLM agent tool selection accuracy
  - **Implementation**: < 1 day (part of MCP optimization work)

### v4.19.1 (Oct 13, 2025) - Point Release

- ✅ **Issue #457: Locale Cache Failure** - Critical fix for international users
  - Automatic cache clearing for corrupted pickle files
  - One-time operation with marker file
  - Transparent to users (< 100ms)
  - **Timeline**: 1h 45m from classification to release (P0 EMERGENCY)

### v4.19.0 (Oct 13, 2025)

- ✅ **MCP Workflow Tools** - 5 workflow-oriented tools for AI assistants
- ✅ **Issue #460** - Fixed quarterly fiscal period labels showing 1 year ahead
- ✅ **Issue #457** (Initial fix) - Fixed locale-dependent date parsing for international users
- ✅ **CI/CD Improvements** - AI extras installation in GitHub Actions

---

## 🐛 Critical Bugs (Point Releases)

*Point releases (4.19.X, 4.20.X, etc.) for critical bugs affecting users*

> **Protocol**: See [ISSUE-PM-INTEGRATION-PROTOCOL.md](ISSUE-PM-INTEGRATION-PROTOCOL.md) for bug triage workflow
>
> **Point Release Triggers** (any of these):
> - Data accuracy issues in financial statements
> - Core functionality blocked
> - Security vulnerabilities
> - Severe regressions from recent releases
>
> **Timeline**: Immediate (hours to 1 day max)

### Pending Point Releases

### v4.21.2 - CRITICAL Point Release (Ready for Release)
**Status**: ✅ FIX COMPLETE - Ready for Publishing
**Trigger**: Issue #466 - CRITICAL regression in dimensional data tagging
**Date Identified**: 2025-10-21
**Date Fixed**: 2025-10-22
**Commit**: c9848f3 on main branch
**Timeline**: Fixed within 5 hours of classification (on target with 24h goal)

#### Critical Bug Fixes
- ✅ **Issue #466**: Fix dimension column always showing False in XBRL statement DataFrames
  - **Root Cause**: Key name mismatch introduced in Issue #463 refactoring (v4.21.0)
  - **Impact**: Users cannot identify dimensional line items (Revenue by Product/Geography)
  - **Data Accuracy**: Metadata field provides incorrect information for filtering/analysis
  - **Regression**: Previously working feature broken in v4.21.0 DataFrame refactoring
  - **Fix**: Changed `item.get('dimension', False)` to `item.get('is_dimension', False)`
  - **File**: edgar/xbrl/statements.py:318
  - **Implementation**: 1 hour (on target with XS estimate)
  - **Tests**: All 6 regression tests pass (Issue #416 un-skipped + Issue #466 new tests)
  - **Regression Test**: tests/issues/regression/test_issue_466_dimension_column.py

**Release Notes**:
```markdown
## [4.21.2] - 2025-10-22

### Fixed
- **Issue #466**: Fixed dimension column always showing False in XBRL statement DataFrames
  - Root cause: Key name mismatch in Issue #463 DataFrame refactoring
  - Impact: Dimensional data (Revenue by Product/Geography) now correctly tagged
  - Regression fix from v4.21.0
  - Un-skipped Issue #416 regression tests for dimensional display
```

---

## v4.23.0 (Target: Early November 2025)

**Theme**: Bug Fixes & Historical Data Completeness

### 🐛 Planned Bug Fixes

**Issue #469: 13F TXT filings fail to parse** (Est: 0.5-1.5 days)
- **Priority**: MEDIUM (P2)
- **Component**: Filing Parsers (13F)
- **Impact**: Historical 13F filings (2012-2013) return None from `.obj()`
- **Solution**: Add TXT parser for "Form 13F Information Table" section
- **User Value**: Historical data completeness, high-profile use case (Berkshire Hathaway)
- **Status**: Triaged NORMAL (Oct 23, 2025), awaiting v4.22.0 verification
- **Dependencies**: Verify issue exists in v4.22.0 (user reported on v4.9.0)

**Issue #472: SGML parser fails on UNDERWRITER tag** (Est: 1-2 hours)
- **Priority**: MEDIUM (P2)
- **Component**: SGML Parser (Filing Access)
- **Impact**: Registration statement headers cannot be parsed
- **Solution**: Add 'UNDERWRITER' to SECTION_TAGS in SubmissionFormatParser
- **User Value**: Complete SEC SGML coverage, enables IPO/offering analysis
- **Status**: Triaged NORMAL (Oct 28, 2025)

### 📋 Considering for v4.23.0

**Period Selection Refactoring: Eliminate Legacy Complexity** (Est: 4-6h)
- **Priority**: HIGH
- **Status**: DEFERRED from v4.22.0 - Not critical for AI-native focus
- Simplify `determine_periods_to_display()` from 400 lines (complexity 81) to thin wrapper
- Delete 300+ lines of legacy fallback code
- Improve XBRL package code quality score from 40/100 to 55-60/100
- **User Value**: Technical debt cleanup, easier maintenance, faster bug fixes
- **Risk**: Medium (Phase 1 - public API), Low (Phase 2)

**FEAT-444: EPS Getter Method** (Est: 4-8 hours)
- **Priority**: HIGH
- **Status**: DEFERRED from v4.22.0 - Focus on AI features first
- Add `get_eps()` method to EntityFacts
- Support both diluted (default) and basic EPS
- **User Value**: Completes standardized financial concepts API
- **Priority Score**: 80 (HIGH)

**MCP Multi-Client Documentation** (Est: 6-8 hours)
- **Priority**: MEDIUM
- **Status**: DEFERRED from v4.22.0 - MCP foundation complete
- Create comprehensive `docs/mcp-setup-guide.md` for all major MCP clients
- Document VS Code, Cursor, Windsurf, Zed, Amazon Q setup
- **User Value**: Broader MCP ecosystem adoption

**ISSUE-447: 10-Q Part-Aware Item Parsing** (Est: 6-10 hours)
- **Priority**: MEDIUM
- Fix conflation of Part I vs Part II items
- Namespaced keys: `'Part I - Item 1'` vs `'Part II - Item 1'`
- **User Value**: Correct 10-Q section access
- **Priority Score**: 34 (MEDIUM - workaround available)

**Cross-API Validation Infrastructure** (Est: 2 days)
- **Priority**: MEDIUM-HIGH
- Separate validation system (non-runtime)
- Cross-validate EntityFacts API vs XBRL parsing
- **User Value**: Builds confidence in data accuracy
- **Priority Score**: 22.5 (MEDIUM-HIGH - strategic value, not urgent)

---

## Q1 2026+ (Future Releases)

**Theme**: Advanced Features & Ecosystem Expansion

---

## Q1 2026 (Considering)

**Theme**: Performance & Advanced Features

### 💭 CONSIDERING - Pending User Feedback

**FEAT-445: Polars DataFrame Backend** (Est: 5-7 days)
- Optional `backend='polars'` parameter for DataFrame exports
- 30-50% performance improvement for large datasets
- Lower memory footprint
- **User Value**: Modern data stack positioning
- **Status**: Strategic value, optional dependency
- **Estimate**: XL feature, significant testing needed

**FEAT-001: Multi-Company Debt Comparison** (Est: 3-4 days)
- `Company.compare()` method for cross-company analysis
- Beautiful rich table + Excel export
- Quarter alignment across different fiscal calendars
- **User Value**: Professional analyst workflows
- **Status**: Need to validate user demand
- **Estimate**: Large feature, complex alignment logic

**MCP Additional Tools** (Est: 20-28 hours)
- `edgar_filing_intelligence` - Smart filing search and content extraction
- `edgar_market_monitor` - Real-time/historical monitoring
- `edgar_compare_companies` - Cross-company screening and comparison
- **User Value**: Expanded MCP capabilities for advanced workflows
- **Status**: Defer pending user demand - current 2 tools optimal for LLM agents
- **Estimate**: Large feature set, well-designed in planning docs
- **Priority Score**: 8-12 (LOW-MEDIUM)
- **Trigger**: User requests for specific tool functionality


---

## Backlog (Lower Priority)

### Features Awaiting User Feedback

**FEAT-comparative-fact-filtering** (Est: 3-4 hours)
- `is_comparative` property on facts
- Query methods: `current_period_only()`, `comparative_only()`
- **Status**: Nice-to-have for power users, defer unless requested

**10-Q Section Detection Enhancements** (Est: 8-12 hours total)
- Part-aware collection API
- Enhanced rich output
- Legacy parser migration
- **Status**: Core complete, enhancements optional

**Feature-448: Section HTML Extraction** (Est: TBD)
- Extract sections as HTML (not just text)
- **Status**: Awaiting user clarification on use case

### Code Quality & Maintenance

**Documents Package Refactoring** (Est: 8-13 hours)
- Eliminate ~450 lines of duplication
- Remove ~1,600 lines of dead code
- **Status**: Internal quality, not user-facing

**MCP UX Improvements** (Est: 14-19 hours)
- Python entry points
- Portable configuration
- **Status**: Working well, incremental improvements

---

## Release Strategy

### Version Numbering

- **Major (5.0.0)**: Breaking changes, major architecture rewrites
- **Minor (4.20.0, 4.21.0)**: New features, enhancements, non-critical bugs
- **Point (4.19.1, 4.19.2)**: Critical bugs, data accuracy fixes, regressions

### Release Cadence

**Current Velocity**: ~1 release every 2.5 days (with AI agents)

**Typical Patterns**:
- Point releases: As needed (within hours/days of critical bug)
- Minor releases: Every 1-2 weeks (batched features)
- Major releases: 6-12 months (rare, requires RFC)

### Feature → Release Mapping

| Feature Size | Typical Implementation | Release Type |
|--------------|----------------------|--------------|
| XS (1-2h) | Same day | Next minor |
| S (4-12h) | 1-2 days | Next minor |
| M (1-3d) | Own minor release | Dedicated 4.X.0 |
| L (3-5d) | Own minor release | Dedicated 4.X.0 |
| XL (5-10d) | Own minor release + blog post | Major 4.X.0 |

---

## Issue Handling Integration

> **Status**: ✅ Phase 2 Complete
> **Protocol**: See [ISSUE-PM-INTEGRATION-PROTOCOL.md](ISSUE-PM-INTEGRATION-PROTOCOL.md) for detailed workflow

### GitHub Issues → Roadmap Flow

```
GitHub Issue Created
     ↓
Issue-Handler (reproduce & assess severity)
     ↓
Product-Manager (classify & schedule)
     ↓
Decision:
  - Critical Bug → Point Release 4.19.1 (immediate)
  - Normal Bug → Next Minor 4.20.0 (scheduled)
  - Feature Request → Priority scored → Roadmap
```

### Key Changes from Phase 2

**Before**:
- Issue-handler: Issue → Implementation → PR → Merge
- No PM coordination
- No bug severity classification
- All bugs bundled with features

**After**:
- Issue-handler coordinates with PM before implementation
- PM classifies bug severity (critical vs normal)
- Critical bugs trigger immediate point releases
- Normal bugs batched with features
- Feature requests get priority scores

**Implementation**: Ready for use with next GitHub issue

---

## Communication

### Internal
- Product Manager reviews this weekly
- Updated after each release
- Reflects actual development priorities

### External
- Consider making public in `docs/` for user visibility?
- Users love knowing what's coming!
- Could reduce "when will X be available?" questions

---

## Notes

- Estimates based on AI-assisted development velocity (3-10x faster than traditional)
- See [VELOCITY-TRACKING.md](VELOCITY-TRACKING.md) for historical data
- See [ESTIMATION-GUIDE.md](ESTIMATION-GUIDE.md) for estimation methodology
- All estimates subject to change based on actual complexity
- Critical bugs can disrupt planned schedule

**Last Major Update**: 2025-10-13 (Initial roadmap creation)
