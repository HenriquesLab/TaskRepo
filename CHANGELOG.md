# Changelog

All notable changes to TaskRepo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2025-10-23

### Added

- **Direct field editing in `tsk edit`**: Edit task fields without opening an editor
  - Single-value fields: `--title`, `--status`, `--priority`, `--project`, `--due`, `--description`, `--parent`
  - List fields - Replace: `--assignees`, `--tags`, `--links`, `--depends`
  - List fields - Add: `--add-assignees`, `--add-tags`, `--add-links`, `--add-depends`
  - List fields - Remove: `--remove-assignees`, `--remove-tags`, `--remove-links`, `--remove-depends`
  - Control: `--edit` flag to open editor after applying changes, `--editor-command` to specify editor
  - Change summary displays old → new values for all modifications
  - Smart defaults: auto-adds `@` prefix to assignees, validates URLs for links
  - Examples:
    ```bash
    tsk edit 1 --priority L                        # Quick priority change
    tsk edit 1 --status in_progress --add-tags urgent
    tsk edit 1 --assignees @alice,@bob             # Replace assignees
    tsk edit 1 --add-assignees @charlie            # Add assignee
    tsk edit 1 --remove-tags old-tag               # Remove tag
    tsk edit 1 --priority H --edit                 # Change then review
    ```

- **CLI command organization**: Commands now grouped by task lifecycle workflow
  - Section 1: Setup & Configuration (init, create-repo, config, config-show)
  - Section 2: Viewing Tasks (list, search, info)
  - Section 3: Managing Tasks (add, edit, ext, done, del)
  - Section 4: Repository Operations (repos, sync)
  - Custom `OrderedGroup` class for organized help display
  - More intuitive for new users following natural workflow

- **Due date clustering**: Group tasks by countdown time buckets instead of exact timestamps
  - New `cluster_due_dates` config option (default: false)
  - Time buckets: overdue (2+ weeks, 1 week, 1-6 days), today, tomorrow, 2-3 days, 4-13 days, 1-3 weeks, 1 month, 2+ months, no due date
  - When enabled, secondary sort fields (like priority) take precedence within each bucket
  - Interactive toggle in `tsk config` (option 10) with detailed explanation
  - Detailed clustering explanation shown in sorting configuration (option 9)
  - Useful for users with many tasks with similar due dates
  - Example: With `sort_by=['due', 'priority']` and clustering enabled, all "today" tasks are grouped together and sorted by priority
  - Displayed in `config-show` command

### Fixed

- **Task display**: Removed duplicate `@@` prefix in task string representation
  - Before: `@@paxcalpt`
  - After: `@paxcalpt`
  - Fixed in `Task.__str__()` method by removing redundant `@` prefix

- **Clustering tiebreaker**: Added exact timestamp tiebreaker when clustering is enabled
  - Tasks in same bucket with same priority now sorted by exact due date
  - Before: Tasks with same priority maintained arbitrary order within bucket
  - After: Sorted by exact timestamp (earliest first) within bucket+priority
  - Example: 4 days → 6 days (10am) → 6 days (2pm) → 7 days → 8 days

- **Pre-commit hooks**: Updated ruff version to v0.14.1 to match CI
  - Prevents formatting inconsistencies between local pre-commit and CI
  - Also updated pre-commit-hooks (v5.0.0 → v6.0.0) and conventional-pre-commit (v3.6.0 → v4.3.0)

- **Type annotations**: Fixed `any` → `Any` in sorting.py for proper type hints

### Changed

- **Config display**: Added clustering status to `tsk config-show` and sorting configuration
- **Editor option naming**: Renamed `--editor` to `--editor-command` in `tsk edit` for clarity (backward compatible with existing usage)

### Technical Details

- Added helper functions in `edit.py`: `parse_list_field()`, `add_to_list_field()`, `remove_from_list_field()`, `show_change_summary()`
- Added `get_due_date_cluster()` in `utils/sorting.py` to convert dates to bucket numbers
- Enhanced sorting logic to respect clustering when enabled for 'due' field
- Added `cluster_due_dates` property to Config class with getter/setter
- Custom `OrderedGroup` class in `cli/main.py` using Click's `formatter.section()`
- Updated `config.py` command to include clustering toggle and explanation
- Enhanced documentation in CLAUDE.md with clustering examples
- All 87 tests passing

## [0.6.2] - 2025-10-23

### Added
- **Assignee sorting**: Sort tasks by assignee with optional preferred user
  - Basic mode: `assignee` - Sort alphabetically by first assignee
  - Preferred mode: `assignee:@username` - Show specified user's tasks first
  - Descending mode: `-assignee:@username` - Reverse priority order
  - Example config: `sort_by: ["assignee:@paxcalpt", "due", "priority"]`
  - Tasks with preferred assignee appear first, then others alphabetically, then unassigned
- **Personalized config examples**: `tsk config` now shows examples using your default_assignee if set
  - Makes configuration more intuitive and immediately useful

### Fixed
- **ID consistency bug**: Fixed display ID mismatch between `tsk add` and `tsk list`
  - Previously: `tsk add` showed ID 17, but `tsk list` showed same task as ID 12
  - Root cause: `add` command saved unsorted tasks to cache, `list` saved sorted tasks
  - Solution: Centralized sorting logic in `utils/sorting.py`, both commands now use same sorted order
  - IDs are now consistent across all commands

### Improved
- **Code organization**: Major refactoring to reduce duplication and improve maintainability
  - Added `utils/display_constants.py` for centralized status/priority display mappings
  - Added `utils/helpers.py::select_task_from_result()` to centralize task selection logic
  - Added `utils/helpers.py::update_cache_and_display_repo()` to standardize cache updates
  - Removed ~140 lines of duplicate code across 5 command files
  - All commands (add, done, edit, delete, info) now use shared helper functions
  - Future updates to task selection or caching now require changes in only 1 place

