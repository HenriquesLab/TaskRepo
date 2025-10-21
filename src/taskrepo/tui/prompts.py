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
            import dateparser

            result = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
            if result is None:
                raise ValueError("Could not parse date")
        except Exception as e:
            raise ValidationError(
                message="Invalid date format. Use YYYY-MM-DD or natural language like 'next friday'"
            ) from e


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

    # If only one repository, auto-select it
    if len(repositories) == 1:
        print(f"Repository: {repositories[0].name}")
        return repositories[0]

    # Display numbered list of repositories
    print("\nAvailable repositories:")
    for idx, repo in enumerate(repositories, start=1):
        print(f"  {idx}. {repo.name}")
    print()

    # Validator for numeric choice
    class ChoiceValidator(Validator):
        def validate(self, document):
            text = document.text.strip()
            if not text:
                raise ValidationError(message="Please enter a number")
            try:
                choice = int(text)
                if choice < 1 or choice > len(repositories):
                    raise ValidationError(message=f"Please enter a number between 1 and {len(repositories)}")
            except ValueError as e:
                raise ValidationError(message="Please enter a valid number") from e

    try:
        choice_str = prompt(
            f"Select repository [1-{len(repositories)}]: ",
            validator=ChoiceValidator(),
        )
        choice = int(choice_str.strip())
        return repositories[choice - 1]
    except (KeyboardInterrupt, EOFError):
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
    priorities = [
        ("H", "High"),
        ("M", "Medium"),
        ("L", "Low"),
    ]

    # Display numbered list of priorities
    print("\nPriority:")
    for idx, (code, name) in enumerate(priorities, start=1):
        marker = " (default)" if code == default else ""
        print(f"  {idx}. {name} [{code}]{marker}")
    print()

    # Validator for numeric choice
    class PriorityChoiceValidator(Validator):
        def validate(self, document):
            text = document.text.strip()
            if not text:
                # Allow empty for default
                return
            try:
                choice = int(text)
                if choice < 1 or choice > len(priorities):
                    raise ValidationError(message=f"Please enter a number between 1 and {len(priorities)}")
            except ValueError as e:
                raise ValidationError(message="Please enter a valid number") from e

    try:
        choice_str = prompt(
            f"Select priority [1-{len(priorities)}] or press Enter for default: ",
            validator=PriorityChoiceValidator(),
            default="",
        )

        if not choice_str.strip():
            return default

        choice = int(choice_str.strip())
        return priorities[choice - 1][0]
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

        import dateparser

        return dateparser.parse(due_str, settings={"PREFER_DATES_FROM": "future"})
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


def prompt_repo_name() -> Optional[str]:
    """Prompt user for repository name.

    Returns:
        Repository name or None if cancelled
    """

    class RepoNameValidator(Validator):
        def validate(self, document):
            text = document.text.strip()
            if not text:
                raise ValidationError(message="Repository name cannot be empty")
            # Check for invalid characters
            if not text.replace("-", "").replace("_", "").isalnum():
                raise ValidationError(
                    message="Repository name can only contain letters, numbers, hyphens, and underscores"
                )

    try:
        name = prompt("Repository name: ", validator=RepoNameValidator())
        return name.strip()
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_github_enabled() -> bool:
    """Prompt user whether to create GitHub repository.

    Returns:
        True if GitHub should be enabled, False otherwise
    """
    try:
        response = prompt("Create GitHub repository? [y/N]: ", default="N")
        return response.strip().lower() in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        return False


def prompt_github_org(default: Optional[str] = None) -> Optional[str]:
    """Prompt user for GitHub organization/owner.

    Args:
        default: Default organization/owner to suggest

    Returns:
        Organization/owner name or None if cancelled
    """

    class OrgValidator(Validator):
        def validate(self, document):
            if not document.text.strip():
                raise ValidationError(message="Organization/owner cannot be empty")

    try:
        prompt_text = "GitHub organization/owner"
        if default:
            prompt_text += f" [{default}]"
        prompt_text += ": "

        org = prompt(prompt_text, validator=OrgValidator(), default=default or "")
        return org.strip() if org.strip() else (default if default else None)
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_visibility() -> str:
    """Prompt user for repository visibility.

    Returns:
        Visibility setting ('public' or 'private')
    """
    visibilities = ["public", "private"]
    completer = WordCompleter(visibilities, ignore_case=True)

    try:
        visibility = prompt(
            "Repository visibility [private]: ",
            completer=completer,
            complete_while_typing=True,
            default="private",
        )
        return visibility.strip().lower()
    except (KeyboardInterrupt, EOFError):
        return "private"
