# GitHub Issue Analysis Templates

Quick-reference templates for Product Managers to systematically analyze and respond to EdgarTools GitHub issues.

## Quick Classification Checklist

```
□ Data Quality Issue (immediate priority)
□ User Experience Issue (high priority) 
□ Feature Request (evaluate against roadmap)
□ Documentation Gap (medium priority)
□ Technical Debt (low priority)
□ Support Request (immediate response needed)
```

## Current Issues Rapid Assessment

### #418: Feature Request: ETF Ticker Holdings

**Classification:** Feature Request - Core Enhancement
**Priority Score:** 80/100
**Product Fit Analysis:**
- ✅ Simple yet powerful: Extends existing fund analysis
- ✅ Accurate financials: Builds on proven 13F data
- ✅ Beginner-friendly: Can use existing API patterns
- ✅ Joyful UX: Natural extension of current workflow
- ✅ Beautiful output: Rich formatting opportunities

**Recommendation:** PROCEED - High strategic value
**Implementation Approach:**
1. Extend existing `edgar.funds` module
2. Leverage 13F filing parsing infrastructure  
3. Create ETF-specific holdings extraction
4. Add ticker-based search functionality

**User Story:**
```
As a financial analyst,
I want to search for ETF holdings by ticker symbol,
So that I can quickly analyze which ETFs hold specific stocks.
```

**Acceptance Criteria:**
- ETF holdings searchable by underlying ticker
- Holdings data includes position sizes and percentages
- Integration with existing fund analysis workflow
- Rich formatted output with tables and visualizations

---

### #417: Feature Request: ETF Series Search

**Classification:** Feature Request - Core Enhancement  
**Priority Score:** 75/100
**Product Fit Analysis:**
- ✅ Simple yet powerful: Complements ETF ticker holdings
- ✅ Accurate financials: Uses official SEC series data
- ✅ Beginner-friendly: Familiar search pattern
- ✅ Joyful UX: Improves fund discovery
- ✅ Beautiful output: Series listing with rich formatting

**Recommendation:** PROCEED - After #418 implementation
**Dependencies:** Should build on #418 infrastructure

**User Story:**
```
As a fund researcher,
I want to search for ETF series by name or partial match,
So that I can discover relevant ETFs for analysis.
```

---

### #412: How to get accurate and complete data?

**Classification:** Documentation/Support Request
**Priority Score:** 60/100
**Root Cause Analysis:**
- User uncertainty about data completeness
- Potential gaps in documentation about data sources
- Need for data quality guidance

**Recommendation:** CREATE comprehensive data accuracy guide
**Implementation:**
1. Document data source hierarchy (XBRL vs HTML vs text)
2. Explain completeness guarantees and limitations  
3. Provide data validation examples
4. Create troubleshooting guide for missing data

**Response Template:**
```
EdgarTools prioritizes data accuracy and completeness. Here's how to ensure you're getting the most reliable data:

**Data Source Hierarchy:**
1. XBRL data (most structured and reliable)
2. HTML tables (standardized but may require parsing)
3. Text extraction (fallback for unstructured data)

**Best Practices:**
- Use company.facts for historical standardized data
- Cross-reference with filing.xbrl() for detailed breakdowns
- Validate critical numbers across multiple periods

**Documentation:** [Link to comprehensive data accuracy guide]
```

---

### #411: Standardization

**Classification:** Standardization Request - Needs Clarification
**Priority Score:** 65/100  
**Analysis:** Broad request requiring detailed requirements gathering

**Immediate Response Template:**
```
Thank you for the standardization suggestion. To provide the most valuable improvements, we'd like to understand your specific needs better.

**Could you clarify:**
- Which aspects need standardization? (API methods, data formats, naming conventions)
- What inconsistencies are causing friction in your workflow?
- Are there specific examples where standardization would help?

**Our Approach:**
EdgarTools follows consistent patterns across modules, but we're always looking to improve. Your specific feedback will help us prioritize the most impactful standardization efforts.

**Next Steps:** We'll schedule a brief call to gather requirements and assess impact.
```

---

### #408: Cash flow statement is missing values

**Classification:** Data Quality Issue - Critical
**Priority Score:** 100/100
**Immediate Actions Required:**

1. **Emergency Response (24 hours):**
   - Reproduce issue with specific filing
   - Identify root cause (XBRL parsing vs data availability)
   - Implement hotfix if possible
   - Document affected filings/companies

2. **Investigation Checklist:**
   ```
   □ Reproduce with specific filing example
   □ Check XBRL source data availability  
   □ Test across multiple companies/periods
   □ Identify parsing logic gaps
   □ Validate against SEC source documents
   □ Create regression test
   ```

3. **Response Template:**
   ```
   This is a critical data quality issue. We're investigating immediately.
   
   **Immediate Actions:**
   - Issue escalated to data quality team
   - Investigation timeline: 24 hours for root cause
   - Fix implementation: 48-72 hours
   - Regression prevention: New tests added
   
   **What we need from you:**
   - Specific filing or company example
   - Expected vs. actual values
   - Your code snippet for reproduction
   
   We'll update this issue every 24 hours until resolved.
   ```

