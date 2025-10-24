"""Repository discovery and management."""

import uuid
from pathlib import Path
from typing import Optional

from git import Repo as GitRepo

from taskrepo.core.task import Task


class Repository:
    """Represents a task repository (tasks-* directory with git).

    Attributes:
        name: Repository name (e.g., 'work' from 'tasks-work')
        path: Path to the repository directory
        git_repo: GitPython Repo object
    """

    def __init__(self, path: Path):
        """Initialize a Repository.

        Args:
            path: Path to the tasks-* directory

        Raises:
            ValueError: If path is not a valid task repository
        """
        if not path.exists():
            raise ValueError(f"Repository path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Repository path is not a directory: {path}")

        # Extract repo name from directory name (tasks-work -> work)
        dir_name = path.name
        if not dir_name.startswith("tasks-"):
            raise ValueError(f"Invalid repository name: {dir_name}. Must start with 'tasks-'")

        self.name = dir_name[6:]  # Remove 'tasks-' prefix
        self.path = path
        self.tasks_dir = path / "tasks"
        self.done_dir = self.tasks_dir / "done"

        # Initialize or open git repository
        try:
            self.git_repo = GitRepo(path)
        except Exception:
            # Not a git repo yet, initialize it
            self.git_repo = GitRepo.init(path)

        # Ensure tasks directory exists
        self.tasks_dir.mkdir(exist_ok=True)
        # Ensure done subdirectory exists inside tasks
        self.done_dir.mkdir(exist_ok=True)

    def list_tasks(self, include_completed: bool = False) -> list[Task]:
        """List all tasks in this repository.

        Args:
            include_completed: If True, also load tasks from done/ folder

        Returns:
            List of Task objects
        """
        tasks = []

        # Always load from tasks/ directory
        if self.tasks_dir.exists():
            for task_file in sorted(self.tasks_dir.glob("task-*.md")):
                try:
                    task = Task.load(task_file, repo=self.name)
                    tasks.append(task)
                except Exception as e:
                    print(f"Warning: Failed to load task {task_file}: {e}")

        # Optionally load from done/ directory
        if include_completed and self.done_dir.exists():
            for task_file in sorted(self.done_dir.glob("task-*.md")):
                try:
                    task = Task.load(task_file, repo=self.name)
                    tasks.append(task)
                except Exception as e:
                    print(f"Warning: Failed to load task {task_file}: {e}")

        return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID.

        Searches both tasks/ and done/ directories.

        Args:
            task_id: Task ID

        Returns:
            Task object or None if not found
        """
        # Try tasks/ directory first
        task_file = self.tasks_dir / f"task-{task_id}.md"
        if task_file.exists():
            return Task.load(task_file, repo=self.name)

        # Try done/ directory
        task_file = self.done_dir / f"task-{task_id}.md"
        if task_file.exists():
            return Task.load(task_file, repo=self.name)

        return None

    def save_task(self, task: Task) -> Path:
        """Save a task to this repository.

        Automatically moves task between tasks/ and tasks/done/ folders based on status.
        - Completed tasks → tasks/done/ folder
        - Non-completed tasks → tasks/ folder

        Args:
            task: Task object to save

        Returns:
            Path to the saved task file
        """
        task.repo = self.name

        # Determine target folder based on status
        if task.status == "completed":
            target_folder = "tasks/done"
        else:
            target_folder = "tasks"

        # Check if file exists in the other folder and delete it
        old_tasks_file = self.tasks_dir / f"task-{task.id}.md"
        old_done_file = self.done_dir / f"task-{task.id}.md"

        if task.status == "completed" and old_tasks_file.exists():
            # Moving from tasks/ to tasks/done/
            old_tasks_file.unlink()
        elif task.status != "completed" and old_done_file.exists():
            # Moving from tasks/done/ back to tasks/
            old_done_file.unlink()

        # Save to target folder
        return task.save(self.path, subfolder=target_folder)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task from this repository.

        Searches both tasks/ and tasks/done/ directories.

        Args:
            task_id: Task ID to delete

        Returns:
            True if task was deleted, False if not found
        """
        # Try tasks/ directory first
        task_file = self.tasks_dir / f"task-{task_id}.md"
        if task_file.exists():
            task_file.unlink()
            return True

        # Try tasks/done/ directory
        task_file = self.done_dir / f"task-{task_id}.md"
        if task_file.exists():
            task_file.unlink()
            return True

        return False

    def next_task_id(self) -> str:
        """Generate the next available task ID using UUID4.

        Returns:
            UUID string
        """
        return str(uuid.uuid4())

    def get_projects(self) -> list[str]:
        """Get list of unique projects in this repository.

        Returns:
            List of project names
        """
        tasks = self.list_tasks()
        projects = {task.project for task in tasks if task.project}
        return sorted(projects)

    def get_assignees(self) -> list[str]:
        """Get list of unique assignees in this repository.

        Returns:
            List of assignee handles (with @ prefix)
        """
        tasks = self.list_tasks()
        assignees = set()
        for task in tasks:
            assignees.update(task.assignees)
        return sorted(assignees)

    def get_tags(self) -> list[str]:
        """Get list of unique tags in this repository.

        Returns:
            List of tags
        """
        tasks = self.list_tasks()
        tags = set()
        for task in tasks:
            tags.update(task.tags)
        return sorted(tags)

    def get_subtasks(self, task_id: str) -> list[Task]:
        """Get all direct subtasks (children) of a given task.

        Args:
            task_id: Parent task ID

        Returns:
            List of Task objects that have this task as their parent
        """
        all_tasks = self.list_tasks()
        return [task for task in all_tasks if task.parent == task_id]

    def get_all_subtasks(self, task_id: str) -> list[Task]:
        """Get all subtasks (descendants) of a given task recursively.

        Args:
            task_id: Parent task ID

        Returns:
            List of all descendant Task objects
        """
        all_tasks = self.list_tasks()
        descendants = []

        # Get direct children
        direct_children = [task for task in all_tasks if task.parent == task_id]

        for child in direct_children:
            descendants.append(child)
            # Recursively get children's children
            descendants.extend(self.get_all_subtasks(child.id))

        return descendants

    def get_task_tree(self, task_id: str) -> dict:
        """Build hierarchical tree structure for a task and its subtasks.

        Args:
            task_id: Root task ID

        Returns:
            Dictionary with task and nested subtasks structure:
            {
                'task': Task object,
                'subtasks': [
                    {'task': Task, 'subtasks': [...]},
                    ...
                ]
            }
        """
        task = self.get_task(task_id)
        if not task:
            return {}

        tree = {"task": task, "subtasks": []}

        # Get direct children
        direct_children = self.get_subtasks(task_id)

        # Recursively build tree for each child
        for child in direct_children:
            child_tree = self.get_task_tree(child.id)
            if child_tree:
                tree["subtasks"].append(child_tree)

        return tree

    def validate_parent(self, task_id: str, parent_id: str) -> bool:
        """Validate that a parent task exists and won't create circular reference.

        Args:
            task_id: ID of the task being created/modified
            parent_id: ID of the proposed parent task

        Returns:
            True if parent is valid, False otherwise
        """
        # Check parent exists
        parent_task = self.get_task(parent_id)
        if not parent_task:
            return False

        # Check for circular reference: parent cannot be a descendant of task
        all_tasks = self.list_tasks()

        # Build chain from parent upwards
        visited = set()
        current_id = parent_id

        while current_id:
            if current_id == task_id:
                # Circular reference detected
                return False

            if current_id in visited:
                # Already visited, break to prevent infinite loop
                break

            visited.add(current_id)

            current_task = next((t for t in all_tasks if t.id == current_id), None)
            if current_task and current_task.parent:
                current_id = current_task.parent
            else:
                break

        return True

    def generate_readme(self, config) -> Path:
        """Generate README.md with active tasks table.

        Args:
            config: Config object for sorting preferences

        Returns:
            Path to the generated README file
        """
        from datetime import datetime

        def get_countdown_text(due_date: datetime) -> tuple[str, str]:
            """Calculate countdown text and emoji from a due date.

            Args:
                due_date: The due date to calculate countdown for

            Returns:
                Tuple of (countdown_text, emoji)
            """
            now = datetime.now()
            diff = due_date - now
            days = diff.days
            hours = diff.seconds // 3600

            # Handle overdue
            if days < 0:
                abs_days = abs(days)
                if abs_days == 1:
                    text = "overdue by 1 day"
                elif abs_days < 7:
                    text = f"overdue by {abs_days} days"
                elif abs_days < 14:
                    text = "overdue by 1 week"
                else:
                    weeks = abs_days // 7
                    text = f"overdue by {weeks} weeks"
                return text, "⚠️"

            # Handle today
            if days == 0:
                if hours < 1:
                    text = "due now"
                else:
                    text = "today"
                return text, "⏰"

            # Handle tomorrow
            if days == 1:
                return "tomorrow", "⏰"

            # Handle within 3 days (urgent)
            if days <= 3:
                return f"{days} days", "⏰"

            # Handle within 2 weeks
            if days < 14:
                return f"{days} days", "📅"

            # Handle weeks
            weeks = days // 7
            if weeks == 1:
                return "1 week", "📅"
            elif weeks < 4:
                return f"{weeks} weeks", "📅"

            # Handle months
            months = days // 30
            if months == 1:
                return "1 month", "📅"
            else:
                return f"{months} months", "📅"

        # Get active tasks (pending or in-progress)
        all_tasks = self.list_tasks()
        active_tasks = [task for task in all_tasks if task.status in ["pending", "in-progress"]]

        # Sort using config sort order (same as list command)
        def get_field_value(task, field):
            """Get sortable value for a field."""
            descending = field.startswith("-")
            field_name = field[1:] if descending else field

            if field_name == "priority":
                priority_order = {"H": 0, "M": 1, "L": 2}
                value = priority_order.get(task.priority, 3)
            elif field_name == "due":
                value = task.due.timestamp() if task.due else float("inf")
            elif field_name == "created":
                value = task.created.timestamp()
            elif field_name == "modified":
                value = task.modified.timestamp()
            elif field_name == "status":
                status_order = {"pending": 0, "in-progress": 1, "completed": 2, "cancelled": 3}
                value = status_order.get(task.status, 4)
            elif field_name == "title":
                value = task.title.lower()
            elif field_name == "project":
                value = (task.project or "").lower()
            else:
                value = ""

            if descending:
                if isinstance(value, (int, float)):
                    value = -value if value != float("inf") else float("-inf")
                elif isinstance(value, str):
                    return (True, value)

            return (False, value) if not descending else (True, value)

        def get_sort_key(task):
            sort_fields = config.sort_by
            key_parts = []
            for field in sort_fields:
                is_desc, value = get_field_value(task, field)
                key_parts.append(value)
            return tuple(key_parts)

        # Build tree structure for active tasks
        def build_tree_for_readme(tasks):
            """Build tree structure and return tasks in display order."""
            task_dict = {t.id: t for t in tasks}
            children_map = {}

            for t in tasks:
                if t.parent and t.parent in task_dict:
                    if t.parent not in children_map:
                        children_map[t.parent] = []
                    children_map[t.parent].append(t)

            result = []

            def add_tree_item(task, depth, is_last, ancestors):
                result.append((task, depth, is_last, ancestors))
                children = children_map.get(task.id, [])
                for i, child in enumerate(children):
                    child_is_last = i == len(children) - 1
                    add_tree_item(child, depth + 1, child_is_last, ancestors + [is_last])

            # Start with top-level tasks
            top_level = [t for t in tasks if not t.parent or t.parent not in task_dict]
            for task in top_level:
                add_tree_item(task, 0, False, [])

            return result

        def format_tree_title_for_readme(title, depth, is_last, ancestors, subtask_count):
            """Format title with tree indentation for README markdown."""
            if depth == 0:
                if subtask_count > 0:
                    return f"{title} 📋 {subtask_count}"
                return title

            # For direct children (depth 1), only show branch without ancestor lines
            if depth == 1:
                branch = "└─ " if is_last else "├─ "
                if subtask_count > 0:
                    return f"{branch}{title} 📋 {subtask_count}"
                return f"{branch}{title}"

            # For deeper nesting, add ancestor lines
            prefix = ""
            # Skip the first ancestor (parent is top-level)
            for is_ancestor_last in ancestors[1:]:
                prefix += "&nbsp;&nbsp;&nbsp;" if is_ancestor_last else "│&nbsp;&nbsp;"

            branch = "└─ " if is_last else "├─ "
            if subtask_count > 0:
                return f"{prefix}{branch}{title} 📋 {subtask_count}"
            return f"{prefix}{branch}{title}"

        def count_children(task_id, tasks):
            return sum(1 for t in tasks if t.parent == task_id)

        # Sort top-level tasks, keep subtasks with parents
        top_level_tasks = [t for t in active_tasks if not t.parent]
        top_level_tasks.sort(key=get_sort_key)

        # Rebuild active_tasks list with all tasks (including subtasks)
        all_task_ids = {t.id for t in active_tasks}
        subtasks = [t for t in active_tasks if t.parent and t.parent in all_task_ids]
        sorted_active = top_level_tasks + subtasks

        tree_items = build_tree_for_readme(sorted_active)

        # Build README content
        lines = [
            f"# Tasks - {self.name}",
            "",
            "## Active Tasks",
            "",
        ]

        if not tree_items:
            lines.append("No active tasks.")
        else:
            # Table header
            lines.extend(
                [
                    "| ID | Title | Status | Priority | Assignees | Project | Tags | Links | Due | Countdown |",
                    "|---|---|---|---|---|---|---|---|---|---|",
                ]
            )

            # Table rows
            for task, depth, is_last, ancestors in tree_items:
                # Format fields with emojis
                task_id = f"[{task.id[:8]}...](tasks/task-{task.id}.md)"

                # Format title with tree structure and subtask count
                subtask_count = count_children(task.id, sorted_active)
                title = format_tree_title_for_readme(task.title, depth, is_last, ancestors, subtask_count)

                # Status with emoji
                status_emoji = {
                    "pending": "⏳",
                    "in-progress": "🔄",
                    "completed": "✅",
                    "cancelled": "❌",
                }.get(task.status, "")
                status = f"{status_emoji} {task.status}"

                # Priority with emoji
                priority_emoji = {"H": "🔴", "M": "🟡", "L": "🟢"}.get(task.priority, "")
                priority = f"{priority_emoji} {task.priority}"

                assignees = ", ".join(task.assignees) if task.assignees else "-"
                project = task.project if task.project else "-"
                tags = ", ".join(task.tags) if task.tags else "-"

                # Format links
                if task.links:
                    # Create markdown links with 🔗 emoji
                    link_items = [f"[🔗]({link})" for link in task.links]
                    links = " ".join(link_items)
                else:
                    links = "-"

                due_date = task.due.strftime("%Y-%m-%d") if task.due else "-"

                # Countdown with emoji
                if task.due:
                    countdown_text, countdown_emoji = get_countdown_text(task.due)
                    countdown = f"{countdown_emoji} {countdown_text}"
                else:
                    countdown = "-"

                # Escape pipe characters
                title = title.replace("|", "\\|")
                project = project.replace("|", "\\|")

                lines.append(
                    f"| {task_id} | {title} | {status} | {priority} | {assignees} | {project} | {tags} | {links} | {due_date} | {countdown} |"
                )

        # Add footer
        lines.extend(
            [
                "",
                f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            ]
        )

        # Write README
        readme_path = self.path / "README.md"
        readme_path.write_text("\n".join(lines) + "\n")

        return readme_path

    def generate_done_readme(self, config) -> Path:
        """Generate tasks/done/README.md with completed tasks archive table.

        Args:
            config: Config object for sorting preferences

        Returns:
            Path to the generated README file
        """
        from datetime import datetime

        from taskrepo.utils.sorting import sort_tasks

        # Get completed tasks only
        all_tasks = self.list_tasks(include_completed=True)
        completed_tasks = [task for task in all_tasks if task.status == "completed"]

        # Sort using config sort order
        sorted_completed = sort_tasks(completed_tasks, config)

        # Build README content
        lines = [
            "# Completed Tasks Archive",
            "",
        ]

        if not sorted_completed:
            lines.append("No completed tasks.")
        else:
            # Table header - Note: "Completed" column instead of "Countdown"
            lines.extend(
                [
                    "| ID | Title | Status | Priority | Assignees | Project | Tags | Links | Due | Completed |",
                    "|---|---|---|---|---|---|---|---|---|---|",
                ]
            )

            # Table rows
            for task in sorted_completed:
                # Format fields with emojis
                task_id = f"[{task.id[:8]}...](task-{task.id}.md)"  # Relative link

                title = task.title

                # Status with emoji (always completed)
                status = "✅ completed"

                # Priority with emoji
                priority_emoji = {"H": "🔴", "M": "🟡", "L": "🟢"}.get(task.priority, "")
                priority = f"{priority_emoji} {task.priority}"

                assignees = ", ".join(task.assignees) if task.assignees else "-"
                project = task.project if task.project else "-"
                tags = ", ".join(task.tags) if task.tags else "-"

                # Format links
                if task.links:
                    # Create markdown links with 🔗 emoji
                    link_items = [f"[🔗]({link})" for link in task.links]
                    links = " ".join(link_items)
                else:
                    links = "-"

                due_date = task.due.strftime("%Y-%m-%d") if task.due else "-"

                # Completed date (modified timestamp)
                completed_date = task.modified.strftime("%Y-%m-%d")

                # Escape pipe characters
                title = title.replace("|", "\\|")
                project = project.replace("|", "\\|")

                lines.append(
                    f"| {task_id} | {title} | {status} | {priority} | {assignees} | {project} | {tags} | {links} | {due_date} | {completed_date} |"
                )

        # Add footer
        lines.extend(
            [
                "",
                f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            ]
        )

        # Write README to done/ folder
        readme_path = self.done_dir / "README.md"
        readme_path.write_text("\n".join(lines) + "\n")

        return readme_path

    def __str__(self) -> str:
        """String representation of the repository."""
        task_count = len(self.list_tasks())
        return f"{self.name} ({task_count} tasks)"


