# Changelog

All notable changes to TaskRepo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-10-22

### Added
- **Automatic update checking**: TaskRepo now automatically checks PyPI for newer versions once per day
- **Update notifications**: Non-intrusive notification displayed when a newer version is available
- **Smart caching**: Update checks are cached for 24 hours to minimize network requests and CLI startup time

### Improved
- **User awareness**: Users stay informed about new releases without manual checking
- **Graceful error handling**: Network failures and timeouts are handled silently without disrupting CLI usage
- **Fast performance**: 2-second timeout ensures update checks don't slow down commands

### Technical Details
- New module: `src/taskrepo/utils/update_checker.py` for update checking logic
- Uses PyPI JSON API (`https://pypi.org/pypi/taskrepo/json`) to fetch latest version
- Added `packaging>=20.0` dependency for proper semantic version comparison
- Cache stored in `~/.taskrepo-update-check` with timestamp
- Integrated via `@cli.result_callback()` to run after each command execution
- Comprehensive test coverage with 10 new tests

## [0.3.2] - 2025-10-22

### Changed
- **Confirmation prompts**: Replaced all `click.confirm()` calls with `prompt_toolkit.shortcuts.confirm()` for consistent validation across the codebase
- **Better input validation**: All y/n prompts now use prompt_toolkit's built-in validation that only accepts y/n keypresses
- **Removed custom validator**: Eliminated `YesNoValidator` class in favor of prompt_toolkit's native confirm function

### Improved
- **User experience**: Confirmation prompts now require explicit y/n input (no default ambiguity)
- **Code consistency**: All interactive prompts use prompt_toolkit ecosystem throughout

### Technical Details
- Updated confirmation prompts in: `delete`, `done`, `config`, `init`, and `create-repo` commands
- All confirmations now use `prompt_toolkit.shortcuts.confirm()` instead of `click.confirm()`

## [0.3.1] - 2025-10-22

### Fixed
- **Sync command**: Verified and documented that `tsk sync` properly handles all file operations (new tasks, modifications, and deletions) using `git add -A`

### Improved
- **Documentation**: Clarified that sync command automatically stages all changes including untracked files and deletions

## [0.2.0] - 2025-10-21

### Added

#### CI/CD Infrastructure
- **Comprehensive CI pipeline**: Automated testing across Python 3.10, 3.11, 3.12
- **Lint and type checking**: ruff formatting, linting, and mypy type checking
- **Coverage reporting**: pytest-cov integration with artifact upload
- **Build verification**: Automated package building and validation
- **Release automation**: Tag-based releases with PyPI OIDC trusted publishing
- **GitHub Releases**: Automatic release creation with changelog extraction and build artifacts
- **Dependabot**: Automated dependency updates for Python packages and GitHub Actions
- **Pre-commit hooks**: Local code quality checks (ruff, trailing whitespace, YAML/TOML validation)
- **CI badges**: Status badges in README for CI pipeline

#### Enhanced Commands
- **`taskrepo done` list view**: Running `taskrepo done` without arguments now displays all completed tasks
- **Repository filtering**: Support `--repo` flag to show completed tasks from specific repository

#### Claude Code Workflows
- **Manual triggers**: Added `workflow_dispatch` for manual testing
- **Concurrency control**: Prevent simultaneous workflow runs on same PR/issue
- **Better git history**: Increased fetch-depth to 0 for improved context
- **Label filtering**: Optional label-based trigger restrictions

#### Developer Experience
- **Comprehensive documentation**: Detailed CI/CD, release process, and pre-commit setup in README
- **uv.lock committed**: Reproducible builds with locked dependencies
- **Type stubs**: Added types-dateparser for better type coverage

### Fixed
- **Exception chaining**: Proper exception chaining with `from` clause (fixes B904 linting errors)
- **Empty test directories**: CI now handles empty integration test directory gracefully

### Changed
- **Mypy as informational**: Type checking runs but doesn't block CI (pre-existing type errors)
- **Code formatting**: Applied ruff formatting across entire codebase

### Technical Details
- GitHub Actions workflows: `ci.yml`, `release.yml`
- Pre-commit configuration with ruff, mypy (optional), and file validators
- Dependabot configuration for weekly updates
- Concurrency groups to optimize CI runs

## [0.1.0] - 2025-10-21

### Added

#### Core Features
- **Git-backed task management**: Store tasks as markdown files in git repositories
- **TaskWarrior-inspired workflow**: Familiar CLI interface with priorities, tags, and dependencies
- **YAML frontmatter**: Rich metadata support in task files
- **Interactive TUI**: User-friendly prompts with fuzzy autocomplete and validation
- **Multiple repositories**: Organize tasks across different projects or contexts (`tasks-work`, `tasks-personal`, etc.)
- **Beautiful terminal output**: Rich tables with colors and formatting using Rich library

#### Task Management
- `taskrepo add` - Create tasks interactively or with CLI flags
- `taskrepo list` - List tasks with powerful filtering (repo, status, priority, project, assignee, tags)
- `taskrepo edit` - Edit tasks with your preferred editor
- `taskrepo done` - Mark tasks as completed
- `taskrepo delete` - Delete tasks from repositories
- Task dependencies support with `depends` field
- Due dates with smart countdown display
- Default assignee configuration for personal task management

#### Repository Management
- `taskrepo init` - Initialize configuration
- `taskrepo create-repo` - Create new task repositories
- `taskrepo repos` - List all repositories
- `taskrepo sync` - Git pull/push synchronization across repositories

#### Configuration
- `taskrepo config` - View and update configuration
- Configurable sort order for task lists (priority, due, created, modified, status, title, project)
- Default values for priority, status, and assignee
- Parent directory configuration for repository location

#### README Auto-Generation
- **Automatic README.md generation** during `taskrepo sync`
- Task table with clickable links to task files
- **Countdown column** with smart text ("2 days", "3 months", "overdue by X")
- **Emoji visual indicators**:
  - Priority: 🔴 High, 🟡 Medium, 🟢 Low
  - Status: ⏳ pending, 🔄 in_progress, ✅ completed, ❌ cancelled
  - Countdown urgency: ⚠️ overdue, ⏰ urgent (<3 days), 📅 future
- Config-based sorting matching CLI behavior
- Auto-commit README changes during sync

#### Developer Experience
- Short alias: `tsk` command (e.g., `tsk list`, `tsk add`)
- ID mapping for easier task reference (sequential display IDs)
- Comprehensive test suite with pytest
- Code quality tools: ruff for linting and formatting
- Type checking with mypy
- UV package manager support

### Technical Details
- Task IDs: UUID-based unique identifiers
- Task statuses: `pending`, `in_progress`, `completed`, `cancelled`
- Priority levels: `H` (High), `M` (Medium), `L` (Low)
- Assignees: GitHub handle format with `@` prefix
- Timestamps: ISO 8601 format
- Git integration: GitPython for repository operations

### Dependencies
- Python >= 3.10
- click >= 8.0.0
- prompt_toolkit >= 3.0.0
- GitPython >= 3.1.0
- PyYAML >= 6.0.0
- rich >= 13.0.0
- python-dateutil >= 2.8.0
- dateparser >= 1.0.0

[0.2.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.2.0
[0.1.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.1.0
