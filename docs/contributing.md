# Contributing to EdgarTools

Thank you for your interest in contributing to EdgarTools! This open-source project thrives on community contributions, and we appreciate any help you can provide. 🎉

## Ways to Contribute

### 💝 Support the Project

If you find EdgarTools useful, consider supporting its development:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 144px !important;" >
</a>

Your support helps maintain and improve EdgarTools, ensuring it remains free and open-source for everyone.

### 🐛 Report Bugs

If you encounter a bug:

1. Check if it's already reported in [GitHub Issues](https://github.com/dgunning/edgartools/issues)
2. If not, [open a new issue](https://github.com/dgunning/edgartools/issues/new/choose)

Include:

1. Clear title and description
2. Steps to reproduce
3. Expected vs actual behavior
4. Environment details (OS, Python version, EdgarTools version)

### 💡 Suggest Features

Have an idea for improvement?
- Open an issue using the "Feature request" template
- Describe your idea clearly
- Explain why it would be beneficial
- Include any implementation ideas

### 📝 Improve Documentation

Help make our docs better:
- Fix typos or unclear explanations
- Add examples and use cases
- Improve API documentation
- Translate documentation

### 🔧 Write Code

Ready to code? Here's how:

1. Find an issue to work on (or create one)
2. Discuss significant changes in issue comments
3. Follow the development workflow below

### 🎓 Share Expertise

Your domain knowledge is valuable!
- Share insights on SEC filings, XBRL, or financial analysis
- Help answer questions in issues
- Review pull requests
- Write tutorials or blog posts

## Development Setup

EdgarTools uses [Hatch](https://hatch.pypa.io/) for project management.

### 1. Fork & Clone

```bash
# Fork on GitHub, then:
git clone https://github.com/<YOUR_USERNAME>/edgartools.git
cd edgartools
```

### 2. Install Hatch

Follow the [official installation guide](https://hatch.pypa.io/latest/install/) if you don't have Hatch.

### 3. Set Up Environment

```bash
# Activate development environment
hatch shell
```

This installs all dependencies including development tools.

## Development Workflow

### 1. Create a Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

Use descriptive branch names like:
- `fix/filing-parsing-error`
- `feature/insider-transaction-api`
- `docs/improve-xbrl-examples`

### 2. Make Changes

- Max line length: 150 characters
- Use type annotations
- Include docstrings for public functions
- Write tests for new features

### 3. Format & Lint

```bash
# Format code
hatch run ruff format .

# Check linting
hatch run lint

# Type check
hatch run pyright
```

### 4. Test

```bash
# Run tests with coverage
hatch run cov

# Run specific tests
hatch run pytest tests/test_file.py::test_function
```

Ensure:
- All tests pass
- Coverage doesn't decrease
- New features have tests

### 5. Commit

Use clear, conventional commit messages:

```bash
git add .
git commit -m "feat: add support for Form 13F parsing"
```

Commit message prefixes:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `style:` - Code style changes
- `chore:` - Maintenance tasks

### 6. Push & Pull Request

```bash
git push origin feature/your-feature-name
```

Then on GitHub:

1. Open a pull request to `main` branch
2. Provide clear title and description
3. Reference relevant issues (e.g., "Closes #123")
4. Explain what and why

### 7. Review Process

- A maintainer will review your PR
- Address feedback constructively
- Make requested changes
- Tests must pass before merging

## Building Documentation

Preview documentation locally:

```bash
# Start local docs server
hatch run mkdocs serve
```

Visit `http://127.0.0.1:8000` to see your changes.

## Code Style Guide

### Python Code

- Line length: 150 chars max
- Use type hints
- Snake_case for functions/variables
- PascalCase for classes
- Descriptive docstrings

### Example:
```python
def get_filing_documents(
    filing: Filing,
    document_type: Optional[str] = None
) -> List[Document]:
    """
    Retrieve documents from an SEC filing.
    
    Args:
        filing: The Filing object to extract documents from
        document_type: Optional filter for specific document types
        
    Returns:
        List of Document objects matching the criteria
    """
    # Implementation
```

### Documentation
- Use clear, concise language
- Include code examples
- Link to related topics
- Keep formatting consistent

## Testing Guidelines

### Writing Tests
- Test files mirror source structure
- Use descriptive test names
- Cover edge cases
- Mock external dependencies

### Example:
```python
def test_company_retrieval_by_ticker():
    """Test that companies can be retrieved by ticker symbol."""
    company = Company("AAPL")
    assert company.name == "Apple Inc."
    assert company.cik == 320193
```

## Getting Help

- 💬 [GitHub Discussions](https://github.com/dgunning/edgartools/discussions) - Ask questions
- 📧 [Email](mailto:edgartools@example.com) - Direct contact
- 📚 [Documentation](https://dgunning.github.io/edgartools/) - Usage guides

## Recognition

Contributors are recognized in:
- [GitHub Contributors](https://github.com/dgunning/edgartools/graphs/contributors)
- Release notes
- Documentation credits

## Support the Project

If you find EdgarTools valuable, please consider:

<a href="https://www.buymeacoffee.com/edgartools" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 180px !important;" >
</a>

Your support helps:

- 🚀 Maintain and improve the library
- 📚 Keep documentation up-to-date
- 🐛 Fix bugs quickly
- ✨ Add new features
- 💻 Keep the project free and open-source

Thank you for contributing to EdgarTools! 🙏