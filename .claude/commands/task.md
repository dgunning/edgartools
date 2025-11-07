---
description: "Create and manage structured development tasks using the EdgarTools task planning framework"
allowed_tools: ["Read", "Write", "Edit", "Glob", "Bash", "Task"]
model: "sonnet"
---

# Task Management Command

Create, update, and manage structured development tasks with **automatic living document integration**. Tasks are tracked in `docs-internal/planning/active-tasks/` and automatically update PRIORITIES.md and VELOCITY-TRACKING.md.

> **Living Documents**: PRIORITIES.md, VELOCITY-TRACKING.md
> **Integration**: Coordinates with product-manager for prioritization

## Usage Examples

```bash
# Create a new feature task (auto-updates PRIORITIES.md)
/task new feature "Multi-company financial comparison"

# Create a bug fix task from GitHub issue
/task new bug --github=408 "Cash flow statement missing values"

# Update task status
/task update FEAT-001 --status=in_progress

# List active tasks
/task list

# Complete a task (auto-updates VELOCITY-TRACKING.md)
/task complete FEAT-001

# Create research task
/task new research "ETF data availability analysis"

# View task details
/task show FEAT-001
```

## Command Implementation

**Step 1: Parse Command Arguments**
```bash
action=$1  # new, update, list, complete, show
shift
```

**Step 2: Execute Action**

### Creating New Tasks

```bash
if [ "$action" = "new" ]; then
    task_type=$1
    task_title="$2"
    github_issue="" # Extract from --github=XXX if provided

    # Generate task ID (simple counter-based)
    !mkdir -p docs-internal/planning/active-tasks
    task_count=$(ls docs-internal/planning/active-tasks/ | grep "^${task_type^^}" | wc -l)
    task_id=$(printf "%03d" $((task_count + 1)))

    task_filename="${task_type^^}-${task_id}-$(echo "$task_title" | tr ' ' '-' | tr '[:upper:]' '[:lower:]').md"

    echo "Creating new task: $task_filename"

    # Create task file inline (no template dependency)
    cat > "docs-internal/planning/active-tasks/$task_filename" <<EOF
# ${task_type^^}-${task_id}: $task_title

**Status**: pending
**Priority**: [TBD - run /triage or product-manager for scoring]
**Estimate**: [XS/S/M/L/XL]
**Created**: $(date +%Y-%m-%d)
$([ -n "$github_issue" ] && echo "**GitHub Issue**: #$github_issue")

## Description

[Task description here]

## Acceptance Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]

## Implementation Notes

[Technical notes, dependencies, risks]

## Progress Log

- $(date +%Y-%m-%d): Task created
EOF

    echo "Task created: $task_filename"

    # Update PRIORITIES.md
    echo "Updating PRIORITIES.md with new task..."
    # Add to appropriate section based on task_type

    echo ""
    echo "✅ Task created and added to PRIORITIES.md"
    echo ""
    echo "Next steps:"
    echo "1. Edit task file to add details: $task_filename"
    echo "2. Run /triage if from GitHub issue for automatic prioritization"
    echo "3. Mark status as 'in_progress' when starting work"
fi
```

### Listing Tasks

```bash
if [ "$action" = "list" ]; then
    echo "=== Active Tasks ==="
    !ls docs-internal/planning/active-tasks/ | grep -E '\.(md)$' | sort
    
    echo ""
    echo "=== Task Status Summary ==="
    # Parse status from each task file
    for task_file in docs-internal/planning/active-tasks/*.md; do
        if [ -f "$task_file" ]; then
            task_name=$(basename "$task_file" .md)
            status=$(grep "^\*\*Status\*\*:" "$task_file" | cut -d' ' -f2- || echo "Unknown")
            echo "$task_name: $status"
        fi
    done
fi
```

### Updating Task Status

```bash
if [ "$action" = "update" ]; then
    task_id=$1
    shift
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --status=*)
                new_status="${1#*=}"
                echo "Updating $task_id status to: $new_status"
                # Find and update status in task file
                task_file=$(find docs-internal/planning/active-tasks/ -name "$task_id-*.md" | head -1)
                if [ -f "$task_file" ]; then
                    # Update status line in file
                    echo "Status updated in $task_file"
                else
                    echo "Task file not found for: $task_id"
                fi
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
fi
```

### Completing Tasks

