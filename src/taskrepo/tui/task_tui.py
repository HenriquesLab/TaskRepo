"""Full-screen TUI for TaskRepo using prompt_toolkit."""

import asyncio
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

        # Viewport scrolling state
        self.viewport_top = 0  # First task visible in viewport
        self.viewport_size = self._calculate_viewport_size()  # Dynamic based on terminal size
        self.scroll_trigger = min(5, max(2, self.viewport_size // 3))  # Start scrolling at 1/3 of viewport

        # Auto-reload state
        self.last_mtime = self._get_repositories_mtime()
        self.auto_reload_task: Optional[asyncio.Task] = None

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

    async def _auto_reload_loop(self):
        """Background task that periodically checks for file changes and reloads."""
        while True:
            await asyncio.sleep(2)  # Check every 2 seconds

            if self._check_for_changes():
                # Reload repositories from disk
                manager = RepositoryManager(self.config.parent_dir)
                self.repositories = manager.discover_repositories()

                # Rebuild view items
                self.view_items = self._build_view_items()

                # Update ID cache with all current tasks
                all_tasks = manager.list_all_tasks(include_archived=False)
                sorted_tasks = sort_tasks(all_tasks, self.config)
                save_id_cache(sorted_tasks)

                # Clear multi-selection since task IDs may have changed
                self.multi_selected.clear()

                # Reset selected row if out of bounds
                tasks = self._get_filtered_tasks()
                if self.selected_row >= len(tasks):
                    self.selected_row = max(0, len(tasks) - 1)

                # Invalidate the display to trigger a redraw
                self.app.invalidate()

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
        # - Status bar: 1 line
        # - Scroll indicators: 2 lines (max)

        detail_panel_height = self._calculate_detail_panel_height()
        fixed_lines = 1 + 2 + detail_panel_height + 2 + 1 + 1 + 2  # All fixed elements
        # = header + task header/sep + detail content + frame borders + filter + status + scrollers
        # = detail_panel_height + 9

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
        @kb.add("n", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Create a new task."""
            event.app.exit(result="new")

        @kb.add("e", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Edit selected task(s)."""
            event.app.exit(result="edit")

        @kb.add("d", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Mark task(s) as done."""
            event.app.exit(result="done")

        @kb.add("p", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Mark task(s) as in-progress."""
            event.app.exit(result="in-progress")

        @kb.add("c", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Mark task(s) as cancelled."""
            event.app.exit(result="cancelled")

        @kb.add("x", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Delete task(s)."""
            event.app.exit(result="delete")

        @kb.add("a", filter=Condition(lambda: not self.filter_active))
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

        @kb.add("+", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Extend task due date."""
            event.app.exit(result="extend")

        # View operations (only when not filtering)
        @kb.add("t", filter=Condition(lambda: not self.filter_active))
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
            height=Dimension.exact(1),
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
        view_info = f"{view_label}: {view_name} ({current_pos}/{total_tabs}) [←/→ items | Tab: view type]"

        if self.filter_text:
            view_info += f" | Filter: '{self.filter_text}'"

        return HTML(f"<b> {view_info} </b>")

    def _get_status_bar_text(self) -> FormattedText:
        """Get the status bar text with keyboard shortcuts."""
        shortcuts = (
            "[n]ew [e]dit [d]one [p]rogress [c]ancelled [a]rchive [m]ove [x]del "
            "[u]subtask [+]extend [s]ync [/]filter [t]ree [q]uit | Multi-select: Space | Auto-reload: ON"
        )
        return HTML(f" {shortcuts} ")

    def _get_task_detail_text(self) -> FormattedText:
        """Get formatted details for the currently selected task."""
        tasks = self._get_filtered_tasks()

        # Check if there's a selected task
        if not tasks or self.selected_row < 0 or self.selected_row >= len(tasks):
            return HTML("<dim>No task selected</dim>")

        task = tasks[self.selected_row]

        # Get display ID
        display_id = get_display_id_from_uuid(task.id)
        display_id_str = str(display_id) if display_id else f"{task.id[:8]}..."

        # Build detail sections
        lines = []

        # Title header
        lines.append(f"<b>Task [{display_id_str}]: {task.title}</b>\n\n")

        # Metadata line 1: Repo, Project, Status, Priority
        repo = task.repo or "-"
        project = task.project or "-"

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
        assignees = ", ".join(task.assignees) if task.assignees else "-"
        tags = ", ".join(task.tags) if task.tags else "-"
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
                lines.append(f"  • {link}\n")

        # Dependencies section
        deps_info = []
        if task.parent:
            deps_info.append(f"Parent: {task.parent}")
        if task.depends:
            deps_info.append(f"Depends on: {', '.join(task.depends)}")
        if deps_info:
            lines.append(f"\n<cyan><b>Dependencies:</b></cyan> {' | '.join(deps_info)}\n")

        # Description section
        if task.description:
            lines.append("\n<cyan><b>Description:</b></cyan>\n")
            # Limit description to first 10 lines for display
            desc_lines = task.description.split("\n")
            display_lines = desc_lines[:10]
            for line in display_lines:
                lines.append(f"{line}\n")
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
            sorted_top_level = sort_tasks(top_level, self.config)
            tree_items = build_task_tree(sorted_top_level + subtasks)
            return [item[0] for item in tree_items]
        else:
            return sort_tasks(tasks, self.config)

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
                tree_items = build_task_tree(tasks)
        else:
            tree_items = [(task, 0, False, []) for task in tasks]

        # Calculate viewport boundaries
        viewport_bottom = min(self.viewport_top + self.viewport_size, len(tree_items))
        viewport_items = tree_items[self.viewport_top : viewport_bottom]

        # Calculate column widths dynamically based on terminal width
        _, terminal_width = self._get_terminal_size()

        # Define minimum and preferred widths for each column
        # Fixed width columns (don't expand)
        max_id_width = 3
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

            # Get display ID
            display_id = get_display_id_from_uuid(task.id)
            display_id_str = str(display_id) if display_id else f"{task.id[:8]}..."

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
                countdown_text, countdown_color = get_countdown_text(task.due)
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
        async def run_with_auto_reload():
            # Start auto-reload background task
            self.auto_reload_task = asyncio.create_task(self._auto_reload_loop())

            try:
                return await self.app.run_async()
            finally:
                # Cancel the background task when exiting
                if self.auto_reload_task:
                    self.auto_reload_task.cancel()
                    try:
                        await self.auto_reload_task
                    except asyncio.CancelledError:
                        pass

        # Run the async function
        return asyncio.run(run_with_auto_reload())
