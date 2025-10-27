"""Tests for search command functionality."""

import shutil
import tempfile
from pathlib import Path

import pytest

from taskrepo.core.config import Config
from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def config(temp_dir):
    """Create a test config."""
    config_file = temp_dir / "config"
    config = Config(config_path=config_file)
    config.parent_dir = temp_dir
    config.save()
    return config


@pytest.fixture
def manager(config):
    """Create repository manager."""
    return RepositoryManager(config.parent_dir)


@pytest.fixture
def test_repo(manager):
    """Create a test repository with sample tasks."""
    repo = manager.create_repository("test")

    # Create sample tasks with different content
    tasks = [
        Task(
            id=repo.next_task_id(),
            title="Follow up Tatiana on fellowship",
            description="Contact Tatiana about the fellowship application deadline",
            status="pending",
            priority="H",
            project="2021__henriques__erc_cog",
            tags=["urgent"],
        ),
        Task(
            id=repo.next_task_id(),
            title="Review bug in authentication",
            description="There's a critical bug that needs fixing",
            status="in-progress",
            priority="H",
            tags=["bug", "v1.0.0"],
        ),
        Task(
            id=repo.next_task_id(),
            title="Update documentation",
            description="Add examples to the API documentation for new users",
            status="pending",
            priority="M",
            project="documentation",
        ),
        Task(
            id=repo.next_task_id(),
            title="Completed task about Tatiana",
            description="This was completed",
            status="completed",
            priority="L",
        ),
        Task(
            id=repo.next_task_id(),
            title="Task with fellowship tag",
            description="Another task",
            status="pending",
            priority="L",
            tags=["fellowship", "admin"],
        ),
    ]

    for task in tasks:
        repo.save_task(task)

    return repo


def search_tasks(tasks, query):
    """Helper function that implements the search logic."""
    query_lower = query.lower()
    matching_tasks = []

    for task in tasks:
        # Search in title
        if query_lower in task.title.lower():
            matching_tasks.append(task)
            continue

        # Search in description
        if task.description and query_lower in task.description.lower():
            matching_tasks.append(task)
            continue

        # Search in project
        if task.project and query_lower in task.project.lower():
            matching_tasks.append(task)
            continue

        # Search in tags
        if any(query_lower in tag.lower() for tag in task.tags):
            matching_tasks.append(task)
            continue

    return matching_tasks


def test_search_in_title(config, manager, test_repo):
    """Test searching for text in task title."""
    tasks = manager.list_all_tasks(include_archived=False)
    results = search_tasks(tasks, "Tatiana")

    # Should find 2 tasks (1 pending, 1 completed)
    assert len(results) == 2
    titles = [t.title for t in results]
    assert "Follow up Tatiana on fellowship" in titles
    assert "Completed task about Tatiana" in titles

    # Exclude completed
    results_active = [t for t in results if t.status != "completed"]
    assert len(results_active) == 1
    assert results_active[0].title == "Follow up Tatiana on fellowship"


def test_search_in_description(config, manager, test_repo):
    """Test searching for text in task description."""
    tasks = manager.list_all_tasks(include_archived=False)
    results = search_tasks(tasks, "critical")

    assert len(results) == 1
    assert results[0].title == "Review bug in authentication"


def test_search_in_project(config, manager, test_repo):
    """Test searching for text in project name."""
    tasks = manager.list_all_tasks(include_archived=False)
    results = search_tasks(tasks, "henriques")

    assert len(results) == 1
    assert results[0].title == "Follow up Tatiana on fellowship"


def test_search_in_tags(config, manager, test_repo):
    """Test searching for text in tags."""
    tasks = manager.list_all_tasks(include_archived=False)
    results = search_tasks(tasks, "admin")

    # Should find task with "admin" tag
    assert len(results) == 1
    assert results[0].title == "Task with fellowship tag"


def test_search_case_insensitive(config, manager, test_repo):
    """Test that search is case-insensitive."""
    tasks = manager.list_all_tasks(include_archived=False)

    # Try uppercase
    results_upper = search_tasks(tasks, "TATIANA")
    assert len(results_upper) == 2

    # Try lowercase
    results_lower = search_tasks(tasks, "tatiana")
    assert len(results_lower) == 2

    # Try mixed case
    results_mixed = search_tasks(tasks, "TaTiAnA")
    assert len(results_mixed) == 2

    # All should return same results
    assert {t.id for t in results_upper} == {t.id for t in results_lower}
    assert {t.id for t in results_upper} == {t.id for t in results_mixed}


def test_search_no_results(config, manager, test_repo):
    """Test search with no matching tasks."""
    tasks = manager.list_all_tasks(include_archived=False)
    results = search_tasks(tasks, "nonexistent")

    assert len(results) == 0


def test_search_with_filters(config, manager, test_repo):
    """Test search combined with filters."""
    tasks = manager.list_all_tasks(include_archived=False)

    # Search for "bug" with high priority
    results = search_tasks(tasks, "bug")
    results = [t for t in results if t.priority == "H"]
    assert len(results) == 1
    assert results[0].title == "Review bug in authentication"

    # Search for "bug" with specific tag
    results = search_tasks(tasks, "bug")
    results = [t for t in results if "v1.0.0" in t.tags]
    assert len(results) == 1

    # Search for "bug" with specific status
    results = search_tasks(tasks, "bug")
    results = [t for t in results if t.status == "in-progress"]
    assert len(results) == 1


def test_search_multiple_fields(config, manager, test_repo):
    """Test that a single task can be found via multiple fields."""
    tasks = manager.list_all_tasks(include_archived=False)

    # The "Follow up Tatiana" task should match on title, description, and project
    results_title = search_tasks(tasks, "Tatiana")
    results_description = search_tasks(tasks, "fellowship application")
    results_project = search_tasks(tasks, "erc_cog")

    # All should find the same task
    assert len(results_title) >= 1
    assert len(results_description) >= 1
    assert len(results_project) >= 1

    task_ids_title = {t.id for t in results_title if "Fellowship" in t.title or "Tatiana" in t.title}
    task_ids_description = {t.id for t in results_description}
    task_ids_project = {t.id for t in results_project}

    # The fellowship task should be in all result sets
    assert len(task_ids_title.intersection(task_ids_description)) > 0
    assert len(task_ids_title.intersection(task_ids_project)) > 0
