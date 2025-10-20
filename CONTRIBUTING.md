# Contributing to TaskRepo

Thank you for your interest in contributing to TaskRepo! This document provides guidelines for contributing to the project.

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/yourusername/taskrepo.git
cd taskrepo
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
- Check the [Issues](https://github.com/paxcalpt/taskrepo/issues) page for open bugs
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
