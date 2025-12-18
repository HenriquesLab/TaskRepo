"""Rich-based upgrade notifier for TaskRepo CLI."""

import click


class TaskRepoUpgradeNotifier:
    """Rich-based upgrade notifier matching TaskRepo's cyan color scheme.

    Implements the UpgradeNotifier protocol from henriqueslab-updater>=1.2.0
    to provide consistent CLI output using Click and Rich formatting.
    """

    def __init__(self, package_name: str = "taskrepo"):
        """Initialize the notifier.

        Args:
            package_name: Name of the package (for display purposes)
        """
        self.package_name = package_name

    def show_checking(self) -> None:
        """Show 'checking for updates' message."""
        click.echo("Checking for updates...")

    def show_version_check(self, current: str, latest: str, available: bool) -> None:
        """Show version check results.

        Args:
            current: Current version
            latest: Latest available version
            available: Whether an update is available
        """
        if available and latest:
            click.echo(f"Current version: v{current}")
            click.secho(f"Latest version: v{latest}", fg="green", bold=True)
            click.secho("Update available!", fg="yellow")
        else:
            click.echo(f"Current version: v{current}")
            click.secho("✓ You are already using the latest version", fg="green")

    def show_update_info(self, current: str, latest: str, release_url: str) -> None:
        """Show update available information.

        Args:
            current: Current version
            latest: Latest available version
            release_url: URL to release notes
        """
        click.echo()
        click.secho(f"Update available: v{current} → v{latest}", fg="yellow", bold=True)
        click.echo(f"Release notes: {release_url}")
        click.echo()

    def show_installer_info(self, friendly_name: str, command: str) -> None:
        """Show detected installer information.

        Args:
            friendly_name: Human-readable installer name
            command: The upgrade command to be executed
        """
        click.echo(f"\nDetected installer: {friendly_name}")
        click.echo(f"Running: {command}")
        click.echo()

    def show_success(self, version: str) -> None:
        """Show successful upgrade message.

        Args:
            version: The version that was installed
        """
        click.echo()
        click.secho(f"✓ Successfully upgraded taskrepo to v{version}", fg="green", bold=True)
        click.echo()
        click.echo("Please restart your terminal or run 'source ~/.bashrc' (or ~/.zshrc)")
        click.echo("to ensure the new version is loaded.")

    def show_error(self, error: str | None) -> None:
        """Show upgrade error message.

        Args:
            error: Error message (if available)
        """
        click.echo()
        click.secho("✗ Upgrade failed", fg="red", bold=True)
        click.echo()
        if error:
            click.secho("Error:", fg="red")
            click.echo(error)
            click.echo()

    def show_manual_instructions(self, install_method: str) -> None:
        """Show manual upgrade instructions.

        Args:
            install_method: The detected installation method
        """
        # Map internal install_method to friendly names
        installer_names = {
            "homebrew": "Homebrew",
            "pipx": "pipx",
            "uv": "uv tool",
            "pip-user": "pip (user)",
            "pip": "pip",
            "dev": "Development mode",
            "unknown": "pip",
        }
        installer_name = installer_names.get(install_method, install_method)

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

    def confirm_upgrade(self, version: str) -> bool:
        """Prompt user to confirm upgrade.

        Args:
            version: The version to upgrade to

        Returns:
            True if user confirmed, False otherwise
        """
        try:
            from prompt_toolkit.shortcuts import confirm

            if not confirm(f"Upgrade taskrepo to v{version}?"):
                click.echo("Upgrade cancelled.")
                return False
            return True
        except (KeyboardInterrupt, EOFError):
            click.echo("\nUpgrade cancelled.")
            return False
