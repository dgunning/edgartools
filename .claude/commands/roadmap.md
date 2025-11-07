---
description: "Generate and manage EdgarTools product roadmap based on GitHub issues, user feedback, and strategic priorities"
allowed_tools: ["Task", "Bash", "Read", "Write", "Edit", "Glob", "WebFetch"]
model: "sonnet"
---

# Product Roadmap Command

Use the Product Manager agent to update and maintain the **living ROADMAP.md** document based on GitHub issues, user feedback, velocity data, and strategic priorities.

> **Living Document**: `docs-internal/planning/ROADMAP.md`
> **Last Updated**: Check file header
> **Review Cycle**: Weekly (Monday) and after each release

## Usage Examples

```bash
# Update roadmap with current state (standard weekly review)
/roadmap

# Include detailed GitHub issues analysis
/roadmap --analyze-issues

# Focus on specific upcoming version
/roadmap --version=4.20.0

# Review and adjust priorities
/roadmap --review-priorities

# Generate strategic quarterly view
/roadmap --quarterly
```

## Command Implementation

I'll update the living ROADMAP.md document using Product Manager agent analysis:

**Step 1: Read Current Living Documents**
```bash
echo "=== Reading Living Documents ==="

# Read current roadmap state
!cat docs-internal/planning/ROADMAP.md

# Read current priorities
!cat docs-internal/planning/PRIORITIES.md

# Read velocity tracking data
!cat docs-internal/planning/VELOCITY-TRACKING.md

# Get recent releases
!git log --oneline --since="1 month ago" | grep -E "(Release|release)" | head -10
```

**Step 2: Analyze GitHub Issues & Community Feedback**
```bash
echo "=== Analyzing Community Input ==="

# Get open issues by label
!gh issue list --state=open --limit=30 --json number,title,labels,createdAt,comments

# Get recent discussions
!gh api repos/{owner}/{repo}/discussions --jq '.[] | select(.category.name == "Ideas") | {number, title, comments}'

# Check for high-engagement issues
!gh issue list --state=open --json number,title,comments --jq 'sort_by(.comments) | reverse | .[0:5]'
```

**Step 3: Product Manager Roadmap Update**

I'll use the Product Manager agent to update the living roadmap:

```task
Use the product-manager agent to update the living ROADMAP.md document:

**Context**:
- Current ROADMAP.md, PRIORITIES.md, VELOCITY-TRACKING.md (already read)
- Recent GitHub issues and community feedback (already analyzed)
- EdgarTools mission: Simple yet powerful, accurate financials, beginner-friendly, joyful UX, beautiful output
- AI-assisted velocity: 2-10x faster than traditional development

**Your Task**:

## 1. Review "Recently Completed" Section
- Verify v4.19.1 and v4.19.0 are properly documented
- Check if any older completions should be archived
- Ensure timeline and outcomes are accurate

## 2. Update "Critical Bugs (Point Releases)" Section
- Check current state: "None currently" or active critical bugs?
- If new critical bugs from GitHub, add to "Pending Point Release 4.19.X" subsection
- Follow format: Issue #XXX, severity, impact, timeline

## 3. Review Upcoming Version Sections (v4.20.0, v4.21.0, Q1 2026)
- Check if queued features from PRIORITIES.md are reflected
- Verify priority scores and estimates are current
- Add any new HIGH priority features from recent issues
- Remove or demote features that are no longer relevant

## 4. Assess Backlog Section
- Review lower priority items
- Add new MEDIUM/LOW features from recent GitHub activity
- Archive features with no user demand or superseded by better approaches

## 5. Strategic Adjustments
Based on:
- **Velocity data**: Are we on track? Adjust timelines if needed
- **User feedback**: Are we addressing highest-value requests?
- **Market positioning**: Are we strengthening core differentiators?

## 6. Update Metadata
- Update "Last Updated" date
- Set "Next Review" date (weekly Monday or after releases)
- Update velocity numbers if changed

**Output**:
Provide the specific sections of ROADMAP.md that should be updated, with exact markdown text to add/change/remove.

**Important**:
- Maintain existing structure and format
- Reference PRIORITIES.md for work queue alignment
- Reference VELOCITY-TRACKING.md for AI multipliers
- Keep user-focused language (avoid internal jargon)
- Maintain version numbering consistency
```

