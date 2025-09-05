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