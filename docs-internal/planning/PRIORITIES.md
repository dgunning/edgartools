# Current Development Priorities

- **Last Updated**: 2025-10-28
- **Next Review**: 2025-11-04

This document tracks **immediate development priorities** and the work queue for the next 2-4 weeks. For longer-term planning, see [ROADMAP.md](ROADMAP.md).

---

## 🚀 Active Development (This Week)

**Recently Completed: v4.22.0** - AI-Native Features Release (Oct 27, 2025)

Recent releases:
- ✅ v4.22.0 (Oct 27): AI-Native Features - .docs property, AI Skills infrastructure, MCP consolidation, Issue #459 fix
- ✅ v4.21.3 (Oct 23): Current filings module bug fixes & PyArrow optimization
- ✅ v4.21.2 (Oct 22): Issue #466 critical fix (dimension column regression)
- ✅ v4.21.1 (Oct 21): Issue #462 Documentation + XBRL Dead Code Cleanup (1,988 lines removed)
- ✅ v4.21.0 (Oct 20): Issue #463 + Issue #464 - Complete fixes with two-layer value system

**Current Focus**: Planning v4.23.0 - Bug fixes & normal priority enhancements
**Target Releases**:
- v4.23.0 (Early November 2025) - Issue #469 (13F TXT parsing), normal bug fixes, potential feature enhancements

---

## 🎯 Planned for Next Release (v4.23.0)

**Target Date**: Early November 2025 (within 1-2 weeks post-v4.22.0)

### 1. Issue #469: 13F TXT filings fail to parse

**Priority**: MEDIUM (P2)
**Estimate**: 0.5-1.5 days (Size: S)
**Target Release**: v4.23.0
**Status**: Triaged NORMAL (Oct 23, 2025)

**Rationale**:
- Historical 13F filings (2012-2013 era) lack XML attachments
- Affects high-profile use case (Berkshire Hathaway analysis)
- Workaround available (use post-2013 XML-based filings)
- Completeness enhancement, not blocking current functionality

**Implementation**:
- Add TXT parser for "Form 13F Information Table" section
- Handle pre-XML 13F format gracefully
- Files affected: `edgar/thirteenf.py`, possibly `files/html.py`

**Priority Score**: ~40 (MEDIUM)
```python
User Value:     4 (Historical data completeness, high-profile use case)
Urgency:        2 (Enhancement, workaround available)
Feasibility:    4 (Clear path, need format analysis)
Effort:         1 day (S feature)

Score = (4 × 2 × 4) / 1 = 32
```

**Dependencies**: Verify issue exists on v4.22.0 (user reported on v4.9.0)
**Blockers**: None

---

## 📋 Queued (Next 2-4 Weeks)

### 2. Period Selection Refactoring: Eliminate Legacy Complexity (DEFERRED from v4.22.0)

**Priority**: HIGH
**Estimate**: 4-6 hours (S-M feature)
**Target Release**: v4.23.0 or later
**Status**: DEFERRED - Not critical for v4.22.0 AI-native focus

**Rationale**:
- pyscn analysis identified as #1 complexity issue (complexity 81, nesting depth 10)
- Newer system already exists in period_selector.py (complexity ~15)
- Just needs feature completion to deprecate legacy code
- Would improve XBRL package score from 40/100 → 55-60/100
- Overall project health: 80/100 → 85-87/100 (B → B+)

**Implementation**:
- **Phase 1** (3-4h): Add missing features to period_selector.py
  - Add `period_view` parameter support (port from legacy lines 221-290)
  - Add `period_filter` parameter support (simple)
  - Test 33 usage sites for backward compatibility
  - Risk: Medium (public API with active usage)

- **Phase 2** (1-2h): Delete legacy fallback
  - Simplify `determine_periods_to_display()` to thin wrapper
  - Delete 300+ lines of legacy code (lines 346-700+)
  - Full regression testing
  - Risk: Low (after Phase 1 validated)

**Priority Score**: 60 (HIGH within normal features)

**Dependencies**: None
**Blockers**: None

### 3. FEAT-444: EPS Getter Method (DEFERRED from v4.22.0)

**Priority**: HIGH
**Estimate**: 4-8 hours (S feature)
**Target Release**: v4.23.0 or later
**Status**: DEFERRED - Focus on bug fixes for v4.23.0

**Rationale**:
- Quick win, completes standardized API
- High user value (EPS is most requested metric)
- Builds on existing EntityFacts infrastructure