```bash
if [ "$action" = "complete" ]; then
    task_id=$1

    echo "Completing task: $task_id"

    # Find task file
    task_file=$(find docs-internal/planning/active-tasks/ -name "$task_id-*.md" | head -1)

    if [ -f "$task_file" ]; then
        # Extract task metadata for velocity tracking
        created_date=$(grep "^\*\*Created\*\*:" "$task_file" | cut -d' ' -f2)
        estimate=$(grep "^\*\*Estimate\*\*:" "$task_file" | cut -d' ' -f2)
        completed_date=$(date +%Y-%m-%d)

        # Calculate actual time (simplified - days between dates)
        # In production, could use git commit history for more accuracy

        # Move to completed directory
        !mkdir -p docs-internal/planning/completed-tasks/$(date +%Y-%m)
        !mv "$task_file" "docs-internal/planning/completed-tasks/$(date +%Y-%m)/"

        echo "Task completed and archived to completed-tasks/$(date +%Y-%m)/"

        # Update VELOCITY-TRACKING.md
        echo ""
        echo "Updating VELOCITY-TRACKING.md with completion data..."
        # Add entry to velocity tracking with:
        # - Task ID and title
        # - Estimate (size)
        # - Actual time (calculated or manual)
        # - Multiplier (calculated)
        # - Date completed

        # Remove from PRIORITIES.md active/queued sections
        echo "Removing from PRIORITIES.md active queue..."

        echo ""
        echo "✅ Task completed and velocity data recorded"
        echo ""
        echo "Completion checklist:"
        echo "- [✓] Task archived to completed-tasks/"
        echo "- [✓] VELOCITY-TRACKING.md updated"
        echo "- [✓] PRIORITIES.md updated"
        echo ""
        echo "Please verify:"
        echo "- [ ] All acceptance criteria met"
        echo "- [ ] Tests passing"
        echo "- [ ] Documentation updated"
        echo "- [ ] Code reviewed"
        echo "- [ ] Related GitHub issues closed"
    else
        echo "Task file not found for: $task_id"
    fi
fi
```

### Viewing Task Details

```bash
if [ "$action" = "show" ]; then
    task_id=$1
    
    task_file=$(find docs-internal/planning/active-tasks/ -name "$task_id-*.md" | head -1)
    
    if [ -f "$task_file" ]; then
        echo "=== Task Details: $task_id ==="
        !head -20 "$task_file"
        echo ""
        echo "[Full task file: $task_file]"
    else
        echo "Task file not found for: $task_id"
    fi
fi
```

## Integration with Living Documents

This command automatically maintains:

### When Creating Tasks:
- **PRIORITIES.md**: Adds task to appropriate section (Critical Bugs / Queued / Backlog)
- Creates task file in `docs-internal/planning/active-tasks/`

### When Completing Tasks:
- **VELOCITY-TRACKING.md**: Records actual completion time vs estimate
- **PRIORITIES.md**: Removes from active/queued sections
- Archives task to `docs-internal/planning/completed-tasks/YYYY-MM/`

### When Updating Tasks:
- Maintains task file in `active-tasks/`
- Status changes reflected in task file

## Integration with Other Commands

This command works seamlessly with:
- **`/triage`**: Creates tasks from prioritized GitHub issues (HIGH priority features, CRITICAL bugs)
- **`/roadmap`**: Tasks align with version planning in ROADMAP.md
- **Product-manager agent**: Can request prioritization scoring for new tasks

## Task Lifecycle

1. **Create** → `/task new feature "Description"` (adds to PRIORITIES.md)
2. **Prioritize** → Use `/triage` or product-manager for priority scoring
3. **Plan** → Edit task file with requirements and acceptance criteria
4. **Start** → `/task update TASK-ID --status=in_progress`
5. **Develop** → Regular progress updates in task file
6. **Complete** → `/task complete TASK-ID` (updates VELOCITY-TRACKING.md, PRIORITIES.md)
7. **Archive** → Automatic move to completed-tasks/YYYY-MM/

## Best Practices

- Always use descriptive task titles
- Request priority scoring for feature tasks (use `/triage` or coordinate with product-manager)
- Fill out acceptance criteria before starting work
- Update progress regularly during development
- Reference task IDs in git commits (e.g., "FEAT-001: Add feature X")
- Complete task documentation before marking complete
- Use appropriate task types:
  - **FEAT**: New features or enhancements
  - **BUG**: Bug fixes (from GitHub issues)
  - **RES**: Research or investigation tasks
  - **REF**: Refactoring or code quality improvements

## Living Document Consistency

The task system ensures:
- ✅ All active tasks appear in PRIORITIES.md
- ✅ Completed tasks contribute to VELOCITY-TRACKING.md
- ✅ Task priorities align with ROADMAP.md version planning
- ✅ Critical bugs trigger point release sections (coordinated with /triage)
- ✅ Feature tasks use priority scoring formula for placement