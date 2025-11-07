---
description: "Triage GitHub issues using the Product Manager agent to classify, prioritize, and convert to structured tasks"
allowed_tools: ["Task", "Bash", "Read", "Write", "Glob", "Grep", "WebFetch"]
model: "sonnet"
---

# GitHub Issue Triage Command

Use the Product Manager agent to systematically triage GitHub issues following the **Issue-PM Integration Protocol**. This command coordinates with issue-handler and product-manager agents to classify bugs, prioritize features, and update living documents.

> **Protocol**: See `docs-internal/planning/ISSUE-PM-INTEGRATION-PROTOCOL.md`

## Usage Examples

```bash
# Triage a specific issue (standard protocol workflow)
/triage 418

# Triage multiple issues
/triage 418 417 412

# Triage all open issues (batch processing)
/triage all

# Emergency triage for critical bugs (fast-track)
/triage --emergency 408

# Triage without automatic task creation
/triage --no-tasks 418
```

## Command Implementation

I'll analyze the specified GitHub issues following the **Issue-PM Integration Protocol**:

### For Bug Reports:
1. **Issue-Handler Coordination**: Reproduction and initial assessment
2. **Product-Manager Classification**: Critical vs Normal bug severity
3. **Release Type Decision**: Point release (4.19.X) vs Minor release (4.20.0)
4. **Beads Issue Creation**: `bd create --external-ref 'gh:XXX' --priority P0/P1 --labels bug`
5. **ROADMAP.md Update**: Add to release planning section if needed

### For Feature Requests:
1. **Product-Manager Priority Scoring**: Using formula `(User Value × Urgency × Feasibility) / Effort`
2. **Roadmap Placement**: HIGH (>20), MEDIUM (10-20), LOW (5-10), DEFER (<5)
3. **Beads Issue Creation**: `bd create --external-ref 'gh:XXX' --priority P1/P2/P3 --labels feature`
4. **ROADMAP.md Update**: Add to target version section for strategic planning

### Bug Severity Classification:
**Critical Bugs** (Point Release 4.19.X - Immediate):
- Data accuracy issues in financial statements
- Core functionality blocked
- Security vulnerabilities
- Severe regressions from recent releases

**Normal Bugs** (Minor Release 4.20.0 - Scheduled):
- Limited use case impact
- Workaround available
- Not data accuracy issue
- Minor functionality impaired

## Processing Logic

```bash
# Fetch issue details
!gh issue view $1 --json number,title,body,labels,author,createdAt,updatedAt

# Use Product Manager agent for analysis
```

Let me triage the specified GitHub issues:

**Issue Numbers**: $ARGUMENTS

**Step 1: Fetch Issue Data**
```bash
issues_to_process="$ARGUMENTS"

if [ "$issues_to_process" = "all" ]; then
    echo "Fetching all open issues..."
    !gh issue list --state=open --limit=20 --json number,title,body,labels,author,createdAt
else
    echo "Fetching specific issues: $issues_to_process"
    for issue_num in $issues_to_process; do
        !gh issue view $issue_num --json number,title,body,labels,author,createdAt,updatedAt
    done
fi
```

**Step 2: Product Manager Analysis**

I'll now use the Product Manager agent following the Issue-PM Integration Protocol:

