# Contributing to Edgartools

A big welcome and thank you for considering contributing to Edgartools! We appreciate your interest in helping make this library better. 🎉

There are many ways to contribute, from reporting bugs and suggesting features to writing code, improving documentation, and sharing your expertise.

## Ways to Contribute

*   **Report Bugs:** If you encounter a bug, please check if it has already been reported in the [GitHub Issues](https://github.com/dgunning/edgartools/issues). If not, please [open a new issue](https://github.com/dgunning/edgartools/issues/new/choose). Include a clear title, a detailed description of the bug, steps to reproduce it, expected behavior, actual behavior, and your environment details (OS, Python version, Edgartools version).
*   **Suggest Enhancements:** Have an idea for a new feature or an improvement to an existing one? Open an issue using the "Feature request" template. Describe your idea clearly, why it would be beneficial, and any potential implementation details you've considered.
*   **Improve Documentation:** See a typo, something unclear, or an area that needs more explanation in the [documentation](https://dgunning.github.io/edgartools/) or docstrings? Submit a pull request with your improvements!
*   **Write Code:** If you want to fix a bug or implement a new feature:
    1.  Find an issue you want to work on (or open one).
    2.  Discuss your plan in the issue comments if it's a significant change.
    3.  Follow the development setup and contribution workflow below.
*   **Share Expertise:** If you have experience with SEC filings, XBRL, financial data analysis, or related areas, your insights are valuable! Participate in discussions on issues or share your knowledge.

## Development Setup

This project uses [Hatch](https://hatch.pypa.io/) for environment and project management.

1.  **Fork & Clone:** Fork the repository on GitHub and clone your fork locally:
    ```bash
    git clone https://github.com/<YOUR_USERNAME>/edgartools.git
    cd edgartools
    ```
2.  **Install Hatch:** If you don't have Hatch installed, follow the [official installation guide](https://hatch.pypa.io/latest/install/).
3.  **Activate Environment:** Set up the development environment and install dependencies (including development tools like `ruff`, `pytest`, `mkdocs`):
    ```bash
    hatch shell
    ```
    This command activates a virtual environment managed by Hatch with all necessary dependencies installed.

## Contribution Workflow

1.  **Create a Branch:** Create a new branch for your changes, based on the `main` branch:
    ```bash
    git checkout main
    git pull origin main # Ensure you have the latest changes
    git checkout -b your-feature-or-fix-branch-name
    ```
    Use a descriptive branch name (e.g., `fix-filing-parsing-error`, `add-insider-transaction-api`).
2.  **Make Changes:** Write your code or documentation improvements.
3.  **Format & Lint:** Ensure your code adheres to the project's style guidelines by running the formatter and linter:
    ```bash
    # Format code
    hatch run ruff format .
    # Check for linting errors
    hatch run lint
    ```
    Fix any reported issues.
4.  **Test:** Run the test suite to ensure your changes haven't introduced regressions:
    ```bash
    hatch run cov
    ```
    Make sure all tests pass and coverage doesn't significantly decrease. Consider adding new tests for your changes if applicable.
5.  **Commit:** Commit your changes with a clear and descriptive commit message. Follow conventional commit message formats if possible (e.g., `fix: Resolve issue with date parsing in Form 4`, `feat: Add support for 8-K item retrieval`).
    ```bash
    git add .
    git commit -m "feat: Describe your change here"
    ```
6.  **Push:** Push your branch to your fork:
    ```bash
    git push origin your-feature-or-fix-branch-name
    ```
7.  **Open Pull Request:** Go to the original `edgartools` repository on GitHub and open a pull request from your branch to the `main` branch.
    *   Provide a clear title and description for your PR.
    *   Reference any relevant issues (e.g., "Closes #123").
    *   Explain the changes you made and why.
8.  **Review:** A maintainer will review your PR. Be prepared to discuss your changes and make further adjustments based on feedback.

## Test Cassettes (VCR)

Network-dependent tests replay recorded SEC responses from `tests/cassettes/`
rather than hitting the network on every run. A cassette is the test's ground
truth: when a test asserts that a section is 91,682 characters, the authority
for that number is the recorded response body, not SEC. Cassettes are therefore
held to the same standard as the assertions they support.

**Record from live SEC, and don't edit afterwards.** Delete the cassette and
re-run the test to record it (`record_mode` is `once`, so an existing file is
never overwritten). Never hand-edit a recorded response — not to shrink a large
cassette, not to remove a field that makes a test flaky, and not to adjust a
value so an assertion passes. An edited cassette produces a test that looks like
it verifies against a real filing while verifying against something SEC never
sent.

**Record against `main`, not against your fix.** If you record while your change
is applied, the cassette captures your patched behaviour and the test can no
longer fail if the fix regresses. Record first, then develop against the
recording.

**Keep cassettes small by scoping the test, not by trimming the file.** If a
cassette is unreasonably large, narrow what the test fetches — a smaller filing,
a single request — and re-record.

**CI will not generate cassettes for you.** They are committed artifacts, and
they are reviewed as part of the PR. Say in the PR description which filings you
recorded and when, so a reviewer can spot-check a value against SEC directly.

Cassettes are loaded as plain data — recorded requests, headers and response
bodies only. `hatch run check-cassettes` verifies this and runs in CI ahead of
the test jobs; run it locally if you are about to run a branch you did not write.

## Regression Tests

A regression test is a claim that one specific bug stays fixed. A year from now
the assertion is the only surviving record of what that bug was, and the only
question that justifies ever deleting the test is "is this bug still
reachable?" — which nobody can answer without the report.

**Every file under `tests/issues/regression/` must name its origin in the module
docstring**, as one of these three shapes:

```
GitHub Issue: https://github.com/dgunning/edgartools/issues/<n>
GitHub PR:    https://github.com/dgunning/edgartools/pull/<n>
Bead:         edgartools-<id>
```

Anywhere in the docstring is fine; directly under the summary line is the usual
place.

**A bare `#819` in prose does not count, and that is the point rather than an
oversight.** 109 files here once named their issue in prose and nothing else.
The number was present, but it was not a link and the form varied — "GH #812",
"GitHub issue #488", "issue #762" — so no tool could follow it. Requiring one
canonical shape is what makes "which of these bugs are still open?" answerable
by a script instead of by reading 300 docstrings. The filename is not enough
either: it carries the number for some of the tree and silently not for the
rest.

**This runs in CI ahead of the test jobs**, as a step inside `test-fast`, so a
missing line fails your pull request before a single test executes. The failure
names the exact line to add. Check it before pushing:

```bash
hatch run check-regression-provenance
```

Place new regression tests in `tests/issues/regression/test_issue_NNN.py`, and
assert specific values rather than mere existence — a ground-truth number taken
from a real filing, verified by hand.

## Changelog Entries

`CHANGELOG.md` is read by someone deciding whether an upgrade affects them. An
entry is the compiled short view of a change, not the record of the
investigation behind it. New entries go under `## [Unreleased]`, in the
`### Added` / `### Changed` / `### Fixed` / `### Performance` / `### Removed`
section they belong to, and are folded into a dated version at release.

**Symptom first, in a bold sentence-case lead that names the public symbol in
backticks** — what a user saw go wrong, not what the code did. Then one to three
sentences for the cause and the fix. Eighty words is the cap for the whole
entry. An entry that will not fit is carrying material that belongs somewhere
else.

**Give it one ground-truth anchor.** Name a real filing and put the wrong value
beside the right one — "on Ambac's FY2022 10-K (`0000874501-23-000040`) Item 7
was cut off at 149,459 of its 158,411 characters". A number the reader can check
against SEC is what separates an entry from a claim, and it is usually the same
number the regression test asserts.

**End with `(GH #NNN)`, and nothing else.** No commit hashes, and no bead IDs:
`.beads/` is not in a clone, so an internal issue ID in a public file points at
something no reader can open. Keep contributor attribution —
`(GH #NNN, thanks @kmatosli)`.

**Name the import path when the symbol is ambiguous.** `edgar.xbrl.facts.FactQuery`
and `edgar.entity.query.FactQuery` are different classes with the same method
names, so "`FactQuery.to_dataframe()` changed" sends a reader to the wrong one.

**The long version is relocated, not deleted.** The regex that backtracked, the
corpus of 1,940 tables, the three different messages pandas produced — that
belongs in the PR body and the commit message, and in the docstring of the
regression test under `tests/issues/regression/`. Someone debugging the same
code finds it there; someone reading the changelog wants to know whether the bug
reached them.

**Write the entry from the code, not from your notes.** Run every claim before
you write it down. The changelog is a compiled view and drifts from the source,
so transcribing a figure out of it is how a wrong number ships.

**A breaking change carries one more obligation.** The entry goes under
`### Changed` or `### Removed`, and the same PR adds a section to
`docs/upgrade/<next-major>.md` giving the behaviour before, the behaviour after,
and the mechanical rewrite where one exists.

### Calibration

Before — the entry as filed in 5.44.1: 171 words, an accurate account of the
investigation, abridged here:

> **`filing["Item 7"]` hung indefinitely on some 10-Ks** — `CrossReferenceIndex.has_index()`
> matched the cross-reference heading, then probed for the index table with a
> single regex nesting six lazy quantifiers under `DOTALL` against the *entire*
> filing HTML. Where the heading matched but the table shape did not, it
> backtracked catastrophically: on ODP Corp's FY2025 10-K (5.6MB) the call did
> not finish within 45 seconds. A successful match returned instantly, so only
> the non-matching case was affected. It is reached from `TenK.__getitem__`, so
> any item lookup on an affected 10-K hung — and because `re` holds the GIL
> throughout, one such filing froze every other thread in the process […]
> (GH #928)

After — 75 words, the same change:

> **`filing["Item 7"]` hung indefinitely on 10-Ks with a cross-reference heading
> but no index table.** The detection probe was a regex nesting six lazy
> quantifiers under `DOTALL` and ran against the entire filing HTML, so it
> backtracked catastrophically. ODP Corp's FY2025 10-K (5.6MB) did not finish
> within 45 seconds, and because `re` holds the GIL, one such filing froze every
> other thread in the process. Detection now scans the index table row by row.
> (GH #928)

Nothing in the first version was wrong; all of it is still on record, in the PR
and the regression test. The standard applies from adoption forward — existing
entries are not rewritten.

## Documentation Structure

EdgarTools uses a three-tier documentation system:

### External Documentation (`docs/`)
- **Purpose**: User-facing documentation published to edgartools.readthedocs.com
- **Content**: API reference, user guides, tutorials, installation, configuration
- **Standards**: Must be maintained, versioned, and follow consistent style
- **Audience**: End users and developers using EdgarTools

### Internal Documentation (`docs-internal/`)
- **Purpose**: Internal planning, research, and development documentation
- **Content**: Architecture decisions, feature proposals, research analysis, runbooks
- **Standards**: Can include sensitive details, work-in-progress, more informal
- **Audience**: EdgarTools maintainers and contributors

### AI Documentation (`ai_docs/`)
- **Purpose**: Documentation for AI agents working with the codebase
- **Content**: Agent instructions, API context, code patterns, generated docs
- **Standards**: CLAUDE.md is source of truth, context should be accurate and concise
- **Audience**: AI assistants and automated tools

### Local Documentation Management

To avoid conflicts over temporary documentation, use **local exclusions** instead of global .gitignore:

```bash
# Setup local exclusions (run once per developer)
cat >> .git/info/exclude << 'EOF'
# AI-generated documentation
ai_docs/generated/

# Module-specific ephemeral docs
edgar/**/.docs/

# Personal temporary docs
**/TEMP_*.md
**/WIP_*.md
**/LOCAL_*.md
EOF
```

## Building Documentation Locally

To preview the external documentation site locally:

```bash
hatch run mkdocs serve
```

Then open your browser to `http://127.0.0.1:8000`.

Thank you again for your contribution!