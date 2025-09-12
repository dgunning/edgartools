# GitHub Issue Triage Framework for EdgarTools

## Product Manager's Systematic Approach to Issue Management

This framework provides a structured approach for Product Managers to triage, prioritize, and convert GitHub issues into actionable development tasks while maintaining alignment with EdgarTools' core product principles.

## Core Product Principles Review

Before analyzing any issue, ensure alignment with:
- **Simple yet powerful**: Every feature must surprise users with elegance and ease of use
- **Accurate financials**: Data reliability is non-negotiable
- **Beginner-friendly**: Complexity must be hidden from new Python users
- **Joyful UX**: Eliminate frustrations and deliver polished experience
- **Beautiful output**: Leverage rich library for enhanced CLI display

## 1. Issue Classification Framework

### Primary Categories

#### A. Data Quality Issues (Critical Priority)
**Indicators**: Incorrect financial data, missing values, parsing errors
**Examples**: #408 (Cash flow missing values), #395 (Missing numeric_value column), #400 (Filing lookup discrepancies)
**Impact**: Direct threat to core principle of accurate financials
**Response Time**: 24-48 hours
**PM Action**: Immediate investigation, data integrity audit

#### B. Feature Requests - Core Enhancement (High Priority)
**Indicators**: Requests that extend existing functionality within current scope
**Examples**: #418 (ETF Ticker Holdings), #417 (ETF Series Search)
**Impact**: Adds power without complexity, expands market reach
**Response Time**: 72 hours
**PM Action**: Evaluate against product roadmap, assess technical feasibility

#### C. User Experience Issues (High Priority)
**Indicators**: Confusion, unexpected behavior, poor documentation
**Examples**: #381 (Local data not working as expected), #384 (User needs major help)
**Impact**: Violates beginner-friendly and joyful UX principles
**Response Time**: 48 hours
**PM Action**: UX audit, documentation review, user journey analysis

#### D. Standardization Requests (Medium Priority)
**Indicators**: Requests for consistent APIs, data formats, naming conventions
**Examples**: #411 (Standardization)
**Impact**: Improves elegance and ease of use
**Response Time**: 1 week
**PM Action**: Architecture review, breaking change assessment

#### E. Documentation/Support Requests (Medium Priority)
**Indicators**: How-to questions, unclear documentation
**Examples**: #412 (How to get accurate/complete data)
**Impact**: Affects beginner-friendliness
**Response Time**: 48 hours
**PM Action**: Documentation gap analysis, user education content

#### F. Technical Debt (Low Priority)
**Indicators**: Performance, refactoring, internal improvements
**Examples**: #387 (Chunked data)
**Impact**: Long-term maintainability
**Response Time**: 2 weeks
**PM Action**: Technical debt prioritization matrix

### Priority Matrix

| Category | Severity | User Impact | Development Effort | Priority Score |
|----------|----------|-------------|-------------------|----------------|
| Data Quality - Critical | 10 | 10 | Variable | 95-100 |
| Data Quality - Major | 8 | 9 | Variable | 85-90 |
| UX - Blocking | 7 | 10 | Low-Med | 80-85 |
| Feature - High Value | 6 | 8 | High | 75-80 |
| Feature - Medium Value | 5 | 6 | Medium | 60-70 |
| Standardization | 4 | 7 | High | 55-65 |
| Documentation | 3 | 8 | Low | 50-60 |
| Technical Debt | 2 | 3 | Variable | 30-50 |

## 2. PM Workflow for Issue Processing

### Phase 1: Initial Triage (Within 24 hours)

1. **Issue Classification**
   - Assign primary category using framework above
   - Tag with appropriate labels (data-quality, feature-request, ux, etc.)
   - Assess severity level (critical, high, medium, low)

2. **Impact Assessment**
   - User impact: How many users affected?
   - Product principle alignment: Which principles are impacted?
   - Technical complexity: Initial estimate (low/medium/high)
   - Breaking change risk: Does this require API changes?

