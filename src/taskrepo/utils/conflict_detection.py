"""Utilities for detecting and reporting merge conflicts in task files."""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def has_conflict_markers(file_path: Path) -> bool:
    """Check if a file contains git conflict markers.

    Args:
        file_path: Path to file to check

    Returns:
        True if conflict markers found, False otherwise
    """
    try:
        content = file_path.read_text()
        return "<<<<<<< HEAD" in content or "=======" in content and ">>>>>>>" in content
    except Exception:
        return False


def find_conflicted_tasks(repo_path: Path) -> list[Path]:
    """Find all task files with unresolved conflict markers.

    Args:
        repo_path: Path to repository root

    Returns:
        List of paths to conflicted task files
    """
    conflicted = []
    tasks_dir = repo_path / "tasks"

    if not tasks_dir.exists():
        return conflicted

    # Check main tasks directory
    for task_file in tasks_dir.glob("task-*.md"):
        if has_conflict_markers(task_file):
            conflicted.append(task_file)

    # Check archive directory
    archive_dir = tasks_dir / "archive"
    if archive_dir.exists():
        for task_file in archive_dir.glob("task-*.md"):
            if has_conflict_markers(task_file):
                conflicted.append(task_file)

    return conflicted


def scan_all_repositories(parent_dir: Path) -> dict[str, list[Path]]:
    """Scan all task repositories for conflicts.

    Args:
        parent_dir: Parent directory containing tasks-* repositories

    Returns:
        Dict mapping repository names to lists of conflicted file paths
    """
    conflicts = {}

    for repo_dir in parent_dir.glob("tasks-*"):
        if not repo_dir.is_dir():
            continue

        repo_name = repo_dir.name[6:]  # Remove 'tasks-' prefix
        conflicted_files = find_conflicted_tasks(repo_dir)

        if conflicted_files:
            conflicts[repo_name] = conflicted_files

    return conflicts


def display_conflict_warning(conflicts: dict[str, list[Path]], console: Console = None):
    """Display a warning about unresolved conflicts with actionable guidance.

    Args:
        conflicts: Dict mapping repository names to lists of conflicted file paths
        console: Rich console for output (creates new if None)
    """
    if not conflicts:
        return

    if console is None:
        console = Console()

    total_files = sum(len(files) for files in conflicts.values())

    # Create warning message
    warning_text = Text()
    warning_text.append("⚠️  Unresolved Merge Conflicts Detected\n\n", style="bold yellow")
    warning_text.append(f"Found {total_files} file(s) with git conflict markers:\n\n", style="yellow")

    for repo_name, files in conflicts.items():
        warning_text.append(f"  {repo_name}:\n", style="cyan bold")
        for file_path in files:
            warning_text.append(f"    • {file_path.name}\n", style="white")

    warning_text.append("\n💡 To resolve conflicts:\n", style="bold")
    warning_text.append("  1. Run: ", style="white")
    warning_text.append("tsk sync", style="green bold")
    warning_text.append(" (auto-resolves most conflicts)\n", style="white")
    warning_text.append("  2. Or manually edit the conflicted files\n", style="white")
    warning_text.append("  3. Or run: ", style="white")
    warning_text.append("git add <file> && git commit", style="green bold")
    warning_text.append(" in the repository\n", style="white")

    panel = Panel(
        warning_text,
        title="[bold red]Conflict Warning[/bold red]",
        border_style="red",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
    console.print()
