---
name: update-autonomous-docs
description: "Update the autonomous system docs (architecture.md + roadmap.md) after implementing changes. Reads git diff, proposes updates, applies with confirmation. Trigger this skill after implementing a plan, completing a milestone, running an overnight eval, finishing a consensus session, or any time the user says 'update docs', 'update autonomous docs', 'sync docs', or 'docs are stale'. Also trigger proactively when you've just completed significant implementation work on the standardization system — the docs should always reflect reality."
allowed-tools: Read, Edit, Write, Bash(git log:*), Bash(git diff:*), Bash(wc:*), Bash(grep:*), Bash(date:*), Glob, Grep
---

## Pre-computed Context

**Last documented update:**
!`grep -A5 'Current State' docs/autonomous-system/architecture.md 2>/dev/null | grep -oP '\d{4}-\d{2}-\d{2}' | tail -1 || echo 'unknown'`

**Recent commits since last update:**
!`LAST_DATE=$(grep -A5 'Current State' docs/autonomous-system/architecture.md 2>/dev/null | grep -oP '\d{4}-\d{2}-\d{2}' | tail -1 || echo '2026-03-24'); git log --oneline --since="$LAST_DATE" -- edgar/xbrl/standardization/ .claude/agents/ .claude/skills/ 2>/dev/null | head -15`

**Pending milestones:**
!`grep '\- \[ \]' docs/autonomous-system/roadmap.md 2>/dev/null`

**Completed milestones:**
!`grep '\- \[x\]' docs/autonomous-system/roadmap.md 2>/dev/null`

---

# Update Autonomous System Documentation

You maintain two docs that are the single source of truth for the autonomous XBRL extraction quality system:

| Doc | Purpose | Update when... |
|-----|---------|----------------|
| `docs/autonomous-system/architecture.md` | How it works NOW | Architecture, components, numbers, file map, or key decisions change |
| `docs/autonomous-system/roadmap.md` | History + plan | Milestones completed, runs finish, consensus sessions happen, new phases added |

The reason these docs exist is so that both humans and AI agents can resume context across sessions. Stale docs waste everyone's time, so keeping them accurate matters. But the flip side: touching sections that haven't changed creates noise. Only update what's actually affected.

## Step 1: Read Current State

Read BOTH docs before doing anything else — you need to know what's already documented to avoid duplicating or contradicting it.

```
Read docs/autonomous-system/architecture.md
Read docs/autonomous-system/roadmap.md
```

Note the current numbers in the Current State table (CQS, EF-CQS, etc.) and which milestones are already checked off.

## Step 2: Identify What Changed

Use TWO sources to understand what changed:

**A. Conversation context** — If you just finished implementing something in this session, you already know what changed. Use that knowledge directly — it's more accurate than git diff for understanding *intent*.

**B. Git history** — For changes you weren't part of, or to catch things you might have missed:

```bash
git log --oneline --since="LAST_UPDATE_DATE" -- edgar/xbrl/standardization/
git diff --stat LAST_COMMIT..HEAD -- edgar/xbrl/standardization/tools/
```

Replace `LAST_UPDATE_DATE` with the date from the Current State table's "Updated" column.

Classify each change:

| Category | Affects | Example |
|----------|---------|---------|
| Architecture change | architecture.md components | New decision gate (LIS), new validation layer |
| Numbers changed | architecture.md Current State | EF-CQS improved from 0.8491 to 0.86 |
| Milestone completed | roadmap.md Phase 6 checkboxes | M1.1 implemented and verified |
| Overnight run | roadmap.md Run Log | Run 006 completed with results |
| Consensus session | roadmap.md Consensus Sessions | Session 005 with GPT/Gemini |
| New file added | architecture.md File Map | New tool in tools/ directory |
| Key decision | architecture.md Key Decisions | New persistent decision from consensus |

If nothing meaningful changed since the last update, say so and stop — don't make edits for the sake of making edits.

## Step 3: Propose Updates

Show the user a concise preview:

```
Proposed doc updates:

architecture.md:
  - Current State: EF-CQS 0.8491 → 0.8623 (updated date → 2026-03-25)
  - Key Components: Added LIS description to Decision Gate section

roadmap.md:
  - Phase 6: M1.1 ✓, M1.2 ✓ (with commit hashes)
  - Run Log: Added Run 006 summary
  - Phase Tracking: Added row for M1 completion

Approve?
```

Wait for confirmation before editing.

## Step 4: Apply Updates

### architecture.md

**Current State table** — Update values and the "Updated" date column. This is the most common update.

**Key Components** — Only modify sections where behavior actually changed. If the decision gate changed from CQS to LIS, update that paragraph. Don't touch the CQS formula section if it hasn't changed.

**File Map** — Add new files. Remove deleted files. Don't reorganize what hasn't changed.

**Key Decisions** — Add only if a consensus session produced a new persistent decision worth preserving across all future sessions.

### roadmap.md

**Phase 6 checkboxes** — Change `- [ ]` to `- [x]` and append completion info:
```markdown
- [x] **M1.1: Implement LIS** — Completed 2026-03-25. `abc123de`.
```

**Run Log** — Append in established format:
```markdown
**Run NNN (2026-XX-XX)** — Duration, cohort
- Result: X/Y kept, Z discards
- CQS: X→Y, EF-CQS: X→Y
- Key: One-line finding.
```

**Phase Completion Tracking** — Add row for completed phase items.

**Consensus Sessions** — Add row to session table + key agreements.

**Continuation IDs** — Add new IDs from consensus sessions.

## Step 5: Verify

After editing, run these checks:

1. Numbers match: architecture.md Current State and roadmap.md latest run agree on CQS/EF-CQS
2. Checkbox count: `grep -c '\- \[ \]' docs/autonomous-system/roadmap.md` — report the count
3. Updated date: architecture.md Current State shows today's date
4. Cross-references: both docs still link to each other correctly

Report the verification results to the user.

## Principles

- **Minimal edits**: Only touch sections affected by the change. Three lines edited beats a full rewrite.
- **Commit hashes**: Every completed milestone and phase tracking entry needs one.
- **Concise entries**: One-line summaries in tables. Git history has the details.
- **No new sections**: If something doesn't fit existing sections, flag it — don't restructure the doc.
- **No memory files**: The auto-memory system manages those separately.
