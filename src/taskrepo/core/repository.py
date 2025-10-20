"""Repository discovery and management."""

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

    def next_task_id(self) -> str:
        """Generate the next available task ID.

        Returns:
            Next task ID as a zero-padded string (e.g., '001', '002')
        """
        tasks = self.list_tasks()
        if not tasks:
            return "001"

        # Find the maximum ID
        max_id = max(int(task.id) for task in tasks if task.id.isdigit())
        return f"{max_id + 1:03d}"

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

    def create_repository(self, name: str) -> Repository:
        """Create a new task repository.

        Args:
            name: Repository name (without 'tasks-' prefix)

        Returns:
            Repository object

        Raises:
            ValueError: If repository already exists
        """
        repo_path = self.parent_dir / f"tasks-{name}"
        if repo_path.exists():
            raise ValueError(f"Repository already exists: {name}")

        repo_path.mkdir(parents=True, exist_ok=True)
        return Repository(repo_path)

    def list_all_tasks(self) -> list[Task]:
        """List all tasks across all repositories.

        Returns:
            List of Task objects
        """
        tasks = []
        for repo in self.discover_repositories():
            tasks.extend(repo.list_tasks())
        return tasks
