---
description: "Create and manage structured development tasks using the EdgarTools task planning framework"
allowed_tools: ["Read", "Write", "Edit", "Glob", "Bash", "Task"]
model: "sonnet"
---

# Task Management Command

Create, update, and manage structured development tasks using **Beads** for fast, scalable tracking. This command is a wrapper around `bd` commands with EdgarTools-specific conventions.

> **Tracking System**: Beads (`bd` commands)
> **Documentation**: ROADMAP.md (strategic planning), VELOCITY-TRACKING.md (historical analysis)
> **Integration**: Coordinates with product-manager for prioritization

## Usage Examples

```bash
# Create a new feature task
/task new feature "Multi-company financial comparison"

# Create a bug fix task from GitHub issue
/task new bug "Cash flow statement missing values" --github=408

# List active tasks
/task list

# Show task details
/task show edgartools-abc

# Mark task as complete
/task complete edgartools-abc
```

**Note**: This command is a convenience wrapper around `bd` commands. For direct Beads usage:
```bash
bd create --title "Feature: X" --status open --priority P1 --labels feature
bd list --status open
bd update ISSUE_ID --status in_progress
bd update ISSUE_ID --status done
```

## Command Implementation

This command wraps `bd` (Beads) commands with EdgarTools conventions:

### Creating New Tasks

```bash
# Map task type to labels
case $task_type in
    feature) labels="feature" ;;
    bug) labels="bug" ;;
    research) labels="research" ;;
    refactor) labels="refactor" ;;
esac

# Create in Beads with external ref if from GitHub
if [ -n "$github_issue" ]; then
    bd create --title "$task_type: $task_title" \
              --status open \
              --external-ref "gh:$github_issue" \
              --labels "$labels" \
              --priority P2
else
    bd create --title "$task_type: $task_title" \
              --status open \
              --labels "$labels" \
              --priority P2
fi

# Optionally create detailed plan markdown file for complex tasks
# (Only create if task requires architectural planning or multiple steps)
```

### Listing Tasks

```bash
# List all open tasks
bd list --status open

# Or filter by type
bd list --status open --labels feature
bd list --status open --labels bug
```

### Showing Task Details

```bash
# Show specific task
bd show $task_id
```

### Completing Tasks

```bash
# Mark task as done
bd update $task_id --status done

# Record velocity data in VELOCITY-TRACKING.md
# (Extract from Beads metadata: created date, completed date, estimate)
```

## Integration with Documentation

**Hybrid Approach - Beads for tracking, Markdown for planning:**

### Beads (Issue Tracking):
- **Creating Tasks**: `bd create` adds to Beads database (fast, scalable)
- **Tracking Progress**: `bd update` changes status (open → in_progress → done)
- **Viewing Work**: `bd list --status open` shows current work queue
- **Linking Issues**: `--external-ref 'gh:XXX'` connects to GitHub

### Markdown (Strategic Planning):
- **ROADMAP.md**: Long-term version planning and feature grouping
- **VELOCITY-TRACKING.md**: Historical velocity analysis and trends
- **Detailed Plans** (optional): Create `docs-internal/planning/` files for:
  - Complex architectural decisions
  - Multi-step implementation plans
  - Design documentation
  - Only when task requires comprehensive documentation

## Integration with Other Commands

This command works seamlessly with:
- **`/triage`**: Creates tasks from prioritized GitHub issues (HIGH priority features, CRITICAL bugs)
- **`/roadmap`**: Tasks align with version planning in ROADMAP.md
- **Product-manager agent**: Can request prioritization scoring for new tasks

## Task Lifecycle

1. **Create** → `/task new feature "Description"` creates Beads issue
2. **Prioritize** → Use `/triage` or product-manager for priority scoring (updates priority in Beads)
3. **Plan** → Create detailed markdown plan if complex (optional, architectural decisions only)
4. **Start** → `bd update ISSUE_ID --status in_progress`
5. **Develop** → Use `bd update` to track progress milestones
6. **Complete** → `bd update ISSUE_ID --status done`
7. **Record** → Update VELOCITY-TRACKING.md with actual vs estimated time

## Best Practices

**Issue Tracking (Beads):**
- Use descriptive titles: "Feature: Multi-company comparison" not "New feature"
- Update status regularly: open → in_progress → done
- Add labels for categorization: `--labels feature,xbrl-parsing`
- Link to GitHub: `--external-ref 'gh:XXX'`
- Set priority: P0 (critical), P1 (high), P2 (medium), P3 (low)

**Documentation (Markdown):**
- Create detailed plans only for complex tasks requiring architecture docs
- Use ROADMAP.md for version planning and feature grouping
- Use VELOCITY-TRACKING.md for historical analysis
- Keep task tracking in Beads, not markdown files

**Task Types (Labels):**
- **feature**: New features or enhancements
- **bug**: Bug fixes (link with `--external-ref 'gh:XXX'`)
- **research**: Research or investigation tasks
- **refactor**: Code quality improvements

## System Benefits

The Beads-first approach provides:
- ✅ **Fast tracking**: `bd list` is instant, no need to parse growing markdown files
- ✅ **Scalable**: Handles 100s of issues without performance degradation
- ✅ **Queryable**: Filter by status, priority, labels with simple commands
- ✅ **GitHub integration**: External refs link to GitHub issues
- ✅ **Markdown for docs**: Strategic planning stays in ROADMAP.md and architecture docs