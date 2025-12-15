"""Upgrade command for auto-upgrading taskrepo."""

import click
from henriqueslab_updater import UpdateChecker, execute_upgrade

from taskrepo.__version__ import __version__

# Installer method to friendly name mapping
INSTALLER_NAMES = {
    "homebrew": "Homebrew",
    "pipx": "pipx",
    "uv": "uv tool",
    "pip-user": "pip (user)",
    "pip": "pip",
    "dev": "Development mode",
    "unknown": "pip",
}


@click.command()
@click.option("--check", is_flag=True, help="Check for updates without upgrading")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def upgrade(ctx, check, yes):
    """Upgrade taskrepo to the latest version.

    This command checks PyPI for the latest version and upgrades
    taskrepo using the detected package installer (pipx, uv, or pip).
    """
    # Check for updates using henriqueslab-updater
    click.echo("Checking for updates...")
    checker = UpdateChecker("taskrepo", __version__)
    update_info = checker.check_sync(force=True)

    # Extract update status
    update_available = update_info is not None and update_info.get("update_available", False)
    latest_version = update_info.get("latest_version") if update_info else None

    if check:
        # Just show version information
        if update_available and latest_version:
            click.echo(f"Current version: v{__version__}")
            click.secho(f"Latest version: v{latest_version}", fg="green", bold=True)
            click.secho("Update available!", fg="yellow")
        else:
            click.echo(f"Current version: v{__version__}")
            click.secho("✓ You are already using the latest version", fg="green")
        return

    # No update available
    if not update_available or not latest_version:
        click.secho(f"✓ You are already using the latest version (v{__version__})", fg="green")
        return

    # Update available
    click.echo()
    click.secho(f"Update available: v{__version__} → v{latest_version}", fg="yellow", bold=True)
    click.echo(f"Release notes: https://pypi.org/project/taskrepo/{latest_version}/")
    click.echo()

    # Confirm upgrade
    if not yes:
        try:
            from prompt_toolkit.shortcuts import confirm

            if not confirm(f"Upgrade taskrepo to v{latest_version}?"):
                click.echo("Upgrade cancelled.")
                return
        except (KeyboardInterrupt, EOFError):
            click.echo("\nUpgrade cancelled.")
            return

    # Get installer info and upgrade command
    install_method = update_info.get("install_method", "unknown")
    installer_name = INSTALLER_NAMES.get(install_method, install_method)
    upgrade_command = update_info.get("upgrade_command", "pip install --upgrade taskrepo")

    click.echo(f"\nDetected installer: {installer_name}")
    click.echo(f"Running: {upgrade_command}")
    click.echo()

    # Run upgrade using centralized executor
    success, error = execute_upgrade(upgrade_command, show_output=False, timeout=300)

    if success:
        click.echo()
        click.secho(f"✓ Successfully upgraded taskrepo to v{latest_version}", fg="green", bold=True)
        click.echo()
        click.echo("Please restart your terminal or run 'source ~/.bashrc' (or ~/.zshrc)")
        click.echo("to ensure the new version is loaded.")
    else:
        click.echo()
        click.secho("✗ Upgrade failed", fg="red", bold=True)
        click.echo()
        if error:
            click.secho("Error:", fg="red")
            click.echo(error)
            click.echo()

        # Provide manual upgrade instructions
        click.secho("Manual upgrade:", fg="yellow")
        if installer_name == "Homebrew":
            click.echo("  brew update && brew upgrade taskrepo")
        elif installer_name == "pipx":
            click.echo("  pipx upgrade taskrepo")
        elif installer_name == "uv tool":
            click.echo("  uv tool upgrade taskrepo")
        elif installer_name == "Development mode":
            click.echo("  cd <repo> && git pull && uv sync")
        else:
            click.echo("  pip install --upgrade taskrepo")
            click.echo("  # Or try with --user flag:")
            click.echo("  pip install --upgrade --user taskrepo")

        ctx.exit(1)