**Implementation**:
```python
# Add to EntityFacts
def get_eps(self, diluted=True, period_offset=0):
    """Get earnings per share (diluted or basic)"""
    pass
```

**Priority Score**: 80 (HIGH)

### 4. MCP Multi-Client Documentation (DEFERRED from v4.22.0)

**Priority**: MEDIUM
**Estimate**: 6-8 hours (S feature)
**Target Release**: v4.23.0 or later
**Status**: DEFERRED - MCP foundation complete, expand docs later

**Rationale**:
- MCP foundation is production-ready (v4.19.0 + v4.20.0)
- 2 workflow tools optimal (better than planned 5)
- Missing: docs for VS Code, Cursor, Windsurf, Zed
- Strategic opportunity for broader MCP ecosystem adoption

**Current State**:
- ✅ Claude Desktop documented and working
- ✅ Python entry points (`python -m edgar.ai`, `edgartools-mcp`)
- ✅ Token optimization complete (8-12% savings)
- ⚠️ Only Claude Desktop has setup guide

**Implementation**:
- Create `docs/mcp-setup-guide.md` with all major clients
- Create `examples/mcp-configs/` with ready-to-use configs
- Add client-specific troubleshooting
- Add verification steps per client

**Priority Score**: 18 (MEDIUM - helps adoption, not blocking)
**Dependencies**: None (documentation only)
**Blockers**: None

**Note**: Additional MCP tools (filing intelligence, market monitor, company comparison) deferred to Q1 2026 pending user demand. Current 2-tool approach is working well.

### 5. ISSUE-447: 10-Q Part-Aware Item Parsing

**Priority**: MEDIUM
**Estimate**: 6-10 hours (S-M feature)
**Target Release**: v4.21.0 or v4.22.0

**Rationale**:
- Investigation complete, clear solution designed
- Workaround available (use `get_item_with_part()`)
- Improves 10-Q section access correctness
- Requires backward compatibility handling

**Implementation**:
- Namespace items by part: 'Part I - Item 1' vs 'Part II - Item 1'
- Add deprecation warnings for old behavior
- Update documentation

**Priority Score**: 34 (MEDIUM - workaround available)

### 6. Cross-API Validation Infrastructure

**Priority**: MEDIUM-HIGH
**Estimate**: 2 days (M feature)
**Target Release**: v4.22.0 (strategic, not urgent)

**Rationale**:
- Research complete (Oct 12)
- High QA value, builds data confidence
- Zero runtime impact (separate system)
- Would have caught Issue #460 automatically
- Strategic value for long-term data quality

**Implementation Phases**:
1. Core ValidationResult infrastructure
2. Fiscal metadata cross-validation
3. Period label validation
4. Investigation utilities

**Priority Score**: 22.5 (MEDIUM-HIGH - strategic value)

---

## 🐛 Bug Triage Queue

> **Integration Protocol**: See [ISSUE-PM-INTEGRATION-PROTOCOL.md](ISSUE-PM-INTEGRATION-PROTOCOL.md)
>
> **Quick Reference**:
> - Issue-handler reproduces → Coordinates with PM → PM classifies → Proceed with fix
> - Critical bugs → Point release (immediate)
> - Normal bugs → Minor release (scheduled)

### Critical Bugs (Point Release Required)

*No critical bugs pending - Issue #466 fix complete and ready for v4.21.2 release*

### Recently Completed

