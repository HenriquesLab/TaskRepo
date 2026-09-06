---
name: taskrepo
description: Task management using TaskRepo (tsk command), a TaskWarrior-inspired system that manages tasks as markdown files in git repositories. Use when the user needs to list, add, edit, search, complete, extend, archive, delete, or manage tasks through the tsk command-line interface. Supports interactive TUI, repository management, and GitHub integration.
---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Core Concepts](#core-concepts)
- [Task File Format](#task-file-format)
- [Description](#description)
- [CLI Commands](#cli-commands)
  - [`tsk add` - Add a new task](#tsk-add---add-a-new-task)
  - [`tsk list` - List tasks](#tsk-list---list-tasks)
  - [`tsk info` - Display detailed task information](#tsk-info---display-detailed-task-information)
  - [`tsk search` - Search tasks by text](#tsk-search---search-tasks-by-text)
  - [`tsk tui` - Interactive TUI](#tsk-tui---interactive-tui)
  - [`tsk edit` - Edit a task](#tsk-edit---edit-a-task)
  - [`tsk in-progress` - Mark tasks as in progress](#tsk-in-progress---mark-tasks-as-in-progress)
  - [`tsk done` - Mark tasks as completed](#tsk-done---mark-tasks-as-completed)
  - [`tsk cancelled` - Mark tasks as cancelled](#tsk-cancelled---mark-tasks-as-cancelled)
  - [`tsk archive` - Archive tasks](#tsk-archive---archive-tasks)
  - [`tsk unarchive` - Restore archived tasks](#tsk-unarchive---restore-archived-tasks)
  - [`tsk del` - Delete tasks permanently](#tsk-del---delete-tasks-permanently)
  - [`tsk ext` - Extend or set task due dates](#tsk-ext---extend-or-set-task-due-dates)
  - [`tsk move` - Move tasks between repositories](#tsk-move---move-tasks-between-repositories)
  - [`tsk sync` - Sync with git](#tsk-sync---sync-with-git)
  - [`tsk config` - Interactive configuration](#tsk-config---interactive-configuration)
  - [`tsk config-show` - Show current configuration](#tsk-config-show---show-current-configuration)
  - [`tsk llm-info` - LLM CLI reference](#tsk-llm-info---llm-cli-reference)
  - [`tsk init` - Initialize TaskRepo](#tsk-init---initialize-taskrepo)
  - [`tsk create-repo` - Create new task repository](#tsk-create-repo---create-new-task-repository)
  - [`tsk repos` - List all repositories](#tsk-repos---list-all-repositories)
  - [`tsk repos-search` - Search GitHub for repositories](#tsk-repos-search---search-github-for-repositories)
  - [`tsk upgrade` - Upgrade TaskRepo](#tsk-upgrade---upgrade-taskrepo)
- [Configuration Details](#configuration-details)
  - [Sorting (`sort_by`)](#sorting-sort_by)
  - [Due Date Clustering (`cluster_due_dates`)](#due-date-clustering-cluster_due_dates)
- [Common Workflows](#common-workflows)
  - [Personal task management with default assignee](#personal-task-management-with-default-assignee)
  - [Finding tasks across all repositories](#finding-tasks-across-all-repositories)
  - [Managing task due dates](#managing-task-due-dates)
  - [Collaborating with git](#collaborating-with-git)
- [Tips and Best Practices](#tips-and-best-practices)
- [Architecture Notes](#architecture-notes)
- [Integration with Other Skills](#integration-with-other-skills)
  - [Gmail Control Skill](#gmail-control-skill)
  - [Google Tasks Control Skill](#google-tasks-control-skill)
- [Development and Customization](#development-and-customization)
  - [Source Code Location](#source-code-location)
  - [Development Environment Setup](#development-environment-setup)
  - [Non-Interactive Mode Modifications](#non-interactive-mode-modifications)
  - [Batch Operations with Modified Version](#batch-operations-with-modified-version)
  - [Alternative: Using Flags](#alternative-using-flags)
- [When to Use This Skill](#when-to-use-this-skill)


# TaskRepo Skill

TaskRepo is a TaskWarrior-inspired CLI for managing tasks as markdown files in git-backed repositories. Tasks are stored with YAML frontmatter in markdown files, providing both structure and version control.

## Prerequisites

- TaskRepo installed separately: `pip install taskrepo`
- Git for version control
- Optional: Gmail integration requires gmail-control skill (macOS only)
- Optional: GitHub integration requires `gh` CLI tool

## Core Concepts

**Task Structure:**
- Tasks are markdown files with YAML frontmatter: `task-{uuid}.md` (e.g., `task-a3f2e1d9-4b7c-4e3f-9a1b-2c3d4e5f6a7b.md`)
- UUIDs are globally unique identifiers generated via `uuid.uuid4()`
- Stored in `tasks/` subdirectory within each repository
- Each repository is a git repository named `tasks-{name}`

**Display IDs:**
- Display IDs (1, 2, 3...) are assigned based on active tasks across ALL repositories
- IDs are cached in `~/.TaskRepo/id_cache.json` for consistent referencing
- **ID Stability System**:
  - **Stable mode** (used by `tsk add`, `tsk edit`, `tsk done`, `tsk del`, `tsk archive`): Preserves existing IDs, fills gaps for new tasks
  - **Rebalance mode** (used by `tsk list` without filters, `tsk sync`): Reassigns sequential IDs from scratch
  - Gap filling: When tasks are deleted, new tasks reuse freed IDs (e.g., if task #5 deleted, next new task gets ID 5)
- Completed tasks displayed with IDs continuing after active tasks (e.g., 16, 17, 18 if active tasks are 1-15)

**Configuration:**
- Location: `~/.TaskRepo/config` (YAML format)
- Key settings:
  - `parent_dir`: Root directory for all task repositories
  - `default_priority`: M (H/M/L)
  - `default_status`: pending
  - `default_assignee`: GitHub handle for auto-assignment (e.g., @username)
  - `default_github_org`: GitHub org/owner for automatic repository creation
  - `sort_by`: List of fields to sort by (priority, due, created, modified, status, title, project, assignee)
  - `cluster_due_dates`: Group tasks by countdown buckets instead of exact dates

## Task File Format

```markdown
---
uuid: 'a3f2e1d9-4b7c-4e3f-9a1b-2c3d4e5f6a7b'
title: Task title
status: pending
priority: M
project: backend
assignees:
- '@alice'
tags:
- bug
links:
- https://github.com/org/repo/issues/123
- https://mail.google.com/mail/u/0/#inbox/abc123
due: '2025-11-15T00:00:00'
created: '2025-10-20T10:30:00'
modified: '2025-10-20T14:22:00'
depends:
- 'b4e8f3a1-5c6d-4e2f-8a9b-1c2d3e4f5a6b'
---

## Description

Markdown content here...
```

**Valid field values:**
- **status**: `pending`, `in-progress`, `completed`, `cancelled`
- **priority**: `H` (High), `M` (Medium), `L` (Low)
- **assignees**: GitHub handles with `@` prefix (e.g., `@alice`) - supports multiple assignees
- **links**: Valid HTTP/HTTPS URLs (GitHub issues, PRs, emails, documentation) - supports multiple links
- **dates**: ISO 8601 format timestamps

## CLI Commands

### `tsk add` - Add a new task

**Interactive mode:**
```bash
tsk add
```
Prompts for all task fields with fuzzy autocomplete for projects, assignees, tags.

**Non-interactive mode:**
```bash
tsk add --repo work --title "Fix login bug" --assignees @alice --priority H --project backend --tags bug,urgent --due tomorrow

# With multiple links (comma-separated)
tsk add --repo work --title "Fix login bug" --assignees @alice --priority H --links "https://github.com/org/repo/issues/123,https://mail.google.com/mail/u/0/#inbox/abc123"
```

**Behavior:**
- If `default_assignee` configured and no assignees provided, it's automatically added
- Repository generates next task ID (finds max ID + 1)
- Shows the new task in a table and updates ID cache immediately
- **Multiple links**: Use comma-separated URLs with `--links` flag (e.g., `--links "url1,url2,url3"`)

### `tsk list` - List tasks

**Syntax:**
```bash
tsk list [OPTIONS]
```

**Options:**
- `--repo, -r`: Filter by repository name
- `--status, -s`: Filter by status (pending/in-progress/completed/cancelled)
- `--priority`: Filter by priority (H/M/L)
- `--assignee, -a`: Filter by assignee (@username)
- `--tag, -t`: Filter by tag
- `--project, -p`: Filter by project name
- `--archived`: Show archived tasks
- `--ready`: Filter for ready tasks (actionable tasks whose dependencies are completed)
- `--blocked`: Filter for blocked tasks (tasks waiting on incomplete dependencies)
- `--json`: Output as JSON (v0.11.0+) — machine-readable, no column truncation. Ideal for scripting and LLM consumption.

**Examples:**
```bash
# List all active tasks (updates ID cache)
tsk list

# List high-priority tasks
tsk list --priority H

# List tasks for specific assignee
tsk list --assignee @alice

# List tasks in specific repo
tsk list --repo work

# List completed tasks
tsk list --status completed

# JSON output for scripting (v0.11.0+)
tsk list --json -s pending | jq '.[] | select(.priority=="H")'

# JSON output for LLM analysis (no truncation, full descriptions)
tsk list --json --priority H

# List ready (unblocked) tasks for agents/execution
tsk list --ready --json

# List blocked tasks waiting on dependencies
tsk list --blocked
```

**Output (default):**
Displays tasks in Rich formatted table with display IDs. Without filters, updates the ID cache.

**Output (`--json`):**
Emits a JSON array on stdout (empty result → `[]`). Each object contains:
- `id` (int): short numeric display ID — same as the table view
- `uuid` (str): stable underlying identifier
- `title`, `status`, `priority`, `repo`, `project` (str|null)
- `assignees`, `tags`, `links`, `depends` (arrays of strings)
- `due`, `created`, `modified` (ISO 8601 timestamps or null)
- `parent` (str|null): parent UUID for subtasks
- `description` (str): full markdown body, untruncated

Merge-conflict warnings are redirected to stderr in JSON mode so stdout stays valid JSON. **Prefer `--json` over parsing the table output** — the table truncates columns and is not stable across versions.

### `tsk info` - Display detailed task information

**Syntax:**
```bash
tsk info TASK_ID [OPTIONS]
```

**Behavior:**
- Displays comprehensive information about a single task
- Shows all task fields including metadata (created, modified timestamps)
- Uses display ID or UUID to find task
- Handles multiple matches by prompting user to select

**Options:**
- `--repo, -r`: Limit search to specific repository

**Examples:**
```bash
# Show detailed info for task by display ID
tsk info 5

# Show info for task in specific repo
tsk info 10 --repo work

# Show info using UUID
tsk info a1b2c3d4-...
```

**Output:**
Displays all task fields in a formatted view including title, status, priority, project, assignees, tags, links, due date, created/modified timestamps, dependencies, and full description.

### `tsk search` - Search tasks by text

**Syntax:**
```bash
tsk search QUERY [OPTIONS]
```

**Search behavior:**
- **Case-insensitive** search
- **Search scope**: Title, description, project name, tags
- **Default exclusion**: Completed tasks excluded (use `--all` to include)

**Options:**
All standard filter options from `list` command:
- `--repo, -r`, `--status, -s`, `--priority`, `--assignee, -a`, `--tag, -t`, `--project, -p`, `--all`

**Examples:**
```bash
# Find all tasks mentioning "Tatiana"
tsk search "Tatiana"

# Search only in specific repository
tsk search "authentication" --repo backend

# Find high-priority bugs
tsk search "bug" --priority H

# Search with multiple filters
tsk search "fellowship" --tag urgent --status pending

# Include completed tasks in search
tsk search "migration" --all
```

### `tsk tui` - Interactive TUI

**Syntax:**
```bash
tsk tui [OPTIONS]
```

**Behavior:**
- Launches full-screen interactive terminal user interface
- Provides keyboard-driven task management
- Supports multi-select operations
- Real-time task viewing and filtering
- Tree view for hierarchical organization
- **Auto-reload**: Automatically detects file changes every 2 seconds and refreshes

**Keyboard Shortcuts:**
- **Navigation**: ↑/↓ (navigate tasks), ←/→ (switch between repos/projects/assignees)
- **Views**: Tab (switch view type), t (toggle tree view)
- **Task Operations**: n (new task), e (edit), d (mark done), p (toggle in-progress/pending), c (cancel), a (archive), m (move), x (delete)
- **Other**: / (filter tasks), s (sync with git), Space (multi-select), q/Esc (quit)

**Options:**
- `--repo, -r`: Start in specific repository

**Examples:**
```bash
# Launch TUI
tsk tui

# Launch TUI for specific repository
tsk tui --repo work
```

**Features:**
- Visual task browsing with color-coded priorities
- Quick status changes with single keystrokes
- Multi-task operations (select multiple tasks with Space, then apply operation)
- Integrated sync functionality
- Filter tasks on the fly

### `tsk edit` - Edit a task

**Syntax:**
```bash
tsk edit TASK_ID [OPTIONS]
```

**Behavior:**
- Uses display ID or UUID to find task
- Opens task file in configured editor (or `$EDITOR`)
- Handles multiple matches by prompting user to select
- Updates `modified` timestamp automatically

**Options:**
- `--repo, -r`: Limit search to specific repository

**Examples:**
```bash
# Edit task by display ID
tsk edit 5

# Edit task in specific repo
tsk edit 10 --repo work
```

### `tsk in-progress` - Mark tasks as in progress

**Syntax:**
```bash
tsk in-progress TASK_IDS [OPTIONS]
```

**Behavior:**
- Supports comma-separated IDs (e.g., `4,5,6`)
- Sets status to `in-progress`
- Updates `modified` timestamp

**Options:**
- `--repo, -r`: Limit search to specific repository

**Examples:**
```bash
# Mark single task as in progress
tsk in-progress 4

# Mark multiple tasks as in progress
tsk in-progress 4,5,6

# Mark task as in progress in specific repo
tsk in-progress 10 --repo work
```

### `tsk done` - Mark tasks as completed

**Syntax:**
```bash
tsk done TASK_IDS [OPTIONS]
```

**Behavior:**
- Supports comma-separated IDs (e.g., `4,5,6`)
- Moves tasks to `done/` subdirectory
- Sets status to `completed`
- Updates `modified` timestamp

**Options:**
- `--repo, -r`: Limit search to specific repository

**Examples:**
```bash
# Mark single task as done
tsk done 4

# Mark multiple tasks as done
tsk done 4,5,6

# Mark task as done in specific repo
tsk done 10 --repo work
```

**Display:**
Shows completed tasks with IDs continuing after active tasks (e.g., if active tasks are 1-15, completed tasks show as 16, 17, 18).

### `tsk cancelled` - Mark tasks as cancelled

**Syntax:**
```bash
tsk cancelled TASK_IDS [OPTIONS]
```

**Behavior:**
- Supports comma-separated IDs (e.g., `4,5,6`)
- Sets status to `cancelled`
- Updates `modified` timestamp

**Options:**
- `--repo, -r`: Limit search to specific repository

**Examples:**
```bash
# Mark single task as cancelled
tsk cancelled 4

# Mark multiple tasks as cancelled
tsk cancelled 4,5,6

# Mark task as cancelled in specific repo
tsk cancelled 10 --repo work
```

### `tsk archive` - Archive tasks

**Syntax:**
```bash
tsk archive [TASK_IDS...] [OPTIONS]
```

**Behavior:**
- Without arguments: Lists all archived tasks
- With task IDs: Archives specified tasks (moves to `archive/` subdirectory)
- Supports comma-separated IDs (e.g., `4,5,6`)
- Archived tasks are hidden from normal lists but preserved in repository
- Maintains task status (archived tasks can be pending, completed, etc.)

**Options:**
- `--repo, -r`: Limit to specific repository
- `--all-completed`: Archive all tasks with status 'completed'
- `--yes, -y`: Automatically archive subtasks without prompting

**Examples:**
```bash
# List archived tasks
tsk archive

# Archive single task
tsk archive 4

# Archive multiple tasks
tsk archive 4,5,6

# Archive task in specific repo
tsk archive 10 --repo work

# Archive all completed tasks at once
tsk archive --all-completed

# Archive all completed tasks in a specific repo
tsk archive --all-completed --repo work
```

**Use cases:**
- Remove clutter from active task lists without deleting
- Preserve historical tasks for reference
- Clean up completed projects while maintaining records

### `tsk unarchive` - Restore archived tasks

**Syntax:**
```bash
tsk unarchive TASK_IDS [OPTIONS]
```

**Behavior:**
- Restores tasks from `archive/` back to `tasks/` subdirectory
- Supports comma-separated IDs (e.g., `4,5,6`)
- Tasks regain their original status
- Updates `modified` timestamp

**Options:**
- `--repo, -r`: Limit to specific repository

**Examples:**
```bash
# Unarchive single task
tsk unarchive 4

# Unarchive multiple tasks
tsk unarchive 4,5,6

# Unarchive task in specific repo
tsk unarchive 10 --repo work
```

### `tsk del` - Delete tasks permanently

**Syntax:**
```bash
tsk del TASK_ID [OPTIONS]
```

**Behavior:**
- Permanently deletes a task file from the repository
- Requires confirmation by default (use `--force` to skip)
- Uses display ID or UUID to find task
- Handles multiple matches by prompting user to select
- **Warning**: This action cannot be undone (unless committed to git)

**Options:**
- `--repo, -r`: Limit search to specific repository
- `--force, -f`: Skip confirmation prompt

**Examples:**
```bash
# Delete task with confirmation
tsk del 5

# Delete without confirmation
tsk del 5 --force

# Delete task in specific repo
tsk del 10 --repo work
```

**Best practice:**
Consider using `tsk archive` instead of `tsk del` to preserve task history.

### `tsk ext` - Extend or set task due dates

**Syntax:**
```bash
tsk ext TASK_IDS DATE_OR_DURATION [OPTIONS]
```

**Duration formats** (extends from current due date or today):
- `d` = days (e.g., `3d` for 3 days)
- `w` = weeks (e.g., `1w` or `2w`)
- `m` = months (e.g., `3m`, calculated as 30 days)
- `y` = years (e.g., `1y`, calculated as 365 days)

**Absolute date formats** (sets due date directly):
- **Keywords**: `today`, `tomorrow`, `yesterday`, `next week`, `next month`, `next year`
- **ISO dates**: `2025-10-30` (YYYY-MM-DD)
- **Natural dates**: `Nov 1`, `October 30 2025`

**Options:**
- `--repo, -r`: Limit search to specific repository

**Examples:**
```bash
# Set due date to tomorrow (absolute)
tsk ext 4 tomorrow

# Extend by 1 week from current due date (relative)
tsk ext 4 1w

# Extend multiple tasks by 2 days
tsk ext 4,5,6 2d

# Set due date to next week
tsk ext 10 "next week"

# Set due date to specific ISO date
tsk ext 7 2025-11-15

# Set due date using natural language
tsk ext 8 "Nov 1"
```

**Output:**
Shows old due date, extension/new date, and updated task table.

### `tsk move` - Move tasks between repositories

**Syntax:**
```bash
tsk move TASK_IDS --to TARGET_REPO [OPTIONS]
```

**Behavior:**
- Moves one or more tasks to a different repository
- Supports comma-separated IDs (e.g., `4,5,6`)
- Handles subtasks: Prompts user whether to move subtasks together or independently
- Warns about dependencies: Alerts if other tasks depend on the task being moved
- Preserves archived status: Archived tasks remain in archive folder after move
- Updates `modified` timestamp
- Works with multi-selection in TUI ([m] key)

**Options:**
- `--to`: Target repository name (required)
- `--repo, -r`: Source repository to search in

**Examples:**
```bash
# Move single task to another repository
tsk move 5 --to personal

# Move multiple tasks
tsk move 4,5,6 --to work

# Move task from specific source repo
tsk move 10 --to personal --repo work
```

**Use cases:**
- Reorganize tasks across repositories
- Move personal tasks from work repo
- Consolidate related tasks
- Rebalance workload across team repos

### `tsk sync` - Sync with git

**Syntax:**
```bash
tsk sync [OPTIONS]
```

**Behavior:**
- **Conflict detection**: Checks for merge conflicts before pulling
- **Smart merging**: Automatically resolves conflicts when possible
  - Uses `modified` timestamp to choose newer values
  - Creates union of list fields (assignees, tags, links)
  - Interactive resolution for description conflicts
- Pulls changes from remote repository
- Optionally pushes local changes with `--push`
- **ID rebalancing**: Rebalances display IDs to sequential order (1, 2, 3...) after sync
- Shows all tasks after sync and displays "IDs rebalanced to sequential order" message

**Options:**
- `--repo, -r`: Sync specific repository only
- `--push/--no-push`: Push local changes after pulling (default: True)
- `--auto-merge/--no-auto-merge`: Automatically merge conflicts when possible (default: True)
- `--strategy`: Conflict resolution strategy
  - `auto` (default): Smart merge, interactive fallback
  - `local`: Always keep local version
  - `remote`: Always keep remote version
  - `interactive`: Always prompt for resolution

**Conflict resolution:**
When conflicts are detected, the interactive resolver displays:
- Side-by-side comparison of local vs remote versions
- Highlighted conflicting fields
- Options: Keep [L]ocal, [R]emote, [N]ewer, [M]anual merge, [E]dit

**Examples:**
```bash
# Pull changes from all repos (auto-merge conflicts)
tsk sync

# Pull and push all repos
tsk sync --push

# Sync specific repo
tsk sync --repo work

# Sync without auto-merge (always prompt)
tsk sync --no-auto-merge

# Always keep local version on conflict
tsk sync --strategy local

# Always prompt for conflicts
tsk sync --strategy interactive
```

### `tsk config` - Interactive configuration

**Syntax:**
```bash
tsk config [OPTIONS]
```

**Options:**
- `--show`: Display current configuration without entering interactive menu (non-interactive mode)

**Behavior:**
- Launches an interactive menu for managing TaskRepo configuration
- All settings are stored in `~/.TaskRepo/config` (YAML format)
- Changes are saved immediately after each selection
- Menu options include:
  1. View current settings
  2. Change parent directory
  3. Set default priority (H/M/L)
  4. Set default status
  5. Set default assignee (GitHub handle)
  6. Set default repository
  7. Set default GitHub organization
  8. Set default editor
  9. Configure task sorting
  10. Toggle due date clustering
  11. Reset to defaults
  12. Exit

**Examples:**
```bash
# Open interactive configuration menu
tsk config

# Display configuration without interactive menu
tsk config --show

# Then in interactive mode: select option 7 to set default GitHub organization
# Or select option 5 to set default assignee
```

**Common mistake:**
```bash
# ❌ WRONG - config doesn't accept value arguments directly
tsk config default_github_org myorg

# ✓ CORRECT - use interactive menu or --show flag
tsk config        # Interactive: select option 7, enter "myorg"
tsk config --show # Non-interactive: just displays current config
```

### `tsk config-show` - Show current configuration

**Syntax:**
```bash
tsk config-show
```

**Behavior:**
- Displays all current configuration settings in a formatted view
- Non-interactive (just displays, doesn't prompt for changes)
- Shows parent directory, defaults, and sorting configuration
- Useful for quickly checking settings or debugging

**Examples:**
```bash
# View current configuration
tsk config-show
```

**Output:**
Shows all config values including parent_dir, default_priority, default_status, default_assignee, default_github_org, default_editor, sort_by, and cluster_due_dates.

**Note:** This command is equivalent to `tsk config --show` and is kept for backward compatibility.

### `tsk llm-info` - LLM CLI reference

**Syntax:**
```bash
tsk llm-info
```

**Behavior:**
- Displays comprehensive CLI reference designed for LLM assistants
- **Dynamic content**: Automatically includes all commands from `tsk --help`
- **Current configuration**: Shows user's actual config via integration with config display
- Includes task properties, command examples, filtering options, and workflows
- Purely user-facing information (no source code details)
- Always up-to-date with latest commands and user's configuration

**Examples:**
```bash
# Display full LLM reference
tsk llm-info
```

**Output sections:**
1. **Available Commands**: Dynamic list from `tsk --help`
2. **Current Configuration**: User's actual config settings
3. **Task Properties**: Statuses, priorities, date formats, display IDs
4. **Command Examples**: Curated real-world usage examples
5. **Filtering & Searching**: Filter flags and search syntax
6. **Common Workflows**: Step-by-step task management patterns
7. **Quick Tips for LLMs**: Best practices for assisting users

**Use case:**
Designed for LLMs (like Claude) to quickly understand TaskRepo's capabilities and the user's specific configuration when helping with task management.

### `tsk init` - Initialize TaskRepo

**Syntax:**
```bash
tsk init
```

**Behavior:**
- Interactive setup wizard for first-time TaskRepo configuration
- Creates `~/.TaskRepo/config` file
- Prompts for parent directory where task repositories will be stored
- Sets up default values for priority, status, etc.
- Creates parent directory if it doesn't exist

**Examples:**
```bash
# Initialize TaskRepo configuration
tsk init
```

**When to use:**
Run this command once when first setting up TaskRepo on a new system.

### `tsk create-repo` - Create new task repository

**Syntax:**
```bash
tsk create-repo
```

**Behavior:**
- Interactive wizard to create a new task repository
- Prompts for repository name
- Creates directory structure: `{parent_dir}/tasks-{name}/`
- Initializes as git repository
- Creates `tasks/`, `done/`, and `archive/` subdirectories
- **GitHub integration defaults to "yes"**: Prompts "Create GitHub repository? [Y/n]:"
- Uses `default_github_org` from config if set
- Automatically creates GitHub repository and sets up remote (unless declined)

**Examples:**
```bash
# Create new repository interactively
tsk create-repo
```

**Workflow:**
1. Prompts for repository name (e.g., "work", "personal")
2. Creates `tasks-work/` directory
3. Initializes git
4. Optionally creates GitHub repo and adds remote

### `tsk repos` - List all repositories

**Syntax:**
```bash
tsk repos
```

**Behavior:**
- Lists all task repositories found in parent directory
- Shows repository names (without "tasks-" prefix)
- Displays count of active tasks in each repository
- Indicates git status (clean, uncommitted changes, etc.)

**Examples:**
```bash
# List all task repositories
tsk repos
```

**Output:**
Table showing repository name, task count, and git status for each repository.

### `tsk repos-search` - Search GitHub for repositories

**Syntax:**
```bash
tsk repos-search [ORG] [OPTIONS]
```

**Behavior:**
- Searches GitHub for repositories matching `tasks-*` pattern
- Shows which repositories are already cloned locally
- Allows you to clone new repositories interactively
- Uses `default_github_org` from config if org not specified

**Options:**
- `--list-only`: Just list repositories without prompting to clone

**Examples:**
```bash
# Search in default GitHub org (from config)
tsk repos-search

# Search in specific org
tsk repos-search myorg

# List only (don't prompt to clone)
tsk repos-search myorg --list-only
```

**Workflow:**
1. Queries GitHub API for `tasks-*` repositories
2. Shows which are already cloned
3. Prompts to clone any not yet local
4. Automatically sets up git remote

### `tsk upgrade` - Upgrade TaskRepo

**Syntax:**
```bash
tsk upgrade
```

**Behavior:**
- Upgrades taskrepo to the latest version
- Uses pip/uv to fetch and install latest release
- Shows current and new version numbers
- Automatically restarts if needed

**Examples:**
```bash
# Upgrade to latest version
tsk upgrade
```

**Notes:**
- Checks PyPI for latest version
- Preserves configuration and task data
- Safe to run anytime

## Configuration Details

### Sorting (`sort_by`)

Tasks are sorted by the specified fields in order.

**Supported fields:**
- `priority`, `due`, `created`, `modified`, `status`, `title`, `project`, `assignee`
- Prefix with `-` for descending order (e.g., `-priority`, `-due`)

**Assignee sorting modes:**

1. **Basic alphabetical** (`assignee`):
   - Tasks sorted by first assignee alphabetically
   - Unassigned tasks appear last

2. **Preferred assignee** (`assignee:@username`):
   - Tasks assigned to specified user appear first
   - Then other assigned tasks (alphabetically)
   - Then unassigned tasks

3. **Descending order** (`-assignee` or `-assignee:@username`):
   - Reverses the priority groups

**Example config:**
```yaml
sort_by:
- assignee:@paxcalpt  # @paxcalpt's tasks first
- due
- priority
```

### Due Date Clustering (`cluster_due_dates`)

When enabled, tasks are grouped by countdown buckets instead of exact due dates, allowing secondary sort fields (like priority) to take precedence within each time bucket.

**Buckets:**
- Overdue (2+ weeks, 1 week, 1-6 days)
- Today
- Tomorrow
- 2-3 days
- 4-13 days
- 1-3 weeks
- 1 month
- 2+ months
- No due date

**Example:**
```yaml
sort_by:
- due
- priority
cluster_due_dates: true
```

With clustering enabled, tasks due "today" are sorted by priority before tasks due "tomorrow".

## Common Workflows

### Personal task management with default assignee

1. Configure default assignee:
```yaml
default_assignee: @yourhandle
```

2. Add tasks without specifying assignee:
```bash
tsk add --repo personal --title "Review PR" --priority H --due tomorrow
```
The task will automatically be assigned to @yourhandle.

### Finding tasks across all repositories

```bash
# Search by keyword
tsk search "authentication"

# List all high-priority tasks
tsk list --priority H

# List tasks assigned to you
tsk list --assignee @yourhandle

# List overdue tasks (use filtering after tsk list)
tsk list
```

### Managing task due dates

```bash
# Add task with due date
tsk add --repo work --title "Deploy feature" --due "next week"

# Extend existing task
tsk ext 5 1w

# Set specific due date
tsk ext 5 2025-11-15

# Extend multiple tasks
tsk ext 3,4,5 2d
```

### Collaborating with git

```bash
# Pull latest tasks
tsk sync

# Mark tasks as done
tsk done 4,5,6

# Push your changes
tsk sync --push
```

## Tips and Best Practices

1. **Use display IDs**: Reference tasks by their display ID (1, 2, 3...) shown in `tsk list`

2. **Update ID cache regularly**: Run `tsk list` without filters to ensure display IDs are current

3. **Search before adding**: Use `tsk search` to avoid duplicate tasks

4. **Use tags for organization**: Tags help categorize tasks across projects (e.g., `urgent`, `bug`, `feature`)

5. **Link related resources**: Add GitHub issues, PRs, email threads, or documentation to the `links` field
   - **Multiple links supported**: Use comma-separated URLs: `--links "url1,url2,url3"`
   - Example: `--links "https://github.com/org/repo/issues/123,https://mail.google.com/mail/u/0/#inbox/abc,https://docs.google.com/document/d/xyz"`
   - **Gmail integration**: Use the `gmail-control` skill to automatically add Gmail URLs to tasks
   - Gmail links format: `https://mail.google.com/mail/u/0/#inbox/{message_id}`

6. **Configure sorting**: Customize `sort_by` in config to match your workflow preferences

7. **Use clustering for better prioritization**: Enable `cluster_due_dates` to prioritize by timeframe instead of exact dates

8. **Default assignee for personal repos**: Set `default_assignee` for automatic self-assignment

9. **Sync regularly**: Keep repositories in sync with `tsk sync --push` to enable collaboration

10. **Filter by repository**: Use `--repo` flag to focus on specific task contexts

## Architecture Notes

**Repository location:**
- Parent directory configured in `~/.TaskRepo/config`
- Each repository: `{parent_dir}/tasks-{name}/`
- Active tasks: `{repo}/tasks/task-{id}.md`
- Completed tasks: `{repo}/done/task-{id}.md`
- Archived tasks: `{repo}/archive/task-{id}.md`

**Task lookup:**
- Commands accept display IDs (from cache) or UUIDs
- If multiple matches found, user is prompted to select
- Task files named by repository-scoped ID, not display ID

**Validation:**
- Status and priority validated against allowed values
- Links validated as HTTP/HTTPS URLs
- Dates parsed to ISO 8601 timestamps
- Assignees must have `@` prefix

## Integration with Other Skills

### show-my-todo Skill

The `show-my-todo` skill answers "what's on my plate" by harvesting this repo
(`tsk list --json`) together with the Obsidian vault's open checkboxes into one
ranked view, verifying which are already done, and ticking those (`tsk done`).

Use it instead of a bare `tsk list` whenever the question is about Ricardo's
workload as a whole, since roughly 90% of his open items live in vault notes
rather than in taskrepo.

### Gmail Control Skill

The `gmail-control` skill integrates seamlessly with TaskRepo:

**Creating tasks from emails:**
```bash
# Automatically creates task with Gmail link embedded
bash .claude/skills/gmail-control/scripts/email-to-task.sh --repo REPO_NAME --priority M
```

**Adding email links to existing tasks:**
- Use `tsk edit TASK_ID` to open the task
- Add Gmail URL to the `links` field manually (supports multiple URLs in YAML list format), or
- Use the gmail-control skill's `get-email-link.sh` script to retrieve the URL
- **Multiple links**: Tasks can have multiple links (GitHub, Gmail, docs, etc.) - just add them as list items in the YAML frontmatter

**Important:** When working on email-related tasks, always ensure the Gmail URL is in the task's `links` field for context and traceability.

### Google Tasks Control Skill

The `google-tasks-control` skill provides bidirectional sync between Google Tasks and TaskRepo:

**Syncing Google Tasks with TaskRepo:**
```bash
# First-time setup: Configure list-to-repo mappings
bash .claude/skills/google-tasks-control/scripts/configure-sync.sh

# Run bidirectional sync
bash .claude/skills/google-tasks-control/scripts/sync-with-taskrepo.sh
```

**How it works:**
- Maps Google Tasks lists to TaskRepo repositories (e.g., "My Tasks" → "personal" repo)
- Pulls from Google Tasks: Creates/updates TaskRepo tasks
- Tasks store `google_tasks_id` in YAML frontmatter for sync tracking
- Conflict resolution using MostRecent strategy (newest change wins)

**Data mapping:**
- Google Tasks title ↔ TaskRepo title
- Google Tasks notes ↔ TaskRepo description
- Google Tasks due date ↔ TaskRepo due (defaults to 23:59:59 for time)
- Google Tasks status (needsAction/completed) ↔ TaskRepo status (pending/completed)
- Google Tasks list name → TaskRepo repository

**TaskRepo-only fields** (don't sync to Google Tasks):
- Priority (H/M/L)
- Tags
- Assignees
- Dependencies

**Use cases:**
- Access TaskRepo tasks from mobile (via Google Tasks app)
- Quick task capture using Google Tasks' interface
- Collaborate with users who prefer Google Tasks
- Backup tasks in both systems

**Important:** Tasks synced from Google Tasks will have `google_tasks_id` and `google_tasks_list` fields in their YAML frontmatter. These fields are mandatory for maintaining sync.

## Development and Customization

### Source Code Location

The TaskRepo source code is located at `/Users/paxcalpt/GitHub/TaskRepo/`:
- Source files: `/Users/paxcalpt/GitHub/TaskRepo/src/taskrepo/`
- CLI commands: `/Users/paxcalpt/GitHub/TaskRepo/src/taskrepo/cli/commands/`
- Configuration: `pyproject.toml` (uses modern Python packaging)

### Development Environment Setup

To modify TaskRepo source code and test changes:

```bash
# Navigate to TaskRepo directory
cd /Users/paxcalpt/GitHub/TaskRepo

# Create virtual environment using homebrew Python (requires Python 3.10+)
/opt/homebrew/bin/python3 -m venv .venv

# Install in editable mode
uv pip install -e .
```

**Development tsk command location:**
```bash
/Users/paxcalpt/GitHub/TaskRepo/.venv/bin/tsk
```

Use this path to test modifications before they're released to the production version.

### Non-Interactive Mode Modifications

**Problem:** When running TaskRepo commands from automation tools or Claude Code, interactive prompts (like confirmation dialogs) fail because stdin is not a terminal, causing `OSError: [Errno 22] Invalid argument` from prompt_toolkit.

**Solution:** Add `sys.stdin.isatty()` checks before interactive prompts to automatically default to "yes" when not in a terminal.

#### Modified Files

**1. `/Users/paxcalpt/GitHub/TaskRepo/src/taskrepo/cli/commands/archive.py`**

Add terminal detection before prompting to archive subtasks:

```python
import sys  # Add at top

# In the archive function, around line 88:
if not yes:
    # Check if we're in a terminal - if not, default to yes
    if not sys.stdin.isatty():
        archive_subtasks = True
    else:
        # Show subtasks and prompt (existing code)
        click.echo(f"\nThis task has {count} {subtask_word}:")
        # ... rest of interactive prompt code
```

**2. `/Users/paxcalpt/GitHub/TaskRepo/src/taskrepo/cli/commands/move.py`**

Add terminal detection for two confirmation prompts:

```python
import sys  # Add at top

# Move confirmation (around line 146):
if not force:
    # Check if we're in a terminal - if not, skip confirmation
    if not sys.stdin.isatty():
        pass  # Automatically confirm when not in terminal
    else:
        # Show confirmation prompt (existing code)
        click.echo()
        # ... rest of interactive prompt code

# Subtask move confirmation (around line 180):
if subtasks_with_repos and not force:
    # Check if we're in a terminal - if not, default to yes
    if not sys.stdin.isatty():
        move_subtasks = True
    else:
        # Show subtasks and prompt (existing code)
        click.echo(f"\nTask '{task.title}' has...")
        # ... rest of interactive prompt code
```

#### Testing Modified Commands

After making changes:

```bash
# Archive completed tasks (no interactive prompts)
/Users/paxcalpt/GitHub/TaskRepo/.venv/bin/tsk archive 56 59 61

# Move task between repos (no confirmation prompts)
/Users/paxcalpt/GitHub/TaskRepo/.venv/bin/tsk move 46 --to rhenriques
```

### Batch Operations with Modified Version

Use the modified version for automation workflows:

```bash
# Archive all completed tasks in a repository
/Users/paxcalpt/GitHub/TaskRepo/.venv/bin/tsk list --repo rhenriques --status completed | \
  grep -oE '^\│ [0-9]+' | awk '{print $2}' > /tmp/completed.txt

while read id; do
  /Users/paxcalpt/GitHub/TaskRepo/.venv/bin/tsk archive $id
done < /tmp/completed.txt
```

### Alternative: Using Flags

Some commands support flags to skip prompts without source modifications:

```bash
# Archive with --yes flag (if available in future versions)
tsk archive 56 --yes

# Move with --force flag to skip all confirmations
tsk move 46 --to rhenriques --force
```

**Note:** As of version 0.10.15, `--yes` flag exists for `archive` but the code still attempts interactive prompts in non-terminal contexts, causing errors. The `sys.stdin.isatty()` modifications fix this issue.

## When to Use This Skill

Use this skill when the user needs to:
- **View tasks**: list, search, info, tui (interactive TUI with auto-reload)
- **Manage tasks**: add, edit, done, in-progress, cancelled, del (delete), move (between repos)
- **Due dates**: ext (extend or set due dates)
- **Archive**: archive, unarchive (preserve without deleting)
- **Repositories**: repos (list), repos-search (search GitHub), create-repo (create new)
- **Configuration**: config (interactive/--show), config-show (view), llm-info (LLM reference), init (first-time setup)
- **Sync**: sync (pull/push with git, auto ID rebalancing)
- **Maintenance**: upgrade (update TaskRepo)
- **Development**: Modify source code for custom functionality or automation
- Filter or sort tasks by various criteria
- Understand TaskRepo configuration options
- Learn TaskRepo command syntax and workflows
- Get LLM-optimized reference with `tsk llm-info`
- Troubleshoot TaskRepo usage issues
- Batch process tasks using automation scripts

Always use the `tsk` command (not `taskrepo`) when executing TaskRepo operations. For automation or when testing modifications, use `/Users/paxcalpt/GitHub/TaskRepo/.venv/bin/tsk`.
