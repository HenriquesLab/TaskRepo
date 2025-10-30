"""File validation utilities for TaskRepo repositories."""

from pathlib import Path

import click
from git import Repo as GitRepo
from prompt_toolkit.shortcuts import confirm


def detect_unexpected_files(git_repo: GitRepo, repo_path: Path) -> dict[str, list[Path]]:
    """Detect unexpected files in repository that don't match task file patterns.

    Args:
        git_repo: GitPython repository object
        repo_path: Path to task repository

    Returns:
        Dictionary mapping patterns to lists of unexpected file paths.
        Empty dict if no unexpected files found.

    Example:
        {
            "*.log": [Path("debug.log"), Path("error.log")],
            ".vscode/*": [Path(".vscode/settings.json"), Path(".vscode/launch.json")],
            "other": [Path("notes.txt")]
        }
    """
    # Get all untracked and modified files
    untracked = [Path(f) for f in git_repo.untracked_files]
    modified = [Path(item.a_path) for item in git_repo.index.diff(None)]
    all_changed = set(untracked + modified)

    # Valid file patterns
    valid_patterns = {
        # Task files
        lambda p: p.parts[0] == "tasks" and p.parts[-1].startswith("task-") and p.suffix == ".md",
        # Archived tasks
        lambda p: len(p.parts) >= 2
        and p.parts[0] == "tasks"
        and "archive" in p.parts
        and p.parts[-1].startswith("task-")
        and p.suffix == ".md",
        # README files
        lambda p: p.name == "README.md",
        # Gitkeep files
        lambda p: p.name == ".gitkeep",
        # Gitignore
        lambda p: p.name == ".gitignore",
        # Git directory (should never appear in changed files, but just in case)
        lambda p: p.parts[0] == ".git",
    }

    def is_valid_file(file_path: Path) -> bool:
        """Check if file matches any valid pattern."""
        return any(pattern(file_path) for pattern in valid_patterns)

    # Find unexpected files
    unexpected_files = [f for f in all_changed if not is_valid_file(f)]

    if not unexpected_files:
        return {}

    # Group files by pattern
    grouped: dict[str, list[Path]] = {}

    for file_path in unexpected_files:
        # Determine pattern for this file
        if file_path.parts[0].startswith(".") and (repo_path / file_path).is_dir():
            # Hidden directory (e.g., .vscode, .idea)
            pattern = f"{file_path.parts[0]}/*"
        elif file_path.suffix:
            # Has extension - group by extension
            pattern = f"*{file_path.suffix}"
        else:
            # No extension or special case - use filename
            pattern = file_path.name

        if pattern not in grouped:
            grouped[pattern] = []
        grouped[pattern].append(file_path)

    return grouped


def prompt_unexpected_files(unexpected_files: dict[str, list[Path]], repo_name: str) -> str:
    """Prompt user about unexpected files and return action choice.

    Args:
        unexpected_files: Dict mapping patterns to file lists
        repo_name: Name of repository for display

    Returns:
        User choice: "ignore", "delete", "commit", or "skip"
    """
    click.echo(f"\n⚠️  Found unexpected files in repository '{repo_name}':\n")

    # Display grouped files
    for pattern, files in unexpected_files.items():
        file_count = len(files)
        click.echo(f"  {pattern} ({file_count} file{'s' if file_count != 1 else ''}):")
        for file_path in sorted(files)[:5]:  # Show max 5 files per pattern
            click.echo(f"    - {file_path}")
        if file_count > 5:
            click.echo(f"    ... and {file_count - 5} more")
        click.echo()

    click.echo("Options:")
    click.echo("  [i] Add patterns to .gitignore and exclude from commit")
    click.echo("  [d] Delete these files")
    click.echo("  [c] Commit these files anyway")
    click.echo("  [s] Skip this repository (don't commit anything)")

    while True:
        choice = click.prompt("\nYour choice", type=str, default="i").lower().strip()
        if choice in ["i", "ignore"]:
            return "ignore"
        elif choice in ["d", "delete", "del"]:
            # Confirm deletion
            if confirm("⚠️  Are you sure you want to delete these files? This cannot be undone."):
                return "delete"
            else:
                click.echo("Cancelled deletion. Choose another option.")
                continue
        elif choice in ["c", "commit"]:
            return "commit"
        elif choice in ["s", "skip"]:
            return "skip"
        else:
            click.secho(f"Invalid choice: {choice}. Please enter i, d, c, or s.", fg="yellow")


def add_to_gitignore(patterns: list[str], repo_path: Path) -> None:
    """Add patterns to repository's .gitignore file.

    Args:
        patterns: List of patterns to add (e.g., ["*.log", ".vscode/*"])
        repo_path: Path to task repository
    """
    gitignore_path = repo_path / ".gitignore"

    # Read existing .gitignore if it exists
    existing_patterns = set()
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            existing_patterns = {line.strip() for line in f if line.strip() and not line.startswith("#")}

    # Add new patterns that don't already exist
    new_patterns = [p for p in patterns if p not in existing_patterns]

    if not new_patterns:
        click.echo("  ℹ️  All patterns already in .gitignore")
        return

    # Append to .gitignore
    with open(gitignore_path, "a") as f:
        if existing_patterns and gitignore_path.stat().st_size > 0:
            # Add blank line if file already has content
            f.write("\n")
        f.write("# Added by TaskRepo sync\n")
        for pattern in sorted(new_patterns):
            f.write(f"{pattern}\n")

    click.secho(f"  ✓ Added {len(new_patterns)} pattern(s) to .gitignore", fg="green")


def delete_unexpected_files(unexpected_files: dict[str, list[Path]], repo_path: Path) -> None:
    """Delete unexpected files from repository.

    Args:
        unexpected_files: Dict mapping patterns to file lists
        repo_path: Path to task repository
    """
    deleted_count = 0
    failed_count = 0

    for files in unexpected_files.values():
        for file_path in files:
            full_path = repo_path / file_path
            try:
                if full_path.is_file():
                    full_path.unlink()
                    deleted_count += 1
                elif full_path.is_dir():
                    # Don't delete directories automatically
                    click.secho(f"  ⚠️  Skipping directory: {file_path}", fg="yellow")
                    failed_count += 1
            except Exception as e:
                click.secho(f"  ✗ Failed to delete {file_path}: {e}", fg="red")
                failed_count += 1

    if deleted_count > 0:
        click.secho(f"  ✓ Deleted {deleted_count} file(s)", fg="green")
    if failed_count > 0:
        click.secho(f"  ⚠️  Failed to delete {failed_count} file(s)", fg="yellow")


def create_default_gitignore(repo_path: Path) -> None:
    """Create a default .gitignore file with common patterns.

    Args:
        repo_path: Path to task repository
    """
    gitignore_path = repo_path / ".gitignore"

    # Don't overwrite existing .gitignore
    if gitignore_path.exists():
        return

    default_patterns = """# TaskRepo - Default .gitignore
# This file was automatically created by TaskRepo

# Common editor and IDE files
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/

# Temporary files
*.tmp
*.temp
.cache/

# OS files
Thumbs.db
.Spotlight-V100
.Trashes
"""

    with open(gitignore_path, "w") as f:
        f.write(default_patterns)
