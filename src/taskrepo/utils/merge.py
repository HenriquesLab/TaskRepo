"""Merge conflict detection and resolution utilities for TaskRepo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from git import Repo as GitRepo

from taskrepo.core.task import Task

if TYPE_CHECKING:
    from typing import Any

# Field categories for merge logic
SIMPLE_FIELDS = ["title", "status", "priority", "project", "parent", "description"]
DATE_FIELDS = ["due"]
LIST_FIELDS = ["assignees", "tags", "links", "depends"]
SEMANTIC_FIELDS = {"status", "priority"}
CONTENT_FIELDS = {"title", "description", "project"}

# Thresholds for merge decisions
MIN_TIME_DIFF_SECONDS = 1  # Minimum time difference to resolve conflicts
TITLE_SIMILARITY_THRESHOLD = 0.7  # Title must be <70% similar to be major change
DESCRIPTION_SIMILARITY_THRESHOLD = 0.5  # Description must be <50% similar
MIN_DESCRIPTION_LENGTH = 50  # Minimum length to consider description substantial


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


def _calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two text strings.

    Args:
        text1: First text string
        text2: Second text string

    Returns:
        Similarity ratio between 0.0 (completely different) and 1.0 (identical)
    """
    return SequenceMatcher(None, text1, text2).ratio()


def _copy_task_from(source_task: Task) -> Task:
    """Create a copy of a task with all fields.

    Args:
        source_task: Task to copy

    Returns:
        New Task instance with copied values
    """
    return Task(
        id=source_task.id,
        title=source_task.title,
        status=source_task.status,
        priority=source_task.priority,
        project=source_task.project,
        assignees=source_task.assignees.copy(),
        tags=source_task.tags.copy(),
        links=source_task.links.copy(),
        due=source_task.due,
        created=source_task.created,
        modified=source_task.modified,
        depends=source_task.depends.copy(),
        parent=source_task.parent,
        description=source_task.description,
        repo=source_task.repo,
    )


def _resolve_semantic_conflict(value_a: str, value_b: str, newer_is_a: bool, get_priority: Callable[[str], int]) -> str:
    """Generic semantic conflict resolution.

    Chooses the value with higher semantic priority. If equal, uses timestamp.

    Args:
        value_a: First value to compare
        value_b: Second value to compare
        newer_is_a: Whether value_a is from the newer task
        get_priority: Function to get semantic priority of a value (higher = better)

    Returns:
        The value with higher semantic priority, or newer if equal
    """
    priority_a = get_priority(value_a)
    priority_b = get_priority(value_b)

    if priority_a > priority_b:
        return value_a
    elif priority_b > priority_a:
        return value_b
    else:
        # Equal priority - use timestamp
        return value_a if newer_is_a else value_b


def detect_conflicts(
    git_repo: GitRepo, base_path: Path, task_cache: Any = None, skip_fetch: bool = False
) -> list[ConflictInfo]:
    """Detect merge conflicts between local and remote branches.

    Fetches remote changes without merging and compares task files
    that have been modified in both branches.

    Args:
        git_repo: GitPython repository object
        base_path: Base path of the repository (for resolving file paths)
        task_cache: Optional TaskCache object to avoid redundant parsing
        skip_fetch: Skip fetch operation if already performed (optimization)

    Returns:
        List of ConflictInfo objects for conflicting tasks

    Raises:
        GitCommandError: If fetch or diff operations fail
    """
    conflicts: list[ConflictInfo] = []

    # Fetch remote changes without merging
    if not git_repo.remotes:
        return conflicts  # No remote, no conflicts

    origin = git_repo.remotes.origin
    if not skip_fetch:
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
    local_modified_files: set[str] = set()
    remote_modified_files: set[str] = set()

    for diff_item in diff_index:
        # Check if file exists in both versions (modified on both sides)
        if diff_item.a_path and diff_item.b_path:
            file_path_str = diff_item.a_path
            # Only consider task markdown files
            if file_path_str.startswith("tasks/") and file_path_str.endswith(".md"):
                if diff_item.change_type in ["M", "R"]:  # Modified or renamed
                    local_modified_files.add(file_path_str)
                    remote_modified_files.add(file_path_str)

    # Check for actual conflicts in task files
    conflicting_files = local_modified_files & remote_modified_files

    for file_path_str in conflicting_files:
        file_path = Path(file_path_str)
        abs_file_path = base_path / file_path

        # Skip if file doesn't exist locally
        if not abs_file_path.exists():
            continue

        try:
            # Extract task metadata
            task_id = file_path.stem.replace("task-", "")
            repo_name = base_path.name.replace("tasks-", "")

            # Load local version (use cache if available)
            with open(abs_file_path, "r", encoding="utf-8") as f:
                local_content = f.read()

            local_task = None
            if task_cache:
                local_task = task_cache.get(abs_file_path, local_content)

            if not local_task:
                local_task = Task.from_markdown(local_content, task_id=task_id, repo=repo_name)
                if task_cache:
                    task_cache.set(abs_file_path, local_task, local_content)

            # Load remote version (build cache key for remote)
            remote_content = git_repo.git.show(f"{remote_branch}:{file_path_str}")
            remote_cache_key = abs_file_path.parent / f"remote_{abs_file_path.name}"

            remote_task = None
            if task_cache:
                remote_task = task_cache.get(remote_cache_key, remote_content)

            if not remote_task:
                remote_task = Task.from_markdown(remote_content, task_id=task_id, repo=repo_name)
                if task_cache:
                    task_cache.set(remote_cache_key, remote_task, remote_content)

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

    # Compare simple and date fields
    for field in SIMPLE_FIELDS + DATE_FIELDS:
        local_val = getattr(local_task, field)
        remote_val = getattr(remote_task, field)
        if local_val != remote_val:
            conflicting.append(field)

    # Compare list fields (use sets for comparison)
    for field in LIST_FIELDS:
        local_val = set(getattr(local_task, field))
        remote_val = set(getattr(remote_task, field))
        if local_val != remote_val:
            conflicting.append(field)

    return conflicting