3. **Stakeholder Assignment**
   - Data Quality: Assign to technical lead + PM
   - Feature Requests: PM + relevant domain expert
   - UX Issues: PM + documentation team
   - Support: Community manager + PM for escalation

### Phase 2: Deep Analysis (Within 72 hours)

1. **Requirements Gathering**
   - User story creation: "As a [user type], I want [goal] so that [benefit]"
   - Acceptance criteria definition
   - Edge case identification
   - Success metrics definition

2. **Technical Feasibility**
   - Architecture impact assessment
   - Integration complexity review
   - Performance implications
   - Testing requirements

3. **Strategic Alignment**
   - Roadmap fit assessment
   - Resource allocation impact
   - Competitive advantage evaluation
   - User segment analysis

### Phase 3: Decision & Planning (Within 1 week)

1. **Go/No-Go Decision**
   - Product fit score (1-10)
   - Development effort estimate
   - ROI calculation
   - Risk assessment

2. **Task Breakdown** (If approved)
   - Epic creation with user stories
   - Technical tasks identification
   - Testing strategy definition
   - Documentation requirements

3. **Sprint Planning Integration**
   - Sprint assignment
   - Dependency mapping
   - Resource allocation
   - Timeline estimation

## 3. Current Issues Analysis

### Immediate Action Required (Critical)

**#408: Cash flow statement missing values**
- Category: Data Quality - Critical
- Priority Score: 100
- Action: Emergency data integrity audit
- Timeline: 24 hours for initial assessment

**#395: CashFlowStatement missing numeric_value column**
- Category: Data Quality - Critical  
- Priority Score: 95
- Action: XBRL parsing investigation
- Timeline: 48 hours for fix

**#400: Filing lookup discrepancies**
- Category: Data Quality - Major
- Priority Score: 90
- Action: Filing retrieval consistency audit
- Timeline: 72 hours for root cause analysis

### High Priority Development

**#418: ETF Ticker Holdings Feature**
- Category: Feature Request - Core Enhancement
- Priority Score: 80
- Analysis: Aligns with fund analysis capabilities, extends market reach
- Requirements: ETF holdings extraction from 13F filings
- Technical Impact: Extends existing fund analysis framework
- Timeline: 2-3 sprints

**#417: ETF Series Search**
- Category: Feature Request - Core Enhancement  
- Priority Score: 75
- Analysis: Complements #418, improves fund discovery
- Requirements: Series-level ETF search functionality
- Dependencies: May depend on #418 implementation
- Timeline: 1-2 sprints after #418

### User Experience Issues

**#384: User needs major help**
- Category: UX - Support Escalation
- Priority Score: 85
- Action: Immediate user outreach, documentation audit
- Root Cause: Likely documentation gaps or API complexity
- Timeline: 48 hours for user resolution, 1 week for systemic fixes

**#381: Local data doesn't work as expected**
- Category: UX - Functional Issue
- Priority Score: 80
- Action: Local data workflow review
- Impact: Affects offline usage scenarios
- Timeline: 1 sprint for investigation and fix

### Medium Priority Items

**#411: Standardization**
- Category: Standardization Request
- Priority Score: 65
- Analysis: Broad request requiring detailed requirements gathering
- Action: User interview to understand specific needs
- Timeline: Requirements gathering phase - 2 weeks

**#412: How to get accurate/complete data**
- Category: Documentation/Education
- Priority Score: 60
- Action: Create comprehensive data accuracy guide
- Timeline: 1 sprint for documentation update

**#387: Chunked data**
- Category: Technical Enhancement
- Priority Score: 45
- Analysis: Performance optimization opportunity
- Timeline: Technical debt backlog

## 4. Integration with Task Planning Framework

### Task Conversion Process

1. **Epic Creation**
   - GitHub issue becomes Epic in task planning system
   - User stories derived from acceptance criteria
   - Technical tasks identified during planning

