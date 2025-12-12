# Beads Issue Tracking Workflow

EdgarTools uses a hybrid approach: **Beads** for active tracking, **Markdown** for planning.

## Beads Commands

### List and Filter Issues

```bash
bd list --status open                    # View open work items
bd list --status open --priority 0       # Critical items (0-4 or P0-P4)
bd list --status open -l bug             # Filter by label (use -l or --label, singular)
bd list --status in_progress             # Currently active work
bd list -t bug -p 1                      # High priority bugs
```

### Create Issues

```bash
bd create --title "Bug: Description" \
          --type bug \
          --priority P1 \
          --label bug,xbrl-parsing \
          --external-ref 'gh:123' \
          --description "Detailed description"
```

### Update Issues

```bash
bd update ISSUE_ID --status in_progress  # Change status
bd update ISSUE_ID --priority P0         # Change priority
bd update ISSUE_ID --notes "Progress"    # Add notes (NOT --add-comment)
bd update ISSUE_ID --assignee "username"
```

### Show Details

```bash
bd show ISSUE_ID
```

## Valid Values

| Field | Values |
|-------|--------|
| Status | `open`, `in_progress`, `blocked`, `closed` (NOT "done") |
| Priority | 0-4 or P0-P4 (0=critical, 1=high, 2=medium, 3=low, 4=backlog) |
| Type | `bug`, `feature`, `task`, `epic`, `chore` |

## When to Use What

| Tool | Use For |
|------|---------|
| Beads | Active work tracking, GitHub issue linking, status updates, priority filtering |
| Markdown | ROADMAP.md (version planning), VELOCITY-TRACKING.md, architecture docs |

## Agent Integration

- **product-manager**: Uses `bd list` for work queue, creates issues with `bd create`, updates ROADMAP.md
- **issue-handler**: Creates `bd create --external-ref 'gh:XXX'`, tracks progress with status updates
- **Slash commands**: `/task` and `/triage` wrap `bd` commands
