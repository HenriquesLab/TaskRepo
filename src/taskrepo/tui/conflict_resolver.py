"""Interactive conflict resolution UI for TaskRepo."""

import tempfile
from datetime import datetime
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.validation import ValidationError, Validator
from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from taskrepo.core.task import Task
from taskrepo.utils.merge import ConflictInfo


class ConflictChoiceValidator(Validator):
    """Validator for conflict resolution choice input."""

    def validate(self, document):
        """Validate that input is one of the allowed choices."""
        text = document.text.strip().upper()
        if text and text not in ("L", "R", "N", "M", "E"):
            raise ValidationError(
                message="Invalid choice. Please enter L, R, N, M, or E.",
                cursor_position=len(document.text),
            )


def resolve_conflict_interactive(conflict_info: ConflictInfo, editor: str = None) -> Task:
    """Interactively resolve a task merge conflict.

    Displays both versions side-by-side and prompts user to choose
    how to resolve the conflict.

    Args:
        conflict_info: Information about the conflict
        editor: Editor command to use for manual editing (optional)

    Returns:
        Resolved task

    Raises:
        KeyboardInterrupt: If user cancels resolution
    """
    import sys

    console = Console()

    local_task = conflict_info.local_task
    remote_task = conflict_info.remote_task

    # Check if stdin is available and interactive
    if not sys.stdin.isatty():
        # Non-interactive mode - use newer version as fallback
        console.print("[yellow]⚠ Non-interactive terminal detected, using newer version[/yellow]")
        if local_task.modified >= remote_task.modified:
            resolved = local_task
        else:
            resolved = remote_task
        resolved.modified = datetime.now()
        return resolved

    # Display conflict header
    console.print()
    console.print(f"[bold red]Conflict in:[/bold red] {conflict_info.file_path}")
    console.print(f"[bold]Task:[/bold] {escape(local_task.title)}")
    console.print()

    # Display both versions side-by-side
    _display_conflict_comparison(console, local_task, remote_task, conflict_info.conflicting_fields)

    # Prompt for resolution strategy
    console.print()
    console.print("[bold]Choose resolution strategy:[/bold]")
    console.print("  [cyan][L][/cyan] Keep local version")
    console.print("  [cyan][R][/cyan] Keep remote version")
    console.print("  [cyan][N][/cyan] Keep newer (based on modified timestamp)")
    console.print("  [cyan][M][/cyan] Manual merge (field by field)")
    console.print("  [cyan][E][/cyan] Edit manually in text editor")
    console.print()

    while True:
        try:
            choice = (
                prompt(
                    HTML("<cyan>Choose [L/R/N/M/E]</cyan> > "),
                    default="N",
                    validator=ConflictChoiceValidator(),
                    validate_while_typing=False,
                )
                .strip()
                .upper()
            )

            if choice == "L":
                console.print("[green]✓ Using local version[/green]")
                resolved = local_task
                resolved.modified = datetime.now()
                return resolved

            elif choice == "R":
                console.print("[green]✓ Using remote version[/green]")
                resolved = remote_task
                resolved.modified = datetime.now()
                return resolved

            elif choice == "N":
                # Use task with newer modified timestamp
                if local_task.modified >= remote_task.modified:
                    console.print(f"[green]✓ Using local (newer: {local_task.modified})[/green]")
                    resolved = local_task
                else:
                    console.print(f"[green]✓ Using remote (newer: {remote_task.modified})[/green]")
                    resolved = remote_task
                resolved.modified = datetime.now()
                return resolved

            elif choice == "M":
                console.print("[cyan]Starting manual merge...[/cyan]")
                return _manual_merge_fields(console, local_task, remote_task, conflict_info.conflicting_fields)

            elif choice == "E":
                console.print("[cyan]Opening editor...[/cyan]")
                return _edit_in_editor(local_task, remote_task, editor)

            else:
                console.print("[yellow]Invalid choice. Please enter L, R, N, M, or E.[/yellow]")

        except (KeyboardInterrupt, EOFError) as e:
            console.print("\n[red]✗ Resolution cancelled[/red]")
            raise KeyboardInterrupt("User cancelled conflict resolution") from e
        except (IOError, OSError) as e:
            # Handle stdin/terminal errors (like [Errno 22] Invalid argument)
            console.print(f"\n[red]✗ Error: {e}[/red]")
            console.print("[yellow]Falling back to newer version[/yellow]")
            if local_task.modified >= remote_task.modified:
                resolved = local_task
            else:
                resolved = remote_task
            resolved.modified = datetime.now()
            return resolved


