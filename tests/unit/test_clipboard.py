"""Tests for clipboard utilities and task markdown link formatting."""

from unittest.mock import MagicMock, patch

from taskrepo.core.task import Task
from taskrepo.utils.clipboard import (
    copy_to_clipboard,
    format_task_markdown_link,
    format_tasks_for_clipboard,
)


def test_format_task_markdown_link_with_numeric_display_id():
    task = Task(id="a1b2c3d4-1111-2222-3333-444455556666", title="Buy groceries")
    link = format_task_markdown_link(task, display_id=1)
    assert link == "[001 - Buy groceries](task-a1b2c3d4-1111-2222-3333-444455556666)"


def test_format_task_markdown_link_without_display_id():
    task = Task(id="a1b2c3d4-1111-2222-3333-444455556666", title="Fix parser bug")
    link = format_task_markdown_link(task, display_id=None)
    assert link == "[a1b2c3d4... - Fix parser bug](task-a1b2c3d4-1111-2222-3333-444455556666)"


def test_format_tasks_for_clipboard_multiple():
    t1 = Task(id="uuid-1", title="Task One")
    t2 = Task(id="uuid-2", title="Task Two")
    id_map = {"uuid-1": 1, "uuid-2": 2}
    result = format_tasks_for_clipboard([t1, t2], get_display_id=lambda tid: id_map.get(tid))
    assert result == "[001 - Task One](task-uuid-1)\n[002 - Task Two](task-uuid-2)"


@patch("sys.platform", "darwin")
@patch("subprocess.run")
def test_copy_to_clipboard_macos(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    success = copy_to_clipboard("test text")
    assert success is True
    mock_run.assert_called_once_with(["pbcopy"], input=b"test text", check=True)


@patch("sys.platform", "linux")
@patch("shutil.which")
@patch("subprocess.run")
def test_copy_to_clipboard_linux_wl_copy(mock_run, mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/wl-copy" if cmd == "wl-copy" else None
    mock_run.return_value = MagicMock(returncode=0)
    success = copy_to_clipboard("test text")
    assert success is True
    mock_run.assert_called_once_with(["wl-copy"], input=b"test text", check=True)


@patch("subprocess.run", side_effect=FileNotFoundError)
def test_copy_to_clipboard_command_not_found(mock_run):
    success = copy_to_clipboard("test text")
    assert success is False
