"""Utilities for analyzing task and git repository history."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from git import Repo as GitRepo

from taskrepo.core.task import Task


@dataclass
class TaskChange:
    """Represents a detected change in a task."""

    field: str  # Field that changed (status, priority, assignees, etc.)
    old_value: str  # Previous value
    new_value: str  # New value
    change_type: str  # 'modified', 'added', 'removed', 'created', 'deleted'
    task_title: Optional[str] = None  # Task title for display


@dataclass
class CommitEvent:
    """Represents a commit with associated task changes."""

    commit_hash: str
    author: str
    timestamp: datetime
    message: str
    task_changes: dict[str, list[TaskChange]]  # task_id -> changes
    files_changed: list[str]


def get_commit_history(
    git_repo: GitRepo,
    since: Optional[datetime] = None,
    task_filter: Optional[str] = None,
) -> list[CommitEvent]:
    """Extract commit history with task changes.

    Args:
        git_repo: GitRepo instance
        since: Only include commits after this date
        task_filter: Only include changes to tasks matching this ID/title pattern

    Returns:
        List of CommitEvent objects
    """
    commits = []
    kwargs = {}
    if since:
        kwargs["since"] = since

    try:
        for commit in git_repo.iter_commits(**kwargs):
            # Get files changed in this commit
            files_changed = []
            task_changes = {}

            # For each parent, get the diff
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit)

                for diff in diffs:
                    # Check if this is a task file
                    if diff.a_path and diff.a_path.startswith("tasks/task-"):
                        files_changed.append(diff.a_path)

                        # Extract task ID from filename
                        task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")

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
                                task = Task.from_markdown(content, task_id)
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

    return commits


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

    try:
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
            old_task = Task.from_markdown(old_content, task_id)
            changes.append(
                TaskChange(
                    field="deleted",
                    old_value="Task existed",
                    new_value="Task deleted",
                    change_type="deleted",
                    task_title=old_task.title,
                )
            )
            return changes

        # Handle additions
        if old_content is None and new_content is not None:
            task_id = diff.b_path.replace("tasks/task-", "").replace(".md", "")
            new_task = Task.from_markdown(new_content, task_id)
            # Include priority in the creation message
            changes.append(
                TaskChange(
                    field="created",
                    old_value="",
                    new_value=new_task.priority,  # Store priority in new_value
                    change_type="created",
                    task_title=new_task.title,
                )
            )
            return changes

        # Parse both versions
        task_id = diff.a_path.replace("tasks/task-", "").replace(".md", "")
        old_task = Task.from_markdown(old_content, task_id)
        new_task = Task.from_markdown(new_content, task_id)

        # Compare fields
        if old_task.status != new_task.status:
            changes.append(
                TaskChange(
                    field="status",
                    old_value=old_task.status,
                    new_value=new_task.status,
                    change_type="modified",
                    task_title=new_task.title,
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