def _display_conflict_comparison(console: Console, local_task: Task, remote_task: Task, conflicting_fields: list[str]):
    """Display side-by-side comparison of conflicting tasks.

    Args:
        console: Rich console for output
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of fields that conflict
    """
    # Create comparison tables
    local_table = Table(show_header=False, box=None, padding=(0, 1))
    local_table.add_column("Field", style="dim")
    local_table.add_column("Value")

    remote_table = Table(show_header=False, box=None, padding=(0, 1))
    remote_table.add_column("Field", style="dim")
    remote_table.add_column("Value")

    # Fields to display
    fields = [
        ("status", lambda t: t.status),
        ("priority", lambda t: t.priority),
        ("project", lambda t: t.project or "(none)"),
        ("assignees", lambda t: ", ".join(t.assignees) if t.assignees else "(none)"),
        ("tags", lambda t: ", ".join(t.tags) if t.tags else "(none)"),
        ("due", lambda t: t.due.strftime("%Y-%m-%d") if t.due else "(none)"),
        ("modified", lambda t: t.modified.strftime("%Y-%m-%d %H:%M")),
    ]

    # Add rows for each field
    for field_name, getter in fields:
        local_val = getter(local_task)
        remote_val = getter(remote_task)

        # Highlight conflicting fields
        if field_name in conflicting_fields:
            local_style = "bold yellow"
            remote_style = "bold yellow"
            conflict_marker = " ← CONFLICT"
        else:
            local_style = None
            remote_style = None
            conflict_marker = ""

        # Escape values to prevent Rich markup interpretation
        local_val_escaped = escape(str(local_val))
        remote_val_escaped = escape(str(remote_val))

        if local_style:
            local_table.add_row(field_name, f"[{local_style}]{local_val_escaped}[/{local_style}]{conflict_marker}")
        else:
            local_table.add_row(field_name, f"{local_val_escaped}{conflict_marker}")

        if remote_style:
            remote_table.add_row(field_name, f"[{remote_style}]{remote_val_escaped}[/{remote_style}]{conflict_marker}")
        else:
            remote_table.add_row(field_name, f"{remote_val_escaped}{conflict_marker}")

    # Create panels
    local_panel = Panel(
        local_table,
        title=f"[bold cyan]LOCAL[/bold cyan] (modified: {local_task.modified.strftime('%Y-%m-%d %H:%M')})",
        border_style="cyan",
    )

    remote_panel = Panel(
        remote_table,
        title=f"[bold magenta]REMOTE[/bold magenta] (modified: {remote_task.modified.strftime('%Y-%m-%d %H:%M')})",
        border_style="magenta",
    )

    # Display side-by-side
    console.print(Columns([local_panel, remote_panel]))

    # Show description diff if it conflicts
    if "description" in conflicting_fields:
        console.print()
        console.print("[bold yellow]Description differs:[/bold yellow]")
        console.print()
        console.print("[cyan]LOCAL:[/cyan]")
        local_desc = (
            local_task.description[:200] + "..." if len(local_task.description) > 200 else local_task.description
        )
        console.print(
            Panel(
                escape(local_desc),
                border_style="cyan",
            )
        )
        console.print()
        console.print("[magenta]REMOTE:[/magenta]")
        remote_desc = (
            remote_task.description[:200] + "..." if len(remote_task.description) > 200 else remote_task.description
        )
        console.print(
            Panel(
                escape(remote_desc),
                border_style="magenta",
            )
        )