### Technical Details
- New utility: `src/taskrepo/utils/sorting.py` - Centralized `sort_tasks()` function
- New utility: `src/taskrepo/utils/display_constants.py` - Display constants for status/priority
- Enhanced: `src/taskrepo/utils/helpers.py` - Added `select_task_from_result()` and `update_cache_and_display_repo()`
- Updated: `src/taskrepo/core/config.py` - Validates `assignee`, `assignee:@username`, and descending variants
- Updated: `src/taskrepo/cli/commands/config.py` - Shows personalized examples with default_assignee
- Updated: All command files to use centralized helpers (add, done, edit, delete)
- Added: 13 new unit tests for sorting functionality in `tests/unit/test_sorting.py`
- Total tests: 87 passing

## [0.6.1] - 2025-10-22

### Changed
- **Default sort order**: Changed from priority→due to due→priority
  - Tasks now sorted by due date first (urgent deadlines at top)
  - Then by priority within the same due date
  - Existing users can keep old behavior by updating `~/.TaskRepo/config`

### Technical Details
- Updated `DEFAULT_CONFIG` in `config.py`: `sort_by: ["due", "priority"]`
- Documentation updated in CLAUDE.md to reflect new default

## [0.6.0] - 2025-10-22

### Added
- **Search command (`tsk search`)**: Full-text search across tasks
  - Case-insensitive search across title, description, project, and tags
  - Supports all filter options from list command (--repo, --status, --priority, --assignee, --tag, --project)
  - Excludes completed tasks by default (use --all to include)
  - Example: `tsk search "Tatiana"` or `tsk search "bug" --priority H`
- **Extend command (`tsk ext`)**: Extend task due dates by duration
  - Supports multiple time units: days (d), weeks (w), months (m), years (y)
  - Extend multiple tasks at once with comma-separated IDs
  - Sets due date from today if task has no existing due date
  - Shows old date, extension amount, and new date for each task
  - Example: `tsk ext 4 1w` or `tsk ext 4,5,6 2d`
- **Duration parsing utility**: New `utils/duration.py` module for parsing duration strings
- **Visibility prompt enhancement**: Fixed default value handling in repository visibility prompt

### Improved
- **Task sorting**: Fixed task list to sort globally by priority and due date (not grouped by repository)
  - Tasks now properly sorted H → M → L priority, then by due date within each priority
  - Matches config settings and README generation behavior
- **User experience**: Pressing Enter on visibility prompt now correctly accepts the default (private)
- **Test coverage**: Added comprehensive tests for search and extend commands (21 new tests)

### Technical Details
- New command: `src/taskrepo/cli/commands/search.py` with text search across multiple fields
- New command: `src/taskrepo/cli/commands/extend.py` for due date extensions
- New utility: `src/taskrepo/utils/duration.py` for parsing duration strings (1w, 2d, 3m, 1y)
- Fixed sorting in `display_tasks_table()` to remove hardcoded repository grouping
- Enhanced `prompt_visibility()` to accept input/output parameters for testing
- Set default to "1" for interactive visibility prompt for better UX
- Comprehensive documentation updates in CLAUDE.md for new commands

## [0.5.0] - 2025-10-22

### Added
- **Consistent task IDs across all views**: Display IDs (1, 2, 3...) now remain consistent whether you use filtered or unfiltered views
  - Task 14 in `tsk list` is also task 14 in `tsk list --repo foo` or `tsk list --priority H`
  - IDs are resolved through a cache mapping display IDs to task UUIDs
- **Completed task IDs**: `tsk done` (without arguments) shows completed tasks with IDs continuing after active tasks
  - If active tasks are 1-15, completed tasks show as 16, 17, 18, etc.
  - Provides clear visual separation between active and completed tasks
- **Task file path in info command**: `tsk info` now displays the full file path to the task markdown file
- **Automatic cache refresh**: All mutating commands automatically update the ID cache in the background
  - `tsk add`, `tsk edit`, `tsk done`, `tsk del` now update cache while showing focused repo views
  - Newly added tasks get display IDs immediately without needing to run `tsk list`
- **Task list after sync**: `tsk sync` now displays all active tasks after syncing, updating the cache
- **Consolidated configuration**: All config and cache files now organized under `~/.TaskRepo/`
  - `~/.TaskRepo/config` (main configuration)
  - `~/.TaskRepo/id_cache.json` (display ID mappings)
  - `~/.TaskRepo/update_check_cache.json` (update check timestamps)
  - Automatic migration from legacy file locations

### Improved
- **User experience**: No need to manually run `tsk list` after adding/editing tasks to get consistent IDs
- **Command output**: Mutating commands show focused repository view while keeping cache fresh
- **File organization**: Cleaner home directory with all TaskRepo files in one location
- **ID consistency**: All commands use the same ID resolution mechanism through `find_task_by_title_or_id()`

### Technical Details
- New module: `src/taskrepo/utils/paths.py` for centralized path management
- New function: `get_cache_size()` in id_mapping.py to get active task count
- New function: `get_display_id_from_uuid()` for reverse ID lookup
- Cache management: `save_id_cache()` called by commands to maintain consistency
- Display logic: `display_tasks_table()` supports `id_offset` parameter for completed tasks
- Legacy file migration: Automatic one-time migration on first run
- Updated all mutating commands to refresh cache before displaying filtered views
- Comprehensive documentation updates in CLAUDE.md

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

[0.6.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.6.1
[0.6.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.6.0
[0.5.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.5.0
[0.4.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.4.0
[0.3.2]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.3.2
[0.3.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.3.1
[0.2.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.2.0
[0.1.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.1.0
