# Changelog

All notable changes to TaskRepo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.14] - 2025-12-15

### Added

- **Changelog Command**: New `tsk changelog` command to view version history
  - View current version changes: `tsk changelog`
  - View specific version: `tsk changelog v0.10.13`
  - Show recent versions: `tsk changelog --recent 5`
  - Show changes since version: `tsk changelog --since v0.10.0`
  - Filter breaking changes only: `tsk changelog --breaking-only`
  - Full or highlight view modes with Rich formatting
  - Automatically detects and highlights breaking changes
  - Fetches live changelog from GitHub repository

### Internal

- Added `changelog_parser` utility module for parsing CHANGELOG.md
- Added `changelog` CLI command with multiple viewing modes
- Similar API to rxiv-maker's changelog command for consistency

## [0.10.13] - 2025-12-14

### Changed

- **Update Checker Modernization**: Migrated to `henriqueslab-updater` package for centralized update checking
  - Removed internal update_checker.py and install_detector.py modules
  - Now uses `henriqueslab-updater>=1.0.0` for all update checking functionality
  - Maintains same user experience with improved code maintainability
  - Reduces code duplication across HenriquesLab packages

### Dependencies

- Added `henriqueslab-updater>=1.0.0` dependency

## [0.10.12] - 2025-12-14

### Fixed

- **Critical sync push rejection bug**: Fixed auto-recovery mechanism for non-fast-forward push rejections
  - Reordered GitPython PushInfo flag checks to prioritize REJECTED before generic ERROR flag
  - Ensures automatic rebase recovery triggers when branches have diverged
  - Previously, sync would fail with error instead of attempting auto-recovery
  - Affects all users using `tsk sync` with remote repositories

### Added

- **History modifier tracking**: Show who made task changes in `tsk history` output
  - New `modifier` field in TaskChange dataclass
  - Infers modifier from task assignees when they differ from git commit author
  - Displays modifier name in history view (e.g., "by @username")
  - Helpful for multi-user repositories to track task ownership

## [0.10.11] - 2025-12-05

### Added

- **Color-coded history display**: Visual enhancements for `tsk history` command
  - Authors, repositories, and projects now have consistent, hash-based colors
  - Project changes in task history are color-coded for easier tracking
  - Hash-based color assignment ensures same author/repo/project always gets same color
  - New color utility functions in `display_constants.py`: `get_author_color()`, `get_repo_color()`, `get_project_color()`

- **History caching for performance**: Dramatically faster history queries
  - Persistent cache system for git commit history (stored in `~/.TaskRepo/history_cache/`)
  - 10x faster repeated `tsk history` queries through incremental cache updates
  - New `--no-cache` flag to bypass cache and recompute from git
  - New `--clear-cache` flag to clear cache for specific repo or all repos
  - Cache format version tracking for safe upgrades
  - Automatic cache invalidation when repository changes

### Improved

- **Enhanced sync error recovery**: More robust push failure handling
  - Improved error detection with explicit GitPython PushInfo flag checks
  - Better error messages for different failure types (ERROR, REJECTED, REMOTE_REJECTED, REMOTE_FAILURE)
  - Auto-recovery now applies to both `tsk sync` and TUI background sync
  - Fixed variable scope issues in nested push functions

- **TUI and display improvements**: Better formatting and consistency
  - Enhanced task display with improved color consistency
  - Better countdown display formatting
  - Improved conflict resolution display

## [0.10.10] - 2025-12-04

### Added

- **Smart auto-merge with major edit detection**: Enhanced merge conflict resolution during `tsk sync`
  - Detects major edit sessions (2+ content fields changed OR title/description significantly different)
  - Context-aware list merging: respects local changes during major edits, uses union for incremental changes
  - Fixes issue where removed tags were brought back by auto-merge during active editing
  - Major edits are detected using text similarity analysis (title <70% similar OR description <50% similar)

### Improved

- **Code centralization in merge logic**: Better maintainability and consistency
  - Added constants for field categories (SIMPLE_FIELDS, DATE_FIELDS, LIST_FIELDS, SEMANTIC_FIELDS, CONTENT_FIELDS)
  - Added threshold constants (TITLE_SIMILARITY_THRESHOLD, DESCRIPTION_SIMILARITY_THRESHOLD, etc.)
  - Created reusable helper functions:
    - `_calculate_text_similarity()`: DRY for text comparison using SequenceMatcher
    - `_copy_task_from()`: DRY for task copying
    - `_resolve_semantic_conflict()`: Generic semantic resolution pattern
  - Refactored all merge functions to use centralized components

## [0.10.9] - 2025-11-19

### Fixed

- **Git push error detection**: Fixed silent push failures that weren't being caught
  - GitPython's `push()` doesn't always raise exceptions on failure
  - Now explicitly checks PushInfo flags (ERROR, REJECTED, REMOTE_REJECTED, REMOTE_FAILURE)
  - Push failures are now properly detected and reported instead of showing false success

- **Automatic recovery for diverged branches**: Added auto-rebase when push is rejected
  - Detects non-fast-forward push rejections (branches have diverged)
  - Automatically runs `git pull --rebase` to integrate remote changes
  - Retries push if rebase succeeds without conflicts
  - Safely aborts and provides manual instructions if conflicts occur
  - Applies to both `tsk sync` and TUI background sync

## [0.10.8] - 2025-11-14

### Added

- **Smart email-to-task integration**: Enhanced gmail-control skill with intelligent defaults
  - Auto-detects priority from email keywords (urgent/asap → High, fyi → Low)
  - Auto-extracts due dates from email content ("by Monday", "by tomorrow", etc.)
  - Auto-tags all email-based tasks with "email" tag
  - Now uses TaskRepo CLI instead of direct file creation for better integration

- **TUI status bar improvements**: Added missing keyboard shortcuts to status bar
  - Added priority shortcuts `[H][M][L]` for setting High/Medium/Low priority
  - Added subtask shortcut `s[u]btask` (was only visible on very wide terminals)
  - All shortcuts now visible at all terminal widths

### Improved