def _manual_merge_fields(console: Console, local_task: Task, remote_task: Task, conflicting_fields: list[str]) -> Task:
    """Manually merge conflicting fields one by one.

    Args:
        console: Rich console for output
        local_task: Local task version
        remote_task: Remote task version
        conflicting_fields: List of fields that conflict

    Returns:
        Manually merged task
    """
    console.print()
    console.print("[bold]Resolving conflicts field by field...[/bold]")
    console.print("[dim]For each field, choose: [L]ocal, [R]emote, or [B]oth (for lists)[/dim]")
    console.print()

    # Start with local task as base
    merged = Task(
        id=local_task.id,
        title=local_task.title,
        status=local_task.status,
        priority=local_task.priority,
        project=local_task.project,
        assignees=local_task.assignees.copy(),
        tags=local_task.tags.copy(),
        links=local_task.links.copy(),
        due=local_task.due,
        created=local_task.created,
        modified=datetime.now(),
        depends=local_task.depends.copy(),
        parent=local_task.parent,
        description=local_task.description,
        repo=local_task.repo,
    )

    # Resolve each conflicting field
    for field in conflicting_fields:
        local_val = getattr(local_task, field)
        remote_val = getattr(remote_task, field)

        # Format values for display
        if isinstance(local_val, list):
            local_str = ", ".join(local_val) if local_val else "(empty)"
            remote_str = ", ".join(remote_val) if remote_val else "(empty)"
            show_both = True
        elif isinstance(local_val, datetime):
            local_str = local_val.strftime("%Y-%m-%d %H:%M") if local_val else "(none)"
            remote_str = remote_val.strftime("%Y-%m-%d %H:%M") if remote_val else "(none)"
            show_both = False
        else:
            local_str = str(local_val) if local_val else "(none)"
            remote_str = str(remote_val) if remote_val else "(none)"
            show_both = False

        console.print(f"[bold]{field}:[/bold]")
        console.print(f"  [cyan]L[/cyan] Local:  {local_str}")
        console.print(f"  [magenta]R[/magenta] Remote: {remote_str}")
        if show_both:
            console.print("  [yellow]B[/yellow] Both (union)")

        while True:
            try:
                options = "L/R/B" if show_both else "L/R"
                choice = prompt(HTML(f"<cyan>Choose [{options}]</cyan> > "), default="L").strip().upper()

                if choice == "L":
                    # Keep local value (already set)
                    break
                elif choice == "R":
                    setattr(merged, field, remote_val)
                    break
                elif choice == "B" and show_both:
                    # Union of both lists
                    merged_list = sorted(set(local_val) | set(remote_val))
                    setattr(merged, field, merged_list)
                    break
                else:
                    console.print(f"[yellow]Invalid choice. Please enter {options}.[/yellow]")
            except (KeyboardInterrupt, EOFError) as e:
                console.print("\n[red]✗ Resolution cancelled[/red]")
                raise KeyboardInterrupt("User cancelled conflict resolution") from e
            except (IOError, OSError) as e:
                # Handle stdin/terminal errors
                console.print(f"\n[red]✗ Error: {e}[/red]")
                console.print("[yellow]Using local value as fallback[/yellow]")
                break  # Keep local value (already set)

        console.print()

    console.print("[green]✓ Manual merge completed[/green]")
    return merged


def _edit_in_editor(local_task: Task, remote_task: Task, editor: str = None) -> Task:
    """Open both versions in text editor for manual editing.

    Args:
        local_task: Local task version
        remote_task: Remote task version
        editor: Editor command (uses $EDITOR if not specified)

    Returns:
        Edited task

    Raises:
        ValueError: If editor fails or result cannot be parsed
    """
    import os
    import subprocess

    editor = editor or os.environ.get("EDITOR", "nano")

    # Create temp file with both versions
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        temp_path = f.name
        f.write("# CONFLICT: Edit below and save. Lines starting with # will be ignored.\n")
        f.write(f"# Task: [{local_task.id}] {local_task.title}\n")
        f.write("#\n")
        f.write("# LOCAL VERSION (modified: {}):\n".format(local_task.modified.strftime("%Y-%m-%d %H:%M")))
        f.write("#\n")
        f.write(local_task.to_markdown())
        f.write("\n\n")
        f.write("# REMOTE VERSION (modified: {}):\n".format(remote_task.modified.strftime("%Y-%m-%d %H:%M")))
        f.write("#\n")
        f.write(remote_task.to_markdown())

    try:
        # Open editor
        subprocess.run([editor, temp_path], check=True)

        # Read edited content
        with open(temp_path, "r", encoding="utf-8") as f:
            edited_content = f.read()

        # Remove comment lines
        lines = [line for line in edited_content.split("\n") if not line.startswith("#")]
        cleaned_content = "\n".join(lines).strip()

        # Parse as task
        if not cleaned_content:
            raise ValueError("No content after editing")

        edited_task = Task.from_markdown(cleaned_content, task_id=local_task.id, repo=local_task.repo)
        edited_task.modified = datetime.now()

        return edited_task

    finally:
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)