2. **Sprint Integration**
   - Tasks distributed across sprints based on priority
   - Dependencies mapped in task planning tool
   - Progress tracked against original GitHub issue

3. **Success Metrics Tracking**
   - Issue resolution time by category
   - User satisfaction scores
   - Feature adoption rates
   - Data quality improvement metrics

### Template Structures

#### Data Quality Issue Template
```
## Issue Analysis
- Data accuracy impact: [High/Medium/Low]
- Affected components: [List]
- User segments impacted: [Segments]

## Investigation Plan
- [ ] Reproduce issue
- [ ] Root cause analysis
- [ ] Data integrity audit
- [ ] Fix implementation
- [ ] Testing strategy
- [ ] User communication plan

## Success Criteria
- Data accuracy restored
- Regression tests added
- Documentation updated
```

#### Feature Request Template
```
## Product Fit Analysis
- Product principle alignment: [Score 1-10]
- User segment: [Primary/Secondary]
- Market opportunity: [Assessment]

## Implementation Plan
- [ ] Requirements gathering
- [ ] Technical design
- [ ] API design review
- [ ] Implementation
- [ ] Testing
- [ ] Documentation
- [ ] User feedback collection

## Success Metrics
- Feature adoption rate target: [X%]
- User satisfaction score: [X/10]
- Performance impact: [Acceptable limits]
```

## 5. Community Communication Strategy

### Response Templates by Category

#### Data Quality Issues
```
Thank you for reporting this data quality issue. EdgarTools prioritizes data accuracy above all else.

**Immediate Actions:**
- Issue escalated to our data quality team
- Investigation underway
- Timeline: [X] hours for initial assessment

**What to Expect:**
1. Root cause analysis within [X] hours
2. Fix implementation and testing
3. Release with regression prevention
4. Follow-up to ensure resolution

**Tracking:** This issue has been added to our data quality dashboard.
```

#### Feature Requests
```
Thank you for this feature suggestion! We appreciate community input on EdgarTools evolution.

**Evaluation Process:**
- Product fit assessment: [In Progress/Complete]
- Technical feasibility review: [Status]
- Roadmap integration: [Timeline]

**Decision Criteria:**
Our evaluation considers user impact, technical complexity, and alignment with our core mission of making SEC data accessible to Python developers of all skill levels.

**Next Steps:**
We'll update this issue within [X] days with our assessment and planned timeline.
```

#### User Support Issues
```
We're here to help! EdgarTools should be intuitive and joyful to use.

**Immediate Support:**
- [Specific guidance for their issue]
- [Relevant documentation links]
- [Code examples if applicable]

**Systemic Improvements:**
Your experience helps us identify areas for improvement. We're reviewing our documentation and user experience based on your feedback.

**Follow-up:** We'll check back within [X] days to ensure you're successful.
```

### Communication Cadence

- **Critical Issues**: Updates every 24 hours until resolved
- **High Priority**: Updates every 72 hours
- **Medium Priority**: Weekly updates
- **Low Priority**: Bi-weekly updates or at major milestones

### Community Health Metrics

- Average response time by issue type
- Issue resolution rate
- User satisfaction scores
- Community engagement levels
- Documentation effectiveness metrics

## 6. Success Metrics and KPIs

### Issue Management Metrics
- Time to first response: &lt;24 hours for critical, &lt;72 hours for others
- Issue resolution time by category
- Reopened issue rate: &lt;5%
- User satisfaction with support: >8/10

### Product Quality Metrics
- Data accuracy incidents: Target &lt;2 per month
- Feature adoption rate: >50% for major features within 3 months
- API consistency score: Measured via automated audits
- Documentation effectiveness: Measured via user surveys

### Community Health Metrics
- Active contributors: Growing month-over-month
- Issue participation rate: Community engagement in discussions
- Feature request quality: Detailed requirements vs. vague requests
- User success stories: Positive outcome reports

This framework ensures that EdgarTools maintains its commitment to elegance, accuracy, and user-friendliness while scaling community contributions and feature development effectively.