- **CLI non-interactive mode**: Enhanced `tsk add` command with intelligent TTY detection
  - Automatically detects when not running in a terminal (stdin is not a TTY)
  - Auto-switches to non-interactive mode without requiring manual flag
  - Only requires `--title` argument (uses `default_repo` from config if `--repo` not specified)
  - Better error messages with helpful context about available defaults
  - Works seamlessly with scripts and automation

- **TUI help documentation**: Updated `tsk tui --help` to reflect actual key bindings
  - Fixed key mapping documentation (a/v/l/m/u/t keys)
  - Added missing shortcuts (move, subtask, extend)
  - Corrected tree toggle key from 't' to 'r'

### Fixed

- **TUI crash when archiving tasks**: Fixed IndexError when archiving the last task in a filtered view
  - Added bounds checking in `_get_filtered_tasks()` method
  - Automatically resets to "All tasks" view when current view becomes empty
  - Prevents crash when view items list changes after archiving/deleting

## [0.10.7] - 2025-11-13

### Added

- **Centralized README conflict auto-resolution**: Added intelligent README conflict resolver in `conflict_detection.py`
  - Automatically resolves timestamp conflicts in auto-generated README files
  - Handles nested conflict markers (`<<<<<<< HEAD` inside `<<<<<<< HEAD`)
  - Integrated into both `sync` and `async_sync` commands
  - README conflicts now resolve automatically during sync without manual intervention

- **Smart word-aware wrapping for TUI shortcuts**: Enhanced status bar to show all shortcuts even on narrow terminals
  - Shortcuts now intelligently wrap to multiple lines on terminals <120 columns
  - Words never break mid-shortcut (e.g., `[q]uit` stays intact instead of `[q` / `uit`)
  - Dynamic height calculation based on actual wrapped lines
  - All shortcuts (including `ex[t]end`) now visible on 80-column terminals

### Improved

- **TUI status bar adaptability**: Status bar now adapts intelligently to terminal width
  - Added `ex[t]end` shortcut to medium-width display (120-160 cols)
  - Smart line-breaking algorithm respects word boundaries
  - Multi-line status bar (2-4 lines) on narrow terminals ensures full visibility
  - Better UX on narrow terminals with no loss of functionality

## [0.10.6] - 2025-11-11

### Added

- **Pre-commit hook to prevent uncommitted files**: Added check-uncommitted-files hook to ensure all changes are staged before committing
  - Blocks commits if there are unstaged changes or untracked files
  - Provides clear error message showing which files need attention
  - Ensures no work is accidentally left uncommitted
  - Helps maintain clean git history and prevents partial commits

## [0.10.5] - 2025-11-10

### Fixed

- **Config corruption bug**: Fixed bug where viewing tasks with subtasks would overwrite user's sort_by configuration
  - The temporary config created for subtask sorting was inadvertently saving back to the config file
  - This caused user's custom sort order (e.g., `assignee:@user, due, priority`) to revert to `due, assignee:@user, priority`
  - Now modifies internal config data without triggering save when sorting subtasks
  - Added regression test to prevent this issue from recurring

- **TUI selection and scroll reset**: Fixed bug where pressing [d] to mark task as done would reset selection and scroll to top
  - When TUI was recreated after marking task as done, both selected_row and viewport_top were reset to 0
  - Now saves and restores both selected_row and viewport_top state across TUI recreation
  - Preserves user's position and scroll location in the task list
  - Selection intelligently moves to task above when completed task is removed from view

- **Sync failure with unfinished merges**: Fixed critical ordering bug causing sync to fail when repository has incomplete merge
  - Error: "You have not concluded your merge (MERGE_HEAD exists)"
  - Sync was attempting to merge remote changes BEFORE checking for unfinished merges
  - Now checks for and completes unfinished merges BEFORE attempting new merge
  - Automatically resolves conflict markers and stages changes if merge is ready
  - Improved error handling: skips repository if conflicts remain, provides clear guidance
  - Auto-stages task file changes if working tree has modifications but no conflicts

- **Countdown showing "-1d" for today**: Fixed bug where tasks due today showed "-1d" instead of "today"
  - When due date was set to midnight (00:00:00) on same day, countdown calculated negative hours
  - Now checks calendar date FIRST before calculating time difference
  - Centralized countdown logic in new `utils/countdown.py` module
  - Both TUI display and README generation now use same countdown calculation
  - Added comprehensive tests to prevent regression (12 new test cases)

### Added

- **New `urgency` sort field**: Sort tasks by urgency level instead of chronological date
  - Sorts by urgency: overdue (critical) → today (high) → soon (medium) → future (low)
  - Unlike `due` which sorts chronologically (oldest first), `urgency` prioritizes urgent tasks
  - Perfect for daily task lists where overdue items should appear at the top
  - Usage: `sort_by: [urgency, priority]` or `sort_by: [assignee:@user, urgency, priority]`
  - Can be combined with other sort fields like assignee and priority
  - Respects effective due dates (includes subtasks and dependencies)

### Improved

- **TUI keyboard shortcuts display**: Consistent pattern using letters from within words
  - Changed `[c]cancelled [v]archive [l]delete` → `[c]ancelled ar[v]hive de[l]ete`
  - More intuitive: users see the highlighted letter within the actual word they're reading
  - Added comprehensive design principle documentation in code to maintain consistency
  - Pattern now consistent across all terminal widths (narrow, medium, wide)

## [0.10.4] - 2025-11-10

### Fixed

- **TUI module import**: Added missing `sync_history.py` module required by the TUI command
  - Fixes `ModuleNotFoundError` when running `tsk tui`
  - Provides persistent logging of sync attempts for reliable status monitoring
  - Tracks last 10 sync attempts in `~/.TaskRepo/sync_history.json`

## [0.10.3] - 2025-11-10

### Improved

- **Simplified sorting configuration** (`tsk config` option 9)
  - Replaced 40+ lines of technical documentation with 6 simple preset choices
  - New presets: "By due date", "By priority", "My tasks first", "Newest first", etc.
  - Advanced custom options still available but hidden behind "custom" choice
  - Makes configuration accessible to all users, not just power users