**Issue #466 (Oct 22, 2025) - CRITICAL Fix Ready for v4.21.2** ✅
- **Issue #466**: Dimension column always False regression - Fixed key name mismatch in statements.py:318
- **Implementation**: 1 hour (on target with XS estimate)
- **Tests**: 6 regression tests passing (Issue #416 un-skipped + Issue #466 new tests)
- **Status**: Committed to main (c9848f3), ready for v4.21.2 point release

**v4.21.1 (Oct 21, 2025) - Technical Debt & Documentation** ✅
- **Issue #462**: 8-K Items Documentation - Added comprehensive docstring clarifying SEC metadata source
- **XBRL Dead Code Cleanup**: Removed 1,988 lines of dead code (parser.py + apply_calculation_weights)
- **XBRL Linting**: Fixed 38 linting issues
- **Implementation**: ~2 hours total (Oct 21, 2025)
- **User Impact**: None - purely internal cleanup and documentation

**v4.21.0 (Oct 20, 2025) - XBRL Value Transformations** ✅
- **Issue #463**: XBRL Value Transformations and Metadata Columns - Two-layer value system (raw/presentation)
- **Issue #464**: Missing Comparative Periods in 10-Q Statements - Expanded period selection
- **Implementation**: 5 days (Oct 17-20, 2025)
- **Outcome**: Raw XBRL values preserved, metadata available, presentation mode optional

**Criteria for critical bug** (any of these triggers point release):
- Data accuracy issues in financial statements
- Core functionality blocked
- Security vulnerabilities
- Severe regressions from recent releases

**Timeline**: Immediate fix (hours to 1 day)
**Release**: Point release (4.X.1, 4.X.2, etc.)

### Normal Bugs (Next Minor Release)

**Issue #469: 13F TXT filings fail to parse** (Est: 0.5-1.5 days)
- **Type**: Filing Access Bug (Historical Format)
- **Impact**: Cannot parse older 13F filings (2012-2013 era) that lack XML attachment
- **Scope**: Pre-XML 13F filings with TXT-only "Form 13F Information Table" section
- **Priority**: MEDIUM (P2)
- **Est Time**: 0.5-1.5 days (Size: S)
- **Timeline**: Scheduled for v4.23.0
- **User Impact**: Historical institutional holdings analysis (Berkshire Hathaway use case)
- **Workaround**: Use post-2013 XML-based 13F filings or manual TXT parsing
- **Status**: Awaiting reproduction on v4.22.0 (user reported on v4.9.0)
- **Files**: `edgar/thirteenf.py`, possibly `files/html.py`

**Issue #472: SGML parser fails on UNDERWRITER tag** (Est: 1-2 hours)
- **Type**: Filing Access Bug (Parser Coverage)
- **Impact**: Cannot parse SGML headers in registration statements (S-1, S-3, etc.)
- **Scope**: Registration statements with underwriter information
- **Priority**: MEDIUM (P2)
- **Est Time**: 0.2 days (Size: XS)
- **Timeline**: Scheduled for v4.23.0
- **User Impact**: IPO/offering analysis, underwriter identification
- **Workaround**: Use other filing access methods (.obj(), .xbrl(), .document())
- **Status**: Triaged NORMAL (Oct 28, 2025)
- **Files**: `edgar/sgml/sgml_parser.py` (add to SECTION_TAGS)
- **Fix**: Add 'UNDERWRITER' to SECTION_TAGS set, verify repeatability

**Issue #447: 10-Q Part-Aware Item Parsing** (Est: 6-10h)
- **Impact**: Item conflation between Part I and Part II in 10-Q filings
- **Root Cause**: `list_items()` drops duplicates without considering Part column
- **Workaround**: Use `get_item_with_part('PART I', 'Item 1')` for explicit access
- **Fix**: Namespace items by part: 'Part I - Item 1' vs 'Part II - Item 1'
- **Priority Score**: 34 (HIGH within normal bugs, but not urgent)
- **Target**: v4.22.0
- **Status**: Investigation complete, ready for implementation when scheduled

**Criteria for normal bug**:
- Affects limited use cases
- Workaround available
- Not data accuracy issue
- Minor functionality impaired

**Timeline**: Scheduled with next features
**Release**: Minor release (4.20.0, 4.21.0, etc.)

---

## 📊 Current Status Summary

| Category | Active | Queued | Backlog |
|----------|--------|--------|---------|
| **Features** | 0 | 4 | 7 |
| **Critical Bugs** | 0 | 0 | 0 |
| **Normal Bugs** | 0 | 4 | 0 |

**Velocity**: Completed v4.21.1 (Oct 21), planning v4.22.0 for late October / early November

**v4.21.1 Achievement** (Oct 21, 2025):
- Issue #462 (8-K Items Documentation): ~20 minutes (on target with 30 min estimate)
- XBRL Dead Code Cleanup: ~1.5-2 hours (on target with 1-2h estimate)
- XBRL Linting Improvements: Included in cleanup work
- **Total**: ~2 hours for technical debt cleanup (perfect estimation!)
- **Released**: Same day completion - rapid turnaround

**v4.21.0 Achievement** (Oct 20, 2025):
- Issue #463 (XBRL Value Transformations): 3 days (two-layer value system with metadata)
- Issue #464 (Missing Comparative Periods): 2 days (expanded period selection)
- **Breaking Change**: Removed normalization mode after proving unnecessary
- **Major Enhancement**: Raw XBRL values preserved by default, presentation mode optional
- **Total**: ~5 days for 2 critical data accuracy fixes + comprehensive documentation

**v4.20.0 Achievement** (Oct 15, 2025):
- FEAT-449 (XBRL Unit & Point-in-Time): 2-3 days (on target with M estimate)
- MCP Token Efficiency: 1 day (faster than S estimate)
- MCP Tool Clarity: < 1 day (part of optimization work)
- Total: ~3-4 days for 3 features (excellent velocity!)

---

## Decision Criteria

### Priority Scoring Formula

```
Priority Score = (User Value × Urgency × Feasibility) / Effort

Where:
- User Value: 1-5 (direct request=5, nice-to-have=2)
- Urgency: 1-5 (critical=5, enhancement=2)
- Feasibility: 1-5 (clear path=5, unclear=2)
- Effort: 0.2-7 days (XS=0.2, S=0.75, M=2, L=4, XL=7)
```

### Current Priorities Scored

| Feature | User Value | Urgency | Feasibility | Effort | Score | Priority |
|---------|-----------|---------|-------------|--------|-------|----------|
| FEAT-449 | 5 | 3 | 5 | 2d | **37.5** | HIGH |
| FEAT-444 | 4 | 3 | 5 | 0.75d | **80** | HIGH |
| Cross-Val | 3 | 3 | 5 | 2d | **22.5** | MEDIUM-HIGH |

**Threshold Interpretation**:
- Score > 20: HIGH - Do Next
- Score 10-20: MEDIUM - Plan Soon
- Score 5-10: LOW - Backlog
- Score < 5: DEFER - Reconsider

---

## Process Notes

### When New Work Arrives

**Feature Requests (GitHub Issues/Discussions)**:
1. Issue-handler or discussion-handler triages
2. Product-manager evaluates & scores
3. Add to queue or backlog based on score
4. Update this document

**Critical Bugs**:
1. Issue-handler identifies severity
2. **Immediate escalation** to product-manager
3. Product-manager decides: point release or scheduled
4. If point release: disrupt queue, fix immediately

**Normal Bugs**:
1. Add to "Normal Bugs" section
2. Batch with next minor release
3. No queue disruption

### Weekly Review (Monday)

1. Review completed work from last week
2. Update queue (move items up)
3. Check GitHub for new issues/discussions
4. Recalculate priorities if needed
5. Update target dates

### After Each Release

1. Move completed items to ROADMAP (Done section)
2. Update VELOCITY-TRACKING.md with actual times
3. Promote queued items to active
4. Communicate changes

---

## Issue Handling Integration

> **STATUS**: ✅ Protocol complete - See [ISSUE-PM-INTEGRATION-PROTOCOL.md](ISSUE-PM-INTEGRATION-PROTOCOL.md)

### Integrated Flow (Phase 2 Complete)

```
GitHub Issue → Issue-Handler (triage) → Product-Manager (classify) → Decision:

If Critical Bug:
  → Add to "Critical Bugs" above
  → Point Release 4.19.1 (immediate)
  → Disrupt current queue

If Normal Bug:
  → Add to "Normal Bugs" above
  → Schedule for next minor (4.20.0)
  → No queue disruption

If Feature Request:
  → Product-Manager evaluates
  → Score using formula
  → Add to queue or backlog
  → Update ROADMAP
```

**Key Changes**:
- Issue-handler now coordinates with PM before implementation
- PM classifies bug severity (critical vs normal)
- Critical bugs trigger immediate point releases
- Normal bugs batched with features

**Implementation**: Ready for use with next GitHub issue

---

## Communication

### Internal Use
- Product Manager updates weekly
- Developers check before starting work
- Shows clear "what's next"

### Coordination with Other Agents
- **Issue-handler**: Coordinates bug triage (Phase 2)
- **Discussion-handler**: Coordinates feature requests (Phase 2)
- **Test-specialist**: Knows what features need tests
- **Docs-writer**: Knows what features need documentation

---

## Historical Note

**Created**: 2025-10-13 as part of product management velocity improvements
**Context**: Analysis showed 24 releases in 60 days (2.5 day average) with AI agents
**Purpose**: Living document to track immediate priorities and coordinate agents

This replaces ad-hoc priority decisions with systematic, data-driven approach.
