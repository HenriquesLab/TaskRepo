"""Upgrade command for auto-upgrading taskrepo."""

import subprocess
from typing import Optional, Tuple

import click
from henriqueslab_updater import UpdateChecker

from taskrepo.__version__ import __version__


def detect_installer(update_info: dict) -> Tuple[str, list[str]]:
    """Extract installer information from update check result.

    Args:
        update_info: Update information from UpdateChecker

    Returns:
        Tuple of (installer_name, upgrade_command_parts)
    """
    install_method = update_info.get("install_method", "unknown")
    upgrade_command = update_info.get("upgrade_command", "pip install --upgrade taskrepo")

    # Map install method to friendly name
    method_names = {
        "homebrew": "Homebrew",
        "pipx": "pipx",
        "uv": "uv tool",
        "pip-user": "pip (user)",
        "pip": "pip",
        "dev": "Development mode",
        "unknown": "pip",
    }

    friendly_name = method_names.get(install_method, install_method)
    return (friendly_name, upgrade_command.split())


def run_upgrade(upgrade_cmd: list[str], is_homebrew: bool = False) -> Tuple[bool, Optional[str]]:
    """Run the upgrade command.

    Args:
        upgrade_cmd: List of command parts to execute
        is_homebrew: Whether this is a Homebrew installation (requires brew update first)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # For Homebrew, run 'brew update' first to fetch latest formulae
        if is_homebrew:
            click.echo("Running: brew update")
            update_result = subprocess.run(
                ["brew", "update"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if update_result.returncode != 0:
                error_msg = update_result.stderr.strip() if update_result.stderr else update_result.stdout.strip()
                return (False, f"brew update failed: {error_msg}")
            click.echo("✓ Homebrew formulae updated")
            click.echo()

        # Run the actual upgrade command
        result = subprocess.run(
            upgrade_cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes timeout
        )

        if result.returncode == 0:
            return (True, None)
        else:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            return (False, error_msg)

    except subprocess.TimeoutExpired:
        return (False, "Upgrade command timed out after 2 minutes")
    except FileNotFoundError:
        installer = upgrade_cmd[0]
        return (False, f"Command '{installer}' not found. Please install {installer} or upgrade manually.")
    except Exception as e:
        return (False, str(e))


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

    # Detect installer from update info
    installer_name, upgrade_cmd = detect_installer(update_info)
    is_homebrew = installer_name == "Homebrew"

    click.echo(f"\nDetected installer: {installer_name}")
    if is_homebrew:
        click.echo("Running: brew update && brew upgrade taskrepo")
    else:
        click.echo(f"Running: {' '.join(upgrade_cmd)}")
    click.echo()

    # Run upgrade
    success, error = run_upgrade(upgrade_cmd, is_homebrew=is_homebrew)

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
            click.echo(f"  {installer_name} install --upgrade taskrepo")
            click.echo("  # Or try with --user flag:")
            click.echo(f"  {installer_name} install --upgrade --user taskrepo")

        ctx.exit(1)