- **Crystal clear exit feedback** (`tsk config`)
  - Prompt now shows "Ctrl+C to exit" hint
  - Exit confirmation changed from plain text to bold green "✓ Configuration saved. Exiting."
  - No more confusion about whether you've exited or just cancelled a submenu

- **Improved clustering toggle** (`tsk config` option 10)
  - Current state shown in bold: "is currently: ON" or "OFF"
  - Context-aware prompts: "Turn OFF clustering?" when ON, "Turn ON?" when OFF
  - Clear feedback: "Clustering turned ON/OFF" or "No changes made."
  - Eliminates confusion about current state and action being taken

## [0.10.2] - 2025-11-10

### Fixed

- **Subtask sorting**: Subtasks now sort by due date first, regardless of global sort configuration
  - Urgent subtasks with earlier due dates now appear first within their parent task
  - Ensures critical subtasks are visible at the top of hierarchical task lists
  - Applies to both TUI and CLI list views with tree display

### Improved

- **Conservative countdown rounding**: All countdown displays now use ceiling division (rounds UP) for more conservative time estimates
  - Future dates: 1-6 days → "1 week", 7-13 days → "2 weeks", etc.
  - Overdue dates: 7-13 days → "-2w", 14-20 days → "-3w", etc.
  - Prevents underestimating urgency by always rounding to the next higher time unit
  - Applies to both CLI and README countdown displays

## [0.10.1] - 2025-11-06

### Improved

- **TUI status bar enhancements**: Status bar now shows persistent sync and reload timing information
  - Always displays last sync time (e.g., "Synced 2m ago") when auto-sync is enabled
  - Shows last reload time (e.g., "Reloaded 15s ago") to verify file watching is working
  - Displays auto-sync interval and status (e.g., "Auto-sync: ON (5m)")
  - Shows conflict warnings with count when manual resolution needed
  - Responsive layout adapts to terminal width:
    - Two-line layout for terminals ≥120 columns (status info on line 1, shortcuts on line 2)
    - Single-line layout for narrower terminals with condensed shortcuts
    - Breakpoints at 80, 120, 160 columns for optimal shortcut visibility
  - Implementation:
    - New `src/taskrepo/utils/time_format.py` with human-readable time formatting
    - Refactored status bar generation into modular helper methods
    - Accurate height calculation accounting for HTML markup
    - State tracking for reload and sync timestamps

- **Compact overdue format**: Overdue tasks now use negative numbers for space efficiency
  - Displays as "-3d" instead of "overdue 3 days"
  - Displays as "-2w" instead of "overdue 2 weeks"
  - Saves significant horizontal space in task lists and TUI
  - Maintains red color for visibility
  - Affects both TUI and CLI list views

## [0.10.0] - 2025-11-05

### Added

- **History command (`tsk history`)**: New command to view task and git repository history with rich timeline display
  - Shows git commit history with task-specific changes highlighted
  - Chronological timeline grouping (Today, Yesterday, This Week, Last Week, etc.)
  - Filters out auto-updates by default, showing only commits with actual task changes
  - Use `--all` flag to include auto-updates and all commits
  - Default time range: 7 days (configurable with `--since`)
  - Task change detection:
    - Status changes (pending → completed, etc.) with color coding
    - Priority changes (H → L, etc.) with color coding
    - Assignee and tag additions/removals
    - Due date changes
    - Title and description modifications
    - Task creation (shows initial priority) and deletion
  - Display features:
    - Task titles shown instead of IDs (truncated at 50 characters for readability)
    - Author name displayed with each commit
    - Color-coded status and priority values
    - Emoji categorization (✅ completions, 🎯 new tasks, 👥 assignee changes, 🔄 sync operations, 📝 updates)
    - Repository name shown when viewing multiple repos
    - Timestamps (time for Today/Yesterday, date for older commits)
    - File change counts
    - Verbose mode (`-v`) shows commit hashes and full commit messages
  - Filter options:
    - `--repo, -r`: Filter by specific repository
    - `--since, -s`: Time range (7d, 2w, 1m, 3m, all)
    - `--task, -t`: Filter by task ID or title pattern
  - Example usage:
    ```bash
    tsk history                    # Last 7 days, task changes only
    tsk history --all              # Last 7 days, including auto-updates
    tsk history --since 2w         # Last 2 weeks
    tsk history --repo work        # Specific repository
    tsk history --verbose          # Detailed output with commit hashes
    ```
  - Implementation files:
    - `src/taskrepo/cli/commands/history.py` - Main command
    - `src/taskrepo/utils/history.py` - History analysis utilities

## [0.9.15] - 2025-11-05

### Added

- **Verbose auto-merge details**: Sync command now displays detailed information about how conflicts were automatically merged
  - Shows which task version (local/remote) was used as the base
  - Displays merge strategy for each conflicting field
  - List fields (assignees, tags, links, depends) show "union" when merged
  - Status field shows "remote priority" when remote status takes precedence
  - Simple fields show which version was used
  - Example output:
    ```
    • task-abc123.md: Auto-merged (base: remote)
      - status: remote priority (in-progress)
      - assignees: union
      - tags: union
    ```

## [0.9.14] - 2025-11-03

### Fixed

- **TUI sync conflict resolution**: Fixed incorrect parameter type passed to conflict resolution
  - TUI sync was passing `click` module instead of Rich `Console` object to `_resolve_conflict_markers()`
  - Caused "Error: print" message and left conflict markers unresolved in task files
  - Resulted in YAML parsing errors when loading tasks with unresolved conflict markers
  - Now properly creates Console instance before calling conflict resolution

## [0.9.13] - 2025-10-31

### Fixed

- **TUI display errors**: Fixed XML/HTML parsing errors in task detail display
  - Added HTML escaping for all user-generated content (titles, descriptions, etc.)
  - Prevents crashes when task content contains special characters like `<`, `>`, `&`
  - Applied to TUI task details, header text, and conflict display

- **Conflict resolution display errors**: Fixed Rich markup parsing errors
  - Removed task ID from conflict display to prevent bracket interpretation issues
  - Fixed empty style markup creating invalid `[]value[/]` patterns
  - Improved robustness of side-by-side conflict comparison display

