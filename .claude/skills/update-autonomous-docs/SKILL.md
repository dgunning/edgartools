---
name: update-autonomous-docs
description: "Update the autonomous system docs (architecture + roadmap) after implementing changes. Reads git diff, proposes updates, applies with confirmation. Use after implementing a plan, completing a milestone, or running an overnight eval."
allowed-tools: Read, Edit, Bash(git log:*), Bash(git diff:*), Bash(wc:*), Bash(grep:*), Glob, Grep
---

## Pre-computed Context

**Recent changes since last doc update:**
!`git log --oneline --since="$(grep 'Updated' docs/autonomous-system/architecture.md 2>/dev/null | head -1 | grep -oP '\d{4}-\d{2}-\d{2}' | head -1 || echo '2026-03-24')" -- edgar/xbrl/standardization/ .claude/agents/ .claude/skills/ 2>/dev/null | head -20`

**Current doc state:**
!`wc -l docs/autonomous-system/architecture.md docs/autonomous-system/roadmap.md 2>/dev/null`

**Pending Phase 6 tasks:**
!`grep '\- \[ \]' docs/autonomous-system/roadmap.md 2>/dev/null`

---

# Update Autonomous System Documentation

You are maintaining two consolidated docs for the autonomous XBRL extraction quality system:

1. **`docs/autonomous-system/architecture.md`** — How the system works RIGHT NOW. Updated when architecture, components, or current state numbers change.
2. **`docs/autonomous-system/roadmap.md`** — Where we've been and where we're going. Updated when milestones are completed, runs finish, or consensus sessions happen.

## Step 1: Detect What Changed

Read the git log and diff since the last documented update date (shown in architecture.md's Current State table).

```bash
# Files changed in standardization
git diff --stat <last_update_commit>..HEAD -- edgar/xbrl/standardization/

# Specific code changes
git diff <last_update_commit>..HEAD -- edgar/xbrl/standardization/tools/
```

Classify changes into categories:
- **Architecture change** — new components, modified decision gate, new validation layer → update architecture.md
- **Numbers changed** — CQS/EF-CQS improved, new companies added → update architecture.md Current State
- **Milestone completed** — Phase 6 checkbox item done → update roadmap.md
- **Overnight run** — new run results → add to roadmap.md Run Log
- **Consensus session** — new multi-model consultation → add to roadmap.md Consensus Sessions
- **Config pattern** — new Tier 1 config patterns → update architecture.md Configuration section

## Step 2: Propose Updates

Present a concise summary to the user:

```
I'll update the autonomous system docs with these changes:

architecture.md:
  - Current State: EF-CQS 0.8491 → 0.8623
  - Key Components: Updated decision gate to describe LIS implementation

roadmap.md:
  - Phase 6: Mark M1.1 and M1.2 as completed
  - Run Log: Add Run 006 summary
  - Phase Completion: Add row for M1 completion

Approve? (y/n)
```

Wait for user confirmation before making edits.

## Step 3: Apply Updates

### architecture.md updates

**Current State table** — Update numbers and the "Updated" date:
```markdown
| Metric | Value | Updated |
|--------|-------|---------|
| EF-CQS | 0.XXXX | 2026-XX-XX |
```

**Key Components** — Only update sections where the architecture actually changed (new component, modified behavior). Do NOT rewrite sections that haven't changed.

**File Map** — Add any new files created in `tools/` or `config/`.

**Key Decisions** — Only add if a new consensus session produced a new persistent decision.

### roadmap.md updates

**Phase 6 checkboxes** — Change `- [ ]` to `- [x]` with date:
```markdown
- [x] **M1.1: Implement LIS** — Completed 2026-03-25. `commit_hash`.
```

**Run Log** — Append new run summary in the established format:
```markdown
**Run NNN (2026-XX-XX)** — Duration, cohort, key config
- Result: X/Y kept, Z discards, W vetoes
- CQS: X→Y, EF-CQS: X→Y
- Key: One-line summary of most important finding.
```

**Phase Completion Tracking** — Add row if a new phase item was completed.

**Consensus Sessions** — Add row to session table + agreements if new consultation happened.

## Step 4: Verify

After applying edits, check:

1. **Current State numbers consistent** — architecture.md and roadmap.md agree on latest CQS/EF-CQS
2. **Checkbox count** — `grep '\- \[ \]' docs/autonomous-system/roadmap.md` shows correct pending count
3. **No broken cross-references** — Both docs reference each other correctly
4. **Updated date** — architecture.md Current State has today's date

## Rules

- **Do NOT rewrite sections that didn't change.** Only touch what's affected by the implementation.
- **Do NOT add new sections.** If the change doesn't fit an existing section, flag it for the user.
- **Do NOT touch memory files.** Those are managed by the auto-memory system.
- **Keep entries concise.** One-line summaries in tables. Detail belongs in git history.
- **Always include commit hashes** for completed milestones and phase tracking entries.
