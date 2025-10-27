# EdgarTools Product Roadmap

- **Last Updated**: 2025-10-21 (v4.21.1 released)
- **Next Review**: 2025-10-28

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

## v4.22.0 (Target: Late October / Early November 2025)

**Theme**: AI-Native Design & API Completeness

### 📋 PLANNED - High Priority

**AI-Native Design: Universal Text Protocol & Agent Teaching System** (Est: 17-22 hours)
- Add `.text()` method to all EdgarTools objects for AI agent consumption
- Add `.info()` method to Filing (since Filing.text() returns document)
- Create `skills/sec-analysis/SKILL.md` teaching document (Anthropic Skills pattern)
- Keep existing `.to_llm_context()` methods (complementary, not replaced)
- Zero breaking changes - leverages existing `__rich__()` displays
- **User Value**: Makes EdgarTools most AI-agent-friendly SEC library
- **Status**: Clear requirements, proven patterns, 3 phases planned
- **Estimate**: Large feature (2-3 days with AI agents)
- **Priority Score**: 21.4 (HIGH)
- **Phases**:
  - Phase 1: Universal text methods (6-8h) - immediate value
  - Phase 2: SKILL.md teaching document (8-10h) - comprehensive guide
  - Phase 3: Testing & documentation (3-4h) - validation
- **Strategic Value**: Positions EdgarTools as AI-first library, complements v4.19-4.21 MCP work

**FEAT-444: EPS Getter Method** (Est: 4-8 hours)
- Add `get_eps()` method to EntityFacts
- Support both diluted (default) and basic EPS
- Intelligent fallback with warnings
- **User Value**: Completes standardized financial concepts API
- **Status**: Quick win, builds on existing infrastructure
- **Estimate**: Small feature, well-defined
- **Priority Score**: 80 (HIGH)

**Issue #459: XBRLS Pre-XBRL Filing Handling** (Est: 1-2h)
- Fix crash when stitching includes pre-2009 filings without XBRL
- Add defensive None filtering in period extraction
- **User Value**: Enables historical analysis back to 2001
- **Status**: Simple fix, clear root cause
- **Estimate**: XS feature, defensive check
- **Priority Score**: 100 (HIGH - user blocked on historical analysis)

**Period Selection Refactoring: Eliminate Legacy Complexity** (Est: 4-6h)
- **Phase 1** (3-4h): Add `period_view` and `period_filter` support to period_selector.py
  - Port `get_period_views()` logic from legacy system
  - Add parameter support to `select_periods()` function
  - Comprehensive testing of 33 usage sites
- **Phase 2** (1-2h): Delete 300+ lines of legacy fallback code from periods.py
  - Simplify `determine_periods_to_display()` to thin wrapper (~15 lines)
  - Remove legacy code (lines 346-700+) after Phase 1 validated
  - Full regression testing
- **User Value**: Code quality improvement, easier maintenance and bug fixes
- **Technical Value**: Complexity reduction (81 → ~5), XBRL package score 40/100 → 55-60/100
- **Status**: Newer system already exists, just needs feature completion
- **Estimate**: S-M feature, two-phase approach
- **Priority Score**: 60 (HIGH within normal features)
- **Risk**: Medium (Phase 1 - public API), Low (Phase 2 - after validation)
- **Dependencies**: None (newer period_selector.py already in use via fallback)
- **Rationale**: Addresses pyscn complexity analysis #1 issue (complexity 81, nesting depth 10)

**Strategic Note - MCP/AI Integration**:
- ✅ v4.19.0 delivered 2 workflow-oriented MCP tools (company research, financial analysis)
- ✅ v4.20.0 delivered token efficiency (8-12% savings) and tool clarity
- ✅ v4.21.0 delivered XBRL value transformations (raw/presentation modes)
- ✅ MCP foundation is **production-ready** - Python entry points, verification tools, optimized display
- 📋 Multi-client documentation scheduled for v4.22.0 (broader ecosystem adoption)

### 📋 PLANNED - Medium Priority

**ISSUE-447: 10-Q Part-Aware Item Parsing** (Est: 6-10 hours)
- Fix conflation of Part I vs Part II items
- Namespaced keys: `'Part I - Item 1'` vs `'Part II - Item 1'`
- Backward compatibility with deprecation warnings
- **User Value**: Correct 10-Q section access
- **Status**: Investigation complete, clear solution designed
- **Estimate**: Small-Medium feature, implementation straightforward
- **Priority Score**: 34 (MEDIUM - workaround available)

**Cross-API Validation Infrastructure** (Est: 2 days)
- Separate validation system (non-runtime)
- Cross-validate EntityFacts API vs XBRL parsing
- Fiscal metadata validation
- Period label enhanced validation
- **User Value**: Builds confidence in data accuracy
- **Status**: Research complete, clear implementation path
- **Estimate**: Medium feature, well-planned
- **Priority Score**: 22.5 (MEDIUM-HIGH - strategic value, not urgent)

---

## v4.23.0 - Next Minor Release (Target: Q4 2025 / Q1 2026)

**Theme**: Bug Fixes & Completeness

### 🐛 Bug Fixes

#### Issue #469: 13F TXT filings fail to parse
- **Component**: Filing Parsers (13F)
- **Impact**: Historical 13F filings (2012-2013) return None from `.obj()`
- **Solution**: Add TXT parser for "Form 13F Information Table" section
- **Priority**: MEDIUM (completeness enhancement)
- **Est Time**: 0.5-1.5 days
- **Value**: Historical data completeness, high-profile use case (Berkshire Hathaway)
- **Dependencies**: Verify issue exists in v4.22.0 (user on v4.9.0)

### 📋 PLANNED - Medium Priority

**MCP Multi-Client Documentation** (Est: 6-8 hours)
- Create comprehensive `docs/mcp-setup-guide.md` for all major MCP clients
- Add `examples/mcp-configs/` with ready-to-use configurations
- Document VS Code, Cursor, Windsurf, Zed, Amazon Q setup
- Client-specific troubleshooting and verification steps
- **User Value**: Broader MCP ecosystem adoption
- **Status**: MCP foundation is production-ready, expand documentation
- **Estimate**: Small feature, documentation-focused
- **Priority Score**: 18 (MEDIUM - helps adoption, not blocking)

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