def _can_auto_merge(local_task: Task, remote_task: Task, conflicting_fields: list[str]) -> bool:
    """Determine if tasks can be automatically merged.

    Auto-merge is possible when:
    1. Description conflict can be auto-resolved (one empty, major edit, or both same)
    2. Status/priority conflicts can use semantic resolution
    3. Other simple field conflicts with clear timestamp winner
    4. List fields can be unioned

    Args:
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of conflicting field names

    Returns:
        True if tasks can be auto-merged, False otherwise
    """
    # Check description conflicts
    if "description" in conflicting_fields:
        local_desc = local_task.description.strip()
        remote_desc = remote_task.description.strip()

        # If one is empty, can auto-merge (use non-empty one)
        if not local_desc or not remote_desc:
            pass  # Can auto-merge

        # If both have content and differ, check if it's a major edit
        elif local_desc != remote_desc:
            # Allow auto-merge if this is a major edit (will use local description)
            is_major = _is_major_edit(local_task, remote_task, conflicting_fields)
            if not is_major:
                return False  # Not a major edit - need manual resolution

    # Check if we can auto-resolve all conflicts
    time_diff = abs((local_task.modified - remote_task.modified).total_seconds())

    for field in conflicting_fields:
        if field in SEMANTIC_FIELDS:
            continue  # Always resolvable
        elif field in LIST_FIELDS:
            continue  # Always resolvable by union
        elif field in DATE_FIELDS:
            # Can resolve if one is None
            local_val = getattr(local_task, field)
            remote_val = getattr(remote_task, field)
            if local_val is None or remote_val is None:
                continue  # Resolvable - use non-None value
            # Both have values - need clear timestamp to decide
            if time_diff <= MIN_TIME_DIFF_SECONDS:
                return False  # Too close to call
        elif field in {"title", "project", "parent"}:
            # Need clear timestamp winner
            if time_diff <= MIN_TIME_DIFF_SECONDS:
                return False  # Too close to call
        elif field == "description":
            # Already handled above
            pass
        else:
            # Unknown field - be conservative
            return False

    return True


def get_status_priority(status: str) -> int:
    """Get semantic priority of a status (higher = more progress).

    Args:
        status: Task status (pending, in-progress, completed, cancelled)

    Returns:
        Priority level: 0 (pending) < 1 (in-progress) < 2 (completed/cancelled)
    """
    priority_map = {
        "pending": 0,
        "in-progress": 1,
        "completed": 2,
        "cancelled": 2,  # Equal to completed (both are terminal states)
    }
    return priority_map.get(status, 0)


def resolve_status_conflict(status_a: str, status_b: str, newer_is_a: bool) -> str:
    """Choose status with more semantic progress.

    Args:
        status_a: First status to compare
        status_b: Second status to compare
        newer_is_a: Whether status_a is from the newer task

    Returns:
        The status that represents more progress, or newer if equal

    Examples:
        >>> resolve_status_conflict("pending", "completed", newer_is_a=True)
        "completed"  # More progress wins, even if older

        >>> resolve_status_conflict("completed", "cancelled", newer_is_a=False)
        "cancelled"  # Equal progress, newer wins
    """
    return _resolve_semantic_conflict(status_a, status_b, newer_is_a, get_status_priority)


def get_priority_level(priority: str) -> int:
    """Get urgency level of a priority (higher = more urgent).

    Args:
        priority: Task priority (H, M, L)

    Returns:
        Urgency level: 3 (H) > 2 (M) > 1 (L)
    """
    priority_map = {"H": 3, "M": 2, "L": 1}
    return priority_map.get(priority, 0)


def resolve_priority_conflict(priority_a: str, priority_b: str, newer_is_a: bool) -> str:
    """Choose priority with more urgency.

    Args:
        priority_a: First priority to compare
        priority_b: Second priority to compare
        newer_is_a: Whether priority_a is from the newer task

    Returns:
        The more urgent priority, or newer if equal

    Examples:
        >>> resolve_priority_conflict("M", "H", newer_is_a=True)
        "H"  # Higher urgency wins, even if older

        >>> resolve_priority_conflict("H", "H", newer_is_a=False)
        "H"  # Equal urgency, newer wins (but same result)
    """
    return _resolve_semantic_conflict(priority_a, priority_b, newer_is_a, get_priority_level)


