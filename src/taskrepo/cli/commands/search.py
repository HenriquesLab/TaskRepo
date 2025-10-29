"""Search command for finding tasks by text query."""

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.tui.display import display_tasks_table


@click.command(name="search")
@click.argument("query")
@click.option("--repo", "-r", help="Filter by repository")
@click.option("--project", "-p", help="Filter by project")
@click.option("--status", "-s", help="Filter by status")
@click.option("--priority", type=click.Choice(["H", "M", "L"], case_sensitive=False), help="Filter by priority")
@click.option("--assignee", "-a", help="Filter by assignee")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--all", "show_all", is_flag=True, help="Show all tasks (including completed)")
@click.pass_context
def search(ctx, query, repo, project, status, priority, assignee, tag, show_all):
    """Search for tasks containing a text query.

    Performs case-insensitive search across task title, description, project, and tags.

    QUERY: Text to search for in tasks
    """
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    # Get tasks from specified repo or all repos
    # Load all non-archived tasks (completed status filtering happens later)
    if repo:
        repository = manager.get_repository(repo)
        if not repository:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)
        tasks = repository.list_tasks(include_archived=False)
    else:
        tasks = manager.list_all_tasks(include_archived=False)

    # Perform case-insensitive search across multiple fields
    query_lower = query.lower()
    matching_tasks = []

    for task in tasks:
        # Search in title
        if query_lower in task.title.lower():
            matching_tasks.append(task)
            continue

        # Search in description
        if task.description and query_lower in task.description.lower():
            matching_tasks.append(task)
            continue

        # Search in project
        if task.project and query_lower in task.project.lower():
            matching_tasks.append(task)
            continue

        # Search in tags
        if any(query_lower in tag.lower() for tag in task.tags):
            matching_tasks.append(task)
            continue

    # Apply additional filters to search results
    tasks = matching_tasks

    # Exclude completed tasks by default
    if not show_all:
        tasks = [t for t in tasks if t.status != "completed"]

    # Apply other filters
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
        click.echo(f"No tasks found matching '{query}'.")
        return

    # Display tasks using shared display function
    # Don't save ID cache for search results (filtered view)
    title = f"Search results for '{query}' ({len(tasks)} found)"
    display_tasks_table(tasks, config, title=title, save_cache=False)
