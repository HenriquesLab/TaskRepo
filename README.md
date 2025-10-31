# TaskRepo

<img src="src/taskrepo/logo/logo-taskrepo.png" align="right" width="200" style="margin-left: 20px;"/>

[![CI](https://github.com/HenriquesLab/TaskRepo/actions/workflows/ci.yml/badge.svg)](https://github.com/HenriquesLab/TaskRepo/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/taskrepo.svg)](https://badge.fury.io/py/taskrepo)
[![Python versions](https://img.shields.io/pypi/pyversions/taskrepo.svg)](https://pypi.org/project/taskrepo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-taskrepo.henriqueslab.org-blue)](https://taskrepo.henriqueslab.org)

> TaskWarrior-inspired CLI for managing tasks as markdown files in git repositories

TaskRepo is a powerful command-line task management tool that combines the best of TaskWarrior's workflow with the simplicity of markdown and the collaboration features of git.

## Features

- **Git-backed storage**: All tasks are stored as markdown files in git repositories
- **TaskWarrior-inspired**: Familiar workflow with priorities, tags, dependencies, and due dates
- **Rich metadata**: YAML frontmatter for structured task data
- **Link associations**: Attach URLs to tasks (GitHub issues, PRs, emails, documentation, etc.)
- **Interactive TUI**: User-friendly prompts with autocomplete and validation
- **Multiple repositories**: Organize tasks across different projects or contexts
- **GitHub integration**: Associate tasks with GitHub user handles
- **Beautiful output**: Rich terminal formatting with tables and colors
- **Version control**: Full git history and collaboration capabilities

### Interactive TUI

<p align="center">
  <img src="docs/screenshots/tui-interface.png" alt="TaskRepo TUI Interface" width="100%"/>
</p>

Browse and manage tasks with the interactive Terminal User Interface featuring color-coded statuses, task details panel, and keyboard shortcuts.

## Installation

### macOS (Homebrew) - Recommended for Mac users

```bash
# Tap the HenriquesLab formulas repository
brew tap henriqueslab/formulas

# Install TaskRepo
brew install taskrepo
```

**Updating:**
```bash
brew update
brew upgrade taskrepo
```

Benefits: Simple installation, automatic dependency management (Python 3.12, git, gh), easy updates

### Using pipx (recommended for Linux/Windows)

```bash
# Install pipx if you haven't already
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install TaskRepo
pipx install taskrepo
```

Benefits: Isolated environment, global CLI access, easy updates with `pipx upgrade taskrepo`

### Using uv (fast alternative)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install TaskRepo
uv tool install taskrepo
```

Benefits: Very fast installation, modern Python tooling, automatic environment management

### Using pip (alternative)

```bash
pip install taskrepo
```

Note: May conflict with other packages. Consider using pipx or uv instead.

## Quick Start

> **Note**: You can use either `tsk` (short alias) or `taskrepo` (full command). Examples below use `tsk` for brevity.

### 1. Initialize TaskRepo

```bash
tsk init
```

This creates a configuration file at `~/.taskreporc` and sets up the parent directory for task repositories (default: `~/tasks`).

### 2. Create a repository

```bash
tsk create-repo work
tsk create-repo personal
```

Repositories are stored as `tasks-{name}` directories with git initialization.

### 3. Add a task

```bash
# Interactive mode (default)
tsk add

# Non-interactive mode
tsk add -r work -t "Fix authentication bug" -p backend --priority H --assignees @alice,@bob --tags bug,security

# With associated links (GitHub issues, emails, docs, etc.)
tsk add -r work -t "Fix authentication bug" -p backend --links https://github.com/org/repo/issues/123,https://mail.google.com/mail/u/0/#inbox/abc
```

### 4. List tasks

```bash
# List all tasks
tsk list

# Filter by repository
tsk list --repo work

# Filter by status, priority, or project
tsk list --status pending --priority H
tsk list --project backend

# Show completed tasks
tsk list --all
```

### 5. Manage tasks

```bash
# Mark task as done
tsk done 001

# Edit a task
tsk edit 001

# Sync with git remote
tsk sync
tsk sync --repo work  # Sync specific repository
```

## Commands Reference

### Configuration

- `tsk init` - Initialize TaskRepo configuration
- `tsk config` - Show current configuration
- `tsk create-repo <name>` - Create a new task repository
- `tsk repos` - List all task repositories

### Task Management

- `tsk add` - Add a new task (interactive)
- `tsk list` - List tasks with filters
- `tsk edit <id>` - Edit a task
- `tsk done <id>` - Mark task as completed
- `tsk delete <id>` - Delete a task

### Git Operations

- `tsk sync` - Pull and push all repositories
- `tsk sync --repo <name>` - Sync specific repository
- `tsk sync --no-push` - Pull only, don't push

## Configuration

Configuration is stored in `~/.taskreporc`:

```yaml
parent_dir: ~/tasks
default_priority: M
default_status: pending
default_assignee: null  # Optional: GitHub handle (e.g., @username)
default_editor: null    # Optional: Text editor (e.g., vim, nano, code)
sort_by:
  - priority
  - due
```

### Editor Selection Priority

When editing tasks with `tsk edit`, the editor is selected in this order:
1. CLI flag: `tsk edit 123 --editor nano`
2. Environment variable: `$EDITOR`
3. Config file: `default_editor` in `~/.taskreporc`
4. Fallback: `vim`

## Directory Structure

```
~/tasks/
   tasks-work/
      .git/
      tasks/
          task-001.md
          task-002.md
          task-003.md
   tasks-personal/
      .git/
      tasks/
          task-001.md
   tasks-opensource/
       .git/
       tasks/
           task-001.md
```

## Documentation

For comprehensive documentation, including:
- **Complete CLI reference** with all commands and options
- **Task file format** and field specifications
- **Advanced features** like conflict resolution, dependencies, and GitHub integration
- **Configuration guides** and examples
- **Troubleshooting** and community support

Visit the official documentation at **[taskrepo.henriqueslab.org](https://taskrepo.henriqueslab.org)**

## Examples

### Create a high-priority bug task

```bash
tsk add \
  --repo work \
  --title "Fix memory leak in worker process" \
  --priority H \
  --project backend \
  --assignees @alice,@bob \
  --tags bug,performance \
  --due "2025-11-01" \
  --description "Memory usage grows unbounded in background worker"
```

### List urgent tasks

```bash
tsk list --priority H --status pending
```

### List tasks assigned to a specific user

```bash
tsk list --assignee @alice
```

### Edit a task in your editor

```bash
EDITOR=vim tsk edit 001
# Or with custom editor
tsk edit 001 --editor code
```

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/henriqueslab/TaskRepo.git
cd TaskRepo

# Install with dev dependencies
uv sync --extra dev

# Install pre-commit hooks (optional but recommended)
uv run pre-commit install
```

### Run tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ -v --cov=taskrepo --cov-report=term-missing

# Run specific test types
uv run pytest tests/unit -v           # Unit tests only
uv run pytest tests/integration -v     # Integration tests only
```

### Code quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type checking
uv run mypy src/taskrepo

# Run all quality checks (what CI runs)
uv run ruff format --check .
uv run ruff check .
uv run mypy src/taskrepo
uv run pytest tests/ -v
```

### Pre-commit hooks

We use pre-commit to ensure code quality before commits:

```bash
# Install hooks
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files

# Skip hooks for a specific commit (use sparingly)
git commit --no-verify
```

The following checks run automatically on commit:
- **ruff format**: Code formatting
- **ruff**: Linting and import sorting
- **mypy**: Static type checking
- **trailing-whitespace**: Remove trailing spaces
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml/toml**: Validate config files

### CI/CD Pipeline

TaskRepo uses GitHub Actions for continuous integration and deployment:

#### CI Workflow (`.github/workflows/ci.yml`)

Runs on every push and pull request to `main`:

1. **Lint & Type Check** (Python 3.11)
   - Code formatting check with ruff
   - Linting with ruff
   - Type checking with mypy

2. **Tests** (Python 3.10, 3.11, 3.12)
   - Unit tests
   - Integration tests
   - Matrix testing across Python versions

3. **Coverage Report** (Python 3.11)
   - Full test suite with coverage measurement
   - Coverage report uploaded as artifact

4. **Build Verification** (Python 3.11)
   - Package build (wheel + sdist)
   - Metadata verification
   - Build artifacts uploaded for inspection

#### Release Workflow (`.github/workflows/release.yml`)

Automatically triggered when you push a version tag (e.g., `v0.2.0`):

1. **Validation**
   - Verify tag version matches `__version__.py`
   - Check CHANGELOG.md has entry for this version
   - Run full test suite

2. **PyPI Publishing**
   - Build package (wheel + sdist)
   - Publish to PyPI using OIDC trusted publishing (secure, no API tokens needed)

3. **GitHub Release**
   - Extract release notes from CHANGELOG.md
   - Create GitHub release with auto-generated notes
   - Attach wheel and sdist as release assets

### Creating a Release

To create a new release:

1. **Update version** in `src/taskrepo/__version__.py`:
   ```python
   __version__ = "0.2.0"
   ```

2. **Update CHANGELOG.md** with release notes:
   ```markdown
   ## [0.2.0] - 2025-10-25

   ### Added
   - New feature X
   - New feature Y

   ### Fixed
   - Bug fix Z
   ```

3. **Commit changes**:
   ```bash
   git add src/taskrepo/__version__.py CHANGELOG.md
   git commit -m "chore: bump version to 0.2.0"
   git push
   ```

4. **Create and push tag**:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

5. **Monitor release**:
   - GitHub Actions will automatically run the release workflow
   - Check [Actions tab](https://github.com/HenriquesLab/TaskRepo/actions) for progress
   - Package will be published to [PyPI](https://pypi.org/project/taskrepo/)
   - GitHub release will be created with artifacts

### Dependency Management

Dependencies are automatically monitored by Dependabot:
- Python dependencies updated weekly
- GitHub Actions updated weekly
- PRs are auto-labeled and grouped for easier review

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Inspired by [TaskWarrior](https://taskwarrior.org/)
- Built with [Click](https://click.palletsprojects.com/), [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/), and [Rich](https://rich.readthedocs.io/)
- Package management by [UV](https://docs.astral.sh/uv/)

## Roadmap

- [ ] Dependency validation and visualization
- [ ] Task templates
- [ ] Recurrence support
- [ ] Time tracking
- [ ] Export to other formats (JSON, CSV, HTML)
- [ ] GitHub integration (create issues from tasks)
- [ ] Task search with advanced queries
- [ ] Statistics and reporting
- [ ] Shell completion (bash, zsh, fish)
- [ ] Web UI for task visualization
