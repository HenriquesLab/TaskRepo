"""Tests for TUI shortcuts remapping and clipboard copy behavior."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from taskrepo.core.config import Config
from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.tui.task_tui import TaskTUI


@pytest.fixture
def tui_instance():
    temp = tempfile.mkdtemp()
    temp_dir = Path(temp)
    config_file = temp_dir / "config"
    config = Config(config_path=config_file)
    config.parent_dir = temp_dir
    config.save()

    manager = RepositoryManager(temp_dir)
    repo = manager.create_repository("test-repo")
    task = Task(id=repo.next_task_id(), title="Test Task One", status="pending")
    repo.save_task(task)

    repositories = manager.discover_repositories()
    tui = TaskTUI(config, repositories)
    return tui, task


def _get_binding_handler(tui, key_tuple):
    for binding in tui.kb.bindings:
        if binding.keys == key_tuple:
            return binding.handler
    return None


def test_tui_keybindings_c_x_l(tui_instance):
    tui, _ = tui_instance
    keys = [b.keys for b in tui.kb.bindings]
    assert ("c",) in keys
    assert ("x",) in keys
    assert ("l",) in keys


def test_tui_x_shortcut_triggers_cancelled(tui_instance):
    tui, _ = tui_instance
    handler = _get_binding_handler(tui, ("x",))
    assert handler is not None, "Shortcut 'x' must be registered"

    event = MagicMock()
    handler(event)
    event.app.exit.assert_called_once_with(result="cancelled")


def test_tui_c_shortcut_copies_link_without_exiting(tui_instance):
    tui, task = tui_instance
    handler = _get_binding_handler(tui, ("c",))
    assert handler is not None, "Shortcut 'c' must be registered"

    event = MagicMock()
    with patch("taskrepo.tui.task_tui.copy_to_clipboard", return_value=True) as mock_copy:
        handler(event)

        assert mock_copy.called
        copied_text = mock_copy.call_args[0][0]
        assert f"Test Task One](task-{task.id})" in copied_text
        event.app.exit.assert_not_called()
        assert tui.sync_message is not None
        assert "Copied" in tui.sync_message


def test_tui_shortcuts_help_text(tui_instance):
    tui, _ = tui_instance
    shortcuts_text = tui._get_shortcuts_text(160, allow_multiline=True)
    assert "cancel[x]" in shortcuts_text or "[x]cancel" in shortcuts_text
    assert "[c]opy" in shortcuts_text
    assert "[c]ancelled" not in shortcuts_text


def test_tui_status_info_displays_sync_message(tui_instance):
    tui, _ = tui_instance
    tui._set_sync_message("✓ Copied 1 task link to clipboard")
    status_info = tui._build_status_info()
    assert "Copied 1 task link to clipboard" in status_info
    assert "green" in status_info
