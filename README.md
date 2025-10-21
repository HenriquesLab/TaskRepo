# TaskRepo

> TaskWarrior-inspired CLI for managing tasks as markdown files in git repositories

TaskRepo is a powerful command-line task management tool that combines the best of TaskWarrior's workflow with the simplicity of markdown and the collaboration features of git.

## Features

- **Git-backed storage**: All tasks are stored as markdown files in git repositories
- **TaskWarrior-inspired**: Familiar workflow with priorities, tags, dependencies, and due dates
- **Rich metadata**: YAML frontmatter for structured task data
- **Interactive TUI**: User-friendly prompts with autocomplete and validation
- **Multiple repositories**: Organize tasks across different projects or contexts
- **GitHub integration**: Associate tasks with GitHub user handles
- **Beautiful output**: Rich terminal formatting with tables and colors
- **Version control**: Full git history and collaboration capabilities

## Installation

### Using pipx (recommended)

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

## Task File Format

Tasks are stored as markdown files with YAML frontmatter:

```markdown
---
id: '001'
title: Fix authentication bug
status: pending
priority: H
project: backend
assignees:
- '@alice'
- '@bob'
tags:
- bug
- security
due: '2025-11-15T00:00:00'
created: '2025-10-20T10:30:00'
modified: '2025-10-20T14:22:00'
depends:
- '002'
---

## Description

The login endpoint is not properly validating JWT tokens.

## Steps to reproduce

1. Attempt to login with expired token
2. Observe that access is granted

## Solution

Update JWT validation middleware to check expiration.
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

## Task Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique task identifier (auto-generated) |
| `title` | string | Task title (required) |
| `status` | string | Task status: `pending`, `in_progress`, `completed`, `cancelled` |
| `priority` | string | Priority level: `H` (High), `M` (Medium), `L` (Low) |
| `project` | string | Project name (optional) |
| `assignees` | list | GitHub user handles (e.g., `@username`) |
| `tags` | list | Tags for categorization |
| `due` | datetime | Due date |
| `created` | datetime | Creation timestamp (auto-generated) |
| `modified` | datetime | Last modification timestamp (auto-updated) |
| `depends` | list | Task IDs this task depends on |
| `description` | string | Markdown description/body |

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
```

### Run tests

```bash
uv run pytest tests/ -v
```

### Code quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type checking
uv run mypy src/taskrepo
```

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
