# Claude Code Configuration

This directory contains Claude Code agent prompts and slash commands for EdgarTools development.

## Directory Structure

### `agents/` (14 files)
Specialized agent prompts for different development tasks:
- **bug-hunter.md** - Systematic bug identification and analysis
- **codebase-analyzer.md** - Code implementation analysis
- **codebase-locator.md** - File and component location mapping
- **codebase-pattern-finder.md** - Pattern cataloging and documentation
- **discussion-handler.md** - GitHub discussion management
- **docs-writer.md** - Documentation creation and updates
- **edgartools-architect.md** - Project structure and architecture decisions
- **issue-handler.md** - GitHub issue triage and resolution
- **product-manager.md** - Feature prioritization and strategic decisions
- **reference-data-expert.md** - SEC reference data expertise
- **release-specialist.md** - Release preparation and execution
- **researcher.md** - SEC filing structure research
- **sec-table-analyst.md** - Table formatting analysis
- **test-specialist.md** - Test creation and maintenance

### `commands/` (8 files)
Slash commands for common workflows:
- **/catchup** - Review recent changes and context
- **/checkpoint** - Save progress before clearing context
- **/implement** - Implementation workflow
- **/plan** - Planning and design workflow
- **/research** - Research and analysis workflow
- **/roadmap** - Roadmap generation and management
- **/task** - Task creation and tracking (Beads integration)
- **/triage** - Issue triage and prioritization (Beads integration)

### Configuration Files
- **settings.local.json** - Local settings (git-excluded for privacy)

## Beads Integration

Agents and commands are configured to use Beads for issue tracking:
- Check status: `bd list --status open`
- Create issues: `bd create "title" --type feature --priority 1`
- Update issues: `bd update <id> --status in_progress`
- Link issues: `bd create "title" --blocks <other-id>`

See: `docs-internal/planning/BEADS-WORKFLOW.md` for complete workflow guide

## Customization

To customize agent behavior:
1. Edit the relevant `.md` file in `agents/` or `commands/`
2. Changes take effect immediately
3. Keep prompts focused and task-specific
4. Link to relevant documentation (CLAUDE.md, docs-internal/)

## Version Control

This directory is tracked in git to:
- ✅ Version control agent prompts
- ✅ Collaborate on agent improvements
- ✅ Track evolution of development workflows
- ❌ Exclude `settings.local.json` (personal settings)

## See Also

- **CLAUDE.md** - Main project instructions for agents
- **docs-internal/CLAUDE.md** - Internal structure navigation guide
- **docs-internal/planning/BEADS-WORKFLOW.md** - Issue tracking workflow
