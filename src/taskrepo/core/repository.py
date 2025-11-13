"""Repository discovery and management."""

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from git import Repo as GitRepo

from taskrepo.core.task import Task


@lru_cache(maxsize=512)
def _load_task_cached(file_path: str, mtime: float, repo: str) -> Task:
    """Load and parse a task file with LRU caching.

    Caches parsed Task objects based on file path and modification time.
    When mtime changes, the cache is automatically invalidated.

    Args:
        file_path: Path to task file (as string for hashability)
        mtime: File modification time (for cache invalidation)
        repo: Repository name

    Returns:
        Parsed Task object
    """
    return Task.load(Path(file_path), repo=repo)


def clear_task_cache():
    """Clear the task loading cache.

    Call this after modifying tasks to ensure fresh data is loaded.
    Useful when tasks are updated outside of the normal flow.
    """
    _load_task_cached.cache_clear()


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
        self.archive_dir = self.tasks_dir / "archive"

        # Initialize or open git repository
        try:
            self.git_repo = GitRepo(path)
        except Exception:
            # Not a git repo yet, initialize it
            self.git_repo = GitRepo.init(path)

        # Ensure tasks directory exists
        self.tasks_dir.mkdir(exist_ok=True)
        # Ensure archive subdirectory exists inside tasks
        self.archive_dir.mkdir(exist_ok=True)

        # Migrate old done tasks to main tasks folder
        self._migrate_done_to_tasks()

    def _migrate_done_to_tasks(self) -> None:
        """Migrate tasks from old done/ folder to main tasks/ folder.

        This is a one-time migration that runs automatically when a repository
        is initialized. It moves all tasks from tasks/done/ back to tasks/
        and removes the done folder.
        """
        done_dir = self.tasks_dir / "done"

        if not done_dir.exists():
            return

        # Move all task files from done/ to tasks/
        migrated_count = 0
        for task_file in done_dir.glob("task-*.md"):
            target_path = self.tasks_dir / task_file.name

            # If target already exists, skip (shouldn't happen, but be safe)
            if target_path.exists():
                print(f"Warning: Skipping {task_file.name} - already exists in tasks/")
                continue

            task_file.rename(target_path)
            migrated_count += 1

        # Remove the done folder and its contents
        try:
            # Remove any remaining files (like README.md)
            for file in done_dir.iterdir():
                file.unlink()
            done_dir.rmdir()

            if migrated_count > 0:
                print(f"✓ Migrated {migrated_count} completed task(s) from done/ to tasks/")
                print("✓ Removed old done/ folder")
        except Exception as e:
            print(f"Warning: Could not fully remove done/ folder: {e}")

    def list_tasks(self, include_archived: bool = False) -> list[Task]:
        """List all tasks in this repository.

        Uses LRU caching to avoid re-parsing unchanged task files.

        Args:
            include_archived: If True, also load tasks from archive/ folder

        Returns:
            List of Task objects (from tasks/ folder, excluding archive/ subdirectory)
        """
        tasks = []

        # Load from tasks/ directory (excluding archive/ subdirectory)
        if self.tasks_dir.exists():
            for task_file in sorted(self.tasks_dir.glob("task-*.md")):
                try:
                    # Use cached loading with mtime for automatic invalidation
                    mtime = task_file.stat().st_mtime
                    task = _load_task_cached(str(task_file), mtime, self.name)
                    tasks.append(task)
                except Exception as e:
                    print(f"Warning: Failed to load task {task_file}: {e}")

        # Optionally load from archive/ directory
        if include_archived and self.archive_dir.exists():
            for task_file in sorted(self.archive_dir.glob("task-*.md")):
                try:
                    # Use cached loading with mtime for automatic invalidation
                    mtime = task_file.stat().st_mtime
                    task = _load_task_cached(str(task_file), mtime, self.name)
                    tasks.append(task)
                except Exception as e:
                    print(f"Warning: Failed to load task {task_file}: {e}")

        return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID.

        Searches both tasks/ and archive/ directories.
        Uses LRU caching to avoid re-parsing unchanged task files.

        Args:
            task_id: Task ID

        Returns:
            Task object or None if not found
        """
        # Try tasks/ directory first
        task_file = self.tasks_dir / f"task-{task_id}.md"
        if task_file.exists():
            mtime = task_file.stat().st_mtime
            return _load_task_cached(str(task_file), mtime, self.name)

        # Try archive/ directory
        task_file = self.archive_dir / f"task-{task_id}.md"
        if task_file.exists():
            mtime = task_file.stat().st_mtime
            return _load_task_cached(str(task_file), mtime, self.name)

        return None

    def save_task(self, task: Task) -> Path:
        """Save a task to this repository.

        Always saves to tasks/ folder regardless of status.
        Use archive_task() to move tasks to archive/ folder.

        Args:
            task: Task object to save

        Returns:
            Path to the saved task file
        """
        task.repo = self.name

        # Always save to tasks/ folder
        return task.save(self.path, subfolder="tasks")

    def delete_task(self, task_id: str) -> bool:
        """Delete a task from this repository.

        Searches both tasks/ and archive/ directories.

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

        # Try archive/ directory
        task_file = self.archive_dir / f"task-{task_id}.md"
        if task_file.exists():
            task_file.unlink()
            return True

        return False

    def list_archived_tasks(self) -> list[Task]:
        """List all archived tasks in this repository.

        Returns:
            List of Task objects from archive/ folder
        """
        tasks = []

        if self.archive_dir.exists():
            for task_file in sorted(self.archive_dir.glob("task-*.md")):
                try:
                    task = Task.load(task_file, repo=self.name)
                    tasks.append(task)
                except Exception as e:
                    print(f"Warning: Failed to load archived task {task_file}: {e}")

        return tasks

    def archive_task(self, task_id: str) -> bool:
        """Archive a task by moving it to the archive/ folder.

        Args:
            task_id: Task ID to archive

        Returns:
            True if task was archived, False if not found or already archived
        """
        # Check if task exists in tasks/ directory
        task_file = self.tasks_dir / f"task-{task_id}.md"
        if not task_file.exists():
            return False

        # Move to archive directory
        archive_file = self.archive_dir / f"task-{task_id}.md"
        task_file.rename(archive_file)
        return True

    def unarchive_task(self, task_id: str) -> bool:
        """Unarchive a task by moving it back to the tasks/ folder.

        Args:
            task_id: Task ID to unarchive

        Returns:
            True if task was unarchived, False if not found or not archived
        """
        # Check if task exists in archive/ directory
        archive_file = self.archive_dir / f"task-{task_id}.md"
        if not archive_file.exists():
            return False

        # Move back to tasks directory
        task_file = self.tasks_dir / f"task-{task_id}.md"

        # If target already exists, return False to avoid overwriting
        if task_file.exists():
            print(f"Warning: Task {task_id} already exists in tasks/ folder")
            return False

        archive_file.rename(task_file)
        return True

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

        Note:
            This function uses centralized sorting from utils/sorting.py to ensure
            README task order matches 'tsk list' command output. When modifying
            sorting logic, verify README generation still works correctly.
        """
        from datetime import datetime

        from taskrepo.utils.sorting import sort_tasks

        def get_countdown_text(due_date: datetime) -> tuple[str, str]:
            """Calculate countdown text and emoji from a due date.

            Args:
                due_date: The due date to calculate countdown for

            Returns:
                Tuple of (countdown_text, emoji)
            """
            from taskrepo.utils.countdown import calculate_countdown, format_countdown_for_readme

            # Use centralized countdown calculation
            countdown_text, countdown_status, _ = calculate_countdown(due_date)
            return format_countdown_for_readme(countdown_text, countdown_status)

        # Get all non-archived tasks (including completed)
        all_tasks = self.list_tasks(include_archived=False)

        # Build tree structure for all tasks (including completed)
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

        # Sort top-level tasks using centralized sorting logic from utils/sorting.py
        # NOTE: all_tasks parameter is critical for recursive due date calculations
        # (parent tasks inherit earliest due dates from subtasks/dependencies)
        top_level_tasks = [t for t in all_tasks if not t.parent]
        sorted_top_level = sort_tasks(top_level_tasks, config, all_tasks=all_tasks)

        # Rebuild all_tasks list with sorted top-level tasks and their subtasks
        all_task_ids = {t.id for t in all_tasks}
        subtasks = [t for t in all_tasks if t.parent and t.parent in all_task_ids]
        sorted_all = sorted_top_level + subtasks

        tree_items = build_tree_for_readme(sorted_all)

        # Build README content
        lines = [
            f"# Tasks - {self.name}",
            "",
            "## Tasks",
            "",
        ]

        if not tree_items:
            lines.append("No tasks.")
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
                subtask_count = count_children(task.id, sorted_all)
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

    def generate_archive_readme(self, config) -> Path:
        """Generate tasks/archive/README.md with archived tasks table.

        Args:
            config: Config object for sorting preferences

        Returns:
            Path to the generated README file

        Note:
            This function uses centralized sorting from utils/sorting.py to ensure
            archive README task order matches 'tsk list' command output. When modifying
            sorting logic, verify README generation still works correctly.
        """
        from datetime import datetime

        from taskrepo.utils.sorting import sort_tasks

        # Get archived tasks only
        archived_tasks = self.list_archived_tasks()

        # Get all tasks (archived + non-archived) for effective due date context
        all_tasks = self.list_tasks(include_archived=True)

        # Sort using centralized sorting logic from utils/sorting.py
        # NOTE: all_tasks parameter is critical for recursive due date calculations
        # (parent tasks inherit earliest due dates from subtasks/dependencies)
        sorted_archived = sort_tasks(archived_tasks, config, all_tasks=all_tasks)

        # Build README content
        lines = [
            "# Archived Tasks",
            "",
        ]

        if not sorted_archived:
            lines.append("No archived tasks.")
        else:
            # Table header - Note: "Archived" column instead of "Countdown"
            lines.extend(
                [
                    "| ID | Title | Status | Priority | Assignees | Project | Tags | Links | Due | Archived |",
                    "|---|---|---|---|---|---|---|---|---|---|",
                ]
            )

            # Table rows
            for task in sorted_archived:
                # Format fields with emojis
                task_id = f"[{task.id[:8]}...](task-{task.id}.md)"  # Relative link

                title = task.title

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

                # Archived date (modified timestamp)
                archived_date = task.modified.strftime("%Y-%m-%d")

                # Escape pipe characters
                title = title.replace("|", "\\|")
                project = project.replace("|", "\\|")

                lines.append(
                    f"| {task_id} | {title} | {status} | {priority} | {assignees} | {project} | {tags} | {links} | {due_date} | {archived_date} |"
                )

        # Add footer
        lines.extend(
            [
                "",
                f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            ]
        )

        # Write README to archive/ folder
        readme_path = self.archive_dir / "README.md"
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

    @staticmethod
    def sort_repositories_alphabetically(repositories: list["Repository"]) -> list["Repository"]:
        """Sort repositories alphabetically by name.

        This is the centralized sorting method used throughout the application
        to ensure consistent repository ordering in all UI contexts.

        Args:
            repositories: List of Repository objects to sort

        Returns:
            Sorted list of Repository objects (alphabetically by name)
        """
        return sorted(repositories, key=lambda r: r.name)

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

        # Create .gitkeep in archive directory
        archive_gitkeep_path = repo.archive_dir / ".gitkeep"
        archive_gitkeep_path.touch()

        # Create default .gitignore
        from taskrepo.utils.file_validation import create_default_gitignore

        create_default_gitignore(repo_path)

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

    def list_all_tasks(self, include_archived: bool = False) -> list[Task]:
        """List all tasks across all repositories.

        Args:
            include_archived: If True, also load tasks from archive/ folders

        Returns:
            List of Task objects
        """
        tasks = []
        for repo in self.discover_repositories():
            tasks.extend(repo.list_tasks(include_archived=include_archived))
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
            for task in repo.list_tasks(include_archived=True):
                if task.parent == task_id:
                    direct_children.append((task, repo))

        # Add direct children and recursively get their descendants
        for child_task, child_repo in direct_children:
            descendants.append((child_task, child_repo))
            # Recursively get children's children
            descendants.extend(self.get_all_subtasks_cross_repo(child_task.id))

        return descendants
