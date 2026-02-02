# Contributing to TaskRepo

Thank you for your interest in contributing to TaskRepo! This document provides guidelines for contributing to the project.

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/yourusername/TaskRepo.git
cd TaskRepo
```

2. **Install UV** (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **Install dependencies**

```bash
uv sync --extra dev
```

4. **Run tests to verify setup**

```bash
uv run pytest tests/ -v
```

## Updating the Homebrew Formula

When releasing a new version, the Homebrew formula must be updated in the [`homebrew-formulas` repository](https://github.com/HenriquesLab/homebrew-formulas).

### Automated Workflow (Recommended)

```bash
cd ../homebrew-formulas
just release taskrepo  # Full workflow: update → test → commit → push
```

This automatically:
- Fetches the latest version from PyPI
- Downloads and calculates SHA256 checksum
- Updates the formula file
- Tests the installation
- Commits with standardized message
- Pushes to remote

### Manual Workflow (Alternative)

If `just` is not available, you can update the formula manually:

#### 1. Get Package Information from PyPI

```bash
VERSION=X.Y.Z  # Replace with new version
curl "https://pypi.org/pypi/taskrepo/$VERSION/json" | \
  jq -r '.urls[] | select(.packagetype=="sdist") | "URL: \(.url)\nSHA256: \(.digests.sha256)"'
```

#### 2. Update the Formula

Navigate to the homebrew-formulas repository and edit the formula:

```bash
cd ../homebrew-formulas  # Use relative path from TaskRepo directory
```

Edit `Formula/taskrepo.rb`:
- Update the `url` line with the new URL
- Update the `sha256` line with the new hash

#### 3. Test Locally

```bash
brew install --build-from-source ./Formula/taskrepo.rb
brew test taskrepo
tsk --version  # Verify correct version
brew uninstall taskrepo
```

#### 4. Audit the Formula

```bash
brew audit --strict --online taskrepo
```

#### 5. Commit and Push

```bash
git add Formula/taskrepo.rb
git commit -m "taskrepo: update to version $VERSION"
git push
```

#### 6. Verify Installation

```bash
brew install henriqueslab/formulas/taskrepo
tsk --version
```

**Note:** The automated workflow using `just` is preferred for consistency and efficiency. See the [homebrew-formulas repository](https://github.com/HenriquesLab/homebrew-formulas) for additional utility commands like `just list`, `just check-updates`, and `just sha256`

## Development Workflow

### Making Changes

1. Create a new branch for your feature or bugfix:

```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and ensure they follow the code style:

```bash
# Format code
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Run type checking
uv run mypy src/taskrepo
```

3. Add tests for your changes:

```bash
# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=src/taskrepo --cov-report=term-missing
```

4. Update documentation if necessary (README.md, docstrings, etc.)

5. Commit your changes with a descriptive message:

```bash
git add .
git commit -m "Add feature: your feature description"
```

### Code Style

TaskRepo follows these coding standards:

- **Python**: PEP 8 style guide
- **Formatter**: Ruff (configured in pyproject.toml)
- **Linter**: Ruff with strict rules
- **Type hints**: Use type hints for all function signatures
- **Docstrings**: Google-style docstrings for all public functions

### Testing Guidelines

- Write unit tests for all new functionality
- Aim for high test coverage (>80% for new code)
- Use descriptive test names that explain what is being tested
- Follow the Arrange-Act-Assert pattern in tests
- Use pytest fixtures for common test setup

### Commit Messages

Write clear, concise commit messages:

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and pull requests where applicable

Examples:
```
Add support for task dependencies
Fix memory leak in task loading
Update documentation for sync command
Refactor repository discovery logic
```

## Submitting Changes

1. Push your branch to your fork:

```bash
git push origin feature/your-feature-name
```

2. Create a Pull Request (PR) on GitHub:
   - Provide a clear description of the changes
   - Reference any related issues
   - Ensure all CI checks pass
   - Request review from maintainers

3. Address review feedback:
   - Make requested changes
   - Push updates to your branch
   - Respond to reviewer comments

## Project Structure

```
taskrepo/
├── src/taskrepo/           # Main package
│   ├── cli/                # CLI commands and framework
│   │   ├── main.py         # Main CLI entry point
│   │   └── commands/       # Individual command implementations
│   ├── core/               # Core business logic
│   │   ├── task.py         # Task model
│   │   ├── repository.py   # Repository management
│   │   └── config.py       # Configuration handling
│   ├── tui/                # Terminal UI components
│   │   └── prompts.py      # Interactive prompts
│   └── utils/              # Utility functions
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
└── docs/                   # Documentation
```

## Areas for Contribution

We welcome contributions in these areas:

### Features
- Task templates
- Recurrence support
- Time tracking
- Advanced search and filtering
- GitHub API integration
- Web UI for visualization
- Shell completion scripts

### Improvements
- Performance optimizations
- Better error messages
- More comprehensive tests
- Documentation improvements
- Accessibility enhancements

### Bug Fixes
- Check the [Issues](https://github.com/henriqueslab/TaskRepo/issues) page for open bugs
- Reproduce and fix reported issues
- Add tests to prevent regressions

## Code Review Process

All submissions require review:

1. Maintainers will review your PR within a few days
2. Feedback will be provided via PR comments
3. Address feedback and push updates
4. Once approved, a maintainer will merge your PR

## Questions?

If you have questions about contributing:

- Open an issue for discussion
- Reach out to maintainers
- Check existing issues and PRs for similar questions

## License

By contributing to TaskRepo, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to TaskRepo! 🎉
