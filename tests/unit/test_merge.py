"""Tests for merge conflict detection and resolution."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from taskrepo.core.task import Task
from taskrepo.utils.merge import (
    ConflictInfo,
    _can_auto_merge,
    _find_conflicting_fields,
    smart_merge_tasks,
)


@pytest.fixture
def base_task():
    """Create a base task for testing."""
    return Task(
        id="001",
        title="Test Task",
        status="pending",
        priority="M",
        project="test-project",
        assignees=["@alice"],
        tags=["bug"],
        links=["https://github.com/org/repo/issues/1"],
        due=datetime(2025, 11, 1),
        created=datetime(2025, 10, 1, 10, 0, 0),
        modified=datetime(2025, 10, 20, 10, 0, 0),
        depends=[],
        parent=None,
        description="Original description",
        repo="test-repo",
    )


@pytest.fixture
def local_task(base_task):
    """Create a local version of the task (modified locally)."""
    task = Task(
        id=base_task.id,
        title=base_task.title,
        status="in-progress",  # Changed
        priority=base_task.priority,
        project=base_task.project,
        assignees=["@alice", "@bob"],  # Added @bob
        tags=base_task.tags.copy(),
        links=base_task.links.copy(),
        due=base_task.due,
        created=base_task.created,
        modified=datetime(2025, 10, 24, 14, 30, 0),  # Newer
        depends=base_task.depends.copy(),
        parent=base_task.parent,
        description=base_task.description,
        repo=base_task.repo,
    )
    return task


@pytest.fixture
def remote_task(base_task):
    """Create a remote version of the task (modified on remote)."""
    task = Task(
        id=base_task.id,
        title=base_task.title,
        status="pending",  # Unchanged
        priority="H",  # Changed
        project=base_task.project,
        assignees=["@alice", "@charlie"],  # Added @charlie
        tags=["bug", "urgent"],  # Added urgent
        links=base_task.links.copy(),
        due=datetime(2025, 10, 30),  # Changed
        created=base_task.created,
        modified=datetime(2025, 10, 24, 10, 15, 0),  # Older
        depends=base_task.depends.copy(),
        parent=base_task.parent,
        description=base_task.description,
        repo=base_task.repo,
    )
    return task


class TestFindConflictingFields:
    """Tests for _find_conflicting_fields function."""

    def test_no_conflicts(self, base_task):
        """Test when tasks are identical."""
        conflicts = _find_conflicting_fields(base_task, base_task)
        assert conflicts == []

    def test_simple_field_conflicts(self, base_task, local_task):
        """Test detection of simple field conflicts."""
        conflicts = _find_conflicting_fields(base_task, local_task)
        assert "status" in conflicts
        assert "assignees" in conflicts

    def test_list_field_conflicts(self, base_task, remote_task):
        """Test detection of list field conflicts."""
        conflicts = _find_conflicting_fields(base_task, remote_task)
        assert "priority" in conflicts
        assert "assignees" in conflicts
        assert "tags" in conflicts
        assert "due" in conflicts

    def test_all_fields_conflict(self, local_task, remote_task):
        """Test when many fields conflict."""
        conflicts = _find_conflicting_fields(local_task, remote_task)
        assert "status" in conflicts
        assert "priority" in conflicts
        assert "assignees" in conflicts
        assert "tags" in conflicts
        assert "due" in conflicts

    def test_modified_timestamp_not_conflict(self, base_task):
        """Test that tasks differing only in modified timestamp have no conflicts."""
        # Create two identical tasks with different modified timestamps
        task1 = Task(
            id=base_task.id,
            title=base_task.title,
            status=base_task.status,
            priority=base_task.priority,
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 20, 10, 0, 0),  # Older
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )
        task2 = Task(
            id=base_task.id,
            title=base_task.title,
            status=base_task.status,
            priority=base_task.priority,
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 21, 14, 30, 0),  # Newer
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        # Should have no conflicts since only modified timestamp differs
        conflicts = _find_conflicting_fields(task1, task2)
        assert conflicts == []


class TestCanAutoMerge:
    """Tests for _can_auto_merge function."""

    def test_can_merge_with_timestamp_difference(self, local_task, remote_task):
        """Test auto-merge when timestamps differ significantly."""
        conflicts = ["status", "priority"]
        assert _can_auto_merge(local_task, remote_task, conflicts) is True

    def test_cannot_merge_with_description_conflict(self, local_task, remote_task):
        """Test cannot auto-merge when description conflicts."""
        local_task.description = "Local description"
        remote_task.description = "Remote description"
        conflicts = ["description", "status"]
        assert _can_auto_merge(local_task, remote_task, conflicts) is False

    def test_can_merge_list_only_conflicts(self, base_task):
        """Test can auto-merge when only list fields conflict."""
        task1 = base_task
        task2 = Task(
            id=base_task.id,
            title=base_task.title,
            status=base_task.status,
            priority=base_task.priority,
            project=base_task.project,
            assignees=["@alice", "@bob"],  # Different
            tags=["bug", "urgent"],  # Different
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=base_task.modified + timedelta(milliseconds=500),  # Same second
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )
        conflicts = ["assignees", "tags"]
        assert _can_auto_merge(task1, task2, conflicts) is True

    def test_can_merge_same_timestamp_with_semantic_fields(self, base_task):
        """Test CAN auto-merge status/priority with semantic resolution even with same timestamp."""
        task1 = base_task
        task2 = Task(
            id=base_task.id,
            title=base_task.title,
            status="in-progress",  # Different - higher progress
            priority="H",  # Different - higher urgency
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=base_task.modified + timedelta(milliseconds=500),  # Same second
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )
        conflicts = ["status", "priority"]
        # With semantic merging, status/priority conflicts can be auto-merged
        assert _can_auto_merge(task1, task2, conflicts) is True


class TestSmartMergeTasks:
    """Tests for smart_merge_tasks function."""

    def test_merge_uses_semantic_resolution(self, local_task, remote_task):
        """Test merge uses semantic resolution for status/priority, not just timestamps."""
        conflicts = ["status", "priority", "due", "assignees", "tags"]
        merged = smart_merge_tasks(local_task, remote_task, conflicts)

        assert merged is not None
        # Status: local="in-progress" (higher progress) vs remote="pending" → use in-progress
        assert merged.status == local_task.status  # Higher progress wins
        # Priority: local="M" vs remote="H" → use H (higher urgency wins, not newer timestamp)
        assert merged.priority == remote_task.priority  # Higher urgency wins

    def test_merge_unions_list_fields(self, local_task, remote_task):
        """Test merge creates union of list fields."""
        conflicts = ["assignees", "tags"]
        merged = smart_merge_tasks(local_task, remote_task, conflicts)

        assert merged is not None
        # Should have union of assignees
        assert set(merged.assignees) == {"@alice", "@bob", "@charlie"}
        # Should have union of tags
        assert set(merged.tags) == {"bug", "urgent"}

    def test_merge_updates_modified_timestamp(self, local_task, remote_task):
        """Test merge updates modified timestamp to now."""
        conflicts = ["status"]
        before_merge = datetime.now()
        merged = smart_merge_tasks(local_task, remote_task, conflicts)
        after_merge = datetime.now()

        assert merged is not None
        assert before_merge <= merged.modified <= after_merge

    def test_cannot_merge_with_description_conflict(self, local_task, remote_task):
        """Test merge returns None when description conflicts."""
        local_task.description = "Local description"
        remote_task.description = "Remote description"
        conflicts = ["description", "status"]

        merged = smart_merge_tasks(local_task, remote_task, conflicts)
        assert merged is None

    def test_merge_preserves_non_conflicting_fields(self, local_task, remote_task):
        """Test merge preserves fields that don't conflict."""
        conflicts = ["status", "priority"]
        merged = smart_merge_tasks(local_task, remote_task, conflicts)

        assert merged is not None
        assert merged.title == local_task.title
        assert merged.project == local_task.project
        assert merged.description == local_task.description

    def test_merge_with_empty_lists(self, base_task):
        """Test merge handles empty list fields."""
        task1 = base_task
        task2 = Task(
            id=base_task.id,
            title=base_task.title,
            status=base_task.status,
            priority=base_task.priority,
            project=base_task.project,
            assignees=[],  # Empty
            tags=["urgent"],
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=base_task.modified + timedelta(seconds=5),
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )
        conflicts = ["assignees", "tags"]
        merged = smart_merge_tasks(task1, task2, conflicts)

        assert merged is not None
        # Should use newer (task2) as base, but union lists
        assert set(merged.assignees) == {"@alice"}  # Union: task1's assignees
        assert set(merged.tags) == {"bug", "urgent"}  # Union of both

    def test_remote_completed_status_takes_priority(self, base_task):
        """Test that remote 'completed' status overrides local changes."""
        # Local task: newer, status=pending
        local = Task(
            id=base_task.id,
            title=base_task.title,
            status="pending",  # Local keeps it pending
            priority="H",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 25, 10, 0, 0),  # Newer
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        # Remote task: older, but status=completed
        remote = Task(
            id=base_task.id,
            title=base_task.title,
            status="completed",  # Remote completed it
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 24, 10, 0, 0),  # Older
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        conflicts = ["status", "priority"]
        merged = smart_merge_tasks(local, remote, conflicts)

        assert merged is not None
        # Remote status should win even though local is newer
        assert merged.status == "completed"
        # But other fields should use local (newer)
        assert merged.priority == "H"

    def test_remote_in_progress_status_takes_priority(self, base_task):
        """Test that remote 'in-progress' status overrides local changes."""
        # Local task: newer, status=pending
        local = Task(
            id=base_task.id,
            title=base_task.title,
            status="pending",
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 25, 10, 0, 0),  # Newer
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        # Remote task: older, but status=in-progress
        remote = Task(
            id=base_task.id,
            title=base_task.title,
            status="in-progress",
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 24, 10, 0, 0),  # Older
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        conflicts = ["status"]
        merged = smart_merge_tasks(local, remote, conflicts)

        assert merged is not None
        # Remote status should win
        assert merged.status == "in-progress"

    def test_remote_cancelled_status_takes_priority(self, base_task):
        """Test that remote 'cancelled' status overrides local changes."""
        # Local task: newer, status=in-progress
        local = Task(
            id=base_task.id,
            title=base_task.title,
            status="in-progress",
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 25, 10, 0, 0),  # Newer
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        # Remote task: older, but status=cancelled
        remote = Task(
            id=base_task.id,
            title=base_task.title,
            status="cancelled",
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 24, 10, 0, 0),  # Older
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        conflicts = ["status"]
        merged = smart_merge_tasks(local, remote, conflicts)

        assert merged is not None
        # Remote status should win
        assert merged.status == "cancelled"

    def test_remote_pending_status_does_not_override(self, base_task):
        """Test that remote 'pending' status does NOT override local changes."""
        # Local task: newer, status=in-progress
        local = Task(
            id=base_task.id,
            title=base_task.title,
            status="in-progress",
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 25, 10, 0, 0),  # Newer
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        # Remote task: older, status=pending (not a priority status)
        remote = Task(
            id=base_task.id,
            title=base_task.title,
            status="pending",
            priority="M",
            project=base_task.project,
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=datetime(2025, 10, 24, 10, 0, 0),  # Older
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )

        conflicts = ["status"]
        merged = smart_merge_tasks(local, remote, conflicts)

        assert merged is not None
        # Local status should win (normal timestamp-based merge)
        assert merged.status == "in-progress"


