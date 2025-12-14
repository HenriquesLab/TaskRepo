"""History command for viewing task and git repository history."""

from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from taskrepo.core.repository import RepositoryManager
from taskrepo.utils import history_cache
from taskrepo.utils.date_parser import parse_date_or_duration
from taskrepo.utils.display_constants import (
    PRIORITY_COLORS,
    STATUS_COLORS,
    get_author_color,
    get_project_color,
    get_repo_color,
)
from taskrepo.utils.history import (
    categorize_commit,
    get_commit_history,
    group_by_timeline,
)

console = Console()


@click.command()
@click.option("--repo", "-r", help="Filter by repository (default: all repos)")
@click.option(
    "--since",
    "-s",
    default="7d",
    help="Time range: 7d, 2w, 1m, 3m, all (default: 7d)",
)
@click.option("--task", "-t", help="Filter by task ID or title pattern")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed commit messages and file lists")
@click.option("--all", "-a", is_flag=True, help="Show all commits including auto-updates (default: only task changes)")
@click.option("--no-cache", is_flag=True, help="Skip cache and recompute from git")
@click.option("--clear-cache", is_flag=True, help="Clear history cache and exit")
@click.pass_context
def history(ctx, repo, since, task, verbose, all, no_cache, clear_cache):
    """Show task and git repository history over time."""
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Handle cache clearing
    if clear_cache:
        if repo:
            # Clear specific repo cache
            count = history_cache.clear_cache(repo)
            if count > 0:
                console.print(f"[green]✓[/green] Cleared history cache for repository: {repo}")
            else:
                console.print(f"[yellow]⚠[/yellow] No cache found for repository: {repo}")
        else:
            # Clear all caches
            count = history_cache.clear_cache()
            if count > 0:
                console.print(f"[green]✓[/green] Cleared {count} history cache file{'s' if count != 1 else ''}")
            else:
                console.print("[yellow]⚠[/yellow] No history cache files found")
        return

    # Parse time range
    cutoff_date = None
    if since.lower() != "all":
        try:
            duration, is_absolute = parse_date_or_duration(since)
            if is_absolute:
                # It's a specific date
                cutoff_date = duration
            else:
                # It's a duration
                cutoff_date = datetime.now() - duration
        except Exception:
            console.print(f"[red]✗[/red] Invalid time range: {since}", style="red")
            console.print("Examples: 7d, 2w, 1m, 3m, all")
            return

    # Get repositories
    if repo:
        repositories = [manager.get_repository(repo)]
        if not repositories[0]:
            console.print(f"[red]✗[/red] Repository not found: {repo}", style="red")
            return
    else:
        repositories = manager.discover_repositories()

    # Collect all commits from all repos
    all_commits = []
    total_task_changes = 0

    for repository in repositories:
        # Check if repository has git repo
        if not repository.git_repo:
            if verbose:
                console.print(f"[yellow]⚠[/yellow] Repository '{repository.name}' is not a git repository, skipping")
            continue

        # Get commit history
        commits = get_commit_history(repository, since=cutoff_date, task_filter=task, use_cache=not no_cache)

        # Add repository name to each commit for display
        for commit in commits:
            commit.repo_name = repository.name
            total_task_changes += sum(len(changes) for changes in commit.task_changes.values())

        all_commits.extend(commits)

    # Sort all commits by timestamp (most recent first)
    all_commits.sort(key=lambda c: c.timestamp, reverse=True)

    # Filter to only commits with task changes (unless --all flag is set)
    if not all:
        all_commits = [c for c in all_commits if c.task_changes]
        # Recalculate total task changes after filtering
        total_task_changes = sum(sum(len(changes) for changes in c.task_changes.values()) for c in all_commits)

    if not all_commits:
        if all:
            console.print(
                Panel(
                    "[yellow]No commit history found in the specified time range.[/yellow]",
                    title="📅 Task History",
                    border_style="yellow",
                )
            )
        else:
            console.print(
                Panel(
                    "[yellow]No task changes found in the specified time range.[/yellow]\n"
                    "[dim]Use --all to show all commits including auto-updates.[/dim]",
                    title="📅 Task History",
                    border_style="yellow",
                )
            )
        return

    # Group commits by timeline
    timeline_groups = group_by_timeline(all_commits)

    # Build the title
    time_range_text = since if since.lower() != "all" else "All Time"
    repo_text = f" ({repo} repo)" if repo else ""
    task_filter_text = f" - Filter: {task}" if task else ""
    title = f"📅 Task History - Last {time_range_text}{repo_text}{task_filter_text}"

    # Create the display
    console.print()
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print("━" * console.width)
    console.print()

    # Display each timeline group (reversed so most recent appears last)
    for group_name, commits in reversed(list(timeline_groups.items())):
        # Create a tree for this group
        tree = Tree(f"[bold]{group_name}[/bold]", guide_style="dim")

        # Reverse commits within group so oldest appears first, newest last
        for commit in reversed(commits):
            # Build commit description
            emoji = categorize_commit(commit)
            commit_time = commit.timestamp.strftime("%H:%M")
            commit_date = commit.timestamp.strftime("%b %d")

            # For groups other than "Today" and "Yesterday", show date
            if group_name not in ["Today", "Yesterday"]:
                time_str = commit_date
            else:
                time_str = commit_time

            # Truncate commit message to first line
            commit_msg = commit.message.split("\n")[0]
            if len(commit_msg) > 50 and not verbose:
                commit_msg = commit_msg[:47] + "..."

            # Build the commit node label with author
            author_color = get_author_color(commit.author)
            commit_label = (
                f"[dim]{time_str}[/dim]  {emoji} {commit_msg} [dim]by[/dim] [{author_color}]{commit.author}[/]"
            )

            # Add repository name if showing multiple repos
            if not repo:
                repo_color = get_repo_color(commit.repo_name)
                commit_label += f" [dim]([/dim][{repo_color}]{commit.repo_name}[/][dim])[/dim]"

            commit_node = tree.add(commit_label)

            # Add task changes
            if commit.task_changes:
                for task_id, changes in commit.task_changes.items():
                    for change in changes:
                        change_text = format_task_change(change, task_id, commit.author)
                        commit_node.add(change_text)
            elif all:
                # Only show file counts when --all flag is used (for commits without task changes)
                if verbose and commit.files_changed:
                    commit_node.add(f"[dim]Files: {', '.join(commit.files_changed)}[/dim]")
                elif commit.files_changed:
                    file_count = len(commit.files_changed)
                    file_word = "file" if file_count == 1 else "files"
                    commit_node.add(f"[dim]{file_count} {file_word} changed[/dim]")

            # Add verbose details
            if verbose:
                # Show full commit message if multi-line
                if "\n" in commit.message:
                    for line in commit.message.split("\n")[1:]:
                        if line.strip():
                            commit_node.add(f"[dim]{line.strip()}[/dim]")

                # Show commit hash and author
                author_color = get_author_color(commit.author)
                commit_node.add(f"[dim]Commit: {commit.commit_hash} by[/dim] [{author_color}]{commit.author}[/]")

        console.print(tree)
        console.print()

    # Summary
    console.print("━" * console.width)
    summary_parts = [
        f"{len(all_commits)} commit{'s' if len(all_commits) != 1 else ''}",
        f"{total_task_changes} task change{'s' if total_task_changes != 1 else ''}",
    ]

    if since.lower() != "all":
        if cutoff_date:
            days = (datetime.now() - cutoff_date).days
            summary_parts.append(f"across {days} day{'s' if days != 1 else ''}")
        else:
            summary_parts.append(f"in {time_range_text}")
    else:
        summary_parts.append("all time")

    console.print(f"[dim]Summary: {', '.join(summary_parts)}[/dim]")
    console.print()


