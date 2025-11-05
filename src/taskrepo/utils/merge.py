"""Merge conflict detection and resolution utilities for TaskRepo."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from git import Repo as GitRepo

from taskrepo.core.task import Task


@dataclass
class ConflictInfo:
    """Information about a merge conflict in a task file.

    Attributes:
        file_path: Path to the conflicting task file (relative to repo root)
        local_task: Task object from local version
        remote_task: Task object from remote version
        conflicting_fields: List of field names that have different values
        can_auto_merge: Whether the conflict can be automatically resolved
    """

    file_path: Path
    local_task: Task
    remote_task: Task
    conflicting_fields: list[str]
    can_auto_merge: bool


def detect_conflicts(git_repo: GitRepo, base_path: Path) -> list[ConflictInfo]:
    """Detect merge conflicts between local and remote branches.

    Fetches remote changes without merging and compares task files
    that have been modified in both branches.

    Args:
        git_repo: GitPython repository object
        base_path: Base path of the repository (for resolving file paths)

    Returns:
        List of ConflictInfo objects for conflicting tasks

    Raises:
        GitCommandError: If fetch or diff operations fail
    """
    conflicts = []

    # Fetch remote changes without merging
    if not git_repo.remotes:
        return conflicts  # No remote, no conflicts

    origin = git_repo.remotes.origin
    origin.fetch()

    # Get the remote branch name (usually origin/main or origin/master)
    try:
        remote_branch = origin.refs[0].name  # e.g., 'origin/main'
    except (IndexError, AttributeError):
        return conflicts  # No remote branch

    # Find files modified in both local and remote
    try:
        # Get diff between local HEAD and remote branch
        diff_index = git_repo.head.commit.diff(remote_branch)
    except Exception:
        return conflicts  # No commits or diff failed

    # Track files modified in both branches
    local_modified_files = set()
    remote_modified_files = set()

    for diff_item in diff_index:
        # Check if file exists in both versions (modified on both sides)
        if diff_item.a_path and diff_item.b_path:
            file_path = diff_item.a_path
            # Only consider task markdown files
            if file_path.startswith("tasks/") and file_path.endswith(".md"):
                if diff_item.change_type in ["M", "R"]:  # Modified or renamed
                    local_modified_files.add(file_path)
                    remote_modified_files.add(file_path)

    # Check for actual conflicts in task files
    conflicting_files = local_modified_files & remote_modified_files

    for file_path_str in conflicting_files:
        file_path = Path(file_path_str)
        abs_file_path = base_path / file_path

        # Skip if file doesn't exist locally
        if not abs_file_path.exists():
            continue

        try:
            # Load local version
            with open(abs_file_path, "r", encoding="utf-8") as f:
                local_content = f.read()
            local_task = Task.from_markdown(
                local_content, task_id=file_path.stem.replace("task-", ""), repo=base_path.name.replace("tasks-", "")
            )

            # Load remote version
            remote_content = git_repo.git.show(f"{remote_branch}:{file_path_str}")
            remote_task = Task.from_markdown(
                remote_content, task_id=file_path.stem.replace("task-", ""), repo=base_path.name.replace("tasks-", "")
            )

            # Compare tasks and find conflicting fields
            conflicting_fields = _find_conflicting_fields(local_task, remote_task)

            # Only report as conflict if there are actual field differences
            # (tasks differing only in modified/created timestamps are not conflicts)
            if conflicting_fields:
                # Determine if auto-merge is possible
                can_auto_merge = _can_auto_merge(local_task, remote_task, conflicting_fields)

                conflict_info = ConflictInfo(
                    file_path=file_path,
                    local_task=local_task,
                    remote_task=remote_task,
                    conflicting_fields=conflicting_fields,
                    can_auto_merge=can_auto_merge,
                )
                conflicts.append(conflict_info)

        except Exception:
            # Skip files that can't be parsed
            continue

    return conflicts


def _find_conflicting_fields(local_task: Task, remote_task: Task) -> list[str]:
    """Find fields that differ between two task versions.

    Note: 'modified' and 'created' timestamps are intentionally excluded from
    conflict detection as they're expected to differ and handled separately.

    Args:
        local_task: Local task version
        remote_task: Remote task version

    Returns:
        List of field names that have different values (excluding timestamps)
    """
    conflicting = []

    # Compare simple fields (excluding timestamps)
    simple_fields = ["title", "status", "priority", "project", "parent", "description"]
    for field in simple_fields:
        local_val = getattr(local_task, field)
        remote_val = getattr(remote_task, field)
        if local_val != remote_val:
            conflicting.append(field)

    # Compare date fields (excluding created/modified timestamps)
    date_fields = ["due"]
    for field in date_fields:
        local_val = getattr(local_task, field)
        remote_val = getattr(remote_task, field)
        # Compare dates, accounting for None
        if local_val != remote_val:
            conflicting.append(field)

    # Compare list fields
    list_fields = ["assignees", "tags", "links", "depends"]
    for field in list_fields:
        local_val = set(getattr(local_task, field))
        remote_val = set(getattr(remote_task, field))
        if local_val != remote_val:
            conflicting.append(field)

    return conflicting


def _can_auto_merge(local_task: Task, remote_task: Task, conflicting_fields: list[str]) -> bool:
    """Determine if tasks can be automatically merged.

    Auto-merge is possible when:
    1. One task is definitively newer (modified timestamp differs by >1 second)
    2. Only list fields conflict (can be unioned)
    3. Description is not modified

    Args:
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of conflicting field names

    Returns:
        True if tasks can be auto-merged, False otherwise
    """
    # If description conflicts, need manual resolution
    if "description" in conflicting_fields:
        return False

    # Check if timestamps differ significantly (>1 second)
    time_diff = abs((local_task.modified - remote_task.modified).total_seconds())
    if time_diff > 1:
        return True  # Can use newer timestamp

    # If only list fields conflict, can merge by union
    list_fields = {"assignees", "tags", "links", "depends"}
    only_list_conflicts = all(field in list_fields for field in conflicting_fields)

    return only_list_conflicts


def smart_merge_tasks(local_task: Task, remote_task: Task, conflicting_fields: list[str]) -> Optional[Task]:
    """Automatically merge two conflicting task versions.

    Uses timestamp-based merging for simple fields and union for list fields.

    **Special Status Priority Rule**:
    If the remote status is a progress/completion state (in-progress, completed, cancelled),
    it takes priority over the local status regardless of timestamps. This ensures that
    important status transitions aren't overwritten by local changes.

    Args:
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of field names that conflict

    Returns:
        Merged task, or None if automatic merge is not possible
    """
    # Check if auto-merge is possible
    if not _can_auto_merge(local_task, remote_task, conflicting_fields):
        return None

    # Determine which task is newer
    use_local = local_task.modified >= remote_task.modified

    # Start with the newer task as base
    if use_local:
        merged = Task(
            id=local_task.id,
            title=local_task.title,
            status=local_task.status,
            priority=local_task.priority,
            project=local_task.project,
            assignees=local_task.assignees.copy(),
            tags=local_task.tags.copy(),
            links=local_task.links.copy(),
            due=local_task.due,
            created=local_task.created,
            modified=local_task.modified,
            depends=local_task.depends.copy(),
            parent=local_task.parent,
            description=local_task.description,
            repo=local_task.repo,
        )
    else:
        merged = Task(
            id=remote_task.id,
            title=remote_task.title,
            status=remote_task.status,
            priority=remote_task.priority,
            project=remote_task.project,
            assignees=remote_task.assignees.copy(),
            tags=remote_task.tags.copy(),
            links=remote_task.links.copy(),
            due=remote_task.due,
            created=remote_task.created,
            modified=remote_task.modified,
            depends=remote_task.depends.copy(),
            parent=remote_task.parent,
            description=remote_task.description,
            repo=remote_task.repo,
        )

    # Apply special status priority rule:
    # If remote status indicates progress/completion, use it regardless of timestamp
    priority_statuses = ["in-progress", "completed", "cancelled"]
    if "status" in conflicting_fields and remote_task.status in priority_statuses:
        merged.status = remote_task.status

    # Merge list fields by taking union
    list_fields = ["assignees", "tags", "links", "depends"]
    for field in list_fields:
        if field in conflicting_fields:
            local_set = set(getattr(local_task, field))
            remote_set = set(getattr(remote_task, field))
            merged_list = sorted(local_set | remote_set)  # Union and sort
            setattr(merged, field, merged_list)

    # Update modified timestamp to now
    merged.modified = datetime.now()

    return merged
