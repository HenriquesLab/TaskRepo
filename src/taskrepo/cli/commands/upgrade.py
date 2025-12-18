"""Upgrade command for auto-upgrading taskrepo."""

import click
from henriqueslab_updater import handle_upgrade_workflow

from taskrepo.__version__ import __version__
from taskrepo.cli.notifiers.upgrade_notifier import TaskRepoUpgradeNotifier


@click.command()
@click.option("--check", is_flag=True, help="Check for updates without upgrading")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def upgrade(ctx, check, yes):
    """Upgrade taskrepo to the latest version.

    This command checks PyPI for the latest version and upgrades
    taskrepo using the detected package installer (pipx, uv, or pip).
    """
    # Create notifier with TaskRepo's styling
    notifier = TaskRepoUpgradeNotifier()

    # Run centralized upgrade workflow
    success, error = handle_upgrade_workflow(
        package_name="taskrepo",
        current_version=__version__,
        check_only=check,
        skip_confirmation=yes,
        notifier=notifier,
        github_org="henriqueslab",
        github_repo="TaskRepo",
    )

    # Exit with appropriate code
    if not success and error:
        ctx.exit(1)