- **Interactive conflict resolution**: Fixed command hanging after user input
  - Progress bars now stop during interactive prompts
  - Prevents terminal I/O conflicts that caused hung state
  - Progress display automatically restarts after user completes interaction

- **Input validation**: Added validation for conflict resolution choices
  - Users can now only submit valid choices (L/R/N/M/E)
  - Invalid input shows error message without submitting
  - Prevents confusion from accidentally submitted typos

- **Unfinished git merge handling**: Sync now detects and resolves incomplete merges
  - Automatically detects MERGE_HEAD file indicating unfinished merge
  - Resolves remaining conflict markers before completing merge
  - Uses git command directly to properly clean up merge state
  - Prevents "You have not concluded your merge" errors

## [0.9.12] - 2025-10-31

### Fixed

- **Conflict marker resolution**: Enhanced robustness of automatic conflict resolution
  - More flexible regex patterns handle various conflict marker formats
  - Fallback mechanism extracts local version when parsing fails
  - Validation ensures conflict markers are actually removed after resolution
  - Better error reporting with debug information for failed resolutions
  - Lists files requiring manual resolution with actionable guidance

- **Sync progress display**: Progress bar now shows for single repository sync
  - Per-operation progress tracking (e.g., "5/7 operations")
  - Consistent visual feedback for both single and multiple repository syncs
  - Operations task advances as each step completes

### Changed

- Improved conflict resolution error handling
  - Three-tier resolution strategy: smart merge → partial fallback → simple extraction
  - Failed files are clearly reported with manual resolution instructions
  - Better user guidance when conflicts cannot be auto-resolved

## [0.9.11] - 2025-10-30

### Added

- **TUI keybindings for subtask and extend**: Added convenient keyboard shortcuts
  - `[u]` - Create subtask under selected task with inherited defaults
  - `ex[t]end` - Extend/set due dates for single or multiple tasks
  - Supports both absolute dates (tomorrow, 2025-11-15) and relative durations (1w, 2d)
  - Instant return to TUI without "Press Enter" prompts

- **Automatic conflict resolution**: Sync now auto-resolves git conflict markers
  - Post-pull detection of conflict markers in task files
  - Automatic parsing of conflicted local/remote versions
  - Smart merge using "keep newer" strategy based on modified timestamp
  - Automatic commit of resolved conflicts
  - Eliminates need for manual conflict marker cleanup
  - Works in both CLI sync and TUI sync

### Fixed

- **TUI sync prompt removal**: Removed redundant "Press Enter" after sync completes
  - Instant return to TUI after sync operation
  - Consistent with other TUI operations (archive, done, etc.)

- **Rich markup escaping in conflict resolver**: Fixed crash when task content contains special characters
  - Escape task titles, field values, and descriptions before display
  - Prevents errors like "closing tag '[/]' has nothing to close"
  - Fixes crashes when displaying conflicts with tasks containing `[/]`, `[+]`, etc.

- **Rich markup escaping in sync errors**: Fixed crash when error messages contain special characters
  - Escape exception messages before displaying
  - Prevents crashes when git errors contain characters interpreted as markup

### Improved

- **TUI keybinding mnemonics**: Reorganized keyboard shortcuts for better intuitiveness
  - `[a]dd` - Add new task (was `[n]ew`)
  - `[d]one` - Mark as done (was `[w]`)
  - `de[l]` - Delete task (was `[x]`)
  - `ar[v]hive` - Archive task (was `[a]`)
  - `ex[t]end` - Extend/set due date (new)
  - `s[u]btask` - Create subtask (new)
  - `t[r]ee` - Toggle tree view (was `[t]`)
  - All shortcuts now align with primary action letters

- **TUI status bar wrapping**: Status bar now wraps on narrow terminals
  - Dynamically calculates required lines based on terminal width
  - Supports up to 3 lines for full shortcut display
  - Makes TUI usable on smaller terminal windows

## [0.9.10] - 2025-10-30

### Added

