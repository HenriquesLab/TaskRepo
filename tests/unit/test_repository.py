"""Unit tests for Repository and RepositoryManager."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from taskrepo.core.repository import Repository, RepositoryManager
from taskrepo.core.task import Task


def test_repository_creation():
    """Test creating a repository."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "tasks-test"
        repo_path.mkdir()

        repo = Repository(repo_path)

        assert repo.name == "test"
        assert repo.path == repo_path
        assert repo.tasks_dir.exists()


def test_repository_invalid_name():
    """Test that invalid repository name raises ValueError."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "invalid-name"
        repo_path.mkdir()

        with pytest.raises(ValueError, match="Must start with 'tasks-'"):
            Repository(repo_path)


def test_repository_save_and_load_task():
    """Test saving and loading tasks in a repository."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "tasks-test"
        repo_path.mkdir()

        repo = Repository(repo_path)

        # Create and save task
        task = Task(id="001", title="Test task", status="pending", priority="M")
        repo.save_task(task)

        # Load task
        loaded_task = repo.get_task("001")
        assert loaded_task is not None
        assert loaded_task.id == "001"
        assert loaded_task.title == "Test task"
        assert loaded_task.repo == "test"


def test_repository_list_tasks():
    """Test listing tasks in a repository."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "tasks-test"
        repo_path.mkdir()

        repo = Repository(repo_path)

        # Create multiple tasks
        for i in range(1, 4):
            task = Task(id=f"{i:03d}", title=f"Task {i}", status="pending", priority="M")
            repo.save_task(task)

        # List tasks
        tasks = repo.list_tasks()
        assert len(tasks) == 3
        assert all(task.repo == "test" for task in tasks)


def test_repository_next_task_id():
    """Test generating next task ID."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "tasks-test"
        repo_path.mkdir()

        repo = Repository(repo_path)

        # First task ID
        assert repo.next_task_id() == "001"

        # Create a task
        task = Task(id="001", title="Task 1", status="pending", priority="M")
        repo.save_task(task)

        # Next task ID
        assert repo.next_task_id() == "002"


def test_repository_get_projects():
    """Test getting unique projects."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "tasks-test"
        repo_path.mkdir()

        repo = Repository(repo_path)

        # Create tasks with projects
        Task(id="001", title="Task 1", project="project-a").save(repo_path)
        Task(id="002", title="Task 2", project="project-b").save(repo_path)
        Task(id="003", title="Task 3", project="project-a").save(repo_path)

        projects = repo.get_projects()
        assert len(projects) == 2
        assert "project-a" in projects
        assert "project-b" in projects


def test_repository_manager_discover():
    """Test discovering repositories."""
    with TemporaryDirectory() as tmpdir:
        parent_dir = Path(tmpdir)

        # Create multiple repositories
        (parent_dir / "tasks-repo1").mkdir()
        (parent_dir / "tasks-repo2").mkdir()
        (parent_dir / "not-a-repo").mkdir()  # Should be ignored

        manager = RepositoryManager(parent_dir)
        repos = manager.discover_repositories()

        assert len(repos) == 2
        assert {repo.name for repo in repos} == {"repo1", "repo2"}


def test_repository_manager_create():
    """Test creating a new repository."""
    with TemporaryDirectory() as tmpdir:
        parent_dir = Path(tmpdir)
        manager = RepositoryManager(parent_dir)

        repo = manager.create_repository("new-repo")

        assert repo.name == "new-repo"
        assert repo.path.exists()
        assert repo.tasks_dir.exists()


def test_repository_manager_list_all_tasks():
    """Test listing tasks across all repositories."""
    with TemporaryDirectory() as tmpdir:
        parent_dir = Path(tmpdir)

        # Create repositories with tasks
        repo1_path = parent_dir / "tasks-repo1"
        repo1_path.mkdir()
        repo1 = Repository(repo1_path)
        Task(id="001", title="Task 1").save(repo1.path)

        repo2_path = parent_dir / "tasks-repo2"
        repo2_path.mkdir()
        repo2 = Repository(repo2_path)
        Task(id="001", title="Task 2").save(repo2.path)

        manager = RepositoryManager(parent_dir)
        all_tasks = manager.list_all_tasks()

        assert len(all_tasks) == 2
        assert {task.repo for task in all_tasks} == {"repo1", "repo2"}