---

### #400: Discrepancy of filing information depending on how it is looked up

**Classification:** Data Quality Issue - Major
**Priority Score:** 90/100
**Root Cause Hypothesis:** Inconsistent data sources or caching issues

**Investigation Plan:**
1. Identify specific lookup methods showing discrepancies
2. Trace data source for each lookup path
3. Check for caching/synchronization issues
4. Validate against SEC source data
5. Implement consistency checks

**Response Template:**
```
Data consistency is fundamental to EdgarTools reliability. We're investigating this discrepancy immediately.

**Investigation Approach:**
1. Map all filing lookup paths in codebase
2. Identify source data differences
3. Implement consistency validation
4. Add automated testing for lookup consistency

**Timeline:** 72 hours for root cause analysis, 1 week for comprehensive fix

**Tracking:** Added to our data quality dashboard for ongoing monitoring.
```

---

### #395: CashFlowStatement doesn't contain numeric_value column

**Classification:** Data Quality Issue - Critical
**Priority Score:** 95/100  
**Technical Analysis:** Likely XBRL parsing issue with statement construction

**Immediate Debugging Steps:**
```python
# Investigation script
filing = Filing(accession_no='[example]')
xbrl = filing.xbrl()
cf_statement = xbrl.statements.cashflow_statement()

# Check raw data
print(f"Columns: {cf_statement.columns}")
print(f"XBRL facts available: {len(xbrl.facts)}")
print(f"Cash flow facts: {xbrl.query().by_statement_type('CashFlowStatement')}")
```

**Response Template:**
```
This is a critical data structure issue affecting financial statement analysis. 

**Immediate Actions:**
- Reproducing with your specific example
- Checking XBRL fact extraction logic  
- Validating statement construction process
- Testing fix across multiple filings

**Timeline:** 48 hours for fix implementation and testing

**Workaround:** While we fix this, you can access raw XBRL data via `xbrl.query().by_statement_type('CashFlowStatement')`
```

---

### #384: I need some major help please

**Classification:** User Experience Issue - Support Escalation
**Priority Score:** 85/100
**Immediate Action:** Personalized support required

**Response Template:**
```
We're here to help! EdgarTools should be intuitive and empower your financial analysis.

**Immediate Support:**
Let's schedule a brief call to understand your specific challenges and get you up and running successfully.

**Common Solutions:**
- [Link to getting started guide]
- [Link to troubleshooting documentation]
- [Code examples for common tasks]

**What helps us help you:**
- Your specific use case or goal
- Any error messages you're seeing
- Code snippet of what you're trying to accomplish

**Follow-up:** I'll personally ensure you're successful with EdgarTools.
```

---

### #381: Use local data doesn't work as expected

**Classification:** User Experience Issue - Functional
**Priority Score:** 80/100
**Technical Investigation:** Local data workflow and caching system

**Investigation Checklist:**
```
□ Test local data setup process
□ Check file path handling across OS
□ Validate caching mechanisms
□ Review documentation accuracy
□ Test offline usage scenarios  
□ Check permissions and access patterns
```

**Response Template:**
```
Local data functionality should work seamlessly. Let's get this resolved quickly.

**Immediate Debugging:**
Could you share:
- Your operating system
- Local data setup steps you followed
- Any error messages
- Code snippet showing the issue

**Common Issues:**
- File path configuration
- Cache directory permissions
- Data format expectations

**Timeline:** 48 hours for investigation and fix once we have reproduction steps.
```

---

### #387: Chunked data

**Classification:** Technical Enhancement/Performance
**Priority Score:** 45/100
**Analysis:** Performance optimization opportunity, not blocking functionality

**Evaluation Criteria:**
- Impact on user experience
- Memory usage improvements
- Processing speed gains
- Implementation complexity

**Response Template:**
```
Thank you for the performance enhancement suggestion. 

**Current Approach:**
EdgarTools prioritizes ease of use and data accuracy. We're interested in performance optimizations that don't compromise these principles.

**Evaluation Process:**
- Measuring current performance bottlenecks
- Assessing chunking implementation complexity
- Ensuring backward compatibility
- Testing across diverse filing sizes

**Timeline:** Added to our performance optimization backlog for evaluation in Q[X] planning.
```

## Implementation Quick Reference

### Priority Response Times
- **Critical (95-100):** 24 hours
- **High (80-94):** 48-72 hours  
- **Medium (60-79):** 1 week
- **Low (30-59):** 2 weeks

### Escalation Triggers
- Data accuracy issues
- User unable to complete core workflows
- Security concerns
- API breaking changes reported

### Success Metrics Tracking
- Issue resolution time by category
- User satisfaction scores  
- Feature adoption rates
- Data quality incident reduction

This template system ensures consistent, product-principle-aligned responses while maintaining the high-quality user experience that EdgarTools is known for.