"""Add command for creating new tasks."""

import sys

import click

from taskrepo.core.repository import RepositoryManager
from taskrepo.core.task import Task
from taskrepo.tui import prompts
from taskrepo.utils.helpers import update_cache_and_display_repo


@click.command()
@click.option("--repo", "-r", help="Repository name (will prompt if not specified)")
@click.option("--title", "-t", help="Task title (will prompt if not specified)")
@click.option("--project", "-p", help="Project name")
@click.option("--priority", type=click.Choice(["H", "M", "L"], case_sensitive=False), help="Task priority")
@click.option("--assignees", "-a", help="Comma-separated list of assignees (e.g., @user1,@user2)")
@click.option("--tags", help="Comma-separated list of tags")
@click.option("--links", "-l", help="Comma-separated list of URLs (e.g., https://github.com/org/repo/issues/123)")
@click.option("--parent", "-P", help="Parent task ID (for creating subtasks)")
@click.option("--due", help="Due date (e.g., 2025-12-31)")
@click.option("--description", "-d", help="Task description")
@click.option(
    "--interactive/--no-interactive",
    "-i/-I",
    default=None,
    help="Use interactive mode (default: auto-detect based on TTY)",
)
@click.pass_context
def add(ctx, repo, title, project, priority, assignees, tags, links, parent, due, description, interactive):
    """Add a new task."""
    config = ctx.obj["config"]
    manager = RepositoryManager(config.parent_dir)

    repositories = manager.discover_repositories()

    # Auto-detect interactive mode if not specified
    if interactive is None:
        # Check if stdin is a TTY (terminal)
        interactive = sys.stdin.isatty()

        # If not a TTY, warn user that non-interactive mode is being used
        if not interactive and not title:
            default_repo_msg = f" (using default: {config.default_repo})" if config.default_repo else ""
            click.secho(
                f"Warning: Input is not a terminal (fd=0).\n"
                f"Running in non-interactive mode. --title is required{', --repo optional' if config.default_repo else ', --repo required'}{default_repo_msg}.",
                fg="yellow",
                err=True,
            )

    # Interactive mode
    if interactive:
        click.echo("Creating a new task...\n")

        # Select repository
        if not repo:
            selected_repo = prompts.prompt_repository(repositories, default=config.default_repo)
            if not selected_repo:
                click.echo("Cancelled.")
                ctx.exit(0)
        else:
            selected_repo = manager.get_repository(repo)
            if not selected_repo:
                click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
                ctx.exit(1)

        # Get task title
        if not title:
            title = prompts.prompt_title()
            if not title:
                click.echo("Cancelled.")
                ctx.exit(0)

        # Get project
        if project is None:
            existing_projects = manager.get_all_projects()
            project = prompts.prompt_project(existing_projects)

        # Get priority
        if priority is None:
            priority = prompts.prompt_priority(config.default_priority)

        # Get assignees
        if assignees is None:
            existing_assignees = manager.get_all_assignees()
            # Add default assignee to existing list if configured
            if config.default_assignee and config.default_assignee not in existing_assignees:
                existing_assignees = [config.default_assignee] + existing_assignees
            assignees_list = prompts.prompt_assignees(existing_assignees)
            # If no assignees entered and default_assignee is set, use it
            if not assignees_list and config.default_assignee:
                assignees_list = [config.default_assignee]
        else:
            assignees_list = [a.strip() for a in assignees.split(",")]
            # Ensure @ prefix
            assignees_list = [a if a.startswith("@") else f"@{a}" for a in assignees_list]

        # Get tags
        if tags is None:
            existing_tags = manager.get_all_tags()
            tags_list = prompts.prompt_tags(existing_tags)
        else:
            tags_list = [t.strip() for t in tags.split(",")]

        # Get links
        if links is None:
            links_list = prompts.prompt_links()
        else:
            links_list = [link.strip() for link in links.split(",") if link.strip()]

        # Get parent task (for subtasks)
        if parent is None:
            existing_tasks = selected_repo.list_tasks()
            parent_id = prompts.prompt_parent_task(existing_tasks)
            if parent_id:
                # Validate parent exists
                if not selected_repo.get_task(parent_id):
                    click.secho(f"Error: Parent task '{parent_id}' not found", fg="red", err=True)
                    ctx.exit(1)
        else:
            parent_id = parent
            # Validate parent exists
            if not selected_repo.get_task(parent_id):
                click.secho(f"Error: Parent task '{parent_id}' not found", fg="red", err=True)
                ctx.exit(1)

        # Get due date
        if due is None:
            due_date = prompts.prompt_due_date()
        else:
            import dateparser

            try:
                due_date = dateparser.parse(due, settings={"PREFER_DATES_FROM": "future"})
                if due_date is None:
                    raise ValueError("Could not parse date")
            except Exception:
                click.secho(
                    f"Error: Invalid due date '{due}'\n"
                    f"Supported formats:\n"
                    f"  - Keywords: tomorrow, today, 'next week', 'next month'\n"
                    f"  - ISO dates: 2025-12-31\n"
                    f"  - Natural dates: 'Oct 30', 'October 30 2025', 'Dec 1'",
                    fg="red",
                    err=True,
                )
                ctx.exit(1)

        # Get description
        if description is None:
            description = prompts.prompt_description()

    else:
        # Non-interactive mode - validate required fields
        if not title:
            click.secho("Error: --title is required in non-interactive mode", fg="red", err=True)
            ctx.exit(1)

        # Use default repo if not specified
        if not repo:
            if config.default_repo:
                repo = config.default_repo
            else:
                click.secho("Error: --repo is required (no default_repo configured)", fg="red", err=True)
                ctx.exit(1)

        selected_repo = manager.get_repository(repo)
        if not selected_repo:
            click.secho(f"Error: Repository '{repo}' not found", fg="red", err=True)
            ctx.exit(1)

        # Parse assignees
        assignees_list = []
        if assignees:
            assignees_list = [a.strip() for a in assignees.split(",")]
            assignees_list = [a if a.startswith("@") else f"@{a}" for a in assignees_list]
        elif config.default_assignee:
            # Use default assignee if none specified
            assignees_list = [config.default_assignee]

        # Parse tags
        tags_list = []
        if tags:
            tags_list = [t.strip() for t in tags.split(",")]

        # Parse links
        links_list = []
        if links:
            links_list = [link.strip() for link in links.split(",") if link.strip()]

        # Validate parent task if provided
        parent_id = None
        if parent:
            parent_task = selected_repo.get_task(parent)
            if not parent_task:
                click.secho(f"Error: Parent task '{parent}' not found", fg="red", err=True)
                ctx.exit(1)
            parent_id = parent

        # Parse due date
        due_date = None
        if due:
            import dateparser

            try:
                due_date = dateparser.parse(due, settings={"PREFER_DATES_FROM": "future"})
                if due_date is None:
                    raise ValueError("Could not parse date")
            except Exception:
                click.secho(
                    f"Error: Invalid due date '{due}'\n"
                    f"Supported formats:\n"
                    f"  - Keywords: tomorrow, today, 'next week', 'next month'\n"
                    f"  - ISO dates: 2025-12-31\n"
                    f"  - Natural dates: 'Oct 30', 'October 30 2025', 'Dec 1'",
                    fg="red",
                    err=True,
                )
                ctx.exit(1)

        if not priority:
            priority = config.default_priority

        if not description:
            description = ""

    # Generate task ID
    task_id = selected_repo.next_task_id()

    # Create task
    try:
        task = Task(
            id=task_id,
            title=title,
            status=config.default_status,
            priority=priority.upper(),
            project=project,
            assignees=assignees_list,
            tags=tags_list,
            links=links_list,
            parent=parent_id,
            due=due_date,
            description=description,
            repo=selected_repo.name,
        )
    except ValueError as e:
        click.secho(f"Error: Invalid task data: {e}", fg="red", err=True)
        ctx.exit(1)

    # Save task
    try:
        task_file = selected_repo.save_task(task)
    except IOError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        ctx.exit(1)

    click.echo()
    click.secho(f"✓ Task created: {task}", fg="green")
    click.echo(f"  File: {task_file}")
    click.echo()

    # Update cache and display repository tasks
    update_cache_and_display_repo(manager, selected_repo, config)
