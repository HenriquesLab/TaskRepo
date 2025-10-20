"""Interactive TUI prompts using prompt_toolkit."""

from datetime import datetime
from typing import Optional

from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter, WordCompleter
from prompt_toolkit.validation import ValidationError, Validator

from taskrepo.core.repository import Repository


class PriorityValidator(Validator):
    """Validator for task priority."""

    def validate(self, document):
        text = document.text.upper()
        if text and text not in {"H", "M", "L"}:
            raise ValidationError(message="Priority must be H, M, or L")


class DateValidator(Validator):
    """Validator for date input."""

    def validate(self, document):
        text = document.text.strip()
        if not text:
            return  # Optional field

        try:
            from dateutil import parser as date_parser

            date_parser.parse(text)
        except Exception:
            raise ValidationError(message="Invalid date format. Use YYYY-MM-DD or natural language")


def prompt_repository(repositories: list[Repository]) -> Optional[Repository]:
    """Prompt user to select a repository.

    Args:
        repositories: List of available repositories

    Returns:
        Selected Repository or None if cancelled
    """
    if not repositories:
        print("No repositories found. Create one first with: taskrepo create-repo <name>")
        return None

    repo_names = [repo.name for repo in repositories]
    completer = WordCompleter(repo_names, ignore_case=True)

    try:
        repo_name = prompt(
            "Repository: ",
            completer=completer,
            complete_while_typing=True,
            default=repo_names[0] if repo_names else "",
        )
    except (KeyboardInterrupt, EOFError):
        return None

    # Find the selected repository
    for repo in repositories:
        if repo.name == repo_name:
            return repo

    return None


def prompt_title() -> Optional[str]:
    """Prompt user for task title.

    Returns:
        Task title or None if cancelled
    """

    class TitleValidator(Validator):
        def validate(self, document):
            if not document.text.strip():
                raise ValidationError(message="Title cannot be empty")

    try:
        title = prompt("Title: ", validator=TitleValidator())
        return title.strip()
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_project(existing_projects: list[str]) -> Optional[str]:
    """Prompt user for project name with autocomplete.

    Args:
        existing_projects: List of existing project names

    Returns:
        Project name or None
    """
    completer = FuzzyWordCompleter(existing_projects) if existing_projects else None

    try:
        project = prompt(
            "Project (optional): ",
            completer=completer,
            complete_while_typing=True,
        )
        return project.strip() or None
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_assignees(existing_assignees: list[str]) -> list[str]:
    """Prompt user for assignees (comma-separated GitHub handles).

    Args:
        existing_assignees: List of existing assignee handles

    Returns:
        List of assignee handles
    """
    completer = FuzzyWordCompleter(existing_assignees) if existing_assignees else None

    try:
        assignees_str = prompt(
            "Assignees (comma-separated, e.g., @user1,@user2): ",
            completer=completer,
            complete_while_typing=True,
        )

        if not assignees_str.strip():
            return []

        # Parse and normalize assignees
        assignees = []
        for assignee in assignees_str.split(","):
            assignee = assignee.strip()
            if assignee:
                # Add @ prefix if missing
                if not assignee.startswith("@"):
                    assignee = f"@{assignee}"
                assignees.append(assignee)

        return assignees
    except (KeyboardInterrupt, EOFError):
        return []


def prompt_priority(default: str = "M") -> str:
    """Prompt user for task priority.

    Args:
        default: Default priority

    Returns:
        Priority (H, M, or L)
    """
    try:
        priority = prompt(
            "Priority [H/M/L]: ",
            validator=PriorityValidator(),
            default=default,
        )
        return priority.upper()
    except (KeyboardInterrupt, EOFError):
        return default


def prompt_tags(existing_tags: list[str]) -> list[str]:
    """Prompt user for tags (comma-separated).

    Args:
        existing_tags: List of existing tags

    Returns:
        List of tags
    """
    completer = FuzzyWordCompleter(existing_tags) if existing_tags else None

    try:
        tags_str = prompt(
            "Tags (comma-separated): ",
            completer=completer,
            complete_while_typing=True,
        )

        if not tags_str.strip():
            return []

        # Parse tags
        tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        return tags
    except (KeyboardInterrupt, EOFError):
        return []


def prompt_due_date() -> Optional[datetime]:
    """Prompt user for due date.

    Returns:
        Due date or None
    """
    try:
        due_str = prompt(
            "Due date (optional, e.g., 2025-12-31 or 'next friday'): ",
            validator=DateValidator(),
        )

        if not due_str.strip():
            return None

        from dateutil import parser as date_parser

        return date_parser.parse(due_str)
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_description() -> str:
    """Prompt user for task description.

    Returns:
        Task description
    """
    print("\nDescription (press Ctrl+D or Ctrl+Z when done):")
    try:
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)
    except KeyboardInterrupt:
        return ""


def prompt_status(default: str = "pending") -> str:
    """Prompt user for task status.

    Args:
        default: Default status

    Returns:
        Task status
    """
    statuses = ["pending", "in_progress", "completed", "cancelled"]
    completer = WordCompleter(statuses, ignore_case=True)

    try:
        status = prompt(
            "Status: ",
            completer=completer,
            complete_while_typing=True,
            default=default,
        )
        return status.strip()
    except (KeyboardInterrupt, EOFError):
        return default