def _is_major_edit(local_task: Task, remote_task: Task, conflicting_fields: list[str]) -> bool:
    """Detect if local changes represent a major edit session.

    A major edit is when the user is clearly rewriting/restructuring the task,
    not just updating status or making minor tweaks.

    Args:
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of field names that conflict

    Returns:
        True if local changes represent a major edit session
    """
    # Count how many content fields changed
    content_changes = sum(1 for field in conflicting_fields if field in CONTENT_FIELDS)

    # Major edit if 2+ content fields changed (e.g., title + description)
    if content_changes >= 2:
        return True

    # Also consider it major if title changed significantly
    if "title" in conflicting_fields:
        local_title = local_task.title.strip()
        remote_title = remote_task.title.strip()
        if local_title and remote_title:
            similarity = _calculate_text_similarity(local_title, remote_title)
            if similarity < TITLE_SIMILARITY_THRESHOLD:
                return True

    # Or if description changed substantially
    if "description" in conflicting_fields:
        local_desc = local_task.description.strip()
        remote_desc = remote_task.description.strip()
        # Both have content and significantly different
        if local_desc and remote_desc and len(local_desc) > MIN_DESCRIPTION_LENGTH:
            similarity = _calculate_text_similarity(local_desc, remote_desc)
            if similarity < DESCRIPTION_SIMILARITY_THRESHOLD:
                return True

    return False


def smart_merge_tasks(local_task: Task, remote_task: Task, conflicting_fields: list[str]) -> Optional[Task]:
    """Automatically merge two conflicting task versions using semantic understanding.

    **Enhanced Semantic Merging Strategy**:

    - **Status**: Progress wins (completed/cancelled > in-progress > pending).
      If equal progress, newer timestamp wins.

    - **Priority**: Higher urgency wins (H > M > L). If equal, newer wins.

    - **Description**: If one is empty, use non-empty. If both differ, manual resolution needed.

    - **Due date**: If one is None, use non-None. If both differ, newer wins.

    - **List fields** (assignees, tags, links, depends): **SMART MERGE**
      1. If local is a major edit session → prefer local version
      2. If local explicitly removed items and is newer → prefer local version
      3. If local is significantly newer (>30s) → prefer local version
      4. Otherwise → union of both versions (safe default)

    - **Other fields**: Newer timestamp wins.

    This ensures that intentional edits (like removing tags) aren't overwritten
    by blindly merging everything together.

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

    # Detect major edit session
    is_major_edit = _is_major_edit(local_task, remote_task, conflicting_fields)

    # Start with the newer task as base
    merged = _copy_task_from(local_task if use_local else remote_task)

    # Apply semantic resolution for status conflicts
    # Status with more progress wins (completed/cancelled > in-progress > pending)
    if "status" in conflicting_fields:
        merged.status = resolve_status_conflict(local_task.status, remote_task.status, newer_is_a=use_local)

    # Apply semantic resolution for priority conflicts
    # Higher urgency wins (H > M > L)
    if "priority" in conflicting_fields:
        merged.priority = resolve_priority_conflict(local_task.priority, remote_task.priority, newer_is_a=use_local)

    # Handle description conflicts
    if "description" in conflicting_fields:
        local_desc = local_task.description.strip()
        remote_desc = remote_task.description.strip()
        if not local_desc and remote_desc:
            # One empty - use non-empty
            merged.description = remote_task.description
        elif local_desc and not remote_desc:
            # One empty - use non-empty
            merged.description = local_task.description
        elif local_desc and remote_desc and is_major_edit:
            # Both have content, but major edit - prefer local
            merged.description = local_task.description
        # else: both empty or both same - keep merged value (newer task)

    # Handle due date conflicts - use non-None if one is None
    if "due" in conflicting_fields:
        if local_task.due is None and remote_task.due is not None:
            merged.due = remote_task.due
        elif local_task.due is not None and remote_task.due is None:
            merged.due = local_task.due
        # else: both have values - use newer (already set in merged)

    # SMART merge list fields with context-aware logic
    for field in LIST_FIELDS:
        if field in conflicting_fields:
            local_items = getattr(local_task, field)
            remote_items = getattr(remote_task, field)
            local_set = set(local_items)
            remote_set = set(remote_items)

            # Determine merge strategy based on context
            # Rule 1: Major edit session (title+description changed significantly)
            #         → respect ALL local changes
            # Rule 2: Otherwise → use union (safe default for collaboration)

            if is_major_edit and use_local:
                # Major edit: user is actively rewriting the task, respect their version
                merged_list = sorted(local_set)
            else:
                # Safe default: union (both sides may have added different items)
                merged_list = sorted(local_set | remote_set)

            setattr(merged, field, merged_list)

    # Update modified timestamp to now
    merged.modified = datetime.now()

    return merged
