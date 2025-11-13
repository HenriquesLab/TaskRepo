"""Interactive TUI prompts using prompt_toolkit."""

from datetime import datetime
from typing import Optional

from prompt_toolkit import prompt
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import Completer, Completion, FuzzyWordCompleter, WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.validation import ValidationError, Validator

from taskrepo.core.repository import Repository


class CommaDelimitedCompleter(Completer):
    """Completer for comma-separated values.

    Provides fuzzy completion for each value after a comma, allowing
    autocomplete to work for multiple comma-separated items.
    """

    def __init__(self, values: list[str]):
        """Initialize with list of possible values.

        Args:
            values: List of possible completion values
        """
        self.values = sorted(values) if values else []

    def get_completions(self, document: Document, complete_event):
        """Get completions for the current segment (after last comma).

        Args:
            document: The current document
            complete_event: The completion event

        Yields:
            Completion objects for matching values
        """
        # Get text before cursor
        text_before_cursor = document.text_before_cursor

        # Split by comma and get the last segment
        segments = text_before_cursor.split(",")
        current_segment = segments[-1].lstrip()  # Remove leading spaces

        # Calculate start position for replacement
        # We want to replace from where the current segment starts
        start_position = -len(segments[-1])

        # Fuzzy match current segment against values
        current_lower = current_segment.lower()

        for value in self.values:
            # Fuzzy matching: check if all characters appear in order
            if self._fuzzy_match(current_lower, value.lower()):
                # For segments after the first, add a leading space
                if len(segments) > 1:
                    replacement = f" {value}"
                else:
                    replacement = value

                yield Completion(
                    replacement,
                    start_position=start_position,
                    display=value,
                )

    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """Check if pattern fuzzy-matches text.

        All characters of pattern must appear in text in order
        (but not necessarily consecutively).

        Args:
            pattern: The pattern to match (lowercased)
            text: The text to search in (lowercased)

        Returns:
            True if pattern fuzzy-matches text
        """
        if not pattern:
            return True

        pattern_idx = 0
        for char in text:
            if char == pattern[pattern_idx]:
                pattern_idx += 1
                if pattern_idx == len(pattern):
                    return True

        return pattern_idx == len(pattern)


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


