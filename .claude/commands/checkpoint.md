---
description: "Save progress checkpoint before clearing context"
---

# Create Progress Checkpoint

You are creating a checkpoint of the current work session to enable a clean context restart.

## Step 1: Determine Context

Ask yourself:
- What is the main task we're working on?
- What's a brief, descriptive name for this task? (e.g., "oauth-migration", "fix-bug-429", "add-13f-support")

## Step 2: Create Checkpoint Document

Create a progress document with this structure:

**Filename**: `docs-internal/sessions/session-{task-name}-{YYYY-MM-DD}.md`

Use today's date and a brief task name (kebab-case, max 3-4 words).

**Document Structure**:

```markdown
# Session Checkpoint: {Task Name}

**Date**: {YYYY-MM-DD}
**Time**: {HH:MM}
**Branch**: {current git branch}

## Task Summary
{1-2 sentence description of what we're working on}

## Completed ✅

- {Specific accomplishment with file path}
- {Another completed item}

## In Progress 🔄

- {Current work item}
- {Any blockers or issues encountered}

## Remaining Tasks ⬜

- [ ] {Next task to complete}
- [ ] {Another remaining task}

## Key Decisions 🎯

- **{Decision topic}**: {What was decided and why}
- **{Another decision}**: {Rationale}

## Important Files 📁

- `path/to/file.py` - {What this file does in this context}
- `path/to/another.py` - {Why this file matters}

## Next Steps 🚀

1. {Explicit next action}
2. {Second action}
3. {Third action}

## Context Notes

{Any important context that would be lost after /clear - patterns discovered,
gotchas encountered, areas of concern, etc.}
```

## Step 3: Quality Check

Ensure the checkpoint includes:
- ✅ Specific file paths (not vague "updated files")
- ✅ Clear next steps (actionable, not vague)
- ✅ Technical decisions with rationale
- ✅ Any blockers or issues that need attention
- ✅ Brief enough to scan quickly (<150 lines ideal)

## Step 4: Save and Instruct

After creating the document, tell the user:

```
✅ Checkpoint saved to: {filename}

To continue after clearing context:
1. Type: /clear
2. Type: @{filename} /catchup
3. Say: "Continue with {specific next step from Next Steps}"

Alternative quick restart:
- /catchup (will catch git changes including this checkpoint if committed)

Ready to clear when you are.
```

## Guidelines

**DO**:
- Use specific file paths and line numbers when relevant
- Capture "why" decisions were made, not just "what"
- Include enough detail for you to resume days later
- Note any gotchas, surprises, or patterns discovered
- Keep it scannable (use bullets, headers, emojis)

**DON'T**:
- Include code snippets (files are in git, /catchup will reload them)
- Document trivial decisions or obvious next steps
- Make it a novel - aim for concise clarity
- Forget to specify the actual next action
- Execute /clear yourself (user controls when to clear)

## Special Cases

**If task just started**: Focus on plan/approach rather than completed items
**If near completion**: Emphasize what's left and how to verify it's done
**If blocked**: Clearly state the blocker and what's needed to unblock
**If multiple workstreams**: Use sections to separate parallel efforts
