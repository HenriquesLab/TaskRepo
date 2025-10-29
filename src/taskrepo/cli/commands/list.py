"""List command for displaying tasks."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table


@click.command(name="list")
@click.option("--repo", "-r", help="Filter by repository")
@click.option("--project", "-p", help="Filter by project")
@click.option("--status", "-s", help="Filter by status")
@click.option("--priority", type=click.Choice(["H", "M", "L"], case_sensitive=False), help="Filter by priority")
@click.option("--assignee", "-a", help="Filter by assignee")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--archived", is_flag=True, help="Show archived tasks")
@click.pass_context
def list_tasks(ctx, repo, project, status, priority, assignee, tag, archived):
    """List tasks with optional filters.

    By default, shows all non-archived tasks (including completed).
    Use --archived to show archived tasks instead.
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Get tasks (including or excluding archived based on flag)
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        if archived:
            tasks = repository.list_archived_tasks()
        else:
            tasks = repository.list_tasks(include_archived=False)
    else:
        if archived:
            # Get archived tasks from all repos
            tasks = []
            for r in manager.discover_repositories():
                tasks.extend(r.list_archived_tasks())
        else:
            tasks = manager.list_all_tasks(include_archived=False)

    # Track if any filters are applied
    has_filters = bool(repo or project or status or priority or assignee or tag or archived)

    # Apply filters (no automatic exclusion of completed tasks)

    if project:
        tasks = [t for t in tasks if t.project == project]

    if status:
        tasks = [t for t in tasks if t.status == status]

    if priority:
        tasks = [t for t in tasks if t.priority.upper() == priority.upper()]

    if assignee:
        if not assignee.startswith("@"):
            assignee = f"@{assignee}"
        tasks = [t for t in tasks if assignee in t.assignees]

    if tag:
        tasks = [t for t in tasks if tag in t.tags]

    # Display results
    if not tasks:
        click.echo("No tasks found.")
        return

    # Display tasks using shared display function
    # Only rebalance IDs for unfiltered views (like sync does)
    if not has_filters:
        from taskrepo.utils.id_mapping import save_id_cache
        from taskrepo.utils.sorting import sort_tasks

        sorted_tasks = sort_tasks(tasks, config)
        save_id_cache(sorted_tasks, rebalance=True)

    display_tasks_table(tasks, config, save_cache=False)
