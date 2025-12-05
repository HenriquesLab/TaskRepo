"""Full-screen TUI for TaskRepo using prompt_toolkit."""

import asyncio
import html
import os
from pathlib import Path
from typing import Optional

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from taskrepo.core.config import Config
from taskrepo.core.repository import Repository, RepositoryManager
from taskrepo.core.task import Task
from taskrepo.tui.display import (
    build_task_tree,
    count_subtasks,
    format_tree_title,
    get_countdown_text,
    pad_to_width,
    truncate_to_width,
)
from taskrepo.utils.id_mapping import get_display_id_from_uuid, save_id_cache
from taskrepo.utils.sorting import sort_tasks


class TaskTUI:
    """Full-screen TUI for managing tasks."""

    def __init__(self, config: Config, repositories: list[Repository]):
        """Initialize the TUI.

        Args:
            config: TaskRepo configuration
            repositories: List of available repositories
        """
        self.config = config
        self.repositories = repositories
        self.view_mode = config.tui_view_mode  # "repo", "project", or "assignee"

        # Build view items based on mode
        self.view_items = self._build_view_items()

        # Start at -1 to show "All" items first
        self.current_view_idx = -1
        self.selected_row = 0
        self.multi_selected: set[str] = set()  # Store task UUIDs
        self.filter_text = ""
        self.tree_view = True
        self.filter_active = False
        self.show_detail_panel = True  # Always show detail panel

        # Auto-reload state
        self.last_mtime = self._get_repositories_mtime()
        self.auto_reload_task: Optional[asyncio.Task] = None
        self.last_reload_time: Optional[float] = None  # timestamp of last reload

        # Background sync state (must be initialized before _calculate_viewport_size)
        self.sync_status = "idle"  # "idle", "syncing", "success", "error"
        self.last_sync_time: Optional[float] = None  # timestamp of last sync
        self.next_sync_time: Optional[float] = None  # timestamp of next scheduled sync
        self.conflicted_repos: set[str] = set()  # repos needing manual resolution
        self.background_sync_task: Optional[asyncio.Task] = None
        self.sync_message: Optional[str] = None  # temporary status bar message
        self.has_unsaved_changes: bool = False  # tracks local modifications since last sync

        # Viewport scrolling state (depends on sync state for height calculation)
        self.viewport_top = 0  # First task visible in viewport
        self.viewport_size = self._calculate_viewport_size()  # Dynamic based on terminal size
        self.scroll_trigger = min(5, max(2, self.viewport_size // 3))  # Start scrolling at 1/3 of viewport
        self.sync_message_time: Optional[float] = None  # when message was set

        # Create filter input widget
        self.filter_input = TextArea(
            height=1,
            prompt="Filter: ",
            multiline=False,
            wrap_lines=False,
        )

        # Build key bindings
        self.kb = self._create_key_bindings()

        # Build layout
        self.layout = self._create_layout()

        # Create style
        self.style = self._create_style()

        # Create application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True,
        )

    def _build_view_items(self) -> list[str]:
        """Build list of view items based on view mode.

        Returns:
            List of view item names (repo names, projects, or assignees)
        """
        if self.view_mode == "repo":
            # Return repository names
            return [repo.name for repo in self.repositories]
        elif self.view_mode == "project":
            # Collect all unique projects from all repos
            projects = set()
            for repo in self.repositories:
                for task in repo.list_tasks():
                    if task.project:
                        projects.add(task.project)
            return sorted(projects)
        elif self.view_mode == "assignee":
            # Collect all unique assignees from all repos
            assignees = set()
            for repo in self.repositories:
                for task in repo.list_tasks():
                    assignees.update(task.assignees)
            return sorted(assignees)
        else:
            # Fallback to repo mode
            return [repo.name for repo in self.repositories]

    def _get_repositories_mtime(self) -> float:
        """Get the latest modification time across all repository task directories.

        Returns:
            Latest modification time as a float timestamp, or 0.0 if no repos
        """
        max_mtime = 0.0
        for repo in self.repositories:
            tasks_dir = Path(repo.path) / "tasks"
            if tasks_dir.exists():
                try:
                    # Check the directory itself
                    dir_mtime = tasks_dir.stat().st_mtime
                    max_mtime = max(max_mtime, dir_mtime)

                    # Check all task files
                    for task_file in tasks_dir.glob("task-*.md"):
                        file_mtime = task_file.stat().st_mtime
                        max_mtime = max(max_mtime, file_mtime)
                except (OSError, PermissionError):
                    # Skip if we can't access the file
                    pass
        return max_mtime

    def _check_for_changes(self) -> bool:
        """Check if any task files have been modified since last check.

        Returns:
            True if changes detected, False otherwise
        """
        current_mtime = self._get_repositories_mtime()
        if current_mtime > self.last_mtime:
            self.last_mtime = current_mtime
            return True
        return False

    def _force_reload(self, preserve_selection: bool = True, select_above: bool = False):
        """Force an immediate reload of repositories and tasks.

        Call this after making changes to tasks to immediately update the display.

        Args:
            preserve_selection: Try to keep selection on the same task (default: True)
            select_above: Move selection one position up (for deleted/archived tasks) (default: False)
        """
        import time

        # Save current selection info before reload
        current_task_uuid = None
        current_position = self.selected_row

        if preserve_selection or select_above:
            tasks = self._get_filtered_tasks()
            if tasks and 0 <= self.selected_row < len(tasks):
                current_task_uuid = tasks[self.selected_row].id

        # Track reload time
        self.last_reload_time = time.time()

        # Update mtime to current
        self.last_mtime = self._get_repositories_mtime()

        # Reload repositories from disk
        manager = RepositoryManager(self.config.parent_dir)
        self.repositories = manager.discover_repositories()

        # Rebuild view items
        self.view_items = self._build_view_items()

        # Update ID cache with all current tasks
        all_tasks = manager.list_all_tasks(include_archived=False)
        sorted_tasks = sort_tasks(all_tasks, self.config, all_tasks=all_tasks)
        save_id_cache(sorted_tasks)

        # Clear multi-selection since task IDs may have changed
        self.multi_selected.clear()

        # Restore selection intelligently
        tasks = self._get_filtered_tasks()

        if select_above:
            # For operations that remove tasks (delete, archive, done), move to task above
            self.selected_row = max(0, current_position - 1)
            if self.selected_row >= len(tasks):
                self.selected_row = max(0, len(tasks) - 1)
        elif preserve_selection and current_task_uuid:
            # Try to find the same task by UUID
            found = False
            for i, task in enumerate(tasks):
                if task.id == current_task_uuid:
                    self.selected_row = i
                    found = True
                    break

            if not found:
                # Task not found (was removed or filtered out), stay at same position
                if current_position >= len(tasks):
                    self.selected_row = max(0, len(tasks) - 1)
                else:
                    self.selected_row = current_position
        else:
            # Default: reset selected row if out of bounds
            if self.selected_row >= len(tasks):
                self.selected_row = max(0, len(tasks) - 1)

        # Invalidate the display to trigger a redraw
        if hasattr(self, "app") and self.app:
            self.app.invalidate()

    def _check_background_sync_status(self):
        """Check global background sync status from CLI and update TUI status."""
        # Import the global flags from tui command module
        try:
            from taskrepo.cli.commands import tui as tui_module

            if tui_module._background_sync_running:
                if self.sync_status != "syncing":
                    self.sync_status = "syncing"
                    self.sync_message = "Syncing repositories..."
                    self.app.invalidate()
            elif tui_module._background_sync_error:
                # Sync failed
                if self.sync_status != "error":
                    self.sync_status = "error"
                    self.sync_message = "Sync failed (press 's' to retry)"
                    self.app.invalidate()
                    # Reset the flag
                    tui_module._background_sync_error = False
            elif tui_module._background_sync_completed:
                # Use the completion time directly from the global variable
                if self.last_sync_time != tui_module._background_sync_completion_time:
                    self.sync_status = "success"
                    self.sync_message = "Sync completed"
                    self.last_sync_time = tui_module._background_sync_completion_time
                    self.has_unsaved_changes = False  # Clear unsaved flag after successful sync
                    self.app.invalidate()
                    # Reset the flag so we don't keep showing success
                    tui_module._background_sync_completed = False
        except (ImportError, AttributeError):
            # If we can't import or access the flags, just skip
            pass

    async def _auto_reload_loop(self):
        """Background task that periodically checks for file changes and reloads."""
        import time

        while True:
            await asyncio.sleep(2)  # Check every 2 seconds

            # Check global background sync status from CLI
            self._check_background_sync_status()

            if self._check_for_changes():
                # Track reload time
                self.last_reload_time = time.time()

                # Reload repositories from disk
                manager = RepositoryManager(self.config.parent_dir)
                self.repositories = manager.discover_repositories()

                # Rebuild view items
                self.view_items = self._build_view_items()

                # Update ID cache with all current tasks
                all_tasks = manager.list_all_tasks(include_archived=False)
                sorted_tasks = sort_tasks(all_tasks, self.config, all_tasks=all_tasks)
                save_id_cache(sorted_tasks)

                # Clear multi-selection since task IDs may have changed
                self.multi_selected.clear()

                # Reset selected row if out of bounds
                tasks = self._get_filtered_tasks()
                if self.selected_row >= len(tasks):
                    self.selected_row = max(0, len(tasks) - 1)

                # Invalidate the display to trigger a redraw
                self.app.invalidate()

    async def _background_sync_loop(self):
        """Background task that periodically syncs repositories."""
        import time

        from taskrepo.utils.sync_history import SyncHistory

        while True:
            await asyncio.sleep(self.config.auto_sync_interval)

            # Skip if user is busy (editing or in a modal)
            if self._should_skip_sync():
                continue

            # Start sync
            self.sync_status = "syncing"
            self.app.invalidate()

            # Sync each repository and track results
            success_count = 0
            error_count = 0
            conflict_count = 0
            repos_synced = []
            repos_failed = []
            error_messages = []

            for repo in self.repositories:
                # Skip repos already marked as conflicted
                if repo.name in self.conflicted_repos:
                    continue

                success, error_msg, has_conflicts = await self._sync_repository_async(repo)

                if success:
                    success_count += 1
                    repos_synced.append(repo.name)
                elif has_conflicts:
                    conflict_count += 1
                    self.conflicted_repos.add(repo.name)
                    repos_failed.append(repo.name)
                    error_messages.append(f"{repo.name}: {error_msg}")
                else:
                    error_count += 1
                    repos_failed.append(repo.name)
                    error_messages.append(f"{repo.name}: {error_msg}")

            # Record sync to history
            sync_history = SyncHistory()
            overall_success = error_count == 0 and conflict_count == 0
            error_summary = "; ".join(error_messages) if error_messages else None

            sync_history.add_entry(
                success=overall_success,
                repos_synced=repos_synced,
                repos_failed=repos_failed,
                error_message=error_summary,
            )

            # Update sync status and message
            self.next_sync_time = time.time() + self.config.auto_sync_interval

            if error_count > 0 or conflict_count > 0:
                self.sync_status = "error"
                # Don't update last_sync_time when there are errors
                if conflict_count > 0:
                    self._set_sync_message(f"⚠ {conflict_count} repo(s) need manual sync")
                else:
                    self._set_sync_message(f"⚠ Sync failed for {error_count} repo(s)")
            else:
                # Only set last_sync_time when sync fully succeeds
                self.last_sync_time = time.time()
                self.sync_status = "success"
                self.has_unsaved_changes = False  # Clear unsaved flag after successful sync
                if success_count > 0:
                    self._set_sync_message(f"✓ Synced {success_count} repo(s)")

            # Reload repositories after sync
            if success_count > 0:
                manager = RepositoryManager(self.config.parent_dir)
                self.repositories = manager.discover_repositories()
                self.view_items = self._build_view_items()

                # Update ID cache
                all_tasks = manager.list_all_tasks(include_archived=False)
                sorted_tasks = sort_tasks(all_tasks, self.config, all_tasks=all_tasks)
                save_id_cache(sorted_tasks)

            self.app.invalidate()

    async def _sync_repository_async(self, repository) -> tuple[bool, str, bool]:
        """Async wrapper for repository sync.

        Args:
            repository: Repository to sync

        Returns:
            Tuple of (success, error_message, has_conflicts)
        """
        from taskrepo.utils.async_sync import sync_repository_background

        # Run sync in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, sync_repository_background, repository, self.config.auto_sync_strategy, self.config
        )

    def _should_skip_sync(self) -> bool:
        """Check if background sync should be skipped.

        Returns:
            True if sync should be skipped
        """
        # Skip if user is editing a task or in a modal
        # We can detect this by checking if the app is showing a dialog
        # For now, we'll always allow sync since we invalidate after
        return False

    def _set_sync_message(self, message: str):
        """Set a temporary status bar message.

        Args:
            message: Message to display
        """
        import time

        self.sync_message = message
        self.sync_message_time = time.time()

    def _get_sync_indicator(self) -> str:
        """Get sync status indicator for header.

        Returns:
            Sync status string (emoji + text)
        """
        if self.sync_status == "syncing":
            return "🔄"
        elif self.sync_status == "success":
            return "✓"
        elif self.sync_status == "error":
            return "⚠"
        else:
            return ""

    def _get_terminal_size(self):
        """Get current terminal size."""
        try:
            terminal_size = os.get_terminal_size()
            return terminal_size.lines, terminal_size.columns
        except (OSError, AttributeError):
            # Fallback if terminal size cannot be determined
            return 40, 120

    def _calculate_viewport_size(self) -> int:
        """Calculate viewport size based on terminal height."""
        terminal_height, _ = self._get_terminal_size()

        # Calculate available space for task rows
        # Fixed UI elements:
        # - Header: 1 line
        # - Task list header + separator: 2 lines
        # - Detail panel content: dynamic (see _calculate_detail_panel_height)
        # - Detail panel Frame borders: 2 lines (top + bottom)
        # - Filter input: 1 line (when visible)
        # - Status bar: dynamic (see _calculate_status_bar_height)
        # - Scroll indicators: 2 lines (max)

        detail_panel_height = self._calculate_detail_panel_height()
        status_bar_height = self._calculate_status_bar_height()
        fixed_lines = 1 + 2 + detail_panel_height + 2 + 1 + status_bar_height + 2  # All fixed elements
        # = header + task header/sep + detail content + frame borders + filter + status + scrollers
        # = detail_panel_height + status_bar_height + 8

        available_lines = terminal_height - fixed_lines

        # Ensure minimum viewport size
        viewport_size = max(6, available_lines)

        # Cap maximum for very tall terminals
        viewport_size = min(50, viewport_size)

        return viewport_size

    def _calculate_detail_panel_height(self) -> int:
        """Calculate detail panel height based on terminal size."""
        terminal_height, _ = self._get_terminal_size()

        # Use about 30% of terminal height for detail panel, but with min/max bounds
        detail_height = int(terminal_height * 0.3)
        detail_height = max(8, min(15, detail_height))

        return detail_height

    def _calculate_status_bar_height(self) -> int:
        """Calculate status bar height based on content and terminal width.

        Returns:
        - 1 line: No status info (just shortcuts on one line or wrapping)
        - 2+ lines: Status info on line 1, shortcuts on line 2+ (wrapped on narrow terminals)
        """
        _, terminal_width = self._get_terminal_size()

        # Build status info to check if we have any
        status_info = self._build_status_info()

        # For narrow terminals, allow shortcuts to wrap
        allow_multiline = terminal_width < 120
        shortcuts = self._get_shortcuts_text(terminal_width, allow_multiline=allow_multiline)

        # Count actual newlines in shortcuts text (smart-wrapped lines)
        shortcuts_lines = shortcuts.count("\n") + 1

        if status_info:
            # Status info takes 1 line, shortcuts on additional lines
            # Total: 1 (status) + N (shortcuts lines)
            total_lines = 1 + shortcuts_lines

            # Cap at 4 lines maximum (1 status + up to 3 for shortcuts)
            return min(4, max(2, total_lines))
        else:
            # Just shortcuts
            # Ensure at least 1 line, max 3 lines
            return max(1, min(3, shortcuts_lines))

    def _create_style(self) -> Style:
        """Create the color scheme for the TUI."""
        return Style.from_dict(
            {
                # Priority colors
                "priority-high": "fg:ansired bold",
                "priority-medium": "fg:ansiyellow",
                "priority-low": "fg:ansigreen",
                # Status colors
                "status-pending": "fg:ansiyellow",
                "status-in-progress": "fg:ansiblue bold",
                "status-completed": "fg:ansigreen",
                "status-cancelled": "fg:ansired",
                # Countdown colors
                "countdown-overdue": "fg:ansired bold",
                "countdown-urgent": "fg:ansiyellow bold",
                "countdown-soon": "fg:ansiyellow",
                "countdown-normal": "fg:ansiwhite",
                # UI elements
                "selected": "bg:ansiblue fg:ansiblack bold",
                "header": "bg:ansiblue fg:ansiwhite bold",
                "scrollbar": "fg:ansicyan",
                "multi-select": "fg:ansigreen bold",
                "field-label": "fg:ansicyan bold",
                "repo": "fg:ansimagenta",
                "project": "fg:ansicyan",
                "assignee": "fg:ansiblue",
                "tag": "fg:ansiyellow",
                "due-date": "fg:ansiwhite",
                "id": "fg:ansibrightblack",
            }
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Create keyboard shortcuts for the TUI."""
        kb = KeyBindings()

        # Quit
        @kb.add("q")
        @kb.add("escape")
        def _(event):
            """Quit the TUI."""
            if self.filter_active:
                # Cancel filter
                self.filter_active = False
                self.filter_text = ""
                self.filter_input.text = ""
            else:
                event.app.exit()

        # Navigation with centered scrolling (only when not filtering)
        @kb.add("up", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Move selection up and scroll viewport if needed."""
            if self.selected_row > 0:
                self.selected_row -= 1

                # Calculate position within viewport
                pos_in_viewport = self.selected_row - self.viewport_top

                # If selected task is above viewport, scroll up
                if pos_in_viewport < 0:
                    self.viewport_top = self.selected_row

        @kb.add("down", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Move selection down and scroll viewport if needed."""
            tasks = self._get_filtered_tasks()
            if self.selected_row < len(tasks) - 1:
                self.selected_row += 1

                # Calculate position within viewport
                pos_in_viewport = self.selected_row - self.viewport_top

                # Start scrolling when selection reaches scroll_trigger position
                if pos_in_viewport > self.scroll_trigger:
                    # Keep selected task at scroll_trigger position
                    self.viewport_top = self.selected_row - self.scroll_trigger
                    # Ensure we don't scroll past the end
                    max_viewport_top = max(0, len(tasks) - self.viewport_size)
                    self.viewport_top = min(self.viewport_top, max_viewport_top)

        @kb.add("home", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Move to first task."""
            self.selected_row = 0
            self.viewport_top = 0

        @kb.add("end", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Move to last task."""
            tasks = self._get_filtered_tasks()
            if tasks:
                self.selected_row = len(tasks) - 1
                # Position viewport to show last task
                # Try to keep last task at scroll_trigger position, or show at bottom if not enough tasks
                self.viewport_top = max(0, self.selected_row - self.scroll_trigger)
                # But don't scroll past the maximum
                max_viewport_top = max(0, len(tasks) - self.viewport_size)
                self.viewport_top = min(self.viewport_top, max_viewport_top)

        # View switching with left/right arrows (only when not filtering)
        @kb.add("right", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Switch to next view (repo/project/assignee)."""
            # Cycle through: -1 (All) -> 0 -> 1 -> ... -> N-1 -> -1 (All)
            self.current_view_idx = (self.current_view_idx + 2) % (len(self.view_items) + 1) - 1
            self.selected_row = 0
            self.viewport_top = 0  # Reset viewport
            self.multi_selected.clear()

        @kb.add("left", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Switch to previous view (repo/project/assignee)."""
            # Cycle backward: -1 (All) -> N-1 -> ... -> 1 -> 0 -> -1 (All)
            self.current_view_idx = (self.current_view_idx) % (len(self.view_items) + 1) - 1
            self.selected_row = 0
            self.viewport_top = 0  # Reset viewport
            self.multi_selected.clear()

        # Tab to switch view type (only when not filtering)
        @kb.add("tab", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Switch view type (repo -> project -> assignee -> repo)."""
            # Cycle through view modes
            view_modes = ["repo", "project", "assignee"]
            current_idx = view_modes.index(self.view_mode)
            next_idx = (current_idx + 1) % len(view_modes)
            self.view_mode = view_modes[next_idx]

            # Save to config for persistence
            self.config.tui_view_mode = self.view_mode

            # Rebuild view items for new mode
            self.view_items = self._build_view_items()

            # Reset to "All" view
            self.current_view_idx = -1
            self.selected_row = 0
            self.viewport_top = 0
            self.multi_selected.clear()

        # Multi-select (only when not filtering)
        @kb.add("space", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Toggle multi-select for current task."""
            tasks = self._get_filtered_tasks()
            if tasks and 0 <= self.selected_row < len(tasks):
                task_id = tasks[self.selected_row].id
                if task_id in self.multi_selected:
                    self.multi_selected.remove(task_id)
                else:
                    self.multi_selected.add(task_id)

        # Task operations (only when not filtering)
        @kb.add("a", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Create a new task."""
            event.app.exit(result="new")

        @kb.add("e", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Edit selected task(s)."""
            event.app.exit(result="edit")

        @kb.add("d", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Mark task(s) as completed (done)."""
            event.app.exit(result="done")

        @kb.add("p", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Mark task(s) as in-progress."""
            event.app.exit(result="in-progress")

        @kb.add("c", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Mark task(s) as cancelled."""
            event.app.exit(result="cancelled")

        @kb.add("l", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Delete task(s)."""
            event.app.exit(result="delete")

        @kb.add("v", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Archive task(s)."""
            event.app.exit(result="archive")

        @kb.add("m", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Move task(s) to another repository."""
            event.app.exit(result="move")

        @kb.add("u", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Create subtask under selected task."""
            event.app.exit(result="subtask")

        @kb.add("t", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Extend task due date."""
            event.app.exit(result="extend")

        # Priority change operations (only when not filtering)
        @kb.add("H", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Set task(s) priority to High."""
            event.app.exit(result="priority-high")

        @kb.add("M", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Set task(s) priority to Medium."""
            event.app.exit(result="priority-medium")

        @kb.add("L", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Set task(s) priority to Low."""
            event.app.exit(result="priority-low")

        # View operations (only when not filtering)
        @kb.add("r", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Toggle tree view."""
            self.tree_view = not self.tree_view

        @kb.add("s", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Sync with git."""
            event.app.exit(result="sync")

        @kb.add("/", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Activate filter mode."""
            self.filter_active = True
            event.app.layout.focus(self.filter_input)

        @kb.add("enter")
        def _(event):
            """View task details or confirm filter."""
            if self.filter_active:
                # Apply filter
                self.filter_text = self.filter_input.text
                self.filter_active = False
                self.selected_row = 0
                # Focus returns automatically when filter is hidden
            else:
                # View task info
                event.app.exit(result="info")

        return kb

    def _create_layout(self) -> Layout:
        """Create the TUI layout."""
        # Header showing current repo and filter
        header = Window(
            content=FormattedTextControl(self._get_header_text),
            height=Dimension.exact(1),
            style="bg:ansiblue fg:ansiwhite bold",
        )

        # Task list
        task_list = Window(
            content=FormattedTextControl(self._get_task_list_text),
            wrap_lines=False,
            always_hide_cursor=True,
        )

        # Detail panel showing extended task info
        detail_panel_content = Window(
            content=FormattedTextControl(self._get_task_detail_text),
            height=lambda: Dimension.exact(self._calculate_detail_panel_height()),  # Dynamic height
            wrap_lines=True,
        )

        # Wrap detail panel in a Frame for border
        detail_panel_with_frame = Frame(
            body=detail_panel_content,
            title="Task Details",
        )

        # Conditional detail panel
        detail_container = ConditionalContainer(
            detail_panel_with_frame,
            filter=Condition(lambda: self.show_detail_panel),
        )

        # Status bar with keyboard shortcuts
        status_bar = Window(
            content=FormattedTextControl(self._get_status_bar_text),
            height=lambda: Dimension.exact(self._calculate_status_bar_height()),  # Dynamic height
            wrap_lines=True,
            style="bg:ansiblack fg:ansiwhite",
        )

        # Conditional filter window
        filter_container = ConditionalContainer(
            self.filter_input,
            filter=Condition(lambda: self.filter_active),
        )

        # Main layout
        root_container = HSplit(
            [
                header,
                task_list,
                detail_container,  # Detail panel between task list and filter
                filter_container,
                status_bar,
            ]
        )

        return Layout(root_container)

    def _get_header_text(self) -> FormattedText:
        """Get the header text showing current view and filter."""
        if not self.repositories:
            return HTML("<b>No repositories found</b>")

        # Determine view label based on mode
        view_label_map = {"repo": "Repository", "project": "Project", "assignee": "Assignee"}
        view_label = view_label_map.get(self.view_mode, "View")

        # Show "All" when index is -1
        if self.current_view_idx == -1:
            if self.view_mode == "repo":
                view_name = "All Repositories"
            elif self.view_mode == "project":
                view_name = "All Projects"
            elif self.view_mode == "assignee":
                view_name = "All Assignees"
            else:
                view_name = "All"
            current_pos = 1
        else:
            view_name = self.view_items[self.current_view_idx]
            current_pos = self.current_view_idx + 2  # +2 because "All" is position 1

        total_tabs = len(self.view_items) + 1  # +1 for "All" tab
        view_info = f"{view_label}: {html.escape(view_name)} ({current_pos}/{total_tabs}) [←/→ items | Tab: view type]"

        if self.filter_text:
            view_info += f" | Filter: '{html.escape(self.filter_text)}'"

        # Sync status is now shown in bottom status bar, no need for top bar indicator

        return HTML(f"<b> {view_info} </b>")

    def _build_status_info(self) -> str:
        """Build status information string with sync/reload/conflict info.

        Returns:
            HTML-formatted status string with priority information
        """
        from taskrepo.utils.sync_history import SyncHistory
        from taskrepo.utils.time_format import format_interval, format_time_ago

        parts = []

        # Priority 1: Conflict warnings (highest priority)
        if self.conflicted_repos:
            count = len(self.conflicted_repos)
            parts.append(f"<yellow>⚠ {count} repo{'s' if count > 1 else ''} need manual sync</yellow>")

        # Priority 2: Active sync status
        if self.sync_status == "syncing":
            parts.append("<cyan>🔄 Syncing...</cyan>")

        # Priority 3: Last sync status from history (reliable source of truth)
        if self.config.auto_sync_enabled:
            sync_history = SyncHistory()
            last_sync = sync_history.get_last_sync()

            if last_sync:
                sync_time_str = format_time_ago(last_sync.timestamp)

                if not last_sync.success:
                    # Show error from history (only if not already showing conflicts)
                    if not self.conflicted_repos:
                        failed_count = len(last_sync.repos_failed)
                        parts.append(
                            f"<red>✗ Sync failed {sync_time_str} ({failed_count} repo{'s' if failed_count != 1 else ''})</red>"
                        )
                elif self.has_unsaved_changes:
                    # Successful sync but have local changes
                    repo_count = len(last_sync.repos_synced)
                    if repo_count > 1:
                        parts.append(f"<yellow>Synced {sync_time_str} ({repo_count} repos, unsaved)</yellow>")
                    else:
                        parts.append(f"<yellow>Synced {sync_time_str} (unsaved)</yellow>")
                else:
                    # Successful sync, no local changes
                    repo_count = len(last_sync.repos_synced)
                    if repo_count > 1:
                        parts.append(f"<green>Synced {sync_time_str} ({repo_count} repos)</green>")
                    else:
                        parts.append(f"<green>Synced {sync_time_str}</green>")
            else:
                parts.append("<dim>Not synced yet</dim>")

        # Priority 4: Last reload time
        if self.last_reload_time:
            reload_time_str = format_time_ago(self.last_reload_time)
            parts.append(f"<blue>Reloaded {reload_time_str}</blue>")

        # Priority 5: Auto-sync status (if enabled)
        if self.config.auto_sync_enabled:
            interval_str = format_interval(self.config.auto_sync_interval)
            parts.append(f"<dim>Auto-sync: ON ({interval_str})</dim>")

        return " | ".join(parts) if parts else ""

    def _get_shortcuts_text(self, terminal_width: int, allow_multiline: bool = False) -> str:
        """Get keyboard shortcuts based on terminal width.

        Args:
            terminal_width: Current terminal width in columns
            allow_multiline: If True, return full shortcuts even on narrow terminals
                            (they'll wrap to multiple lines with smart word-break logic)

        Returns:
            HTML-formatted shortcuts string responsive to width
        """
        # Very narrow (<80 cols): Just help hint (unless multiline allowed)
        if terminal_width < 80 and not allow_multiline:
            return "[?]help"

        # ==================================================================================
        # KEYBOARD SHORTCUT DISPLAY DESIGN PRINCIPLE:
        # ==================================================================================
        # ALWAYS use letters FROM WITHIN the word itself (not before it) when possible.
        #
        # ✅ GOOD:    [c]ancelled    ar[v]hive    de[l]ete    [p]rogress    t[r]ee
        # ❌ BAD:     [c]cancelled   [v]archive   [l]delete   [p]rogress    [r]tree
        #
        # Why? It's more intuitive and memorable - users see the letter highlighted
        # within the actual word they're reading. Exceptions only when:
        # 1. The letter doesn't exist in the word (e.g., [/]filter uses /)
        # 2. First letter is clearer and unambiguous (e.g., [a]dd, [e]dit, [d]one)
        #
        # ⚠️  DO NOT change this pattern without strong justification - it improves UX!
        # ==================================================================================

        # When multiline is allowed, manually wrap to avoid breaking words
        if allow_multiline:
            # Standard shortcuts as a list
            shortcuts_list = [
                "[a]dd",
                "[e]dit",
                "[d]one",
                "[p]rogress",
                "[c]ancelled",
                "[H][M][L]",
                "ar[v]hive",
                "[m]ove",
                "de[l]ete",
                "s[u]btask",
                "ex[t]end",
                "[s]ync",
                "[/]filter",
                "t[r]ee",
                "[q]uit",
            ]

            # Smart wrap: build lines that fit within terminal width without breaking words
            lines = []
            current_line = ""
            padding = 2  # Account for " " padding on each side

            for shortcut in shortcuts_list:
                # Check if adding this shortcut would exceed terminal width
                test_line = f"{current_line} {shortcut}".strip()
                if len(test_line) + padding <= terminal_width:
                    current_line = test_line
                else:
                    # Line is full, start a new one
                    if current_line:
                        lines.append(current_line)
                    current_line = shortcut

            # Add the last line
            if current_line:
                lines.append(current_line)

            return "\n ".join(lines)

        # Medium width (120-160 cols): Standard shortcuts on one line
        if terminal_width < 160:
            return "[a]dd [e]dit [d]one [p]rogress [c]ancelled [H][M][L] ar[v]hive [m]ove de[l]ete s[u]btask ex[t]end [s]ync [/]filter t[r]ee [q]uit"

        # Wide (>=160 cols): Full shortcuts with multi-select hint
        return (
            "[a]dd [e]dit [d]one [p]rogress [c]ancelled [H][M][L] ar[v]hive [m]ove de[l]ete "
            "s[u]btask ex[t]end [s]ync [/]filter t[r]ee [q]uit | Multi-select: Space"
        )

    def _get_status_bar_text(self) -> FormattedText:
        """Get status bar with sync/reload info and responsive shortcuts.

        Returns a multi-line status bar:
        - Line 1: Status info (sync/reload times, conflicts, auto-sync status)
        - Lines 2+: Keyboard shortcuts (will wrap on narrow terminals to show all shortcuts)

        On narrow terminals (<120 cols), shortcuts wrap to multiple lines automatically,
        ensuring all shortcuts are visible even on 80-column terminals.
        """
        # Get terminal width for responsive layout
        _, terminal_width = self._get_terminal_size()

        # Build status information (always priority)
        status_info = self._build_status_info()

        # Always allow shortcuts to wrap to multiple lines if needed
        # This ensures shortcuts are visible even when terminal is too narrow for single line
        allow_multiline = True

        # Get shortcuts based on terminal width (with multiline wrapping when needed)
        shortcuts = self._get_shortcuts_text(terminal_width, allow_multiline=allow_multiline)

        # Always use separate lines for status and shortcuts when status exists
        if status_info:
            return HTML(f" {status_info}\n {shortcuts} ")
        else:
            # Just shortcuts if no status info
            return HTML(f" {shortcuts} ")

    def _get_task_detail_text(self) -> FormattedText:
        """Get formatted details for the currently selected task."""
        tasks = self._get_filtered_tasks()

        # Check if there's a selected task
        if not tasks or self.selected_row < 0 or self.selected_row >= len(tasks):
            return HTML("<dim>No task selected</dim>")

        task = tasks[self.selected_row]

        # Get display ID (zero-padded to 3 digits for consistent width)
        display_id = get_display_id_from_uuid(task.id)
        display_id_str = f"{display_id:03d}" if display_id else f"{task.id[:8]}..."

        # Build detail sections
        lines = []

        # Title header
        lines.append(f"<b>Task [{display_id_str}]: {html.escape(task.title)}</b>\n\n")

        # Metadata line 1: Repo, Project, Status, Priority
        repo = html.escape(task.repo) if task.repo else "-"
        project = html.escape(task.project) if task.project else "-"

        # Color-code status
        status_color_map = {
            "pending": "yellow",
            "in-progress": "blue",
            "completed": "green",
            "cancelled": "red",
        }
        status_color = status_color_map.get(task.status, "white")

        # Color-code priority
        priority_color_map = {"H": "red", "M": "yellow", "L": "green"}
        priority_color = priority_color_map.get(task.priority, "white")

        lines.append(
            f"<cyan>Repo:</cyan> <magenta>{repo}</magenta> | "
            f"<cyan>Project:</cyan> <cyan>{project}</cyan> | "
            f"<cyan>Status:</cyan> <{status_color}><b>{task.status}</b></{status_color}> | "
            f"<cyan>Priority:</cyan> <{priority_color}><b>{task.priority}</b></{priority_color}>\n"
        )

        # Metadata line 2: Timestamps
        created_str = task.created.strftime("%Y-%m-%d %H:%M") if task.created else "-"
        modified_str = task.modified.strftime("%Y-%m-%d %H:%M") if task.modified else "-"
        lines.append(f"<cyan>Created:</cyan> {created_str} | <cyan>Modified:</cyan> {modified_str}\n")

        # Metadata line 3: Assignees, Tags, Due
        assignees = ", ".join(html.escape(a) for a in task.assignees) if task.assignees else "-"
        tags = ", ".join(html.escape(t) for t in task.tags) if task.tags else "-"
        due_str = task.due.strftime("%Y-%m-%d") if task.due else "-"

        # Color-code assignees and tags
        lines.append(
            f"<cyan>Assigned:</cyan> <blue>{assignees}</blue> | "
            f"<cyan>Tags:</cyan> <yellow>{tags}</yellow> | "
            f"<cyan>Due:</cyan> {due_str}\n"
        )

        # Links section
        if task.links:
            lines.append("\n<cyan><b>Links:</b></cyan>\n")
            for link in task.links:
                lines.append(f"  • {html.escape(link)}\n")

        # Dependencies section
        deps_info = []
        if task.parent:
            deps_info.append(f"Parent: {html.escape(task.parent)}")
        if task.depends:
            deps_info.append(f"Depends on: {', '.join(html.escape(d) for d in task.depends)}")
        if deps_info:
            lines.append(f"\n<cyan><b>Dependencies:</b></cyan> {' | '.join(deps_info)}\n")

        # Description section
        if task.description:
            lines.append("\n<cyan><b>Description:</b></cyan>\n")
            # Limit description to first 10 lines for display
            desc_lines = task.description.split("\n")
            display_lines = desc_lines[:10]
            for line in display_lines:
                lines.append(f"{html.escape(line)}\n")
            if len(desc_lines) > 10:
                lines.append(f"<dim>... ({len(desc_lines) - 10} more lines)</dim>\n")

        return HTML("".join(lines))

    def _get_current_repo(self) -> Optional[Repository]:
        """Get the currently selected repository (only valid in repo mode).

        Returns None when not in repo mode or showing all items (index -1).
        """
        if self.view_mode != "repo":
            return None
        if not self.repositories:
            return None
        if self.current_view_idx == -1:
            return None
        # Get repository by name
        repo_name = self.view_items[self.current_view_idx]
        return next((r for r in self.repositories if r.name == repo_name), None)

    def _get_filtered_tasks(self) -> list[Task]:
        """Get tasks from current view with filters applied."""
        # Load all tasks first
        all_tasks = []
        for repo in self.repositories:
            all_tasks.extend(repo.list_tasks())

        # Filter by current view
        if self.current_view_idx == -1:
            # Show all tasks
            tasks = all_tasks
        else:
            # Check if current_view_idx is still valid (it may be out of bounds after archiving/deleting)
            if self.current_view_idx >= len(self.view_items):
                # Index out of bounds - reset to "All" view
                self.current_view_idx = -1
                tasks = all_tasks
            else:
                # Filter based on view mode
                current_view_value = self.view_items[self.current_view_idx]

                if self.view_mode == "repo":
                    # Filter by repository
                    tasks = [t for t in all_tasks if t.repo == current_view_value]
                elif self.view_mode == "project":
                    # Filter by project
                    tasks = [t for t in all_tasks if t.project == current_view_value]
                elif self.view_mode == "assignee":
                    # Filter by assignee
                    tasks = [t for t in all_tasks if current_view_value in t.assignees]
                else:
                    tasks = all_tasks

        # Apply text filter if active
        if self.filter_text:
            filter_lower = self.filter_text.lower()
            tasks = [
                t
                for t in tasks
                if (
                    filter_lower in t.title.lower()
                    or (t.description and filter_lower in t.description.lower())
                    or (t.project and filter_lower in t.project.lower())
                    or any(filter_lower in tag.lower() for tag in t.tags)
                    or any(filter_lower in assignee.lower() for assignee in t.assignees)
                )
            ]

        # Sort tasks
        if self.tree_view:
            # Separate top-level and subtasks
            top_level = [t for t in tasks if not t.parent]
            subtasks = [t for t in tasks if t.parent]
            # Pass all tasks for effective due date calculation
            sorted_top_level = sort_tasks(top_level, self.config, all_tasks=tasks)
            tree_items = build_task_tree(sorted_top_level + subtasks, self.config)
            return [item[0] for item in tree_items]
        else:
            return sort_tasks(tasks, self.config, all_tasks=tasks)

    def _get_task_list_text(self) -> FormattedText:
        """Get formatted task list for viewport display."""
        # Recalculate viewport size dynamically based on current terminal size
        self.viewport_size = self._calculate_viewport_size()
        self.scroll_trigger = min(5, max(2, self.viewport_size // 3))

        tasks = self._get_filtered_tasks()

        if not tasks:
            return HTML("<yellow>No tasks found. Press 'n' to create one.</yellow>")

        # Determine which column to hide (only when viewing specific item, not "All")
        hide_repo = self.view_mode == "repo" and self.current_view_idx >= 0
        hide_project = self.view_mode == "project" and self.current_view_idx >= 0
        hide_assignee = self.view_mode == "assignee" and self.current_view_idx >= 0

        # Build tree structure if needed
        if self.tree_view:
            tree_items = [(tasks[i], 0, False, []) for i in range(len(tasks))]
            # Rebuild tree structure properly
            top_level = [t for t in tasks if not t.parent]
            subtasks = [t for t in tasks if t.parent]
            if top_level or subtasks:
                tree_items = build_task_tree(tasks, self.config)
        else:
            tree_items = [(task, 0, False, []) for task in tasks]

        # Calculate viewport boundaries
        viewport_bottom = min(self.viewport_top + self.viewport_size, len(tree_items))
        viewport_items = tree_items[self.viewport_top : viewport_bottom]

        # Calculate column widths dynamically based on terminal width
        _, terminal_width = self._get_terminal_size()

        # Define minimum and preferred widths for each column
        # Fixed width columns (don't expand)
        max_id_width = 4  # Accommodate 3-digit zero-padded IDs (001-999)
        max_status_width = 7
        max_priority_width = 3
        max_due_width = 10
        max_countdown_width = 9

        # Calculate space used by fixed columns and separators
        fixed_width = max_id_width + max_status_width + max_priority_width + max_due_width + max_countdown_width

        # Calculate number of separators dynamically based on visible columns
        # Each visible column has 1 space separator, except:
        # - ID column has its marker (no additional space)
        # - Due/Count has 4 spaces between them (3 extra + 1 normal)
        num_visible_cols = 5  # ID, Title, Status, Priority, Tags (always visible)
        if not hide_repo:
            num_visible_cols += 1  # Repo
        if not hide_project:
            num_visible_cols += 1  # Project
        if not hide_assignee:
            num_visible_cols += 1  # Assignee
        num_visible_cols += 2  # Due and Count

        # Each column gets 1 separator space, except ID (no space before) and Count (no space after)
        # Plus 3 extra spaces between Due and Count
        separators = num_visible_cols - 1 + 3

        # Calculate remaining space for flexible columns
        remaining_width = terminal_width - fixed_width - separators - 2  # -2 for margins

        # Distribute remaining space among flexible columns
        # Priority: Title > Repo/Project/Assignees/Tags (equal distribution)
        if remaining_width < 60:
            # Narrow terminal: use minimum widths
            max_title_width = 20
            max_repo_width = 8
            max_project_width = 8
            max_assignees_width = 8
            max_tags_width = 6
        else:
            # Wide terminal: distribute space
            # Title gets 40% of remaining space, others share the rest
            max_title_width = max(25, int(remaining_width * 0.4))
            other_space = remaining_width - max_title_width
            each_other = max(8, other_space // 4)
            max_repo_width = each_other
            max_project_width = each_other
            max_assignees_width = each_other
            max_tags_width = each_other

        # Adjust widths for hidden columns - give space to title
        freed_space = 0
        if hide_repo:
            freed_space += max_repo_width + 1  # +1 for separator
            max_repo_width = 0
        if hide_project:
            freed_space += max_project_width + 1  # +1 for separator
            max_project_width = 0
        if hide_assignee:
            freed_space += max_assignees_width + 1  # +1 for separator
            max_assignees_width = 0

        # Add freed space to title column
        max_title_width += freed_space

        # Build result
        result = []

        # Build header with abbreviated column names, conditionally including columns
        header_parts = []
        header_parts.append(f"{'ID':<{max_id_width}} ")
        header_parts.append(f"{'Title':<{max_title_width}} ")
        if not hide_repo:
            header_parts.append(f"{'Repo':<{max_repo_width}} ")
        if not hide_project:
            header_parts.append(f"{'Proj':<{max_project_width}} ")  # Project -> Proj
        header_parts.append(f"{'Status':<{max_status_width}} ")
        header_parts.append(f"{'P':<{max_priority_width}} ")  # Pri -> P
        if not hide_assignee:
            header_parts.append(f"{'Assign':<{max_assignees_width}} ")  # Assigned -> Assign
        header_parts.append(f"{'Tags':<{max_tags_width}} ")
        header_parts.append(f"{'Due':<{max_due_width}}    ")  # Extra spacing before Countdown
        header_parts.append(f"{'Count':<{max_countdown_width}}")  # Countdown -> Count

        header = "".join(header_parts)
        table_width = len(header)

        # Add scroll indicator at top if there are tasks above viewport
        if self.viewport_top > 0:
            scroll_msg = f"▲ {self.viewport_top} more above"
            result.append(("class:scrollbar", f"{scroll_msg:^{table_width}}\n"))
        result.append(("class:header", header + "\n"))
        result.append(("class:header", "─" * len(header) + "\n"))

        # Build task rows (only viewport items)
        for viewport_idx, (task, depth, is_last, ancestors) in enumerate(viewport_items):
            # Calculate actual index in full task list
            actual_idx = self.viewport_top + viewport_idx
            is_selected = actual_idx == self.selected_row
            is_multi_selected = task.id in self.multi_selected

            # Get display ID (zero-padded to 3 digits for consistent width)
            display_id = get_display_id_from_uuid(task.id)
            display_id_str = f"{display_id:03d}" if display_id else f"{task.id[:8]}..."

            # Format title with tree structure and selection markers
            if self.tree_view:
                all_repo_tasks = self._get_current_repo().list_tasks() if self._get_current_repo() else []
                subtask_count = count_subtasks(task, all_repo_tasks)
                formatted_title = format_tree_title(task.title, depth, is_last, ancestors, subtask_count)
            else:
                formatted_title = task.title

            # Truncate title if too long (account for multi-select marker)
            # Use display width to properly handle emojis and wide characters
            title_space = max_title_width - 2  # Reserve space for markers
            formatted_title = truncate_to_width(formatted_title, title_space)

            # Add selection markers
            selection_marker = ">" if is_selected else " "
            multi_marker = "✓" if is_multi_selected else " "

            # Format other fields with proper truncation
            repo_str = (task.repo or "-")[:max_repo_width]
            project_str = (task.project or "-")[:max_project_width]

            # Abbreviate status for compact display
            status_map = {"pending": "pending", "in-progress": "progres", "completed": "done", "cancelled": "cancel"}
            status_str = status_map.get(task.status, task.status)[:max_status_width]
            priority_str = task.priority
            assignees_str = (", ".join(task.assignees) if task.assignees else "-")[:max_assignees_width]
            tags_str = (", ".join(task.tags) if task.tags else "-")[:max_tags_width]
            due_str = (task.due.strftime("%Y-%m-%d") if task.due else "-")[:max_due_width]

            # Format countdown with color
            if task.due:
                countdown_text, countdown_color = get_countdown_text(task.due, task.status)
                countdown_text = countdown_text[:max_countdown_width]
                # Map colors to style classes
                countdown_style_map = {
                    "red": "class:countdown-overdue",
                    "yellow": "class:countdown-urgent",
                    "green": "class:countdown-normal",
                }
                countdown_style = countdown_style_map.get(countdown_color, "")
            else:
                countdown_text = "-"
                countdown_style = ""

            # Get style classes for priority and status
            priority_style_map = {"H": "class:priority-high", "M": "class:priority-medium", "L": "class:priority-low"}
            priority_style = priority_style_map.get(task.priority, "")

            status_style_map = {
                "pending": "class:status-pending",
                "in-progress": "class:status-in-progress",
                "completed": "class:status-completed",
                "cancelled": "class:status-cancelled",
            }
            status_style = status_style_map.get(task.status, "")

            # Build the row with colored segments
            if is_selected:
                # Selected row - use selected style for entire row
                row_parts = []
                row_parts.append(f"{selection_marker}")
                row_parts.append(f"{display_id_str:<{max_id_width - 1}} ")
                # Pad title with display width awareness
                padded_title = pad_to_width(formatted_title, max_title_width - 2)
                row_parts.append(f"{multi_marker} {padded_title} ")
                if not hide_repo:
                    row_parts.append(f"{repo_str:<{max_repo_width}} ")
                if not hide_project:
                    row_parts.append(f"{project_str:<{max_project_width}} ")
                row_parts.append(f"{status_str:<{max_status_width}} ")
                row_parts.append(f"{priority_str:<{max_priority_width}} ")
                if not hide_assignee:
                    row_parts.append(f"{assignees_str:<{max_assignees_width}} ")
                row_parts.append(f"{tags_str:<{max_tags_width}} ")
                row_parts.append(f"{due_str:<{max_due_width}}    ")  # Extra spacing before Countdown
                row_parts.append(f"{countdown_text:<{max_countdown_width}}")

                row = "".join(row_parts)
                result.append(("class:selected", row + "\n"))
            else:
                # Unselected row - use individual field colors
                # Selection marker and ID
                result.append(("", selection_marker))
                result.append(("class:id", f"{display_id_str:<{max_id_width - 1}} "))

                # Multi-select marker
                if is_multi_selected:
                    result.append(("class:multi-select", multi_marker))
                else:
                    result.append(("", multi_marker))

                # Title (pad with display width awareness)
                padded_title = pad_to_width(formatted_title, max_title_width - 2)
                result.append(("", f" {padded_title} "))

                # Repo (conditional)
                if not hide_repo:
                    result.append(("class:repo", f"{repo_str:<{max_repo_width}} "))

                # Project (conditional)
                if not hide_project:
                    result.append(("class:project", f"{project_str:<{max_project_width}} "))

                # Status (colored)
                result.append((status_style, f"{status_str:<{max_status_width}} "))

                # Priority (colored)
                result.append((priority_style, f"{priority_str:<{max_priority_width}} "))

                # Assignees (conditional)
                if not hide_assignee:
                    result.append(("class:assignee", f"{assignees_str:<{max_assignees_width}} "))

                # Tags
                result.append(("class:tag", f"{tags_str:<{max_tags_width}} "))

                # Due date
                result.append(("class:due-date", f"{due_str:<{max_due_width}}    "))  # Extra spacing before Countdown

                # Countdown (colored)
                result.append((countdown_style, f"{countdown_text:<{max_countdown_width}}"))

                result.append(("", "\n"))

        # Add scroll indicator at bottom if there are tasks below viewport
        if viewport_bottom < len(tree_items):
            remaining = len(tree_items) - viewport_bottom
            scroll_msg = f"▼ {remaining} more below"
            result.append(("class:scrollbar", f"{scroll_msg:^{table_width}}\n"))

        return FormattedText(result)

    def _get_selected_tasks(self) -> list[Task]:
        """Get the currently selected task(s) for operations."""
        tasks = self._get_filtered_tasks()

        if self.multi_selected:
            # Return all multi-selected tasks
            return [t for t in tasks if t.id in self.multi_selected]
        elif tasks and 0 <= self.selected_row < len(tasks):
            # Return single selected task
            return [tasks[self.selected_row]]
        return []

    def run(self) -> Optional[str]:
        """Run the TUI application.

        Returns:
            Action result string or None
        """

        # Run the application with async support for background tasks
        async def run_with_background_tasks():
            # Start auto-reload background task
            self.auto_reload_task = asyncio.create_task(self._auto_reload_loop())

            # Start background sync task if enabled
            if self.config.auto_sync_enabled:
                self.background_sync_task = asyncio.create_task(self._background_sync_loop())

            try:
                return await self.app.run_async()
            finally:
                # Cancel background tasks when exiting
                if self.auto_reload_task:
                    self.auto_reload_task.cancel()
                    try:
                        await self.auto_reload_task
                    except asyncio.CancelledError:
                        pass

                if self.background_sync_task:
                    self.background_sync_task.cancel()
                    try:
                        await self.background_sync_task
                    except asyncio.CancelledError:
                        pass

        # Run the async function
        return asyncio.run(run_with_background_tasks())
