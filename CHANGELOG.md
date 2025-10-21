# Changelog

All notable changes to TaskRepo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/paxcalpt/taskrepo/releases/tag/v0.1.0
