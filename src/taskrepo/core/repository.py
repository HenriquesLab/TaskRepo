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

        # Initialize or open git repository
        try:
            self.git_repo = GitRepo(path)
        except Exception:
            # Not a git repo yet, initialize it
            self.git_repo = GitRepo.init(path)

        # Ensure tasks directory exists
        self.tasks_dir.mkdir(exist_ok=True)

    def list_tasks(self) -> list[Task]:
        """List all tasks in this repository.

        Returns:
            List of Task objects
        """
        tasks = []
        if not self.tasks_dir.exists():
            return tasks

        for task_file in sorted(self.tasks_dir.glob("task-*.md")):
            try:
                task = Task.load(task_file, repo=self.name)
                tasks.append(task)
            except Exception as e:
                print(f"Warning: Failed to load task {task_file}: {e}")

        return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task object or None if not found
        """
        task_file = self.tasks_dir / f"task-{task_id}.md"
        if not task_file.exists():
            return None

        return Task.load(task_file, repo=self.name)

    def save_task(self, task: Task) -> Path:
        """Save a task to this repository.

        Args:
            task: Task object to save

        Returns:
            Path to the saved task file
        """
        task.repo = self.name
        return task.save(self.path)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task from this repository.

        Args:
            task_id: Task ID to delete

        Returns:
            True if task was deleted, False if not found
        """
        task_file = self.tasks_dir / f"task-{task_id}.md"
        if not task_file.exists():
            return False

        task_file.unlink()
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

        # Get active tasks (pending or in_progress)
        all_tasks = self.list_tasks()
        active_tasks = [task for task in all_tasks if task.status in ["pending", "in_progress"]]

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
                status_order = {"pending": 0, "in_progress": 1, "completed": 2, "cancelled": 3}
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

        active_tasks.sort(key=get_sort_key)

        # Build README content
        lines = [
            f"# Tasks - {self.name}",
            "",
            "## Active Tasks",
            "",
        ]

        if not active_tasks:
            lines.append("No active tasks.")
        else:
            # Table header
            lines.extend(
                [
                    "| ID | Title | Status | Priority | Assignees | Project | Tags | Due | Countdown |",
                    "|---|---|---|---|---|---|---|---|---|",
                ]
            )

            # Table rows
            for task in active_tasks:
                # Format fields with emojis
                task_id = f"[{task.id[:8]}...](tasks/task-{task.id}.md)"
                title = task.title

                # Status with emoji
                status_emoji = {
                    "pending": "⏳",
                    "in_progress": "🔄",
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
                    f"| {task_id} | {title} | {status} | {priority} | {assignees} | {project} | {tags} | {due_date} | {countdown} |"
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
            raise ValueError(f"Repository already exists: {name}")

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

    def list_all_tasks(self) -> list[Task]:
        """List all tasks across all repositories.

        Returns:
            List of Task objects
        """
        tasks = []
        for repo in self.discover_repositories():
            tasks.extend(repo.list_tasks())
        return tasks
