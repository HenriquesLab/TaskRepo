# Claude Instructions for TaskRepo Development

This file provides guidance for AI assistants working on TaskRepo development.

## Project Overview

TaskRepo is a TaskWarrior-inspired task management system that stores tasks as markdown files in git repositories. It provides a modern CLI interface with TUI support and GitHub integration.

## Development Environment

### Setup
```bash
# Install UV (recommended package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/ -v
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type checking
uv run mypy src/taskrepo
```

## Release Process

### Version Bumping

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md with new release notes
3. Create PR to main
4. Tag release triggers PyPI publication
5. Update Homebrew formula (see below)

### Homebrew Formula Updates

TaskRepo is distributed via PyPI and Homebrew. After the PyPI release is live, update the Homebrew formula.

#### Homebrew Formula Location

The Homebrew formula is maintained in a separate repository located at `../homebrew-formulas`:
- **Repository**: `../homebrew-formulas/`
- **Formula file**: `Formula/taskrepo.rb`
- **Automation**: Managed via justfile commands

#### Commands

After the PyPI release is live and verified at https://pypi.org/project/taskrepo/:

```bash
cd ../homebrew-formulas

# Option 1: Full automated release workflow (recommended)
# This will update, test, commit, and push in one command
just release taskrepo

# Option 2: Manual step-by-step workflow
just update taskrepo           # Updates to latest PyPI version
just test taskrepo             # Tests the formula installation
just commit taskrepo VERSION   # Commits with standardized message
git push                       # Push to remote

# Utility commands
just list                      # List all formulas with current versions
just check-updates             # Check for available PyPI updates
just sha256 taskrepo VERSION   # Get SHA256 for a specific version
```

#### Workflow Notes

- **Always verify PyPI first**: The formula update pulls package info from PyPI, so the release must be live
- **Automatic metadata**: The `just update` command automatically fetches the version, download URL, and SHA256 checksum from PyPI
- **Full automation**: The `just release` command runs the complete workflow: update → test → commit → push
- **Standardized commits**: Formula updates use consistent commit message format
- **Testing**: The `just test` command uninstalls and reinstalls the formula to verify it works correctly

## Key Features

### Task Management
- Tasks stored as markdown files with YAML frontmatter
- Git-based version control and synchronization
- Support for tags, priorities, due dates, and dependencies
- Rich CLI with color-coded output

### Repository Support
- Multiple task repositories
- GitHub integration for remote storage
- Discovery and initialization commands
- Automatic syncing capabilities

### TUI Components
- Interactive prompts using questionary
- Rich formatting for better UX
- Progress bars and status indicators

## Testing Strategy

- **Unit tests**: Individual component testing
- **Integration tests**: End-to-end workflow testing
- Use pytest with fixtures for common setups
- Aim for >80% test coverage

## Code Style

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Google-style docstrings for public functions
- Ruff for linting and formatting

## Important Notes

- Tasks are stored in `~/.taskrepo/` by default or in user-configured locations
- Each repository is a git repository with tasks as markdown files
- YAML frontmatter contains task metadata
- GitHub integration requires `gh` CLI tool

## Security Considerations

- Sanitize user input for file paths
- Validate repository URLs
- Handle git credentials securely
- Avoid exposing sensitive data in task files