class TestConflictInfo:
    """Tests for ConflictInfo dataclass."""

    def test_conflict_info_creation(self, local_task, remote_task):
        """Test ConflictInfo can be created."""
        conflict = ConflictInfo(
            file_path=Path("tasks/task-001.md"),
            local_task=local_task,
            remote_task=remote_task,
            conflicting_fields=["status", "priority"],
            can_auto_merge=True,
        )

        assert conflict.file_path == Path("tasks/task-001.md")
        assert conflict.local_task == local_task
        assert conflict.remote_task == remote_task
        assert conflict.conflicting_fields == ["status", "priority"]
        assert conflict.can_auto_merge is True


class TestEdgeCases:
    """Tests for edge cases in merge logic."""

    def test_merge_with_none_values(self, base_task):
        """Test merge handles None values in optional fields."""
        task1 = base_task
        task2 = Task(
            id=base_task.id,
            title=base_task.title,
            status=base_task.status,
            priority=base_task.priority,
            project=None,  # None instead of value
            assignees=base_task.assignees.copy(),
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=None,  # None instead of value
            created=base_task.created,
            modified=base_task.modified + timedelta(seconds=5),
            depends=base_task.depends.copy(),
            parent=None,
            description=base_task.description,
            repo=base_task.repo,
        )
        conflicts = _find_conflicting_fields(task1, task2)
        assert "project" in conflicts
        assert "due" in conflicts

    def test_merge_with_identical_timestamps(self, base_task):
        """Test merge behavior with identical timestamps."""
        task1 = base_task
        task2 = Task(
            id=base_task.id,
            title=base_task.title,
            status="in-progress",
            priority=base_task.priority,
            project=base_task.project,
            assignees=["@alice", "@bob"],
            tags=base_task.tags.copy(),
            links=base_task.links.copy(),
            due=base_task.due,
            created=base_task.created,
            modified=base_task.modified,  # Identical timestamp
            depends=base_task.depends.copy(),
            parent=base_task.parent,
            description=base_task.description,
            repo=base_task.repo,
        )
        conflicts = ["status", "assignees"]
        # Should be able to merge:
        # - assignees is a list field (union)
        # - status uses semantic resolution (progress priority)
        can_merge = _can_auto_merge(task1, task2, conflicts)
        # With semantic merging, status can be auto-merged even with identical timestamp
        assert can_merge is True
