"""Utilities for detecting and reporting merge conflicts in task files."""

import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from taskrepo.core.task import Task


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


def scan_all_repositories(parent_dir: Path, auto_resolve: bool = True) -> dict[str, list[Path]]:
    """Scan all task repositories for conflicts and optionally auto-resolve them.

    Args:
        parent_dir: Parent directory containing tasks-* repositories
        auto_resolve: Whether to attempt automatic conflict resolution (default: True)

    Returns:
        Dict mapping repository names to lists of conflicted file paths that need manual resolution
    """
    conflicts = {}

    for repo_dir in parent_dir.glob("tasks-*"):
        if not repo_dir.is_dir():
            continue

        repo_name = repo_dir.name[6:]  # Remove 'tasks-' prefix
        conflicted_files = find_conflicted_tasks(repo_dir)

        if conflicted_files:
            # Try to auto-resolve if enabled
            if auto_resolve:
                unresolved_files = []
                for file_path in conflicted_files:
                    if not _try_auto_resolve_conflict(file_path):
                        # Couldn't auto-resolve, needs manual intervention
                        unresolved_files.append(file_path)

                # Only add to conflicts if there are still unresolved files
                if unresolved_files:
                    conflicts[repo_name] = unresolved_files
            else:
                # No auto-resolve, add all conflicted files
                conflicts[repo_name] = conflicted_files

    return conflicts


def _parse_conflicted_file(content: str, file_path: Path) -> tuple[Task | None, Task | None]:
    """Parse a file with git conflict markers into local and remote task objects.

    Args:
        content: File content with conflict markers
        file_path: Path to the file

    Returns:
        Tuple of (local_task, remote_task) or (None, None) if parsing fails
    """
    try:
        # Extract task ID from filename
        task_id = file_path.stem.replace("task-", "")
        repo_name = file_path.parent.parent.name.replace("tasks-", "")

        # Pattern to match conflict markers
        pattern = r"<<<<<<< HEAD\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>> [^\n]*"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            # Try alternative pattern
            pattern_alt = r"<<<<<<< HEAD(.*?)=======(.*?)>>>>>>> "
            match = re.search(pattern_alt, content, re.DOTALL)
            if not match:
                return None, None

        local_section = match.group(1).strip()
        remote_section = match.group(2).strip()

        # Get the parts before and after the conflict
        before_conflict = content[: match.start()]
        after_match = re.search(r">>>>>>> [^\n]*\n?", content[match.start() :])
        after_conflict = content[match.start() + after_match.end() :] if after_match else ""

        # Reconstruct full local and remote versions
        local_content = before_conflict + local_section + "\n" + after_conflict
        remote_content = before_conflict + remote_section + "\n" + after_conflict

        # Parse as Task objects
        local_task = Task.from_markdown(local_content, task_id=task_id, repo=repo_name)
        remote_task = Task.from_markdown(remote_content, task_id=task_id, repo=repo_name)

        return local_task, remote_task

    except Exception:
        return None, None


def _try_auto_resolve_conflict(file_path: Path) -> bool:
    """Try to automatically resolve a conflict using smart merge.

    Args:
        file_path: Path to conflicted task file

    Returns:
        True if successfully auto-resolved, False if manual intervention needed
    """
    try:
        content = file_path.read_text()

        # Parse the conflicted content
        local_task, remote_task = _parse_conflicted_file(content, file_path)

        if not local_task or not remote_task:
            # Can't parse - needs manual resolution
            return False

        # Use smart merge: prefer newer modified timestamp
        if local_task.modified >= remote_task.modified:
            resolved_task = local_task
        else:
            resolved_task = remote_task

        # Update modified timestamp
        resolved_task.modified = datetime.now()

        # Write resolved version
        resolved_content = resolved_task.to_markdown()
        file_path.write_text(resolved_content)

        # Verify conflict markers are gone
        verified_content = file_path.read_text()
        if "<<<<<<< HEAD" in verified_content:
            # Resolution failed - restore original and return False
            file_path.write_text(content)
            return False

        return True

    except Exception:
        return False


def _extract_title_from_conflicted_file(file_path: Path) -> str:
    """Try to extract task title from a file with conflict markers.

    Args:
        file_path: Path to conflicted task file

    Returns:
        Task title if found, or filename as fallback
    """
    try:
        content = file_path.read_text()
        # Try to find title in YAML frontmatter (look for "title:" line)
        # This works even with conflict markers since title is often the same in both versions
        for line in content.split("\n"):
            if line.startswith("title:"):
                title = line.replace("title:", "").strip().strip("'\"")
                if title and "<<<" not in title:  # Make sure we didn't get a conflict marker
                    return title
    except Exception:
        pass

    # Fallback: return filename
    return file_path.name


def display_conflict_warning(conflicts: dict[str, list[Path]], console: Console = None, auto_resolved: int = 0):
    """Display a warning about unresolved conflicts with actionable guidance.

    Args:
        conflicts: Dict mapping repository names to lists of conflicted file paths
        console: Rich console for output (creates new if None)
        auto_resolved: Number of conflicts that were automatically resolved (default: 0)
    """
    if console is None:
        console = Console()

    total_files = sum(len(files) for files in conflicts.values())

    # Create warning message
    warning_text = Text()

    if auto_resolved > 0:
        warning_text.append("✓ Auto-resolved ", style="green")
        warning_text.append(f"{auto_resolved} conflict(s)\n", style="green bold")
        warning_text.append("\n")

    if not conflicts:
        # All conflicts were auto-resolved!
        if auto_resolved > 0:
            warning_text.append("All conflicts were automatically resolved!\n", style="bold green")
            panel = Panel(
                warning_text,
                title="[bold green]Conflicts Resolved[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
            console.print()
            console.print(panel)
            console.print()
        return

    warning_text.append("⚠️  Unresolved Merge Conflicts Detected\n\n", style="bold yellow")
    warning_text.append(
        f"Found {total_files} file(s) with git conflict markers that need manual resolution:\n\n", style="yellow"
    )

    for repo_name, files in conflicts.items():
        warning_text.append(f"  {repo_name}:\n", style="cyan bold")
        for file_path in files:
            title = _extract_title_from_conflicted_file(file_path)
            warning_text.append(f"    • {title}\n", style="white")

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
