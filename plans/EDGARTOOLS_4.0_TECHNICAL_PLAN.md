# EdgarTools 4.0 Technical Release Plan

## Executive Summary

EdgarTools 4.0 represents a significant milestone with two primary objectives:

1. **XBRL to XBRL2 Transition**: Complete migration from the legacy XBRL implementation to the new XBRL2 architecture
2. **Technical Debt Reduction**: Eliminate duplicate code, remove unnecessary functionality, and improve overall code quality

This document outlines the technical approach, implementation strategy, and release plan.

## 1. XBRL to XBRL2 Transition

### Current Status

The codebase currently maintains two XBRL implementations:
- Legacy implementation in `edgar/xbrl/`
- New implementation in `edgar/xbrl2/`

Based on repository analysis, XBRL2 appears to be functionally complete but not yet the default implementation.

### Transition Plan

#### Phase 1: Feature Parity Verification
- Complete test coverage comparison between XBRL and XBRL2
- Identify and implement any missing XBRL2 functionality
- Document any API differences between implementations

#### Phase 2: API Compatibility Layer
- Create compatibility layer for breaking changes
- Implement deprecation warnings for legacy XBRL functions
- Update documentation to reflect new recommended patterns

#### Phase 3: Default Implementation Switch
- Make XBRL2 the default implementation
- Update all internal code to use XBRL2
- Redirect legacy import paths to XBRL2 equivalents

#### Phase 4: Legacy Code Deprecation
- Mark legacy XBRL as deprecated
- Plan for eventual removal in future release (5.0)

### Implementation Details

1. **API Surface Analysis**
   - Catalog all public methods in both implementations
   - Document signature changes and behavior differences
   - Develop transition guide for users

2. **Performance Benchmarking**
   - Leverage existing performance tests in `tests/perf/`
   - Ensure XBRL2 meets or exceeds XBRL performance
   - Optimize critical paths if needed

3. **Documentation Updates**
   - Create migration guide for users
   - Update all examples in documentation and notebooks
   - Add specific XBRL2 feature documentation

## 2. Technical Debt Reduction

### Code Duplication Analysis

Several areas appear to have duplicate functionality:
- HTML/text processing in multiple modules
- Overlapping filing parsing logic
- Redundant HTTP client implementations

### Code Quality Issues

Based on repository structure, potential focus areas include:
- Inconsistent error handling
- Missing type annotations
- Unclear module responsibilities
- Test coverage gaps

### Implementation Plan

#### Phase 1: Static Analysis
- Run comprehensive linting (ruff)
- Complete type checking with pyright
- Generate code quality metrics

#### Phase 2: Modularization
- Consolidate duplicate functionality
- Clearly define module boundaries
- Enforce dependency direction

#### Phase 3: Code Removal
- Identify and remove dead code
- Remove deprecated functionality
- Consolidate overlapping implementations

#### Phase 4: Documentation & Tests
- Ensure test coverage for refactored code
- Update documentation to reflect changes
- Add clearer docstrings to key functions

### Target Areas

1. **HTTP Client Consolidation**
   - Standardize on a single HTTP client approach
   - Implement proper error handling and retries
   - Consolidate caching strategy

2. **Filing Parsing Streamlining**
   - Remove duplicate parsing logic
   - Create unified parser architecture
   - Improve error recovery for malformed filings

3. **HTML/Text Processing**
   - Consolidate HTML parsing functions
   - Standardize text extraction approach
   - Improve table recognition and handling

4. **Storage and Caching**
   - Review and optimize local storage implementation
   - Consolidate caching strategies
   - Improve serialization/deserialization

## Release Strategy

### Timeline

1. **Development Phase (2-3 months)**
   - Complete XBRL2 feature parity
   - Implement technical debt reduction
   - Internal testing and benchmarking

2. **Alpha Release (2-4 weeks)**
   - Limited release to select users
   - Focus on API compatibility
   - Performance testing in real-world scenarios

3. **Beta Release (2-4 weeks)**
   - Public beta with deprecation warnings
   - Documentation for migration
   - Collect feedback on breaking changes

4. **Release Candidate (1-2 weeks)**
   - Final testing and bug fixes
   - Complete documentation updates
   - Finalize migration guide

5. **General Availability**
   - Release final 4.0 version
   - Announce deprecation timeline for legacy XBRL

### Backward Compatibility

1. **Compatibility Guarantees**
   - Maintain backward compatibility for primary APIs
   - Provide clear migration path for breaking changes
   - Include deprecation warnings for future removals

2. **Breaking Changes**
   - Document all breaking changes thoroughly
   - Provide utility functions to ease migration
   - Version-specific documentation

### Testing Strategy

1. **Automated Testing**
   - Maintain and expand test suite
   - Ensure all refactored code has tests
   - Add performance tests for critical paths

2. **Integration Testing**
   - Test with real-world data
   - Focus on edge cases from production
   - Verify compatibility with common use patterns

3. **User Acceptance Testing**
   - Engage with key users for beta testing
   - Provide preview documentation
   - Collect and integrate feedback

## Appendix: Module-by-Module Analysis

### XBRL Migration Impact

| Module | Complexity | Risk | Migration Path |
|--------|------------|------|---------------|
| `edgar/financials.py` | High | High | Update to use XBRL2 |
| `edgar/company_reports.py` | Medium | Medium | Update API calls |
| Notebooks | Medium | Medium | Update examples |
| Tests | High | Medium | Maintain both temporarily |

### Technical Debt Target Areas

| Area | Current Issues | Improvement Approach |
|------|----------------|----------------------|
| HTTP Client | Multiple implementations | Consolidate to single pattern |
| HTML Processing | Scattered functionality | Create unified module |
| Filing Parsing | Duplication | Standardize approach |
| Error Handling | Inconsistent | Implement standard patterns |
| Type Annotations | Incomplete | Add full typing |

### Code Quality Metrics Targets

- Line coverage: >90%
- Type annotation coverage: >95%
- Complexity per function: <10
- Maintainability index: >70
- Duplicate code: <5%