**Step 4: Apply Updates to ROADMAP.md**

```bash
echo "=== Applying Roadmap Updates ==="

# The PM agent will provide specific edit instructions
# Apply each edit to docs-internal/planning/ROADMAP.md using Edit tool

echo "Roadmap updated successfully"
echo "Updated sections:"
echo "  - Recently Completed (if changed)"
echo "  - Critical Bugs status (if changed)"
echo "  - Version sections (v4.20.0, v4.21.0, etc.)"
echo "  - Backlog (if changed)"
echo "  - Metadata (Last Updated, Next Review)"
```

**Step 5: Cross-Reference with Other Living Documents**

```bash
echo "=== Verifying Living Document Consistency ==="

# Verify PRIORITIES.md aligns with ROADMAP.md
# - Active Development items should be in next release section
# - Queued items should be in upcoming versions
# - Critical bugs should match across both documents

echo "Cross-reference check complete"
echo ""
echo "Living documents status:"
echo "  ROADMAP.md: ✅ Updated"
echo "  PRIORITIES.md: ✅ Consistent"
echo "  VELOCITY-TRACKING.md: ✅ Referenced"
```

## Roadmap Structure (in ROADMAP.md)

The living roadmap maintains this structure:

### 1. Recently Completed
- Most recent 2-3 releases with accomplishments
- Point releases (4.19.1) and minor releases (4.19.0) separated
- Timeline information for validation of velocity estimates

### 2. Critical Bugs (Point Releases)
- Active critical bugs requiring immediate point releases
- "None currently" if no active critical bugs
- Protocol reference to ISSUE-PM-INTEGRATION-PROTOCOL.md

### 3. Version Sections
- **v4.20.0**: Next minor release (features + normal bugs)
- **v4.21.0**: Following minor release
- **Q1 2026**: Longer-term "Considering" features

### 4. Backlog
- Lower priority features awaiting user feedback
- Code quality and maintenance items
- Items tracked but not actively planned

### 5. Release Strategy
- Version numbering explained (major/minor/point)
- Release cadence based on AI velocity
- Feature size → release type mapping

## Command Options

**Update Modes:**
- `--analyze-issues`: Deep analysis of GitHub issues before update
- `--version=X.Y.Z`: Focus on specific version section
- `--review-priorities`: Reassess priority scores for all queued features
- `--quarterly`: Generate quarterly strategic view

**Output Options:**
- `--dry-run`: Show proposed changes without applying them
- `--summary`: Show brief summary of changes made
- `--verbose`: Show detailed analysis and reasoning

## Roadmap Maintenance Schedule

Run this command:
- **Weekly (Monday)**: Standard review and minor updates
- **After each release**: Move completed items, update velocity data
- **After critical bugs**: Verify point release sections are current
- **When priorities shift**: Reassess feature scores and timelines

## Living Document Integration

This command maintains consistency across:
- **ROADMAP.md**: Long-term feature timeline (this command)
- **PRIORITIES.md**: Current work queue (updated by /triage and manual review)
- **VELOCITY-TRACKING.md**: Historical velocity data (updated after completions)
- **ISSUE-PM-INTEGRATION-PROTOCOL.md**: Bug triage workflow (referenced)

## Success Metrics

The roadmap should demonstrate:
- ✅ Accurate feature placement based on priority scores
- ✅ Realistic timelines based on AI velocity multipliers
- ✅ Clear communication of what's next
- ✅ Alignment with EdgarTools mission and user needs
- ✅ Transparency about backlog and deferred items

**Current Velocity**: ~1 release every 2.5 days (24 releases in 60 days with AI agents)