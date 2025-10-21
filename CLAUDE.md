# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TaskRepo is a TaskWarrior-inspired CLI for managing tasks as markdown files in git repositories. Tasks are stored with YAML frontmatter in markdown files, organized into git-backed repositories, providing both structure and version control.

## Development Commands

### Setup
```bash
# Install with UV (recommended)
uv sync
uv pip install -e .

# Install with dev dependencies
uv sync --extra dev
```

### Testing
```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/unit/test_task.py -v

# Run with coverage
uv run pytest tests/ -v --cov=taskrepo --cov-report=term-missing
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Fix linting issues automatically
uv run ruff check --fix .

# Type checking
uv run mypy src/taskrepo
```

### Running the CLI
```bash
# Run directly from source
uv run taskrepo --help

# After installation
taskrepo --help
```

## Architecture

### Core Components

**Task Model** (`src/taskrepo/core/task.py`)
- `Task` dataclass represents individual tasks with YAML frontmatter + markdown body
- Supports parsing from/to markdown with `from_markdown()` and `to_markdown()`
- Task files are named `task-{id}.md` (e.g., `task-001.md`)
- IDs are zero-padded 3-digit strings generated sequentially
- Task validation ensures status and priority are valid

**Repository Management** (`src/taskrepo/core/repository.py`)
- `Repository` class represents a single task repository (directory named `tasks-{name}`)
- `RepositoryManager` discovers and manages multiple repositories under a parent directory
- Each repository is a git repository with a `tasks/` subdirectory containing task markdown files
- Repositories provide helper methods to get projects, assignees, and tags for autocomplete

**Configuration** (`src/taskrepo/core/config.py`)
- Config stored in `~/.taskreporc` as YAML
- Manages parent directory path and defaults (priority, status, assignee)
- **default_assignee feature**: When set, automatically adds this GitHub handle to new tasks if no assignees specified

**CLI Structure** (`src/taskrepo/cli/`)
- Built with Click framework
- Commands are in `cli/commands/` directory: `add`, `list`, `edit`, `done`, `sync`
- Main entry point: `cli/main.py` with `cli()` group function
- Console script registered in pyproject.toml as `taskrepo`

**TUI Prompts** (`src/taskrepo/tui/prompts.py`)
- Interactive prompts using `prompt_toolkit`
- Provides fuzzy autocomplete for projects, assignees, tags
- Uses existing values from repository for smart suggestions
- Validates input (dates, priorities, titles)

### Data Flow

1. **Adding a Task**:
   - User runs `taskrepo add` (interactive) or `taskrepo add --repo work --title "..." --assignees @alice` (non-interactive)
   - If default_assignee is configured and no assignees provided, it's automatically added
   - Repository generates next task ID using `next_task_id()` (finds max ID + 1)
   - Task object created and saved to `tasks/task-{id}.md`
   - File written with YAML frontmatter + markdown description

2. **Listing Tasks**:
   - Repository scans `tasks/*.md` files
   - Each file parsed into Task object
   - Tasks filtered by repo, status, priority, project, assignee, or tags
   - Results displayed in Rich formatted table

3. **Syncing with Git**:
   - Each repository is a git repo
   - Sync command pulls and optionally pushes changes
   - Enables collaboration and version control of tasks

### Task File Format

Tasks use YAML frontmatter with markdown body:

```markdown
---
id: '001'
title: Task title
status: pending
priority: M
project: backend
assignees:
- '@alice'
tags:
- bug
due: '2025-11-15T00:00:00'
created: '2025-10-20T10:30:00'
modified: '2025-10-20T14:22:00'
depends:
- '002'
---

## Description

Markdown content here...
```

### Key Design Decisions

- **Task IDs are repository-scoped**: Each repository has its own sequence starting at 001
- **Assignees use GitHub handles**: Always prefixed with `@` for consistency
- **Status values**: `pending`, `in_progress`, `completed`, `cancelled` (enforced by Task validation)
- **Priority values**: `H` (High), `M` (Medium), `L` (Low) (enforced by Task validation)
- **Timestamps are ISO 8601**: Stored as strings in YAML, parsed to datetime objects
- **Default assignee feature**: Config option `default_assignee` automatically adds a GitHub handle to tasks when no assignees specified (useful for personal task management)

## Testing Notes

- Unit tests in `tests/unit/` cover Task and Repository models
- Tests should use temporary directories for repositories
- Task parsing/serialization is critical - test edge cases (missing fields, invalid dates, etc.)

## Configuration File

Default config at `~/.taskreporc`:
```yaml
parent_dir: ~/tasks
default_priority: M
default_status: pending
default_assignee: null  # Can be set to @username for automatic assignment
```
