"""GitHub integration utilities."""

import shutil
import subprocess
from pathlib import Path


class GitHubError(Exception):
    """Exception raised for GitHub-related errors."""

    pass


def check_gh_cli_installed() -> bool:
    """Check if GitHub CLI (gh) is installed.

    Returns:
        True if gh is installed, False otherwise
    """
    return shutil.which("gh") is not None


def check_gh_auth() -> bool:
    """Check if user is authenticated with GitHub CLI.

    Returns:
        True if authenticated, False otherwise
    """
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False


def create_github_repo(org: str, repo_name: str, visibility: str = "private") -> str:
    """Create a GitHub repository using gh CLI.

    Args:
        org: GitHub organization or username
        repo_name: Repository name
        visibility: Repository visibility ('public' or 'private')

    Returns:
        URL of the created repository

    Raises:
        GitHubError: If repository creation fails
    """
    # Check prerequisites
    if not check_gh_cli_installed():
        raise GitHubError("GitHub CLI (gh) is not installed. Install it from: https://cli.github.com/")

    if not check_gh_auth():
        raise GitHubError("Not authenticated with GitHub. Run: gh auth login")

    # Build the repository identifier
    full_repo_name = f"{org}/{repo_name}"

    # Build command
    visibility_flag = f"--{visibility}"
    cmd = ["gh", "repo", "create", full_repo_name, visibility_flag, "--confirm"]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Extract URL from output (gh prints the URL)
        url = f"https://github.com/{full_repo_name}"
        return url

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to create GitHub repository: {error_msg}") from e


def setup_git_remote(repo_path: Path, remote_url: str, remote_name: str = "origin"):
    """Set up git remote for a local repository.

    Args:
        repo_path: Path to the local git repository
        remote_url: URL of the remote repository
        remote_name: Name of the remote (default: origin)

    Raises:
        GitHubError: If remote setup fails
    """
    try:
        subprocess.run(
            ["git", "remote", "add", remote_name, remote_url], cwd=repo_path, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to add git remote: {error_msg}") from e


def push_to_remote(repo_path: Path, branch: str = "main", remote_name: str = "origin"):
    """Push local commits to remote repository.

    Args:
        repo_path: Path to the local git repository
        branch: Branch to push (default: main)
        remote_name: Name of the remote (default: origin)

    Raises:
        GitHubError: If push fails
    """
    try:
        subprocess.run(
            ["git", "push", "-u", remote_name, branch], cwd=repo_path, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to push to remote: {error_msg}") from e