def prompt_repository(repositories: list[Repository], default: Optional[str] = None) -> Optional[Repository]:
    """Prompt user to select a repository.

    Args:
        repositories: List of available repositories
        default: Default repository name (without 'tasks-' prefix) to preselect

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

    # Sort alphabetically by name
    from taskrepo.core.repository import RepositoryManager

    repositories = RepositoryManager.sort_repositories_alphabetically(repositories)

    # Find the default repository's index (after sorting)
    default_index = None
    if default:
        for idx, repo in enumerate(repositories):
            if repo.name == default:
                default_index = idx
                break

    # Display numbered list of repositories
    print("\nAvailable repositories:")
    for idx, repo in enumerate(repositories, start=1):
        task_count = len(repo.list_tasks())
        marker = " (default)" if default and repo.name == default else ""
        print(f"  {idx}. {repo.name} ({task_count} tasks){marker}")
    print()

    # Validator for numeric choice
    class ChoiceValidator(Validator):
        def validate(self, document):
            text = document.text.strip()
            if not text:
                # Allow empty if there's a default
                if default_index is not None:
                    return
                raise ValidationError(message="Please enter a number")
            try:
                choice = int(text)
                if choice < 1 or choice > len(repositories):
                    raise ValidationError(message=f"Please enter a number between 1 and {len(repositories)}")
            except ValueError as e:
                raise ValidationError(message="Please enter a valid number") from e

    try:
        # If there's a default, show it in the prompt and allow pressing Enter
        if default_index is not None:
            choice_str = prompt(
                f"Select repository [1-{len(repositories)}] or press Enter for default: ",
                validator=ChoiceValidator(),
                default="",
            )
            if not choice_str.strip():
                return repositories[default_index]
        else:
            choice_str = prompt(
                f"Select repository [1-{len(repositories)}]: ",
                validator=ChoiceValidator(),
            )

        choice = int(choice_str.strip())
        return repositories[choice - 1]
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_title(default: Optional[str] = None) -> Optional[str]:
    """Prompt user for task title.

    Args:
        default: Default title to pre-fill

    Returns:
        Task title or None if cancelled
    """

    class TitleValidator(Validator):
        def validate(self, document):
            if not document.text.strip():
                raise ValidationError(message="Title cannot be empty")

    try:
        title = prompt("Title: ", validator=TitleValidator(), default=default or "")
        return title.strip()
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_project(existing_projects: list[str], default: Optional[str] = None) -> Optional[str]:
    """Prompt user for project name with autocomplete.

    Args:
        existing_projects: List of existing project names
        default: Default project name to pre-fill

    Returns:
        Project name or None
    """
    completer = FuzzyWordCompleter(existing_projects) if existing_projects else None

    try:
        project = prompt(
            "Project (optional): ",
            completer=completer,
            complete_while_typing=True,
            default=default or "",
        )
        return project.strip() or None
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_assignees(existing_assignees: list[str], default: Optional[list[str]] = None) -> list[str]:
    """Prompt user for assignees (comma-separated GitHub handles).

    Args:
        existing_assignees: List of existing assignee handles
        default: Default list of assignees to pre-fill

    Returns:
        List of assignee handles
    """
    completer = CommaDelimitedCompleter(existing_assignees) if existing_assignees else None

    # Convert default list to comma-separated string
    default_str = ", ".join(default) if default else ""

    try:
        assignees_str = prompt(
            "Assignees (comma-separated, e.g., @user1,@user2): ",
            completer=completer,
            complete_while_typing=True,
            default=default_str,
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


def prompt_tags(existing_tags: list[str], default: Optional[list[str]] = None) -> list[str]:
    """Prompt user for tags (comma-separated).

    Args:
        existing_tags: List of existing tags
        default: Default list of tags to pre-fill

    Returns:
        List of tags
    """
    completer = CommaDelimitedCompleter(existing_tags) if existing_tags else None

    # Convert default list to comma-separated string
    default_str = ", ".join(default) if default else ""

    try:
        tags_str = prompt(
            "Tags (comma-separated): ",
            completer=completer,
            complete_while_typing=True,
            default=default_str,
        )

        if not tags_str.strip():
            return []

        # Parse tags
        tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        return tags
    except (KeyboardInterrupt, EOFError):
        return []


def prompt_links(default: Optional[list[str]] = None) -> list[str]:
    """Prompt user for associated links/URLs (comma-separated).

    Args:
        default: Default list of links to pre-fill

    Returns:
        List of validated URLs
    """
    from taskrepo.core.task import Task

    class LinksValidator(Validator):
        def validate(self, document):
            text = document.text.strip()
            if not text:
                return  # Optional field

            # Split by comma and validate each URL
            urls = [url.strip() for url in text.split(",") if url.strip()]
            for url in urls:
                if not Task.validate_url(url):
                    raise ValidationError(message=f"Invalid URL: {url}. URLs must start with http:// or https://")

    # Convert default list to comma-separated string
    default_str = ", ".join(default) if default else ""

    try:
        links_str = prompt(
            "Links (comma-separated URLs, optional): ",
            validator=LinksValidator(),
            default=default_str,
        )

        if not links_str.strip():
            return []

        # Parse and filter links
        links = [link.strip() for link in links_str.split(",") if link.strip()]
        return links
    except (KeyboardInterrupt, EOFError):
        return []


def prompt_due_date(default: Optional[datetime] = None) -> Optional[datetime]:
    """Prompt user for due date.

    Args:
        default: Default due date to pre-fill

    Returns:
        Due date or None
    """
    # Format default datetime to YYYY-MM-DD string
    default_str = default.strftime("%Y-%m-%d") if default else ""

    try:
        due_str = prompt(
            "Due date (optional, e.g., 2025-12-31 or 'next friday'): ",
            validator=DateValidator(),
            default=default_str,
        )

        if not due_str.strip():
            return None

        from datetime import datetime, timedelta

        from taskrepo.utils.date_parser import parse_date_or_duration

        # Parse the input - can be either a date or duration
        parsed_value, is_absolute_date = parse_date_or_duration(due_str.strip())

        if is_absolute_date:
            # Return the parsed datetime directly
            assert isinstance(parsed_value, datetime)
            return parsed_value
        else:
            # It's a duration (timedelta) - add to today at midnight
            assert isinstance(parsed_value, timedelta)
            now = datetime.now()
            today_midnight = datetime(now.year, now.month, now.day)
            return today_midnight + parsed_value

    except (KeyboardInterrupt, EOFError):
        return None


def prompt_parent(default: Optional[str] = None) -> Optional[str]:
    """Prompt user for parent task ID (for subtasks).

    Args:
        default: Default parent task ID to pre-fill

    Returns:
        Parent task ID or None
    """
    try:
        parent = prompt(
            "Parent task ID (optional, for subtasks): ",
            default=default or "",
        )
        return parent.strip() or None
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_depends(default: Optional[list[str]] = None) -> list[str]:
    """Prompt user for task dependencies (comma-separated task IDs).

    Args:
        default: Default list of dependencies to pre-fill

    Returns:
        List of task IDs
    """
    # Convert default list to comma-separated string
    default_str = ", ".join(default) if default else ""

    try:
        depends_str = prompt(
            "Dependencies (comma-separated task IDs, optional): ",
            default=default_str,
        )

        if not depends_str.strip():
            return []

        # Parse and filter dependencies
        depends = [dep.strip() for dep in depends_str.split(",") if dep.strip()]
        return depends
    except (KeyboardInterrupt, EOFError):
        return []


def prompt_description(default: str = "") -> str:
    """Prompt user for task description.

    Args:
        default: Default description to show and optionally keep

    Returns:
        Task description
    """
    # Show current description if it exists
    if default:
        print("\nCurrent description:")
        print("-" * 40)
        print(default)
        print("-" * 40)

        # Ask if they want to keep or replace
        try:
            choice = prompt("Keep current description? (y/n, default=y): ", default="y").strip().lower()
            if choice in ["y", "yes", ""]:
                return default
        except (KeyboardInterrupt, EOFError):
            return default

    print("\nEnter new description (press Ctrl+D or Ctrl+Z when done):")
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
        return default if default else ""


def prompt_status(default: str = "pending") -> str:
    """Prompt user for task status.

    Args:
        default: Default status

    Returns:
        Task status
    """
    statuses = ["pending", "in-progress", "completed", "cancelled"]
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


def get_repo_name_toolbar():
    """Get bottom toolbar text showing the full repository name with tasks- prefix.

    Returns:
        Formatted HTML text for the bottom toolbar
    """
    try:
        # Get the current application and buffer text
        app = get_app()
        current_text = app.current_buffer.text.strip()

        if current_text:
            return HTML(f"Will create: <b>tasks-{current_text}</b>")
        else:
            return HTML("Repository names are automatically prefixed with <b>tasks-</b>")
    except Exception:
        # Fallback if we can't access the app (e.g., during testing)
        return HTML("Repository names are automatically prefixed with <b>tasks-</b>")


def prompt_repo_name(
    existing_names: list[str] | None = None,
    input=None,
    output=None,
) -> Optional[str]:
    """Prompt user for repository name.

    Args:
        existing_names: List of existing repository names (without 'tasks-' prefix) to check for duplicates
        input: Input object for testing (optional)
        output: Output object for testing (optional)

    Returns:
        Repository name or None if cancelled
    """
    if existing_names is None:
        existing_names = []

    # Capture existing_names in closure by creating validator function
    class RepoNameValidator(Validator):
        def __init__(self, existing_repo_names):
            super().__init__()
            self.existing_repo_names = existing_repo_names

        def validate(self, document):
            text = document.text.strip()
            if not text:
                raise ValidationError(message="Repository name cannot be empty")
            # Check for invalid characters
            if not text.replace("-", "").replace("_", "").isalnum():
                raise ValidationError(
                    message="Repository name can only contain letters, numbers, hyphens, and underscores"
                )
            # Check if repository already exists
            if text in self.existing_repo_names:
                raise ValidationError(message=f"Repository 'tasks-{text}' already exists")

    validator = RepoNameValidator(existing_names)

    try:
        # For testing with pipe input, handle validation manually to avoid hanging
        if input is not None or output is not None:
            from prompt_toolkit.document import Document

            session = PromptSession(
                message="Repository name: ",
                input=input,
                output=output,
                bottom_toolbar=get_repo_name_toolbar,
            )

            while True:
                name = session.prompt()
                # Manually validate
                try:
                    validator.validate(Document(name))
                    return name.strip()
                except ValidationError:
                    # With pipe input, if validation fails, read next line
                    # If no more input, this will raise EOFError
                    continue
        else:
            # For normal interactive use, use built-in validation
            name = prompt(
                "Repository name: ",
                validator=validator,
                bottom_toolbar=get_repo_name_toolbar,
            )
            return name.strip()
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_github_enabled() -> bool:
    """Prompt user whether to create GitHub repository.

    Returns:
        True if GitHub should be enabled, False otherwise
    """

    class YesNoValidator(Validator):
        def validate(self, document):
            text = document.text.strip().lower()
            if text and text not in {"y", "yes", "n", "no"}:
                raise ValidationError(message="Please enter 'y' or 'n'")

    try:
        answer = prompt(
            "Create GitHub repository? [Y/n]: ",
            validator=YesNoValidator(),
            default="y",
        )
        return answer.strip().lower() in {"y", "yes"}
    except (KeyboardInterrupt, EOFError):
        return False


def prompt_github_org(default: Optional[str] = None, existing_orgs: list[str] | None = None) -> Optional[str]:
    """Prompt user for GitHub organization/owner.

    Args:
        default: Default organization/owner to suggest
        existing_orgs: List of existing organizations for autocomplete

    Returns:
        Organization/owner name or None if cancelled
    """
    if existing_orgs is None:
        existing_orgs = []

    class OrgValidator(Validator):
        def validate(self, document):
            if not document.text.strip():
                raise ValidationError(message="Organization/owner cannot be empty")

    completer = FuzzyWordCompleter(existing_orgs) if existing_orgs else None

    try:
        prompt_text = "GitHub organization/owner"
        if default:
            prompt_text += f" [{default}]"
        prompt_text += ": "

        org = prompt(
            prompt_text,
            validator=OrgValidator(),
            default=default or "",
            completer=completer,
            complete_while_typing=True,
        )
        return org.strip() if org.strip() else (default if default else None)
    except (KeyboardInterrupt, EOFError):
        return None


def prompt_visibility(input=None, output=None) -> str:
    """Prompt user for repository visibility.

    Args:
        input: Input object for testing (optional)
        output: Output object for testing (optional)

    Returns:
        Visibility setting ('public' or 'private')
    """
    visibilities = [
        ("private", "Private"),
        ("public", "Public"),
    ]
    default = "private"

    # Display numbered list of visibilities
    print("\nRepository visibility:")
    for idx, (code, name) in enumerate(visibilities, start=1):
        marker = " (default)" if code == default else ""
        print(f"  {idx}. {name}{marker}")
    print()

    # Validator for numeric choice
    class VisibilityChoiceValidator(Validator):
        def validate(self, document):
            text = document.text.strip()
            if not text:
                # Allow empty for default
                return
            try:
                choice = int(text)
                if choice < 1 or choice > len(visibilities):
                    raise ValidationError(message=f"Please enter a number between 1 and {len(visibilities)}")
            except ValueError as e:
                raise ValidationError(message="Please enter a valid number") from e

    try:
        # For testing with pipe input, use PromptSession
        if input is not None or output is not None:
            session = PromptSession(
                message=f"Select visibility [1-{len(visibilities)}] or press Enter for default: ",
                input=input,
                output=output,
            )
            choice_str = session.prompt(default="")
        else:
            # For normal interactive use, set default to "1" (private) for better UX
            # This ensures pressing Enter submits the form with the default value
            choice_str = prompt(
                f"Select visibility [1-{len(visibilities)}] or press Enter for default: ",
                validator=VisibilityChoiceValidator(),
                default="1",  # Default to option 1 (private)
            )

        if not choice_str.strip():
            return default

        choice = int(choice_str.strip())
        return visibilities[choice - 1][0]
    except (KeyboardInterrupt, EOFError):
        return default


def prompt_parent_task(existing_tasks: list) -> Optional[str]:
    """Prompt user for parent task (for creating subtasks).

    Args:
        existing_tasks: List of Task objects to choose from

    Returns:
        Parent task ID or None if no parent selected
    """
    if not existing_tasks:
        return None

    # Build completion list with display IDs and titles for easier selection
    from taskrepo.utils.id_mapping import get_display_id_from_uuid

    task_options = []
    task_map = {}

    for task in existing_tasks:
        # Try to get display ID for this task
        display_id = get_display_id_from_uuid(task.id)

        if display_id:
            # Format: "DisplayID: Title"
            display_text = f"{display_id}: {task.title}"
            task_options.append(display_text)
            task_map[display_text] = task.id
            # Also allow matching by just display ID
            task_map[str(display_id)] = task.id
        else:
            # Fallback to UUID if no display ID found
            display_text = f"{task.id}: {task.title}"
            task_options.append(display_text)
            task_map[display_text] = task.id

        # Also allow matching by UUID
        task_map[task.id] = task.id

    completer = FuzzyWordCompleter(task_options) if task_options else None

    try:
        parent_input = prompt(
            "Parent task (optional, leave empty for top-level task): ",
            completer=completer,
            complete_while_typing=True,
        )

        if not parent_input.strip():
            return None

        # Try to find task ID from input
        parent_input = parent_input.strip()

        # First, try to resolve display ID to UUID (e.g., "11" -> UUID)
        from taskrepo.utils.helpers import normalize_task_id

        normalized_id = normalize_task_id(parent_input)

        # Check if it matches a display text from completer
        if parent_input in task_map:
            return task_map[parent_input]

        # Check if normalized ID matches any task
        for task in existing_tasks:
            if task.id == normalized_id or task.id.startswith(normalized_id):
                return task.id

        # If no match found, return None
        return None

    except (KeyboardInterrupt, EOFError):
        return None


def confirm_single_key(message: str) -> bool:
    """Prompt for yes/no confirmation with single-key input (no Enter required).

    Args:
        message: The confirmation message to display

    Returns:
        True if user confirmed (pressed 'y'), False otherwise
    """
    from prompt_toolkit.application import Application
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    result = [False]  # Use list to allow modification in nested function

    kb = KeyBindings()

    @kb.add("y")
    @kb.add("Y")
    def yes(event):
        result[0] = True
        event.app.exit()

    @kb.add("n")
    @kb.add("N")
    @kb.add("escape")
    def no(event):
        result[0] = False
        event.app.exit()

    # Create a simple layout with the message
    layout = Layout(Window(content=FormattedTextControl(HTML(f"<b>{message}</b> (y/n): "))))

    # Create and run application
    app: Application[None] = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
    )

    app.run()
    return result[0]


def prompt_yes_no(message: str, default: str = "y") -> bool:
    """Reusable yes/no confirmation prompt.

    This function centralizes the common yes/no prompt pattern used throughout
    the CLI commands, providing consistent validation and user experience.

    Args:
        message: The question to ask the user (should not include "(y/n)")
        default: Default value - "y" for yes (default), "n" for no

    Returns:
        True if user answered yes, False if user answered no

    Example:
        >>> if prompt_yes_no("Delete this task?"):
        ...     delete_task()
        >>> if prompt_yes_no("Archive subtasks?", default="y"):
        ...     archive_subtasks()
    """
    # Create validator for y/n input
    yn_validator = Validator.from_callable(
        lambda text: text.lower() in ["y", "n", "yes", "no"],
        error_message="Please enter 'y' or 'n'",
        move_cursor_to_end=True,
    )

    # Add (Y/n) or (y/N) suffix based on default
    if default.lower() == "y":
        prompt_suffix = " (Y/n) "
    else:
        prompt_suffix = " (y/N) "

    # Get user response
    response = prompt(
        message + prompt_suffix,
        default=default,
        validator=yn_validator,
    ).lower()

    return response in ["y", "yes"]


def prompt_field_selection(task) -> Optional[str]:
    """Prompt user to select which task field to edit.

    Args:
        task: The Task object being edited

    Returns:
        Field name to edit ('title', 'status', 'priority', etc.), 'all', 'done', or None if cancelled
    """
    print("\n" + "=" * 60)
    print("Edit Task - Field Selection")
    print("=" * 60)
    print(f"\nTask: {task.title}")
    print("\nSelect field to edit:")
    print()

    # Show all fields with current values
    fields = {
        "1": ("title", f"Title: {task.title}"),
        "2": ("status", f"Status: {task.status}"),
        "3": ("priority", f"Priority: {task.priority}"),
        "4": ("project", f"Project: {task.project or '(none)'}"),
        "5": ("assignees", f"Assignees: {', '.join(task.assignees) if task.assignees else '(none)'}"),
        "6": ("tags", f"Tags: {', '.join(task.tags) if task.tags else '(none)'}"),
        "7": ("links", f"Links: {len(task.links)} link(s)"),
        "8": ("due", f"Due date: {task.due.strftime('%Y-%m-%d') if task.due else '(none)'}"),
        "9": ("parent", f"Parent: {task.parent or '(none)'}"),
        "10": ("depends", f"Dependencies: {len(task.depends)} task(s)"),
        "11": (
            "description",
            f"Description: {(task.description[:50] + '...') if len(task.description) > 50 else task.description if task.description else '(none)'}",
        ),
        "a": ("all", "Edit all fields"),
        "d": ("done", "Done editing"),
    }

    for key, (_field_name, display) in fields.items():
        if key.isdigit():
            print(f"  [{key}]  {display}")
        else:
            print()
            print(f"  [{key}]  {display}")

    print()

    try:
        choice = prompt("Choose field (1-11, a=all, d=done): ").strip().lower()

        if choice in fields:
            field_name, _ = fields[choice]
            return field_name
        else:
            print("Invalid choice. Please try again.")
            return prompt_field_selection(task)

    except (KeyboardInterrupt, EOFError):
        return None