- **Unexpected file detection in sync**: Protect against accidentally committing non-task files
  - Detects and groups unexpected files by pattern (*.log, .vscode/*, etc.)
  - Interactive prompt with 4 options: add to .gitignore, delete, commit anyway, or skip
  - Default .gitignore automatically created for new repositories
  - Covers common patterns: editor files, Python cache, OS files, temporary files
  - Works in both CLI sync and TUI sync commands
  - New utility module: `src/taskrepo/utils/file_validation.py`

### Fixed

- **TUI selected row contrast**: Improved text readability on light backgrounds
  - Changed selected row text from white to black for better contrast
  - Fixes visibility issue where selected text was nearly invisible on light/white backgrounds

- **TUI archive prompt**: Removed redundant "Press Enter" after confirming archive
  - Archive operation now returns immediately after y/n confirmation
  - Consistent with other quick operations like done and in-progress

- **TUI sync in project/assignee views**: Fixed context-aware repository syncing
  - Project view: Now syncs only repositories containing tasks in that project
  - Assignee view: Now syncs only repositories with tasks for that assignee
  - Shows count of repositories being synced (e.g., "Syncing 3 repos with project 'X'")
  - More efficient - doesn't sync unrelated repositories

### Improved

- **Default repository setup**: New repositories include sensible defaults
  - Automatic .gitignore with common patterns
  - Protects against committing .DS_Store, .vscode/, __pycache__/, etc.

## [0.9.9] - 2025-10-29

### Fixed

- **TUI column alignment**: Fixed misalignment caused by emojis and tree characters
  - Implemented wcwidth-based display width calculation
  - Added `display_width()`, `truncate_to_width()`, and `pad_to_width()` utility functions
  - Properly handles 📋 emoji (2 terminal cells) and tree characters (└─)
  - All columns now align perfectly regardless of content

- **Archived subtask detection**: Fixed data loss bug when moving parent tasks
  - `get_all_subtasks_cross_repo()` now includes archived subtasks
  - Prevents orphaning of archived children during move operations

- **Stack trace errors**: Replaced Python tracebacks with user-friendly error messages
  - Task validation errors (invalid status, priority, links) show clean messages with examples
  - File I/O errors (disk full, permissions) show descriptive messages
  - Edit/done command exceptions no longer re-raise in single-task mode

### Improved

- **Batch operation syntax**: Standardized across all commands
  - `extend`, `done`, `edit` now support BOTH comma AND space-separated task IDs
  - Example: `tsk done 1,2,3` or `tsk done 1 2 3` (both work)
  - Consistent with `move` command pattern

- **TUI status changes**: Made instant without confirmation prompts
  - Press [p] to toggle in-progress/pending instantly
  - Press [d] to mark done instantly
  - Press [c] to cancel instantly
  - No more "Press Enter to continue" interruptions

- **Validation error messages**: More actionable with examples
  - Invalid status/priority shows all valid options with examples
  - Date parsing errors include supported formats (ISO, keywords, natural language)
  - Link validation shows example URLs

### Added

- **Batch delete support**: Delete multiple tasks at once
  - `tsk delete 1 2 3` or `tsk delete 1,2,3`
  - Batch confirmation prompt with summary
  - Proper error handling for each task

- **Move subtask warning**: Warns when subtasks stay behind
  - Yellow warning: "⚠ Warning: N subtask(s) will remain in original repository"
  - Prevents silent orphaning of subtasks

- **Homebrew installation**: TaskRepo now available via Homebrew for macOS users
  - Install: `brew tap henriqueslab/formulas && brew install taskrepo`
  - Simplifies macOS installation with automatic dependency management
  - Update: `brew update && brew upgrade taskrepo`
  - Tap repository: https://github.com/HenriquesLab/homebrew-formulas

- **Installation detection utilities**: Auto-detect how TaskRepo was installed
  - Detects Homebrew, pipx, uv, pip, or dev installations
  - Shows appropriate update commands in upgrade notifications
  - Implementation: `src/taskrepo/utils/install_detector.py`

### Technical Details

- Added `wcwidth` library integration for accurate terminal width calculations
- Enhanced error handling in `add.py`, `edit.py`, `done.py`, `task.py`
- Refactored TUI status change handlers to remove blocking prompts
- Updated batch syntax parsing in `extend.py`, `done.py`, `edit.py`, `delete.py`
- New display utilities: `display_width()`, `truncate_to_width()`, `pad_to_width()`

Files Modified: 18 files
Tests: 124/130 passing

## [0.9.8] - 2025-10-29

### Added

- **LLM CLI reference**: New `tsk llm-info` command provides concise CLI usage reference for LLM assistants
  - **Dynamic content**: Automatically includes output from `tsk --help` (all available commands)
  - **Current configuration**: Shows user's actual config via `tsk config --show` integration
  - Task properties (statuses, priorities, date formats)
  - Curated command examples and common workflows
  - Filtering options and search syntax
  - Quick tips specifically for LLMs assisting users
  - Purely user-facing information (no source code details)
  - Always up-to-date with latest commands and user's actual configuration
  - Example: `tsk llm-info`

- **Non-interactive config display**: New `tsk config --show` flag to display configuration without entering interactive menu
  - Shows all configuration settings in formatted output
  - Useful for scripts and quick reference
  - Same detailed output as interactive menu option 1
  - Example: `tsk config --show`

## [0.9.7] - 2025-10-29

### Added

- **TUI auto-reload**: TUI now automatically detects file changes and reloads every 2 seconds
  - Monitors task directories for modifications
  - Automatically refreshes task list when changes detected
  - Clears multi-selection on reload to prevent ID mismatches
  - Status bar shows "Auto-reload: ON" indicator
  - Removed manual [r]efresh key (no longer needed)
  - Implementation: `src/taskrepo/tui/task_tui.py` with async background task

- **ID stability system**: Smart ID assignment preserves existing task IDs when possible
  - **Stable mode** (`rebalance=False`): Preserves existing IDs, fills gaps for new tasks
  - **Rebalance mode** (`rebalance=True`): Reassigns sequential IDs from scratch
  - Gap filling: When tasks are deleted, new tasks reuse freed IDs (e.g., if task #5 deleted, next new task gets ID 5)
  - Used by `tsk add`, `tsk edit`, `tsk done`, `tsk del`, `tsk archive` to maintain stable IDs
  - Implementation: `src/taskrepo/utils/id_mapping.py`

### Changed

- **ID rebalancing behavior**: `tsk list` (unfiltered) and `tsk sync` now explicitly rebalance IDs to sequential order
  - Ensures clean sequential numbering (1, 2, 3...) after sync operations
  - Displays "IDs rebalanced to sequential order" message after sync
  - Eliminates gaps from deleted tasks during these operations
  - Other commands preserve existing IDs for stability

- **GitHub repository default**: Changed default prompt answer from "no" to "yes" when creating repositories
  - New prompt: "Create GitHub repository? [Y/n]:" (capital Y indicates default)
  - Makes GitHub integration more accessible for new users
  - Implementation: `src/taskrepo/tui/prompts.py`

### Technical Details

- New async background task using `asyncio.create_task()` for TUI auto-reload
- Application runs with `run_async()` instead of `run()` for concurrent task support
- File modification time tracking across all task directories
- Enhanced `save_id_cache()` with gap detection and filling algorithm
- Added `.folder2md_ignore` file for folder2md4llms tool compatibility

## [0.9.6] - 2025-10-29

### Fixed

- **Release automation**: Fixed missing CHANGELOG entry that caused v0.9.5 release workflow to fail
  - Added complete v0.9.5 CHANGELOG documentation retroactively
  - Ensures CI/CD validation passes for future releases

## [0.9.5] - 2025-10-28

### Added

- **Move tasks between repositories**: New command and TUI feature to relocate tasks
  - **CLI command**: `tsk move TASK_IDS --to TARGET_REPO` to move one or more tasks to a different repository
  - **TUI key binding**: Press [m] to move selected task(s) to another repository
  - **Subtask handling**: Prompts user when moving tasks with subtasks (move together or independently)
  - **Dependency warnings**: Warns about tasks that depend on the task being moved
  - **Preserves archived status**: Archived tasks remain in archive folder after move
  - **Multi-selection support**: Move multiple tasks at once in TUI or CLI
  - Implementation: `src/taskrepo/cli/commands/move.py`, `src/taskrepo/cli/commands/tui.py:350-450`

### Improved

- **TUI state preservation**: View state (view mode, filter text, tree mode) now persists after task operations
  - Previously: Operations like done/delete/edit would reset view to default state
  - Now: Returns to exact view state after completing operations
  - Implementation: `src/taskrepo/tui/task_tui.py`

- **TUI column alignment**: Fixed dynamic column separator calculation for consistent spacing
  - Resolves alignment issues in task list display
  - Implementation: `src/taskrepo/tui/task_tui.py`

- **Repository sorting**: Repositories now sorted by task count in prompts and config
  - Shows busiest repositories first for better UX
  - Implementation: `src/taskrepo/cli/commands/config.py`, `src/taskrepo/tui/prompts.py`

### Technical Details

- New utility: `src/taskrepo/utils/banner.py` for ASCII art banners (future use)
- Enhanced TUI with [m]ove key binding and move handler
- Updated CLI main to register move command
- Total: 594 insertions, 20 deletions across 8 files

## [0.9.4] - 2025-10-27

### Fixed

- **TUI Edit Task Error**: Fixed crash when editing tasks in TUI with "unexpected keyword argument 'repo_name'" error
  - Root cause: `Task.from_markdown()` was called with incorrect parameter names
  - Changed `repo_name` → `repo` (correct parameter name)
  - Added missing required `task_id` parameter
  - TUI edit handler now correctly parses edited task content
  - Implementation: `src/taskrepo/cli/commands/tui.py:207`

## [0.9.3] - 2025-10-27

### Fixed

- **TUI Task Operations in Non-Repo Views**: Fixed critical bug where [d]one, [p]rogress, [c]ancelled, and [x]delete operations would fail when using Project or Assignee view modes
  - Previously: Operations only worked in Repository view mode because handlers used `_get_current_repo()` which returns None in other view modes
  - Now: All operations consistently look up repository by `task.repo` name, working across all view modes
  - Affected handlers: `_handle_in_progress_toggle()`, `_handle_status_change()`, `_handle_delete_task()`, `_handle_archive_task()`
  - Implementation: `src/taskrepo/cli/commands/tui.py`

### Added

- **TUI Archive Key Binding**: Restored [a]rchive functionality to TUI
  - Press [a] to archive selected task(s)
  - Supports multi-select for batch archiving
  - Includes confirmation prompt before archiving
  - Shows success/failure feedback for each task
  - Updated status bar and command docstring
  - Implementation: `src/taskrepo/tui/task_tui.py`, `src/taskrepo/cli/commands/tui.py`

### Technical Details

- Simplified repository lookup logic to always use `task.repo` name instead of view-dependent methods
- Consistent error handling across all view modes
- Archive handler follows same pattern as delete/status change handlers

## [0.9.2] - 2025-10-27

### Added

- **Configurable TUI View Modes**: Choose how to organize and navigate tasks in the TUI
  - **View modes**: Repository, Project, or Assignee-based organization
  - **Configuration**: Set default view mode via `tsk config` (option 11: "Set TUI view mode")
  - **Config field**: `tui_view_mode` in `~/.TaskRepo/config` (options: `repo`, `project`, `assignee`)
  - **Dynamic switching**: Press `Tab` to cycle through view types during TUI session (Repo → Project → Assignee → Repo)
  - **Persistent**: Last used view mode is automatically saved and remembered for next session
  - **Navigation**: Left/Right arrows cycle through items within current view type (repos, projects, or assignees)
  - **Header indicator**: Shows current view type and navigation hints: `[←/→ items | Tab: view type]`
  - Implementation: `src/taskrepo/core/config.py`, `src/taskrepo/tui/task_tui.py`, `src/taskrepo/cli/commands/config.py`

- **Smart Column Hiding in TUI**: Automatically hide redundant columns when viewing filtered items
  - Hides **Repo column** when viewing a specific repository
  - Hides **Project column** when viewing a specific project
  - Hides **Assignee column** when viewing a specific assignee
  - Only applies when viewing specific items, not "All" views
  - **Freed space**: Expands Title column to show longer task names
  - Example: Viewing "Feature A" project hides Project column and expands Title from 25 to 34 characters
  - Implementation: `src/taskrepo/tui/task_tui.py` (`_get_task_list_text()` method)

- **Platform-specific GitHub CLI Installation Messages**: Smarter guidance for installing `gh` CLI
  - Detects macOS + Homebrew and suggests: `brew install gh`
  - Falls back to generic installation URL for other platforms
  - Applies to `tsk repos-search` and other GitHub-dependent commands
  - Implementation: `src/taskrepo/utils/github.py` (`get_gh_install_message()` function)

### Changed

- **TUI [p] Key Behavior**: Toggle between in-progress and pending status
  - Previously: Always set to in-progress
  - Now: If task is in-progress → set to pending; otherwise → set to in-progress
  - Provides quick way to "reset" tasks to pending state
  - Implementation: `src/taskrepo/cli/commands/tui.py` (`_handle_in_progress_toggle()` function)

- **TUI Command Documentation**: Updated docstring to reflect new keyboard shortcuts
  - Tab key: "Switch view type (repo/project/assignee)"
  - [p] key: "Toggle in-progress/pending"
  - Left/Right arrows: "Switch between items (repos/projects/assignees)"

### Technical Details

- View mode configuration with property getter/setter and validation in `Config` class
- Tab key binding with view mode cycling and config persistence
- Dynamic `_build_view_items()` method to collect repos/projects/assignees based on mode
- Conditional column rendering in `_get_task_list_text()` with freed space reallocation
- Platform detection using `platform.system()` and `shutil.which()` for Homebrew check

## [0.9.1] - 2025-10-27

### Improved

- **TUI Color Enhancements**: Rich color scheme throughout the TUI for better visual scanning
  - **Priority colors**: Red (High), Yellow (Medium), Green (Low) in both task list and detail panel
  - **Status colors**: Yellow (pending), Blue (in-progress), Green (completed), Red (cancelled)
  - **Countdown colors**: Red (overdue), Yellow (urgent), Green (normal) - dynamically colored based on urgency
  - **Field-specific colors**:
    - ID numbers: Dimmed (bright black)
    - Repo names: Magenta
    - Projects: Cyan
    - Assignees: Blue
    - Tags: Yellow
    - Due dates: White
  - **UI elements**: Cyan scroll indicators, green multi-select markers
  - **Detail panel**: Color-coded field labels (cyan bold) with colored values for better readability
  - **Selected row**: Blue background highlight for easy visual tracking
  - Comprehensive color styling using `prompt_toolkit.styles.Style` system

### Technical Details

- Added `Style` import from `prompt_toolkit.styles`
- Created `_create_style()` method with comprehensive color definitions
- Individual field coloring in task rows using `FormattedText` tuples
- Color-coded countdown based on `get_countdown_text()` return values
- HTML color tags in detail panel for rich formatting

## [0.9.0] - 2025-10-27

### Added

- **Full-screen TUI (Text User Interface)**: New interactive terminal UI for task management
  - Launch with `tsk tui` command for immersive full-screen experience
  - **Keyboard-driven navigation**: Arrow keys for task selection, left/right for repository switching
  - **Multi-repository support**: Tab between "All Repositories" view and individual repos
  - **Task operations**:
    - `[n]` Create new task
    - `[e]` Edit selected task(s)
    - `[d]` Mark as done
    - `[p]` Mark as in-progress
    - `[c]` Mark as cancelled
    - `[x]` Delete task(s)
    - `[a]` Archive task(s)
    - `[u]` Unarchive task(s)
  - **Multi-select**: Use `Space` to select multiple tasks for batch operations
  - **Live filtering**: Press `/` to filter tasks by text, `Escape` to clear
  - **Tree view toggle**: Press `[t]` to toggle hierarchical task display
  - **Git sync**: Press `[s]` to sync with remote repositories
  - **Task detail panel**: Bottom panel shows extended task information (metadata, links, dependencies, description)
  - **Scrollable viewport**: Rolodex-style scrolling for large task lists (starts scrolling after 5th task)
  - **Status bar**: Always-visible keyboard shortcuts and commands
  - **Dynamic terminal sizing**: Automatically adapts to terminal width and height
    - Viewport height adjusts based on available space
    - Detail panel uses ~30% of terminal height (8-15 lines)
    - Column widths dynamically distributed based on terminal width
    - Title column gets 40% of flexible space, other columns share remaining space
  - **Keyboard shortcut isolation**: Filter mode disables command shortcuts to prevent accidental triggers
  - Implementation: `src/taskrepo/tui/task_tui.py`, `src/taskrepo/cli/commands/tui.py`

- **Archive/Unarchive commands**: New commands for managing archived tasks
  - `tsk archive TASK_IDS` - Archive one or more tasks to `tasks/archive/` folder
  - `tsk archive` (no args) - List all archived tasks with display IDs
  - `tsk unarchive TASK_IDS` - Restore archived tasks back to active status
  - Archived tasks are excluded from regular task listings by default
  - Archive folder has its own README.md with archived task table
  - Subtask handling: Prompts to archive subtasks when archiving parent task
  - Implementation: `src/taskrepo/cli/commands/archive.py`, `src/taskrepo/cli/commands/unarchive.py`

### Changed

- **TUI keyboard shortcuts**: Updated for better usability
  - Left/Right arrows for repository navigation (instead of Tab)
  - `[s]` for sync (instead of sort)
  - Filter mode (`/`) now properly isolates input from command shortcuts

### Technical Details

- New TUI framework using `prompt_toolkit` for full-screen terminal applications
- Layout components: `Application`, `Layout`, `HSplit`, `Window`, `Frame`, `ConditionalContainer`
- Dynamic sizing with `_get_terminal_size()`, `_calculate_viewport_size()`, `_calculate_detail_panel_height()`
- Viewport scrolling mechanism with configurable trigger point
- Conditional key bindings to prevent shortcut conflicts during text input
- Archive folder structure: `tasks/archive/` with its own README.md
- ID mapping for archived tasks: Display IDs continue after active tasks (e.g., 1-15 active, 16-20 archived)

## [0.8.2] - 2025-10-24

### Added

- **Interactive organization prompt for repos-search**: Running `tsk repos-search` without args now prompts for organization
  - Prompts user to enter GitHub organization instead of showing error
  - Offers to save organization as default after entering it
  - Better error messages explaining all options:
    - Interactive prompt to enter organization
    - Command-line usage: `tsk repos-search <org>`
    - How to set default via `tsk config` (interactive menu, option 7)
  - Fixes confusing error message that suggested non-existent CLI syntax

### Fixed

- **Test suite compatibility**: Updated tests to use new `in-progress` status format (hyphenated)
  - Ensures all tests pass with the status format change introduced in 0.8.1

## [0.8.1] - 2025-10-25

### Added

- **Status change commands**: New `tsk in-progress` and `tsk cancelled` commands
  - `tsk in-progress TASK_IDS` - Mark one or more tasks as in progress
  - `tsk cancelled TASK_IDS` - Mark one or more tasks as cancelled
  - Both commands support comma-separated task IDs for batch operations
  - Follow same pattern as `tsk done` command with error handling and summaries
  - Registered in CLI help menu under "Managing Tasks" section

- **Merge conflict handling**: Intelligent detection and resolution of git merge conflicts
  - **Conflict detection**: Checks for conflicts before pulling by fetching and comparing local vs remote
  - **Smart merging**: Timestamp-based automatic resolution
    - Simple fields (status, priority): Uses value from task with newer `modified` timestamp
    - List fields (assignees, tags, links, depends): Creates union of both versions, deduplicated
    - Description conflicts: Requires manual resolution (cannot auto-merge)
  - **Interactive conflict resolver**: Rich TUI for manual resolution
    - Side-by-side comparison of local vs remote versions
    - Highlighted conflicting fields with "← CONFLICT" markers
    - Multiple resolution strategies: Keep [L]ocal, [R]emote, [N]ewer, [M]anual merge, [E]dit
    - Field-by-field manual merge for granular control
    - Text editor integration for complex conflicts
  - **Sync command enhancements**:
    - `--auto-merge/--no-auto-merge` flag (default: True)
    - `--strategy` option: `auto`, `local`, `remote`, `interactive`
    - Conflict resolution happens before pull to prevent git conflicts
    - Resolved conflicts automatically committed before sync continues
  - New modules: `src/taskrepo/utils/merge.py`, `src/taskrepo/tui/conflict_resolver.py`
  - Comprehensive test suite: `tests/unit/test_merge.py`

- **Claude Code skill**: Added comprehensive TaskRepo skill for AI assistant
  - Created `.claude/skills/taskrepo/SKILL.md` with full command documentation
  - Enables Claude to autonomously help with TaskRepo task management
  - Includes all CLI commands, examples, configuration, and best practices

### Changed

- **BREAKING**: Status value format changed from `in_progress` to `in-progress`
  - Updated `Task.VALID_STATUSES` to use hyphenated format
  - All status mappings and filtering logic updated across codebase
  - Existing tasks with old `in_progress` status automatically migrated
  - Consistent with other multi-word status values (e.g., command name `in-progress`)

### Fixed

- Python bytecode cache issues resolved by clearing `__pycache__` directories
- Status validation now properly enforces hyphenated format
- Countdown display bug: Tasks due in 28-44 days no longer show "0 months"
  - Extended weeks display range from 28 to 45 days (up to 6 weeks)
  - Months display only shows for 45+ days to avoid "0 months" for ~1 month tasks
  - Tasks due in 29 days now correctly show "4 weeks" instead of "0 months"

## [0.8.0] - 2025-10-23

### Added

- **GitHub repository search**: New `tsk repos-search` command to discover TaskRepo repositories on GitHub
  - Searches for repositories matching `tasks-*` pattern in a GitHub organization or user
  - Shows which repositories are already cloned locally vs remote-only
  - Interactive multi-select interface to clone multiple repositories at once
  - Uses default_github_org from config if organization not specified
  - Rich table display with color-coded status indicators (✓ cloned / ✗ remote)
  - Includes `--list-only` flag to list without prompting to clone
  - New `list_github_repos()` function in utils/github.py with pattern filtering
  - Helpful error messages for missing GitHub CLI or authentication issues

## [0.7.1] - 2025-10-23

### Added

- **Completed task archiving**: Completed tasks are now automatically moved to `tasks/done/` subfolder
  - Tasks with `status=completed` are moved from `tasks/` to `tasks/done/` immediately when saved
  - Tasks moved back to `tasks/` when status changes from completed to another state
  - `tsk list` hides completed tasks by default (use `--all` to show them)
  - `tsk list --status completed` automatically loads from done/ folder
  - `tsk search` searches both active and completed tasks (use `--all` to include in results)
  - `tsk done` (no args) lists completed tasks from done/ folder
  - Git sync properly commits and pushes done/ folder changes
  - New repositories automatically create `tasks/done/.gitkeep` file
  - Backward compatible: existing completed tasks in `tasks/` continue to work

- **Done folder README**: Automatically generates `tasks/done/README.md` with completed tasks archive
  - Updated during sync command (alongside main README)
  - Shows completed tasks in table format with tree structure
  - Displays "Completed" date (when task was marked done) instead of countdown
  - Archive-focused header: "# Completed Tasks Archive"
  - Relative links to task files within done/ folder

- **GitHub repository existence check**: `tsk create-repo` now checks if repo already exists on GitHub before creation
  - Interactive mode: Warns if repo exists and offers to clone it or create local-only
  - Non-interactive mode: Shows error and exits if repo already exists
  - Prevents accidentally overwriting existing GitHub repositories
  - New `check_github_repo_exists()` helper function in utils/github.py

- **Clone existing GitHub repositories**: New `clone_github_repo()` function enables cloning
  - Integrated into create-repo workflow when repo exists
  - Preserves git history when cloning existing repos
  - Helpful error messages if clone fails with fallback options

- **Repository name preview toolbar**: Real-time preview of full repo name as you type
  - Shows "Will create: tasks-{name}" dynamically in bottom toolbar
  - Helps users understand the final directory name before creation
  - Displays helpful message when input is empty

- **Comma-separated autocomplete**: Autocomplete now works after commas in assignees and tags
  - New `CommaDelimitedCompleter` class for intelligent comma-aware completion
  - Fuzzy matching for each segment after a comma
  - Example: typing "@alice,@bob" shows suggestions after the comma
  - Works for both assignees and tags fields

### Changed

- **Week-based countdown display**: Countdown now shows "2 days", "1 week", "3 months" instead of abbreviated format
- **Week-based clustering for sorting**: Due date clustering now uses one bucket per week instead of mixed time periods
  - Provides more granular grouping while maintaining priority-based sorting within buckets
- **`tsk done` display**: Now shows "Completed" date instead of countdown for completed tasks
  - Displays when each task was marked as completed (using modified timestamp)
  - Makes it easier to track when work was actually finished

### Fixed

- **Assignee sorting with preferred user**: Fixed bug where tasks with preferred assignee not listed first would be sorted incorrectly
  - When using `sort_by: ["assignee:@username"]`, tasks with the preferred assignee are now treated equally regardless of assignee position
  - Previously, tasks with preferred assignee as second or later in the list would sort before tasks with preferred assignee first
  - Now all tasks with the preferred assignee sort together, with secondary sort fields (due, priority) taking precedence

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

[0.9.8]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.8
[0.9.7]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.7
[0.9.6]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.6
[0.9.5]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.5
[0.9.4]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.4
[0.9.3]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.3
[0.9.2]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.2
[0.9.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.1
[0.9.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.9.0
[0.8.2]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.8.2
[0.8.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.8.1
[0.8.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.8.0
[0.7.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.7.1
[0.7.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.7.0
[0.6.2]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.6.2
[0.6.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.6.1
[0.6.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.6.0
[0.5.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.5.0
[0.4.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.4.0
[0.3.2]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.3.2
[0.3.1]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.3.1
[0.2.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.2.0
[0.1.0]: https://github.com/henriqueslab/TaskRepo/releases/tag/v0.1.0
