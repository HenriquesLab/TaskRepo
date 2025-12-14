"""Utilities for analyzing task and git repository history."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

from taskrepo.core.repository import Repository
from taskrepo.core.task import Task
from taskrepo.utils import history_cache


@dataclass
class TaskChange:
    """Represents a detected change in a task."""

    field: str  # Field that changed (status, priority, assignees, etc.)
    old_value: str  # Previous value
    new_value: str  # New value
    change_type: str  # 'modified', 'added', 'removed', 'created', 'deleted'
    task_title: Optional[str] = None  # Task title for display
    modifier: Optional[str] = None  # Inferred person who made the change (from assignees)


@dataclass
class CommitEvent:
    """Represents a commit with associated task changes."""

    commit_hash: str
    author: str
    timestamp: datetime
    message: str
    task_changes: dict[str, list[TaskChange]]  # task_id -> changes
    files_changed: list[str]


@lru_cache(maxsize=2048)
def _parse_task_cached(commit_hash: str, task_id: str, content: str) -> Task:
    """Parse a task with caching to avoid redundant YAML parsing.

    OPTIMIZATION: Cache parsed tasks by commit+task_id to avoid re-parsing
    the same task content multiple times during history analysis.
    Increased from 512 to 2048 entries for better hit rate on large histories.

    Args:
        commit_hash: Git commit hash (for cache key)
        task_id: Task ID (for cache key)
        content: Task markdown content

    Returns:
        Parsed Task object
    """
    return Task.from_markdown(content, task_id)


def _commit_event_to_dict(event: CommitEvent) -> dict:
    """Convert CommitEvent to JSON-serializable dict for caching.

    Args:
        event: CommitEvent object

    Returns:
        Dict representation
    """
    return {
        "commit_hash": event.commit_hash,
        "author": event.author,
        "timestamp": event.timestamp.isoformat(),
        "message": event.message,
        "task_changes": {
            task_id: [
                {
                    "field": change.field,
                    "old_value": change.old_value,
                    "new_value": change.new_value,
                    "change_type": change.change_type,
                    "task_title": change.task_title,
                    "modifier": change.modifier,
                }
                for change in changes
            ]
            for task_id, changes in event.task_changes.items()
        },
        "files_changed": event.files_changed,
    }


def _dict_to_commit_event(data: dict) -> CommitEvent:
    """Convert cached dict back to CommitEvent object.

    Args:
        data: Dict representation from cache

    Returns:
        CommitEvent object
    """
    task_changes = {}
    for task_id, changes_list in data.get("task_changes", {}).items():
        task_changes[task_id] = [
            TaskChange(
                field=c["field"],
                old_value=c["old_value"],
                new_value=c["new_value"],
                change_type=c["change_type"],
                task_title=c.get("task_title"),
                modifier=c.get("modifier"),
            )
            for c in changes_list
        ]

    return CommitEvent(
        commit_hash=data["commit_hash"],
        author=data["author"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        message=data["message"],
        task_changes=task_changes,
        files_changed=data.get("files_changed", []),
    )


def get_commit_history(
    repository: Repository,
    since: Optional[datetime] = None,
    task_filter: Optional[str] = None,
    use_cache: bool = True,
) -> list[CommitEvent]:
    """Extract commit history with task changes.

    PERFORMANCE: Uses persistent cache to dramatically speed up repeated queries.
    Cache is per-repository and supports incremental updates.

    Args:
        repository: Repository instance
        since: Only include commits after this date
        task_filter: Only include changes to tasks matching this ID/title pattern
        use_cache: If False, bypass cache and recompute from git (default: True)

    Returns:
        List of CommitEvent objects
    """
    # Try to load from cache first
    if use_cache:
        cached_commits = history_cache.get_cached_commits(repository, since, use_cache=True)
        if cached_commits is not None:
            # Cache hit! Convert dicts back to CommitEvent objects
            return [_dict_to_commit_event(c) for c in cached_commits]

    # Cache miss or bypass - compute from git
    git_repo = repository.git_repo
    if not git_repo:
        return []

    commits = []
    kwargs = {}
    if since:
        kwargs["since"] = since

    # OPTIMIZATION: Only load commits that touch task files
    kwargs["paths"] = ["tasks/", "archive/"]

    try:
        for commit in git_repo.iter_commits(**kwargs):
            # Get files changed in this commit
            files_changed = []
            task_changes = {}

            # For each parent, get the diff
            if commit.parents:
                parent = commit.parents[0]
                # OPTIMIZATION: Only diff task files to avoid processing non-task changes
                diffs = parent.diff(commit, paths=["tasks/", "archive/"])

                for diff in diffs:
                    # Check if this is a task file (in tasks/ or archive/)
                    is_task_file = False
                    task_id = None

                    # Check for moves between tasks/ and archive/ (archive/unarchive operations)
                    if diff.a_path and diff.b_path:
                        # Archive: tasks/ -> archive/
                        if diff.a_path.startswith("tasks/task-") and diff.b_path.startswith("archive/task-"):
                            is_task_file = True
                            task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
                            files_changed.append(f"{diff.a_path} → {diff.b_path}")
                        # Unarchive: archive/ -> tasks/
                        elif diff.a_path.startswith("archive/task-") and diff.b_path.startswith("tasks/task-"):
                            is_task_file = True
                            task_id = diff.b_path.replace("tasks/task-", "").replace(".md", "")
                            files_changed.append(f"{diff.a_path} → {diff.b_path}")
                        # Regular task file change
                        elif diff.a_path.startswith("tasks/task-"):
                            is_task_file = True
                            task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
                            files_changed.append(diff.a_path)
                    # Task file added or deleted
                    elif diff.a_path and diff.a_path.startswith("tasks/task-"):
                        is_task_file = True
                        task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
                        files_changed.append(diff.a_path)
                    elif diff.b_path and diff.b_path.startswith("tasks/task-"):
                        is_task_file = True
                        task_id = diff.b_path.replace("tasks/task-", "").replace(".md", "")
                        files_changed.append(diff.b_path)

                    if is_task_file and task_id:
                        # Parse task changes
                        changes = parse_task_changes(diff, parent, commit)
                        if changes:
                            task_changes[task_id] = changes
            else:
                # First commit - all tasks are new
                for item in commit.tree.traverse():
                    if item.path.startswith("tasks/task-") and item.path.endswith(".md"):
                        files_changed.append(item.path)
                        task_id = item.path.replace("tasks/task-", "").replace(".md", "")
                        task_changes[task_id] = [
                            TaskChange(
                                field="created",
                                old_value="",
                                new_value="Task created",
                                change_type="created",
                            )
                        ]

            # Apply task filter if specified
            if task_filter:
                filtered_changes = {}
                for task_id, changes in task_changes.items():
                    if task_filter.lower() in task_id.lower():
                        filtered_changes[task_id] = changes
                    else:
                        # Also check if filter matches task title
                        # We'll need to parse the task content for this
                        try:
                            if commit.tree / f"tasks/task-{task_id}.md":
                                content = (commit.tree / f"tasks/task-{task_id}.md").data_stream.read().decode("utf-8")
                                task = _parse_task_cached(commit.hexsha, task_id, content)
                                if task_filter.lower() in task.title.lower():
                                    filtered_changes[task_id] = changes
                        except Exception:
                            pass

                task_changes = filtered_changes

            # Only include commits with task changes (if filtering)
            if not task_filter or task_changes:
                commits.append(
                    CommitEvent(
                        commit_hash=commit.hexsha[:8],
                        author=str(commit.author.name),
                        timestamp=commit.committed_datetime,
                        message=commit.message.strip(),
                        task_changes=task_changes,
                        files_changed=files_changed,
                    )
                )

    except Exception:
        # Handle repos with no commits or other git errors
        pass

    # Save to cache for future queries (if caching is enabled)
    if use_cache and commits:
        commit_dicts = [_commit_event_to_dict(c) for c in commits]
        history_cache.update_cache_incremental(repository, commit_dicts)

    return commits


def _infer_modifier(task: Task, commit_author: str) -> Optional[str]:
    """Infer who likely modified the task based on assignees.

    Args:
        task: Task object
        commit_author: Git commit author name

    Returns:
        Assignee username if different from commit author, None otherwise
    """
    if not task.assignees:
        return None

    # If task has exactly one assignee, they likely made the change
    if len(task.assignees) == 1:
        assignee = task.assignees[0]
        # Simple heuristic: if assignee differs from commit author, return it
        # We can't do perfect matching without more metadata, but this is useful
        return assignee

    return None


def parse_task_changes(diff, parent_commit, current_commit) -> list[TaskChange]:
    """Parse changes between two versions of a task file.

    Args:
        diff: GitPython diff object
        parent_commit: Parent commit object
        current_commit: Current commit object

    Returns:
        List of TaskChange objects
    """
    changes = []
    commit_author = str(current_commit.author.name)

    try:
        # Check for archive/unarchive operations (file moves between directories)
        if diff.a_path and diff.b_path:
            # Archive: tasks/ -> archive/
            if diff.a_path.startswith("tasks/task-") and diff.b_path.startswith("archive/task-"):
                task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
                # Get task content to extract title
                if diff.a_blob:
                    content = diff.a_blob.data_stream.read().decode("utf-8")
                    task = _parse_task_cached(parent_commit.hexsha, task_id, content)
                    modifier = _infer_modifier(task, commit_author)
                    changes.append(
                        TaskChange(
                            field="archived",
                            old_value="active",
                            new_value="archived",
                            change_type="archived",
                            task_title=task.title,
                            modifier=modifier,
                        )
                    )
                return changes
            # Unarchive: archive/ -> tasks/
            elif diff.a_path.startswith("archive/task-") and diff.b_path.startswith("tasks/task-"):
                task_id = diff.b_path.replace("tasks/task-", "").replace(".md", "")
                # Get task content to extract title
                if diff.b_blob:
                    content = diff.b_blob.data_stream.read().decode("utf-8")
                    task = _parse_task_cached(current_commit.hexsha, task_id, content)
                    modifier = _infer_modifier(task, commit_author)
                    changes.append(
                        TaskChange(
                            field="unarchived",
                            old_value="archived",
                            new_value="active",
                            change_type="unarchived",
                            task_title=task.title,
                            modifier=modifier,
                        )
                    )
                return changes

        # Get old and new content
        old_content = None
        new_content = None

        if diff.a_blob:
            old_content = diff.a_blob.data_stream.read().decode("utf-8")
        if diff.b_blob:
            new_content = diff.b_blob.data_stream.read().decode("utf-8")

        # Handle deletions
        if new_content is None and old_content is not None:
            task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
            old_task = _parse_task_cached(parent_commit.hexsha, task_id, old_content)
            modifier = _infer_modifier(old_task, commit_author)
            changes.append(
                TaskChange(
                    field="deleted",
                    old_value="Task existed",
                    new_value="Task deleted",
                    change_type="deleted",
                    task_title=old_task.title,
                    modifier=modifier,
                )
            )
            return changes

        # Handle additions
        if old_content is None and new_content is not None:
            task_id = diff.b_path.replace("tasks/task-", "").replace(".md", "")
            new_task = _parse_task_cached(current_commit.hexsha, task_id, new_content)
            modifier = _infer_modifier(new_task, commit_author)
            # Include priority in the creation message
            changes.append(
                TaskChange(
                    field="created",
                    old_value="",
                    new_value=new_task.priority,  # Store priority in new_value
                    change_type="created",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )
            return changes

        # Parse both versions
        task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
        old_task = _parse_task_cached(parent_commit.hexsha, task_id, old_content)
        new_task = _parse_task_cached(current_commit.hexsha, task_id, new_content)

        # Infer who made the changes
        modifier = _infer_modifier(new_task, commit_author)

        # Compare fields
        if old_task.status != new_task.status:
            changes.append(
                TaskChange(
                    field="status",
                    old_value=old_task.status,
                    new_value=new_task.status,
                    change_type="modified",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        if old_task.priority != new_task.priority:
            changes.append(
                TaskChange(
                    field="priority",
                    old_value=old_task.priority,
                    new_value=new_task.priority,
                    change_type="modified",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        if old_task.title != new_task.title:
            changes.append(
                TaskChange(
                    field="title",
                    old_value=old_task.title,
                    new_value=new_task.title,
                    change_type="modified",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        # Compare assignees
        old_assignees = set(old_task.assignees)
        new_assignees = set(new_task.assignees)

        added_assignees = new_assignees - old_assignees
        removed_assignees = old_assignees - new_assignees

        if added_assignees:
            changes.append(
                TaskChange(
                    field="assignees",
                    old_value="",
                    new_value=", ".join(added_assignees),
                    change_type="added",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        if removed_assignees:
            changes.append(
                TaskChange(
                    field="assignees",
                    old_value=", ".join(removed_assignees),
                    new_value="",
                    change_type="removed",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        # Compare tags
        old_tags = set(old_task.tags)
        new_tags = set(new_task.tags)

        added_tags = new_tags - old_tags
        removed_tags = old_tags - new_tags

        if added_tags:
            changes.append(
                TaskChange(
                    field="tags",
                    old_value="",
                    new_value=", ".join(added_tags),
                    change_type="added",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        if removed_tags:
            changes.append(
                TaskChange(
                    field="tags",
                    old_value=", ".join(removed_tags),
                    new_value="",
                    change_type="removed",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        # Compare due date
        old_due = old_task.due.strftime("%Y-%m-%d") if old_task.due else None
        new_due = new_task.due.strftime("%Y-%m-%d") if new_task.due else None

        if old_due != new_due:
            changes.append(
                TaskChange(
                    field="due",
                    old_value=old_due or "None",
                    new_value=new_due or "None",
                    change_type="modified",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        # Compare project
        if old_task.project != new_task.project:
            changes.append(
                TaskChange(
                    field="project",
                    old_value=old_task.project or "None",
                    new_value=new_task.project or "None",
                    change_type="modified",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

        # Compare description
        if old_task.description.strip() != new_task.description.strip():
            changes.append(
                TaskChange(
                    field="description",
                    old_value="(see diff)",
                    new_value="(modified)",
                    change_type="modified",
                    task_title=new_task.title,
                    modifier=modifier,
                )
            )

    except Exception:
        # If parsing fails, return empty changes
        pass

    return changes


def group_by_timeline(commits: list[CommitEvent]) -> dict[str, list[CommitEvent]]:
    """Group commits into timeline buckets.

    Args:
        commits: List of CommitEvent objects

    Returns:
        Dict mapping timeline labels to commit lists
    """
    now = datetime.now(commits[0].timestamp.tzinfo if commits else None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    # Calculate week boundaries
    days_since_monday = today.weekday()
    this_week_start = today - timedelta(days=days_since_monday)
    last_week_start = this_week_start - timedelta(weeks=1)

    groups = {
        "Today": [],
        "Yesterday": [],
        "This Week": [],
        "Last Week": [],
        "2 Weeks Ago": [],
        "3 Weeks Ago": [],
        "Earlier": [],
    }

    for commit in commits:
        commit_date = commit.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

        if commit_date >= today:
            groups["Today"].append(commit)
        elif commit_date >= yesterday:
            groups["Yesterday"].append(commit)
        elif commit_date >= this_week_start:
            groups["This Week"].append(commit)
        elif commit_date >= last_week_start:
            groups["Last Week"].append(commit)
        elif commit_date >= last_week_start - timedelta(weeks=1):
            groups["2 Weeks Ago"].append(commit)
        elif commit_date >= last_week_start - timedelta(weeks=2):
            groups["3 Weeks Ago"].append(commit)
        else:
            groups["Earlier"].append(commit)

    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


def build_change_summary(changes: list[TaskChange], task_id: str) -> str:
    """Build a human-readable summary of task changes.

    Args:
        changes: List of TaskChange objects
        task_id: Task ID (short form)

    Returns:
        Formatted string describing the changes
    """
    lines = []

    for change in changes:
        if change.change_type == "created":
            lines.append(f"Task #{task_id[:8]} created")
        elif change.change_type == "deleted":
            lines.append(f"Task #{task_id[:8]} deleted")
        elif change.change_type == "modified":
            if change.field == "status":
                lines.append(f"Task #{task_id[:8]}: {change.field} {change.old_value} → {change.new_value}")
            elif change.field == "priority":
                lines.append(f"Task #{task_id[:8]}: {change.field} {change.old_value} → {change.new_value}")
            elif change.field == "due":
                lines.append(f"Task #{task_id[:8]}: due date {change.old_value} → {change.new_value}")
            elif change.field == "description":
                lines.append(f"Task #{task_id[:8]}: description modified")
            else:
                lines.append(f"Task #{task_id[:8]}: {change.field} updated")
        elif change.change_type == "added":
            if change.field == "assignees":
                lines.append(f"Task #{task_id[:8]}: added assignee {change.new_value}")
            elif change.field == "tags":
                lines.append(f"Task #{task_id[:8]}: added tag {change.new_value}")
        elif change.change_type == "removed":
            if change.field == "assignees":
                lines.append(f"Task #{task_id[:8]}: removed assignee {change.old_value}")
            elif change.field == "tags":
                lines.append(f"Task #{task_id[:8]}: removed tag {change.old_value}")

    return "\n".join(lines)


def categorize_commit(commit: CommitEvent) -> str:
    """Categorize a commit based on its changes.

    Args:
        commit: CommitEvent object

    Returns:
        Emoji representing the commit category
    """
    # Check for task completions
    for changes in commit.task_changes.values():
        for change in changes:
            if change.field == "status" and change.new_value == "completed":
                return "✅"
            if change.field == "created":
                return "🎯"

    # Check for archive/unarchive operations
    for changes in commit.task_changes.values():
        for change in changes:
            if change.change_type == "archived":
                return "📦"
            if change.change_type == "unarchived":
                return "📤"

    # Check for assignee changes
    for changes in commit.task_changes.values():
        for change in changes:
            if change.field == "assignees":
                return "👥"

    # Check for sync operations
    if "sync" in commit.message.lower() or "pull" in commit.message.lower():
        return "🔄"

    # Default
    return "📝"
