# AGENTS.md

Instructions for AI coding agents working on this repository (Claude Code, Codex, Cursor, Copilot, Gemini CLI and others).
People should start with [CONTRIBUTING.md](CONTRIBUTING.md). Everything here applies to them too.

## Setup and commands

- Python 3.11+, managed with [Hatch](https://hatch.pypa.io/): `hatch shell`.
- The package installs as `edgartools` but imports as `edgar` (`from edgar import Company`).
- SEC requires a contact identity on every request: `export EDGAR_IDENTITY="Your Name you@example.com"`.

```bash
hatch run test-fast                       # offline tests: run these often
hatch run lint                            # ruff
hatch run test-network tests/path/test_x.py   # network tests: one file at a time, never in parallel (SEC allows 10 req/s)
hatch run check-cassettes                 # before running tests on a branch you did not write
hatch run check-regression-provenance     # CI runs this before tests
```

## Where things are

| Area | Location |
|---|---|
| Filing, Filings | `edgar/_filings.py` |
| Company, Entity | `edgar/entity/` |
| XBRL, statements | `edgar/xbrl/` |
| HTML parsing, sections, markdown | `edgar/documents/` (the only HTML parser; `edgar.files` was removed in 6.0) |
| 10-K / 10-Q / 8-K objects | `edgar/company_reports/` |
| Form 3/4/5, 13F, funds | `edgar/ownership/`, `edgar/thirteenf/`, `edgar/funds/` |
| Full-text search | `edgar/search/efts.py` |
| Form → class routing for `filing.obj()` | the `obj()` chain in `edgar/__init__.py` |
| MCP server and bundled skills | `edgar/ai/` |

## Things you cannot infer from the code

- `edgar/xbrl/standardization/gaap_mappings.json` is generated outside this repo. Keep edits to the concepts in your issue, add a regression test, and check that no other open PR touches it (see below).
- Concept-mapping bugs usually need fixing twice: once in the XBRL standardization and once in EntityFacts (`edgar/entity/`).
- The `Filing.text()`, `Filing.html()` and `Attachment.empty` contracts are frozen. Fix text extraction in `FilingSGML` or `edgar/documents`, never by rerouting `Filing.*`.
- Test cassettes are recorded from live SEC, against `main`, and never edited afterwards (CONTRIBUTING.md, "Test Cassettes").
- Never edit `CHANGELOG.md`. Add a fragment instead: `changelog.d/<issue>.<section>.md` (see `changelog.d/README.md`).
- A deprecation or breaking change needs an entry in `docs/upgrade/6.0.md`. CI fails the PR without one.

## Definition of done

- At least one assertion checks a specific value from a real SEC filing that you looked up yourself. Name the filing and accession number in the PR. `assert x is not None` does not count.
- A bug fix has a regression test in `tests/issues/regression/test_issue_NNN.py`, and its docstring names its origin (`GitHub Issue: https://github.com/dgunning/edgartools/issues/NNN`).
- Bad or missing input raises a useful error. It does not return `None`.
- Any documented example your change touches still runs.

## Boundaries

**Always:** run `hatch run test-fast` before opening a PR, and report what you verified and against which filing.

**Ask first, in the issue:**
- renaming or removing public API
- adding a dependency
- changing more than one subsystem
- editing `gaap_mappings.json` beyond the concepts in the issue

**Never:**
- weaken, skip or delete a test to make it pass (CI rejects `pytest.skip` under `tests/issues/regression/`)
- hand-edit a cassette
- use `git stash` in a worktree: every worktree shares one `refs/stash`, so parallel agents pop each other's changes (save with `git diff > file` instead)
- invent a filing value you did not read from SEC
- open, comment on or merge GitHub issues or PRs without the human you work for reviewing them first

## Before opening a pull request

1. Check that nobody is already on it:
   ```bash
   gh pr list --repo dgunning/edgartools --state open --search "<issue number> in:body"
   ```
2. If you touch a shared data file, check for other open PRs on the same file, and wait if there is one:
   ```bash
   gh pr list --repo dgunning/edgartools --state open --json number,files \
     --jq '[.[] | select(any(.files[]; .path=="edgar/xbrl/standardization/gaap_mappings.json")) | .number]'
   ```
3. Use one PR per issue. Several related fixes start with one umbrella issue that proposes a merge order. Keep at most three of your PRs open at a time.
   Exception: when the maintainer asks for a batch, open one draft PR per subsystem area instead. Each PR keeps one commit
   per issue, each with its own regression test and its own `Fixes #N`, so any single fix can be reverted. The three-PR
   limit does not apply to that batch, and every PR passes an agent review before the maintainer reads it.
4. Fill in the PR template's Verification section, and name the AI tool and model you used. That is not a confession; it tells the reviewer where to start.
