"""Tests for TUI prompt functions."""

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from taskrepo.tui.prompts import prompt_repo_name


def test_prompt_repo_name_accepts_new_name():
    """Test that prompt_repo_name accepts a new repository name."""
    with create_pipe_input() as inp:
        inp.send_text("NewRepo\n")

        result = prompt_repo_name(
            existing_names=["TaskRepo", "other"],
            input=inp,
            output=DummyOutput(),
        )

        assert result == "NewRepo"


def test_prompt_repo_name_rejects_duplicate():
    """Test that prompt_repo_name rejects duplicate repository names."""
    with create_pipe_input() as inp:
        # First try duplicate, then provide a new name
        inp.send_text("TaskRepo\nNewRepo\n")

        # This should reject "TaskRepo" and accept "NewRepo"
        result = prompt_repo_name(
            existing_names=["TaskRepo", "other"],
            input=inp,
            output=DummyOutput(),
        )

        # If validation works, it should return NewRepo after rejecting TaskRepo
        assert result == "NewRepo"


def test_prompt_repo_name_rejects_invalid_characters():
    """Test that prompt_repo_name rejects names with invalid characters."""
    with create_pipe_input() as inp:
        # Try invalid name first, then valid name
        inp.send_text("invalid@name\nvalid-name\n")

        result = prompt_repo_name(
            existing_names=[],
            input=inp,
            output=DummyOutput(),
        )

        assert result == "valid-name"


def test_prompt_repo_name_rejects_empty():
    """Test that prompt_repo_name rejects empty names."""
    with create_pipe_input() as inp:
        # Try empty, then valid
        inp.send_text("\nValidName\n")

        result = prompt_repo_name(
            existing_names=[],
            input=inp,
            output=DummyOutput(),
        )

        assert result == "ValidName"


def test_prompt_repo_name_accepts_hyphens_underscores():
    """Test that prompt_repo_name accepts names with hyphens and underscores."""
    with create_pipe_input() as inp:
        inp.send_text("valid-name_123\n")

        result = prompt_repo_name(
            existing_names=[],
            input=inp,
            output=DummyOutput(),
        )

        assert result == "valid-name_123"


def test_prompt_repo_name_no_existing_names():
    """Test that prompt_repo_name works when no existing names provided."""
    with create_pipe_input() as inp:
        inp.send_text("MyRepo\n")

        result = prompt_repo_name(
            input=inp,
            output=DummyOutput(),
        )  # No existing_names parameter

        assert result == "MyRepo"


def test_prompt_repo_name_case_sensitive():
    """Test that repository name comparison is case-sensitive."""
    with create_pipe_input() as inp:
        inp.send_text("taskrepo\n")  # lowercase

        # Should accept since existing is "TaskRepo" (different case)
        result = prompt_repo_name(
            existing_names=["TaskRepo"],
            input=inp,
            output=DummyOutput(),
        )

        assert result == "taskrepo"


def test_prompt_visibility_returns_default_on_empty():
    """Test that prompt_visibility returns default when Enter is pressed."""
    from taskrepo.tui.prompts import prompt_visibility

    with create_pipe_input() as inp:
        # Send just Enter (empty input)
        inp.send_text("\n")

        # Should return default "private"
        result = prompt_visibility(input=inp, output=DummyOutput())

        assert result == "private"


def test_prompt_visibility_returns_public():
    """Test that prompt_visibility returns public when 2 is entered."""
    from taskrepo.tui.prompts import prompt_visibility

    with create_pipe_input() as inp:
        inp.send_text("2\n")

        result = prompt_visibility(input=inp, output=DummyOutput())

        assert result == "public"