class RepositoryManager:
    """Manages discovery and access to task repositories."""

    def __init__(self, parent_dir: Path):
        """Initialize RepositoryManager.

        Args:
            parent_dir: Parent directory containing tasks-* repositories
        """
        self.parent_dir = parent_dir
        self.parent_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def scan_for_task_repositories(search_path: Path, max_depth: int = 3) -> dict[Path, list[str]]:
        """Scan a directory tree for task repositories (tasks-* directories).

        Args:
            search_path: Starting directory to scan
            max_depth: Maximum directory depth to search (default: 3)

        Returns:
            Dictionary mapping parent directories to lists of repository names found within them
            Example: {Path('/home/user/Code'): ['work', 'personal']}
        """
        if not search_path.exists() or not search_path.is_dir():
            return {}

        found_repos = {}

        def scan_directory(path: Path, current_depth: int):
            """Recursively scan directory for tasks-* folders."""
            if current_depth > max_depth:
                return

            try:
                # Check if this directory contains any tasks-* subdirectories
                tasks_dirs = []
                for item in path.iterdir():
                    if item.is_dir() and item.name.startswith("tasks-"):
                        # Extract repo name (remove tasks- prefix)
                        repo_name = item.name[6:]
                        tasks_dirs.append(repo_name)

                # If we found any task repos in this directory, record it
                if tasks_dirs:
                    found_repos[path] = sorted(tasks_dirs)

                # Continue scanning subdirectories (but not into tasks-* dirs themselves)
                for item in path.iterdir():
                    if item.is_dir() and not item.name.startswith("tasks-") and not item.name.startswith("."):
                        scan_directory(item, current_depth + 1)

            except (PermissionError, OSError):
                # Skip directories we can't access
                pass

        scan_directory(search_path, 0)
        return found_repos

    def discover_repositories(self) -> list[Repository]:
        """Discover all task repositories in parent directory.

        Returns:
            List of Repository objects
        """
        repos = []
        if not self.parent_dir.exists():
            return repos

        for path in sorted(self.parent_dir.iterdir()):
            if path.is_dir() and path.name.startswith("tasks-"):
                try:
                    repo = Repository(path)
                    repos.append(repo)
                except Exception as e:
                    print(f"Warning: Failed to load repository {path}: {e}")

        return repos

    def get_repository(self, name: str) -> Optional[Repository]:
        """Get a specific repository by name.

        Args:
            name: Repository name (without 'tasks-' prefix)

        Returns:
            Repository object or None if not found
        """
        repo_path = self.parent_dir / f"tasks-{name}"
        if not repo_path.exists():
            return None

        return Repository(repo_path)

    def get_github_orgs(self) -> list[str]:
        """Get list of GitHub organizations from existing repositories.

        Extracts organization/owner names from GitHub remote URLs
        in existing repositories.

        Returns:
            Sorted list of unique GitHub organizations
        """
        import re

        orgs = set()
        repos = self.discover_repositories()

        for repo in repos:
            try:
                # Check if repo has a remote
                if not repo.git_repo.remotes:
                    continue

                # Get origin remote (most common)
                remote = repo.git_repo.remote("origin")
                remote_url = next(remote.urls, None)

                if not remote_url:
                    continue

                # Parse GitHub URL to extract org
                # HTTPS format: https://github.com/org/repo.git
                # SSH format: git@github.com:org/repo.git
                github_patterns = [
                    r"https://github\.com/([^/]+)/",
                    r"git@github\.com:([^/]+)/",
                ]

                for pattern in github_patterns:
                    match = re.match(pattern, remote_url)
                    if match:
                        orgs.add(match.group(1))
                        break

            except Exception:
                # Skip repos without remotes or with invalid URLs
                continue

        return sorted(orgs)

    def create_repository(
        self,
        name: str,
        github_enabled: bool = False,
        github_org: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> Repository:
        """Create a new task repository.

        Args:
            name: Repository name (without 'tasks-' prefix)
            github_enabled: Whether to create GitHub repository
            github_org: GitHub organization/owner (required if github_enabled)
            visibility: Repository visibility ('public' or 'private', required if github_enabled)

        Returns:
            Repository object

        Raises:
            ValueError: If repository already exists or invalid parameters
        """
        from taskrepo.utils.github import (
            GitHubError,
            create_github_repo,
            push_to_remote,
            setup_git_remote,
        )

        repo_path = self.parent_dir / f"tasks-{name}"
        if repo_path.exists():
            raise ValueError(f"Repository already exists: tasks-{name}")

        # Validate GitHub parameters
        if github_enabled:
            if not github_org:
                raise ValueError("GitHub organization/owner is required when --github is enabled")
            if not visibility:
                raise ValueError("Repository visibility is required when --github is enabled")
            if visibility not in ["public", "private"]:
                raise ValueError("Visibility must be 'public' or 'private'")

        # Create local repository
        repo_path.mkdir(parents=True, exist_ok=True)
        repo = Repository(repo_path)

        # Create initial commit with README
        readme_content = f"""# Tasks - {name}

## Active Tasks

No active tasks.

_Last updated: {self._get_timestamp()}_
"""
        readme_path = repo_path / "README.md"
        readme_path.write_text(readme_content)

        # Create .gitkeep in tasks directory
        gitkeep_path = repo.tasks_dir / ".gitkeep"
        gitkeep_path.touch()

        # Create .gitkeep in done directory
        done_gitkeep_path = repo.done_dir / ".gitkeep"
        done_gitkeep_path.touch()

        # Commit initial structure
        repo.git_repo.git.add(A=True)
        repo.git_repo.index.commit("Initial commit: Repository structure")

        # Create GitHub repository if requested
        if github_enabled:
            try:
                # Create GitHub repository
                github_url = create_github_repo(github_org, f"tasks-{name}", visibility)

                # Setup remote
                setup_git_remote(repo_path, github_url)

                # Push to remote
                push_to_remote(repo_path)

            except GitHubError as e:
                # Clean up local repository on GitHub error
                import shutil

                shutil.rmtree(repo_path)
                raise ValueError(f"GitHub error: {e}") from e

        return repo

    def _get_timestamp(self) -> str:
        """Get current timestamp for README.

        Returns:
            Formatted timestamp string
        """
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def list_all_tasks(self, include_completed: bool = False) -> list[Task]:
        """List all tasks across all repositories.

        Args:
            include_completed: If True, also load tasks from done/ folders

        Returns:
            List of Task objects
        """
        tasks = []
        for repo in self.discover_repositories():
            tasks.extend(repo.list_tasks(include_completed=include_completed))
        return tasks

    def get_all_assignees(self) -> list[str]:
        """Get list of unique assignees across all repositories.

        Returns:
            Sorted list of all assignee handles (with @ prefix)
        """
        assignees = set()
        for repo in self.discover_repositories():
            assignees.update(repo.get_assignees())
        return sorted(assignees)

    def get_all_projects(self) -> list[str]:
        """Get list of unique projects across all repositories.

        Returns:
            Sorted list of all project names
        """
        projects = set()
        for repo in self.discover_repositories():
            projects.update(repo.get_projects())
        return sorted(projects)

    def get_all_tags(self) -> list[str]:
        """Get list of unique tags across all repositories.

        Returns:
            Sorted list of all tags
        """
        tags = set()
        for repo in self.discover_repositories():
            tags.update(repo.get_tags())
        return sorted(tags)

    def get_all_subtasks_cross_repo(self, task_id: str) -> list[tuple[Task, "Repository"]]:
        """Get all subtasks (descendants) of a given task across all repositories.

        Recursively finds all descendants regardless of which repository they're in.

        Args:
            task_id: Parent task ID

        Returns:
            List of tuples: (task, repository) for all descendants
        """
        all_repos = self.discover_repositories()
        descendants = []

        # Get direct children from all repositories
        direct_children = []
        for repo in all_repos:
            for task in repo.list_tasks():
                if task.parent == task_id:
                    direct_children.append((task, repo))

        # Add direct children and recursively get their descendants
        for child_task, child_repo in direct_children:
            descendants.append((child_task, child_repo))
            # Recursively get children's children
            descendants.extend(self.get_all_subtasks_cross_repo(child_task.id))

        return descendants
