"""Clipboard utilities and markdown link formatting for TaskRepo."""

import shutil
import subprocess
import sys
from typing import Callable, Iterable, Optional

from taskrepo.core.task import Task


def format_task_markdown_link(task: Task, display_id: Optional[int | str] = None) -> str:
    """Format a task as a standard markdown link referencing its task ID.

    Format: [001 - Title](task-UUID)

    Args:
        task: Task instance
        display_id: Optional display ID (integer or string). If integer, zero-padded to 3 digits.

    Returns:
        Formatted markdown link string
    """
    if display_id is not None and str(display_id).isdigit():
        display_id_str = f"{int(display_id):03d}"
    elif display_id:
        display_id_str = str(display_id)
    else:
        display_id_str = f"{task.id[:8]}..."

    return f"[{display_id_str} - {task.title}](task-{task.id})"


def format_tasks_for_clipboard(
    tasks: Iterable[Task],
    get_display_id: Optional[Callable[[str], Optional[int | str]]] = None,
) -> str:
    """Format multiple tasks as newline-separated markdown links for clipboard.

    Args:
        tasks: Iterable of Task objects
        get_display_id: Optional callable that maps task.id to display_id

    Returns:
        Newline-separated markdown links
    """
    links = []
    for task in tasks:
        d_id = get_display_id(task.id) if get_display_id else None
        links.append(format_task_markdown_link(task, display_id=d_id))
    return "\n".join(links)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard across macOS, Linux, and Windows.

    Uses native platform tools without external dependencies:
    - macOS: pbcopy
    - Linux: wl-copy, xclip, or xsel
    - Windows: clip

    Args:
        text: String content to copy

    Returns:
        True if successfully copied, False otherwise
    """
    data = text.encode("utf-8")

    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=data, check=True)
            return True

        if sys.platform.startswith("linux"):
            if shutil.which("wl-copy"):
                subprocess.run(["wl-copy"], input=data, check=True)
                return True
            if shutil.which("xclip"):
                subprocess.run(["xclip", "-selection", "clipboard"], input=data, check=True)
                return True
            if shutil.which("xsel"):
                subprocess.run(["xsel", "--clipboard", "--input"], input=data, check=True)
                return True
            return False

        if sys.platform == "win32":
            subprocess.run(["clip"], input=data, check=True)
            return True

        return False
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return False
