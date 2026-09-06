"""Dependency and readiness resolution for TaskRepo."""

from typing import Iterable

from taskrepo.core.task import Task

ACTIONABLE_STATUSES = {"pending", "in-progress"}


def build_task_lookup(tasks: Iterable[Task]) -> dict[str, Task]:
    """Build a lookup mapping task ID to Task object.

    Also indexes by short prefix (8 chars) if unique, to support short UUIDs.
    """
    task_list = list(tasks)
    lookup: dict[str, Task] = {task.id: task for task in task_list}

    prefix_counts: dict[str, int] = {}
    for task in task_list:
        if len(task.id) >= 8:
            prefix = task.id[:8]
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    for task in task_list:
        if len(task.id) >= 8:
            prefix = task.id[:8]
            if prefix_counts[prefix] == 1 and prefix not in lookup:
                lookup[prefix] = task

    return lookup


def is_task_ready(task: Task, task_lookup: dict[str, Task]) -> bool:
    """Return True if a task is actionable and all its dependencies are completed."""
    if task.status not in ACTIONABLE_STATUSES:
        return False

    if not task.depends:
        return True

    for dep_id in task.depends:
        dep_task = task_lookup.get(dep_id.strip())
        if not dep_task or dep_task.status != "completed":
            return False

    return True


def is_task_blocked(task: Task, task_lookup: dict[str, Task]) -> bool:
    """Return True if a task is actionable but has at least one incomplete dependency."""
    if task.status not in ACTIONABLE_STATUSES:
        return False

    if not task.depends:
        return False

    for dep_id in task.depends:
        dep_task = task_lookup.get(dep_id.strip())
        if not dep_task or dep_task.status != "completed":
            return True

    return False


def filter_ready_tasks(tasks: list[Task], all_tasks: list[Task]) -> list[Task]:
    """Filter tasks to only those ready to work on, evaluated against all known tasks."""
    lookup = build_task_lookup(all_tasks)
    return [t for t in tasks if is_task_ready(t, lookup)]


def filter_blocked_tasks(tasks: list[Task], all_tasks: list[Task]) -> list[Task]:
    """Filter tasks blocked by incomplete dependencies (pending, in-progress, or missing)."""
    lookup = build_task_lookup(all_tasks)
    return [t for t in tasks if is_task_ready(t, lookup) is False and is_task_blocked(t, lookup)]
