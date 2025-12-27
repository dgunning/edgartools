# Repository Guidelines

## Project Structure & Module Organization
EdgarTools is a Python package. Core source lives in `edgar/`, with supporting assets and data embedded under subfolders (for example `edgar/reference/data/`). Tests are in `tests/` with pytest markers and helper fixtures in `tests/conftest.py`. Documentation is split between public docs in `docs/` and internal notes in `docs-internal/`. Examples and experiments live in `examples/`, `notebooks/`, and `scripts/`, while data snapshots and outputs appear in `data/` and `test_outputs/`.

## Build, Test, and Development Commands
Use Hatch for environments and common tasks.
- `hatch shell` sets up and activates the dev environment.
- `hatch run lint` runs Ruff linting on `edgar/`.
- `hatch run ruff format .` formats code with the repo’s formatter.
- `hatch run cov` runs pytest with coverage for `edgar/` and `tests/`.
- `hatch run test-fast` or `hatch run test-core` runs targeted test groups.
- `hatch run mkdocs serve` serves docs locally at `http://127.0.0.1:8000`.

## Coding Style & Naming Conventions
Follow standard Python style: 4-space indentation, snake_case for functions/variables, PascalCase for classes, and `test_*.py` for test modules. Formatting and linting are enforced with Ruff; line length is 150. Prefer type hints and keep module APIs clean and intentional.

## Testing Guidelines
Tests use pytest with markers such as `fast`, `slow`, `network`, and `regression`. Prefer adding a marker to new tests and avoid mixing slow/network tests into fast suites. Example: `hatch run test-network` for network-bound tests. Coverage is checked via `hatch run cov`.

## Commit & Pull Request Guidelines
Commit messages follow conventional prefixes found in history and docs: `feat:`, `fix:`, `test:`, `docs:`. Keep commits focused and descriptive. For PRs, include a clear summary, link relevant issues (e.g., “Closes #123”), and explain behavior changes or data impacts.

## Security & Configuration Tips
SEC data access requires an identity string. Use `set_identity("name@email")` in code and set `EDGAR_IDENTITY` when running tests or scripts to avoid request blocks.
