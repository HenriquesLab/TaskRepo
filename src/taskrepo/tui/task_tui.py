"""Full-screen TUI for TaskRepo using prompt_toolkit."""

import os
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
from taskrepo.core.repository import Repository
from taskrepo.core.task import Task
from taskrepo.tui.display import build_task_tree, count_subtasks, format_tree_title, get_countdown_text
from taskrepo.utils.id_mapping import get_display_id_from_uuid
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
        # Start at -1 to show "All" repositories first
        self.current_repo_idx = -1
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
                "selected": "bg:ansiblue fg:ansiwhite bold",
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

        # Repository switching with left/right arrows (only when not filtering)
        @kb.add("right", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Switch to next repository."""
            # Cycle through: -1 (All) -> 0 -> 1 -> ... -> N-1 -> -1 (All)
            self.current_repo_idx = (self.current_repo_idx + 1) % (len(self.repositories) + 1) - 1
            self.selected_row = 0
            self.viewport_top = 0  # Reset viewport
            self.multi_selected.clear()

        @kb.add("left", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Switch to previous repository."""
            # Cycle backward: -1 (All) -> N-1 -> ... -> 1 -> 0 -> -1 (All)
            self.current_repo_idx = (self.current_repo_idx) % (len(self.repositories) + 1) - 1
            self.selected_row = 0
            self.viewport_top = 0  # Reset viewport
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

        @kb.add("u", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Unarchive task(s)."""
            event.app.exit(result="unarchive")

        # View operations (only when not filtering)
        @kb.add("r", filter=Condition(lambda: not self.filter_active))
        def _(event):
            """Refresh view."""
            # Just trigger a redraw
            pass

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
                event.app.layout.focus(None)
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
        """Get the header text showing current repo and filter."""
        if not self.repositories:
            return HTML("<b>No repositories found</b>")

        # Show "All Repositories" when index is -1
        if self.current_repo_idx == -1:
            repo_name = "All Repositories"
            current_pos = 1
        else:
            repo_name = self.repositories[self.current_repo_idx].name
            current_pos = self.current_repo_idx + 2  # +2 because "All" is position 1

        total_tabs = len(self.repositories) + 1  # +1 for "All" tab
        repo_info = f"Repository: {repo_name} ({current_pos}/{total_tabs}) [←/→ to switch]"

        if self.filter_text:
            repo_info += f" | Filter: '{self.filter_text}'"

        return HTML(f"<b> {repo_info} </b>")

    def _get_status_bar_text(self) -> FormattedText:
        """Get the status bar text with keyboard shortcuts."""
        shortcuts = (
            "[n]ew [e]dit [d]one [p]rogress [c]ancelled [x]del [a]rchive [u]narchive "
            "[/]filter [s]ync [t]ree [r]efresh [q]uit | Multi-select: Space"
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
        """Get the currently selected repository.

        Returns None when showing all repositories (index -1).
        """
        if not self.repositories:
            return None
        if self.current_repo_idx == -1:
            return None
        return self.repositories[self.current_repo_idx]

    def _get_filtered_tasks(self) -> list[Task]:
        """Get tasks from current repository with filters applied."""
        # Load tasks from all repos or current repo
        if self.current_repo_idx == -1:
            # Show tasks from all repositories
            tasks = []
            for repo in self.repositories:
                tasks.extend(repo.list_tasks())
        else:
            # Show tasks from current repository
            repo = self._get_current_repo()
            if not repo:
                return []
            tasks = repo.list_tasks()

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
        separators = 9  # Number of spaces between columns

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

        # Build result
        result = []

        # Build header with abbreviated column names first to get total width
        header = (
            f"{'ID':<{max_id_width}} "
            f"{'Title':<{max_title_width}} "
            f"{'Repo':<{max_repo_width}} "
            f"{'Proj':<{max_project_width}} "  # Project -> Proj
            f"{'Status':<{max_status_width}} "
            f"{'P':<{max_priority_width}} "  # Pri -> P
            f"{'Assign':<{max_assignees_width}} "  # Assigned -> Assign
            f"{'Tags':<{max_tags_width}} "
            f"{'Due':<{max_due_width}} "
            f"{'Count':<{max_countdown_width}}"  # Countdown -> Count
        )
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
            title_space = max_title_width - 2  # Reserve space for markers
            if len(formatted_title) > title_space:
                formatted_title = formatted_title[: title_space - 3] + "..."

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
                row = (
                    f"{selection_marker}"
                    f"{display_id_str:<{max_id_width - 1}} "
                    f"{multi_marker} {formatted_title:<{max_title_width - 2}} "
                    f"{repo_str:<{max_repo_width}} "
                    f"{project_str:<{max_project_width}} "
                    f"{status_str:<{max_status_width}} "
                    f"{priority_str:<{max_priority_width}} "
                    f"{assignees_str:<{max_assignees_width}} "
                    f"{tags_str:<{max_tags_width}} "
                    f"{due_str:<{max_due_width}} "
                    f"{countdown_text:<{max_countdown_width}}"
                )
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

                # Title
                result.append(("", f" {formatted_title:<{max_title_width - 2}} "))

                # Repo
                result.append(("class:repo", f"{repo_str:<{max_repo_width}} "))

                # Project
                result.append(("class:project", f"{project_str:<{max_project_width}} "))

                # Status (colored)
                result.append((status_style, f"{status_str:<{max_status_width}} "))

                # Priority (colored)
                result.append((priority_style, f"{priority_str:<{max_priority_width}} "))

                # Assignees
                result.append(("class:assignee", f"{assignees_str:<{max_assignees_width}} "))

                # Tags
                result.append(("class:tag", f"{tags_str:<{max_tags_width}} "))

                # Due date
                result.append(("class:due-date", f"{due_str:<{max_due_width}} "))

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
        return self.app.run()