def format_task_change(change, task_id: str, commit_author: str) -> str:
    """Format a task change for display.

    Args:
        change: TaskChange object
        task_id: Task ID
        commit_author: Git commit author name

    Returns:
        Formatted string with colors
    """
    # Use task title if available, otherwise use short ID
    if change.task_title:
        # Truncate long titles
        task_display = change.task_title
        if len(task_display) > 50:
            task_display = task_display[:47] + "..."
    else:
        task_display = f"#{task_id[:8]}"

    # Add modifier suffix if present and different from commit author
    modifier_suffix = ""
    if change.modifier:
        # Simple check: if modifier is present, show it
        # (We only set modifier when it differs from commit author in the first place)
        author_color = get_author_color(change.modifier)
        modifier_suffix = f" [dim](by[/dim] [{author_color}]{change.modifier}[/][dim])[/dim]"

    if change.change_type == "created":
        # Show priority with the creation
        priority_color = PRIORITY_COLORS.get(change.new_value, "white")
        return f"[green]• {task_display}[/green] [dim](priority [{priority_color}]{change.new_value}[/{priority_color}])[/dim]{modifier_suffix}"
    elif change.change_type == "deleted":
        return f"[red]• {task_display} [dim](deleted)[/dim][/red]{modifier_suffix}"
    elif change.change_type == "modified":
        if change.field == "status":
            old_color = STATUS_COLORS.get(change.old_value, "white")
            new_color = STATUS_COLORS.get(change.new_value, "white")
            return (
                f"• {task_display}: status [{old_color}]{change.old_value}[/{old_color}] "
                f"→ [{new_color}]{change.new_value}[/{new_color}]{modifier_suffix}"
            )
        elif change.field == "priority":
            old_color = PRIORITY_COLORS.get(change.old_value, "white")
            new_color = PRIORITY_COLORS.get(change.new_value, "white")
            return (
                f"• {task_display}: priority [{old_color}]{change.old_value}[/{old_color}] "
                f"→ [{new_color}]{change.new_value}[/{new_color}]{modifier_suffix}"
            )
        elif change.field == "project":
            old_color = get_project_color(change.old_value) if change.old_value != "None" else "dim"
            new_color = get_project_color(change.new_value) if change.new_value != "None" else "dim"
            old_display = change.old_value if change.old_value != "None" else "no project"
            new_display = change.new_value if change.new_value != "None" else "no project"
            return f"• {task_display}: project [{old_color}]{old_display}[/] → [{new_color}]{new_display}[/]{modifier_suffix}"
        elif change.field == "due":
            return f"• {task_display}: due date {change.old_value} → {change.new_value}{modifier_suffix}"
        elif change.field == "title":
            return f"• Title changed: [dim]{change.old_value}[/dim] → {change.new_value}{modifier_suffix}"
        elif change.field == "description":
            return f"• {task_display}: description modified{modifier_suffix}"
        else:
            return f"• {task_display}: {change.field} updated{modifier_suffix}"
    elif change.change_type == "added":
        if change.field == "assignees":
            return f"• {task_display}: added assignee [cyan]{change.new_value}[/cyan]{modifier_suffix}"
        elif change.field == "tags":
            return f"• {task_display}: added tag [magenta]{change.new_value}[/magenta]{modifier_suffix}"
        elif change.field == "priority":
            priority_color = PRIORITY_COLORS.get(change.new_value, "white")
            return (
                f"• {task_display}: priority [{priority_color}]{change.new_value}[/{priority_color}]{modifier_suffix}"
            )
    elif change.change_type == "removed":
        if change.field == "assignees":
            return f"• {task_display}: removed assignee [dim]{change.old_value}[/dim]{modifier_suffix}"
        elif change.field == "tags":
            return f"• {task_display}: removed tag [dim]{change.old_value}[/dim]{modifier_suffix}"
    elif change.change_type == "archived":
        return f"[yellow]• {task_display} [dim](archived)[/dim][/yellow]{modifier_suffix}"
    elif change.change_type == "unarchived":
        return f"[cyan]• {task_display} [dim](unarchived)[/dim][/cyan]{modifier_suffix}"

    return f"• {task_display}: {change.field} changed{modifier_suffix}"