```task
Use the product-manager agent to triage GitHub issues following the Issue-PM Integration Protocol:

**Issues to analyze**: $ARGUMENTS

**IMPORTANT**: Follow the protocol documented in `docs-internal/planning/ISSUE-PM-INTEGRATION-PROTOCOL.md`

For each issue, provide:

## 1. Issue Type Classification

**If Bug Report**:
- Determine severity: CRITICAL vs NORMAL
- **CRITICAL indicators** (ANY of these):
  - ✅ Data accuracy issues in financial statements
  - ✅ Core functionality blocked (can't fetch filings, parse XBRL, etc.)
  - ✅ Security vulnerabilities
  - ✅ Severe regressions from recent releases
- **Release Type**: Point release (4.19.X) immediate OR Minor release (4.20.0) scheduled
- **Timeline**: CRITICAL = hours to 1 day | NORMAL = scheduled with features

**If Feature Request**:
- Calculate priority score using formula:
  ```
  Priority Score = (User Value × Urgency × Feasibility) / Effort

  Scales (1-5):
  - User Value: 5=Direct request, 4=Fills API gap, 3=Enhancement, 2=Nice-to-have
  - Urgency: 5=Critical, 4=Data accuracy, 3=User blocked, 2=Enhancement
  - Feasibility: 5=Clear path, 4=Minor research, 3=Moderate complexity
  - Effort: Days (XS=0.2, S=0.75, M=2, L=4, XL=7)

  Priority Thresholds:
  - Score > 20: HIGH - Do Next
  - Score 10-20: MEDIUM - Plan Soon
  - Score 5-10: LOW - Backlog
  - Score < 5: DEFER - Reconsider
  ```

## 2. Issue Tracking & Documentation

**For CRITICAL Bugs**:
- Create Beads issue: `bd create --external-ref 'gh:XXX' --priority P0 --labels bug,critical --status open`
- Add to "Pending Point Release 4.19.X" section in ROADMAP.md
- Include: Est time, impact description, timeline

**For NORMAL Bugs**:
- Create Beads issue: `bd create --external-ref 'gh:XXX' --priority P1 --labels bug --status open`
- Add to v4.20.0 section in ROADMAP.md if affects release planning

**For Feature Requests**:
- Create Beads issue: `bd create --external-ref 'gh:XXX' --priority P1/P2/P3 --labels feature`
- Add to target version section in ROADMAP.md based on priority score and strategic planning

## 3. Coordination Requirements

**For Bugs**:
- Coordinate with issue-handler agent for reproduction and root cause
- Use structured communication template from protocol
- Wait for issue-handler assessment before final classification

**For Features**:
- May coordinate with discussion-handler if from GitHub Discussion
- Assess user value from community engagement metrics

## 4. Implementation Guidance

**CRITICAL Bugs**:
- **Action**: Immediate implementation (disrupt current queue)
- **Timeline**: Within hours to 1 day maximum
- **Release**: Point release 4.19.X

**NORMAL Bugs**:
- **Action**: Add to implementation queue
- **Timeline**: Batched with next minor release features
- **Release**: Minor release 4.20.0

**HIGH Priority Features** (Score > 20):
- **Action**: Add to "Starting Next Week" section
- **Timeline**: Plan for next minor release or dedicated release

**MEDIUM/LOW Features**:
- **Action**: Add to queued or backlog
- **Timeline**: Future releases based on capacity

## 5. GitHub Response

Provide recommended response for each issue based on classification.

Context: EdgarTools mission - "Simple yet powerful, accurate financials, beginner-friendly, joyful UX, beautiful output"
```

**Step 3: Create Beads Issue**

After product-manager classification, create Beads issue for tracking:

```bash
# Critical bug
bd create --external-ref 'gh:XXX' --priority P0 --labels bug,critical --status open --title "Bug: Description"

# Normal bug
bd create --external-ref 'gh:XXX' --priority P1 --labels bug --status open --title "Bug: Description"

# Feature request
bd create --external-ref 'gh:XXX' --priority P1 --labels feature --status open --title "Feature: Description"

# Update ROADMAP.md if affects release planning
```

**Step 4: Detailed Planning (Optional)**

For complex tasks, optionally create detailed markdown plan in `docs-internal/planning/` for:
- Architectural decisions
- Multi-step implementation plans
- Design documentation

**Step 5: GitHub Response**

Provide recommended responses based on triage:
- **CRITICAL Bugs**: "Classified as P0 EMERGENCY. Point release 4.19.X scheduled within [timeline]"
- **NORMAL Bugs**: "Confirmed bug. Scheduled for v4.20.0 (target: [date])"
- **HIGH Priority Features**: "Feature prioritized HIGH (score: X). Scheduled for v4.X.0"
- **MEDIUM/LOW Features**: "Feature added to backlog. Community contributions welcome!"

## Configuration Options

The command supports several flags:

- `--emergency`: Fast-track CRITICAL bugs (bypass standard workflow for speed)
- `--no-tasks`: Skip automatic task creation, provide analysis and document updates only
- `--dry-run`: Show what would be updated without modifying living documents
- `--respond`: Automatically post initial response to GitHub issues

## Integration with Issue-PM Protocol

This command implements the protocol workflow:

```
GitHub Issue
    ↓
/triage command
    ↓
Product-Manager Classification
    ↓
Decision Tree:
    ├─ Critical Bug → Point Release 4.19.X (immediate)
    ├─ Normal Bug → Minor Release 4.20.0 (scheduled)
    └─ Feature Request → Priority scored → Roadmap placement
    ↓
Beads Issue Created:
    - bd create --external-ref 'gh:XXX' --priority P0/P1/P2
    - Fast, scalable tracking
    ↓
Documentation Updated (if needed):
    - ROADMAP.md (strategic planning)
```

## Tracking System

This command uses a **hybrid approach**:

**Beads (Issue Tracking)**:
- **Fast**: `bd list --status open` shows current work instantly
- **Scalable**: Handles 100s of issues without performance issues
- **Queryable**: Filter by priority, labels, status
- **GitHub-linked**: External refs connect to GitHub issues

**Markdown (Strategic Planning)**:
- **`ROADMAP.md`**: Version-mapped feature timeline and release planning
- **`ISSUE-PM-INTEGRATION-PROTOCOL.md`**: Workflow documentation

## Success Metrics

Protocol validation with Issue #457 achieved:
- Classification time: < 30 minutes (target: < 2 hours)
- Correct severity identification: 100% (1/1)
- Living document updates: Immediate
- Timeline adherence: 1h 45m (target: 2 hours)

This command maintains those standards.